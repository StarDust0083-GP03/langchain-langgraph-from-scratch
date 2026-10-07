# 检查点与 Store：两种记忆边界

LangGraph 有两套互补的持久化系统。checkpointer 保存一个 thread 的图状态，store 保存应用定义的跨 thread 数据。把“记忆”当成一个大字典，会同时破坏恢复语义和数据生命周期。

## checkpointer 保存什么

编译图时传入 checkpointer，调用时提供 `thread_id`：

```python
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "thread-42"}}
result = graph.invoke(input_state, config)
```

运行时在步骤边界保存 checkpoint。它通常包含 channel values、版本、待处理任务和元数据，使图能够：

- 延续同一会话；
- interrupt 后恢复；
- 查看历史 state；
- 从历史点派生新分支；
- 进程故障后继续。

`thread_id` 是持久化地址的一部分，不只是 trace 标签。复用错误的 ID 会串会话，每次随机生成又会失去连续性。

## store 保存什么

Store 使用 namespace 与 key 保存业务数据：

```text
namespace = ("users", user_id, "preferences")
key       = "writing-style"
value     = {"tone": "concise", "language": "zh"}
```

它适合跨会话仍应存在的数据，例如用户偏好、经过确认的事实、共享知识或任务产物索引。节点可通过 runtime 访问 store，也可以在图外由应用服务读写。

Store 不是自动长期记忆。何时写、写什么、如何纠错和过期，仍由应用定义。

## 选择边界

| 问题 | Checkpointer | Store |
| --- | --- | --- |
| 数据跟随哪个范围？ | 单个 thread | 用户、组织或业务 namespace |
| 主要用途 | 恢复执行与短期状态 | 跨 thread 查询 |
| 典型内容 | messages、plan、pending task | 偏好、事实、档案 |
| 访问方式 | `thread_id` 与图状态 | `get/put/search` |
| 是否参与节点重放 | 是 | 作为外部读写依赖 |

一个常见组合是：checkpoint 保存本轮原始消息和摘要，store 保存用户确认过的长期偏好。下一轮从 store 选择相关偏好注入上下文，但不把用户全部历史复制到新 thread。

### 用换会话和换进程区分两种保存

用户在 thread A 说默认中文，在 thread B 开始新任务。若中文只在 A 的 state 中，B 不会自动看到；应用把已确认偏好存入用户 namespace，B 才能主动读取。反过来，store 中有中文偏好，也不会告诉图 A 正暂停在哪个审批节点。

再退出进程重启，内存 saver 和 store 都丢失；持久实现才可能恢复。可见跨 thread 与跨进程是两个不同问题。设计测试时各做一次，不要把同一进程里第二次 invoke 成功当成灾后恢复证明。

## 一次审批请求的两条时间线

假设 `thread_id=review-42` 的流程在“等待审批”处中断，用户偏好则保存在 `("tenant-a", "users", "u7")`。恢复时读取同一个 thread 的 checkpoint，偏好通过可信租户身份另行查询 store：

```text
请求 A → 节点生成草稿 → checkpoint → interrupt 等待审批
                                   │
请求 B（同一 thread_id）→ Command(resume=审批结果) → 后续节点
                                   │
独立 store：用户偏好 ← 按租户和用户命名空间读取
```

如果请求 B 换了 `thread_id`，它不会恢复原审批；如果把用户偏好仅存在 checkpoint，另一个 thread 也不会自动看到。恢复还会重新进入中断所在节点，节点中位于 `interrupt()` 之前的代码可能再次执行；调用外部服务时应使用稳定业务幂等键，不能把 checkpoint 当作外部副作用的提交记录。这里的图表示概念顺序，具体重放范围取决于节点与任务边界，详见中断章节。

## InMemory 只适合开发

`InMemorySaver` 与 `InMemoryStore` 在进程退出后丢失数据，也不解决多实例共享。它们适合单元测试、教程和本地调试。

生产环境应使用持久化实现，并明确：

- 连接初始化和 schema migration；
- 数据保留时间与删除请求；
- 加密和敏感字段；
- 并发更新与事务边界；
- checkpoint 大小和索引；
- 租户 namespace 隔离。

数据库 checkpoint 成功，不代表工具调用的外部数据库事务也成功。跨系统仍需幂等键或 outbox 等业务方案。

## 状态为什么会无限增长

最常见来源是完整 messages、检索原文、工具大结果和重复计划。每一步保存整份累计状态时，存储与读取成本会随会话长度上升。

治理顺序：

1. 不把无需恢复的数据放入 State。
2. 工具结果只保留模型所需摘要和外部引用。
3. 对旧消息做受控摘要，保留最近窗口。
4. 给 thread 和 checkpoint 设置保留策略。
5. 测量仍不足时，再考虑 delta 存储等优化。

不要先删除历史再想审计需求。摘要和清理策略应由产品、合规与故障恢复共同决定。

### 压缩状态之前先确定恢复还需要什么

检索原文可以改存引用，但引用对应的文档若后来被修改，重放可能得到另一份材料。需要精确审计时，记录版本或内容指纹；只需继续业务时，可以重新核验当前资料，并明确这是重新决策。摘要省空间，也会丢细节，应保留返回原材料的路径。

消息清理还不能破坏正在等待的工具闭环和审批预览。清掉当前工具请求再恢复结果，会让下一次模型调用失去协议上下文。保留策略必须理解状态用途，而非统一删除最旧字段。

## time travel 不是修改过去

从历史 checkpoint 恢复通常会创建新的执行分支，而不是物理改写已有历史。节点会从选定状态重新运行，外部世界却不会自动回滚。旧 run 已发送的邮件、写入的数据库和产生的费用依然存在。

因此 time travel 适合调试和重新决策，不是分布式事务回滚。

## 一个实用命名策略

- `thread_id`：稳定表示一次会话或工作流实例。
- `checkpoint_id`：定位 thread 中某个历史点，由系统生成或读取。
- store namespace：从可信身份构造，包含 tenant/user/domain。
- store key：稳定业务标识，不用自然语言整句充当 key。

任何来自请求参数的 namespace 都要经过服务端租户校验。

### 一个地址正确，还不代表访问被授权

thread_id 与 namespace 是持久化定位键，不是密码。服务端应从可信租户和业务对象映射它们，并核验请求者是否能读取或恢复这个流程。随机字符串难猜只能减少偶然碰撞，不能替代权限检查。

删除用户数据时，也要分别处理 thread checkpoint、store 偏好、外部文档引用和运行日志。删掉当前 state 的字段，旧 checkpoint 仍可能保留；将数据移到 store，也没有自动获得完整删除政策。

## 源码入口

- `langgraph/checkpoint/base/__init__.py`
- `langgraph/checkpoint/memory/__init__.py`
- `langgraph/store/base/__init__.py`
- `langgraph/store/memory/__init__.py`
- `langgraph/pregel/_checkpoint.py`
