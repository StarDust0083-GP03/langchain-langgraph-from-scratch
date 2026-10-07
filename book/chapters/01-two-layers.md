# 两层框架，一条执行链

一句话区分两个项目：**LangChain 负责让模型、消息、工具和应用组件说同一种语言；LangGraph 负责让这些组件在有状态、可循环、可暂停的程序里可靠运行。**

它们不是二选一。当前 `langchain` 包的依赖声明直接包含 `langgraph`，而 `create_agent()` 返回 `CompiledStateGraph`。你可以只用 LangGraph，也可以在 LangGraph 节点里调用任意 Python 函数，但 LangChain 已经准备好了常见模型与工具协议。

## 从应用表面往下看

```text
你的产品
  │  输入、权限、业务数据、UI
  ▼
LangChain Agent harness
  │  模型、工具、消息、中间件、结构化输出
  ▼
LangGraph StateGraph
  │  状态、节点、边、路由、checkpoint、interrupt
  ▼
Pregel runtime
     Plan -> Execution -> Update -> 下一 super-step
```

这张图里最容易被忽略的是 harness。官方当前的定义很直接：Agent 是模型调用工具的循环，harness 是围绕循环的提示、工具和中间件。真正决定 Agent 是否可控的，往往不是模型那一行，而是“此时给模型看什么、允许它调用什么、失败后怎样继续”。

### 用一次研究任务看清每层负责什么

用户问某份文档是否支持一个结论。消息对象保留问题与角色，聊天模型提出检索工具请求，工具执行器读取被授权的资料，再把结果配回请求。LangChain 提供这些对象之间的统一协议。模型猜中了工具名还不够，执行层仍要核验参数和读取权限。

如果查到的材料不够，流程需要再次检索；草稿完成后还可能等待审批。这时 LangGraph 保存计划、已读材料和待执行步骤，决定继续循环还是暂停。Pregel 则把图转换成具体任务，执行、合并结果，再推进下一步。应用仍拥有业务权限与发布规则，框架不会替你判断这份结论是否真的可信。

## LangChain 的四块底座

### 消息

`HumanMessage`、`AIMessage`、`ToolMessage` 等类型保存的不只是文本。`AIMessage` 可以携带结构化 `tool_calls`，`ToolMessage` 用 `tool_call_id` 把执行结果配回原请求。多模态内容、token usage 和 provider 元数据也附着在消息上。

### 模型

`BaseChatModel` 统一 `invoke`、`stream`、`batch` 等调用表面。provider 包负责把统一消息翻译成具体 API，再把响应还原成标准消息。统一接口降低切换成本，但不会抹平供应商能力差异。

### 工具

工具由名称、描述、输入 schema 和执行函数组成。模型只提出调用意图，真正执行工具的是应用或 `ToolNode`。这条边界很重要：模型不能因为生成了一段 JSON 就自动获得系统权限。

### Runnable

Runnable 把“可调用单元”统一成同步、异步、批处理和流式接口，并支持顺序、并行、重试与配置传播。模型、prompt、parser、Retriever 和编译后的图都可以出现在这套调用表面上。

## LangGraph 增加了什么

普通函数调用只关心当前栈。Agent 工作流还需要回答：

- 当前对话和中间结果存在哪里？
- 两个节点并行写同一字段时如何合并？
- 工具失败后从哪里重试？
- 进程退出后如何从上一步继续？
- 人工审批等待一天后如何恢复？

LangGraph 把这些问题变成显式概念：State、Node、Edge、Reducer、Checkpointer、Store、Interrupt。图不是为了画图，而是为了给状态转换一个可检查、可保存的边界。

### 为什么组件协议不能替代运行时

普通顺序调用能完成“搜索后总结”，但进程在搜索之后退出，Python 调用栈通常不会自动恢复。把步骤建成状态图，可以在明确边界保存已完成结果和待处理任务。它解决的是运行连续性，不是模型正确率；保存了一份错误草稿，恢复后仍是一份错误草稿。

反过来，只有图而没有统一消息和工具协议，节点之间也可能传递不兼容的数据。图负责何时运行，组件协议负责运行时传什么。两层配合后，调试可以分别查消息转换、工具执行和状态推进，不必把所有失败都称为“Agent 出错”。

## 三种使用层级

| 层级 | 适合场景 | 代价 |
| --- | --- | --- |
| `create_agent` | 标准模型工具循环，需要中间件和记忆 | 控制流形状相对固定 |
| `StateGraph` / Functional API | 自定义路由、审批、并行、长流程 | 需要自己定义状态边界 |
| 直接使用 Pregel | 运行时研究或特殊通道语义 | API 低层，维护成本高 |

大多数项目应从第一层开始，只有控制流真的超出标准循环时才下沉。直接使用 Pregel 通常不是“更专业”，而是主动承担编译器本来替你做的工作。

## 什么时候不需要它们

如果应用只是一次 prompt 加一次模型调用，原生 SDK 更短。如果流程完全确定、没有模型路由，普通 Python 函数和任务队列通常更清楚。如果需要的是全文搜索而非 Agent，先把检索系统做好。

框架的价值来自组合与运行保障，不来自 import 的数量。

### 怎样决定是否下沉到自定义图

先写出一个无法用标准循环表达的真实需求。比如检索和数据库核验必须并行完成，再共同进入审批，这个依赖关系值得显式建图；只是希望换一个 prompt，通常用模型配置或中间件即可。每增加一个层级，都意味着自己接管更多状态和恢复责任，不能只凭图更复杂就认为设计更完整。

## 源码入口

- `langchain/libs/core/langchain_core/messages/`
- `langchain/libs/core/langchain_core/runnables/base.py`
- `langchain/libs/langchain_v1/langchain/agents/factory.py`
- `langgraph/libs/langgraph/langgraph/graph/state.py`
- `langgraph/libs/langgraph/langgraph/pregel/main.py`

下一章先把框架拿掉，手写一遍最小 Agent 循环。看清循环之后，后面的封装才不会变成魔法。
