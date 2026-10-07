# 生产检查表与源码阅读路线

能跑通一次 Agent 不等于能长期运行。生产问题通常不在 happy path，而在重试、恢复、并发、版本升级和数据边界。

## 上线前检查表

### 状态

- 每个字段都有唯一含义和明确写入者。
- 并行写入字段定义了 reducer 或避免冲突。
- 大对象存外部，只在 state 留引用。
- messages 有裁剪、摘要或保留策略。
- 输入、输出与 stream 字段分别做白名单。

### 控制流

- 每个循环都有业务停止条件和总步数上限。
- 空结果走业务分支，瞬时故障走有限重试。
- 超时与取消语义已经定义。
- 并行任务允许部分成功时，有明确聚合规则。

### 工具与副作用

- 工具参数在信任边界校验。
- 服务端执行最终授权，不依赖 prompt。
- 敏感工具有审批或策略门。
- 外部写操作使用幂等键。
- 超时后先查询外部状态，再决定重试。

### 持久化

- thread ID 从可信业务对象映射，不串租户。
- 开发内存 saver 已替换为持久实现。
- checkpoint 和 store 有备份、清理、加密策略。
- 图版本与 checkpoint 兼容策略已记录。
- 恢复路径在进程重启后实际测试过。

### 观测与评估

- 每次 run 有稳定 ID、版本、模型和配置记录。
- trace 不向终端用户暴露内部消息。
- 指标区分模型耗时、工具耗时、排队和人工等待。
- 评估覆盖最终答案，也覆盖工具选择与轨迹。
- 线上失败样本可脱敏进入回归集。

### 把检查表还原成一次真实故障

假设发布工具已成功写入外部系统，随后节点保存状态失败。恢复时可能再执行发布，工具必须通过业务幂等键返回原结果。若身份层只验证新请求、不验证旧 thread 归属，恢复还可能被其他用户触发。副作用、持久化和授权三条检查因此属于同一故障链。

再假设最终答案正确，却搜索了无权资料或循环花费过高。答案评估看不到这些问题，轨迹需要记录实际工具、来源、尝试次数与预算。日志自己也含敏感信息，只保存排查需要的字段，不把全部内部消息推给终端用户。

## 四类测试

### 1. 确定性节点测试

普通 Python 函数直接测试，不需要启动整张图。状态输入固定，断言 partial update。

### 2. 图结构与路由测试

使用 fake model 和内存 saver，覆盖条件边、循环边界、interrupt 和 reducer 冲突。这类测试速度快，应成为主要回归面。

### 3. Provider 合同测试

少量验证消息、工具 schema、结构化输出和 streaming 在目标 provider 上成立。它们会花钱并受网络影响，不应替代本地测试。

### 4. 轨迹评估

同一个最终答案可能经过危险或昂贵的路径。评估工具调用次数、是否访问禁用工具、引用是否存在、预算是否超限。

## 升级策略

LangChain 与 LangGraph 更新频繁。升级时不要只运行 import smoke test：

1. 记录当前包版本和图版本。
2. 阅读目标版本 release notes 与 deprecation。
3. 运行确定性图回归。
4. 用旧 checkpoint 副本测试恢复。
5. 检查 stream event、结构化输出和 provider schema。
6. 小流量部署，比较错误率、步数、延迟和 token。

涉及 checkpoint 格式的能力尤其谨慎。当前文档明确提示 `DeltaChannel` 写出的格式无法被旧运行时理解，回滚前需要迁移或丢弃受影响 thread。

### 升级测试为什么必须带一份旧 checkpoint

新代码能创建新 thread，不代表能继续旧任务。旧 checkpoint 中的节点名、字段含义、channel 格式和暂停位置可能与新图不同。用脱敏副本分别恢复批准与拒绝分支，核对后续动作与旧版一致，再决定迁移或让旧实例继续跑完。

模型 provider 合同也会变化。工具参数、消息顺序和流式片段需小规模真实测试，确定性图测试则负责固定路由和 reducer。两类证据不能互相代替，import 成功更不能证明全部兼容。

## 源码阅读路线

### 想看 Agent 工厂

```text
langchain/agents/factory.py
  -> middleware/types.py
  -> structured_output.py
  -> langgraph/prebuilt/tool_node.py
  -> langgraph/graph/state.py::compile
```

重点找 model node、tools node 和 route 的组装，而不是先读所有 overload。

### 想看状态合并

```text
graph/state.py::_get_channels
  -> channels/last_value.py 或 binop.py
  -> pregel/_algo.py::apply_writes
```

从字段注解如何变成 channel 开始，再看每步写入如何应用。

### 想看恢复与中断

```text
types.py::interrupt
  -> _internal/_scratchpad.py
  -> pregel/_loop.py
  -> pregel/_checkpoint.py
  -> checkpoint/base
```

带着“暂停信息存在哪里、恢复值怎样回到节点”两个问题阅读。

### 想看流式

```text
pregel/main.py 的 stream 入口
  -> stream/run_stream.py
  -> stream/_types.py
  -> transformers.py
```

先确认版本和 stream mode，再跟事件如何从节点到消费者。

## 避免低效阅读

- 不按目录逐文件打开，先从公开 API 找调用链。
- 测试常比实现更能说明边界条件，遇到歧义先搜测试名。
- docstring 表示承诺，实现表示当前机制，两者都要看。
- deprecated 代码用于兼容，不等于新项目推荐用法。
- 仓库 README 的营销描述不能替代执行语义。

### 一次排查应该跟着对象走

看到重复消息，先从节点返回值追到 reducer；看到工具结果无法回填，从调用 ID 追到 ToolMessage；看到审批丢失，从 thread 配置追到 checkpoint 和 resume。每次只追改变目标对象的路径，不需要顺序读完整个框架。

修复后保留那个失败的最小输入和预期状态，作为下一次升级的回归题。书中的检查表便有了具体含义：每条要求都能对应一条故障路径和一项可以重复的验证。

## 最终心智模型

```text
LangChain 规范组件合同
    messages / models / tools / runnables / agent harness
                         │
                         ▼
LangGraph 规范状态转换
    state / reducers / nodes / routing / persistence / interrupts
                         │
                         ▼
Pregel 运行每个 super-step
    plan / parallel execution / update / checkpoint / stream
```

遇到问题时先定位层级。模型没有调用工具，是上下文或 schema 问题；并行更新冲突，是 state/reducer 问题；恢复后重复发邮件，是 checkpoint 与副作用边界问题；页面最后一次性出现，是 stream 链路问题。框架复杂，但故障并不神秘。
