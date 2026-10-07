# Runnable 与 LCEL：统一调用表面

Runnable 的价值不是管道运算符本身，而是把不同组件放到同一个执行协议里。源码对它的定义是“一项可以调用、批处理、流式处理、变换和组合的工作单元”。

## 一套接口

一个 Runnable 通常暴露：

| 方法 | 含义 |
| --- | --- |
| `invoke` / `ainvoke` | 单输入同步或异步调用 |
| `batch` / `abatch` | 多输入批处理 |
| `stream` / `astream` | 增量产出 |
| `with_retry` | 包装重试策略 |
| `with_config` | 绑定 tag、metadata、并发配置等 |
| `get_graph` | 查看组合结构 |

默认实现会提供一些退化路径，例如异步方法可能在线程池里调用同步实现。统一表面不等于统一性能，provider 或组件只有覆写原生 batch/stream 才能得到对应优化。

## 顺序与并行

LCEL 用 `|` 构造 `RunnableSequence`：

```python
from langchain_core.runnables import RunnableLambda

normalize = RunnableLambda(lambda s: s.strip().lower())
length = RunnableLambda(len)
chain = normalize | length

assert chain.invoke("  LangGraph  ") == 9
```

字典出现在序列中时会被提升为 `RunnableParallel`，同一个输入送给多个分支：

```python
inspect = normalize | {
    "length": RunnableLambda(len),
    "prefix": RunnableLambda(lambda s: s[:4]),
}
```

并行不是数据依赖分析。字典中的分支彼此独立，如果一个分支需要另一个分支的输出，应改成后续 sequence 或显式图节点。

### 并行组合怎样形成下一步输入

前面的 inspect 把同一份规范字符串分别交给 length 与 prefix，等分支结果收集后形成字典。它没有先算 length 再让 prefix 读取长度。需要这种依赖时，应把字典结果交给后续 sequence；运行得快或先返回，不会改变依赖关系。

batch 同样要区分执行协议与 provider 的服务批处理。框架可以并发调用多个输入，但供应商是否合并请求、是否限流，由具体实现决定。增加并发可能提高等待效率，也可能更快触发配额，不能只凭接口名字预测吞吐。

## 配置如何传播

Runnable config 承载 callback、tag、metadata、最大并发和可配置字段。组合调用时，框架把配置向子 Runnable 传播，所以一次顶层调用能形成完整 trace。

业务状态不应塞进 config。可观测元数据、执行参数与业务数据应分开：

- 输入和 State：会影响业务结果的数据；
- Runtime context：本次 run 的依赖或身份；
- Runnable config：执行与追踪配置。

把 user ID 只放在 trace metadata 里，然后在工具里当作授权依据，是危险的边界混用。

## 流式传播有条件

序列能否逐段流式输出，取决于每个组件是否实现可转换的流式接口。中间插入一个只支持完整输入的普通函数，可能让下游必须等它完成后再开始。

因此遇到“模型支持 streaming，但页面仍最后一次性出现”时，应逐段检查：

1. 模型是否真的产出 chunk；
2. parser 是否等待完整消息；
3. RunnableLambda 是否缓存全部输入；
4. 应用是否消费了正确的 stream mode；
5. 网络代理是否缓冲响应。

### 一个缓冲步骤会怎样改变流式体验

假设模型逐字输出，后面的 parser 却需要完整 JSON 才能解析。整体链会等到对象结束，用户看到的便不是逐字结果。流式能力需要每个步骤支持增量转换；一个只处理完整输入的函数就可能成为缓冲边界。

这不一定是缺陷。审批结果或工具参数本来就需要完整校验才能执行。设计时区分哪些增量仅用于展示、哪些结果必须原子地形成，不要为页面更快而提前执行半个对象。

## 重试放在最小的不稳定边界

```python
model_step = model.with_retry(stop_after_attempt=3)
chain = prompt | model_step | parser
```

如果只模型调用可能遇到限流，就只重试模型。把整条链重试会再次执行前面的检索甚至外部副作用。重试范围越大，幂等要求越高。

同理，图节点级 retry policy 应包住可安全重放的工作单元，而不是整个业务流程。

## Runnable 与 LangGraph 的连接

LangGraph 节点可以是普通 callable 或 Runnable。编译后的图本身也实现 Runnable，因此可以：

- 在图节点中调用模型 Runnable；
- 把一段 LCEL chain 作为节点；
- 从外部用 `invoke`、`stream`、`batch` 调图；
- 让 callback 和配置穿过两层。

这就是两个项目共享执行表面的关键。LangChain 组件不需要知道自己正处于图的哪个 super-step，LangGraph 也不需要理解节点内部是 prompt 还是数据库查询。

## 何时用 LCEL，何时用图

用 LCEL 表示无环的数据变换，特别是“输入经过一串组件得到输出”。出现以下情况时转向图：

- 需要循环或条件分支；
- 需要持久化中间状态；
- 需要人工中断和恢复；
- 多个节点共同更新显式业务状态；
- 需要从特定步骤重放或查看历史。

不要为了画图把三步纯转换拆成三十个节点，也不要用嵌套 RunnableBranch 隐藏一个本来应显式展示的业务状态机。

### 重试整条链，为什么可能重复已经成功的工作

检索成功、模型超时，若重试最外层链，检索也重新运行；前一步若是扣款，风险更高。将重试包在最小故障单元，可减少重复费用与副作用，但前后结果仍要有清晰输入输出。Runnable 的重试包装不自动推断哪些操作安全。

当流程需要保存中间结果、等待人工决定或回到修订步骤时，用图表达这些边界更直观；固定的文本变换组合仍适合 LCEL。不必为了统一外观，把可靠性需求藏进一个复杂 lambda。

## 源码入口

- `langchain_core/runnables/base.py`
- `langchain_core/runnables/config.py`
- `langchain_core/runnables/retry.py`
- `langgraph/_internal/_runnable.py`
