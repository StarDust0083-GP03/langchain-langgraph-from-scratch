# Pregel：图在运行时如何前进

`StateGraph` 是用户友好的构建层，Pregel 是执行层。理解 Pregel 不要求直接使用它的低层 API，但能解释并行节点为什么看不到彼此的新值、checkpoint 为什么落在步骤边界，以及恢复为何可能重放节点。

## Bulk Synchronous Parallel

每个 super-step 分三阶段：

```text
┌────────┐    ┌──────────────┐    ┌────────┐
│  Plan  │ -> │  Execution   │ -> │ Update │
└────────┘    └──────────────┘    └────────┘
  选 actor       并行运行           应用写入
      ▲                                  │
      └──────── 下一 super-step ─────────┘
```

### Plan

根据输入 channel 或上一步更新的 channel，选择本步激活的 actor。没有触发条件的节点不会因为“存在于图中”就执行。

### Execution

选中的 actor 并行运行，直到全部完成、某个失败或超时。此阶段产生的 channel 写入暂存在任务结果中，对同一步的其他 actor 不可见。

### Update

运行时按 channel 规则合并写入，生成新的可见状态。随后决定下一步哪些 actor 被激活。

当没有 actor 可执行且没有消息在传递时，图停止。

## actor 与 channel

Pregel actor 是 `PregelNode`，实现 Runnable 接口。它订阅 channel、读取值并写回 channel。StateGraph 编译时把节点函数和状态字段翻译成这些低层对象。

常见 channel：

- `LastValue`：保留最后一次写入，对应默认覆盖字段。
- `BinaryOperatorAggregate`：用二元操作累计值。
- `Topic`：发布订阅，可累计多个更新。
- `EphemeralValue`：在步骤间传递临时值。
- `DeltaChannel`：当前快照中的 beta 能力，只持久化增量并按需重建累计值。

在日常 StateGraph 代码里，类型注解和 reducer 已经替你选择 channel。只有需要特殊存储语义时才应下沉。

## 为什么本步写入不可见

如果一个并行节点能偶然看到另一个刚写出的值，业务结果就可能依赖线程调度。BSP 让同一步节点读取稳定快照，再在 Update 阶段统一合并结果。读取边界确定以后，还需为每个字段选择正确的合并规则。

这带来一个设计规则：有先后数据依赖的工作必须放在不同 super-step。不要期待并行节点通过共享 state 即时通信。

### 两种并行更新的不同结果

输入快照是 count=0，A、B 都读取它。两个任务分别产生增量 1，此时尚未相互可见。Update 阶段使用加法 channel 得到 2；使用单值覆盖 channel 则不能接受这种并发写法。同样的输入和任务，只改合并规则，就会改变运行是否合法。

并行不会替业务决定如何合并。两个专家分别给“通过”和“拒绝”，没有自然相加的意义，应保存独立结果，让下一步审核节点选择。BSP 稳定了可见边界，reducer 和聚合逻辑才定义业务结果。

## 运行循环中的关键对象

阅读源码时可以沿这条路线：

```text
Pregel.invoke / stream
    -> PregelLoop 建立本次运行上下文
    -> prepare_next_tasks 选择任务
    -> PregelRunner 执行任务
    -> apply_writes 更新 channels
    -> checkpoint / emit stream
    -> tick 下一步
```

同步与异步、普通 invoke 与 stream 共享核心状态机，但执行器和事件出口不同。排查问题时先确认故障属于任务执行、写入合并、持久化还是消费端。

## checkpoint 为什么适合放在步骤边界

Update 完成后，所有 actor 的写入已经形成一致状态。这个边界适合持久化：恢复时从完整 super-step 之后继续，而不是尝试还原一半线程完成、一半仍运行的瞬间。

如果进程在外部副作用之后、checkpoint 之前退出，恢复可能再次运行该节点。这就是工具和节点副作用必须幂等的根本原因之一。

### 步骤边界不是跨系统事务边界

节点发出邮件，外部服务确认成功，进程在状态持久化前退出。checkpoint 仍指向此前步骤，恢复可能再调用邮件节点。运行时没有办法仅凭旧图状态知道邮件已经发过，因此业务幂等键必须在外部系统也有效。

并行失败恢复还可能保留已经完成任务的 pending writes，实际重跑范围受任务和持久化机制影响。安全设计不应依赖某个节点碰巧没有重跑，应让允许重放的操作始终有正确业务语义。

## recursion limit 计算什么

它限制图步骤，不等价于 Python 递归深度。一个 model -> tools -> model 循环会消耗多个 super-step。并行节点处于同一步，不一定按节点数逐个计数。

设置过低会中断合法长流程，设置过高只会让错误循环运行更久。更好的做法是用业务字段表达剩余步骤、费用和截止时间，再把 recursion limit 留作总保险。

## DeltaChannel 的取舍

对持续增长的消息列表，传统 checkpoint 可能每一步重复序列化完整列表。`DeltaChannel` 只写本步增量，并在读取时重建值，可减少写入体积。

代价包括：

- reducer 变成批量 reducer，必须满足 batching invariant；
- 无快照时读取需要重放增量；
- channel 格式影响 checkpoint 兼容性；
- 当前文档标记为 beta，降级到不支持的版本会无法读取。

只有观察到具体 checkpoint 体积问题后才值得采用。先用普通消息 reducer，测量，再优化。

### 增量存储为什么对 reducer 提出更高要求

若每次保存完整累计值，读取直接拿结果；只保存增量，则读取需要把多次更新重新合并。将更新分成一批或两批应得到相同业务结果，否则重建会受存储分组影响。依赖墙上时钟、随机数或外部查询的 reducer 很难满足这种要求。

因此 DeltaChannel 的优化不仅是换一个类名，还涉及批处理不变量、格式兼容和读取成本。先证明 checkpoint 体积确实是瓶颈，再用已知更新序列验证完整与增量两种恢复结果。

## 直接用 Pregel 吗

官方源码和文档都给出相同建议：多数用户应使用 StateGraph 或 Functional API。直接 Pregel 适合运行时研究、自定义 channel 拓扑或框架作者。业务团队通常更需要清晰 schema 和节点，而不是手动接线 actor 与 channel。

## 源码入口

- `langgraph/pregel/main.py`
- `langgraph/pregel/_loop.py`
- `langgraph/pregel/_runner.py`
- `langgraph/pregel/_algo.py`
- `langgraph/channels/`
