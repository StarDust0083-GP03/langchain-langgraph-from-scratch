# LangChain 与 LangGraph 源码学习书：研究笔记

## 研究范围

本书面向已经会 Python、了解大模型调用，但尚未形成 Agent 工程心智模型的读者。重点是 Python 生态中的 LangChain 1.x 与 LangGraph 1.x，不覆盖 JavaScript 实现、LangSmith 商业部署细节，也不把历史 API 当作当前推荐写法。

快照日期：2026-09-22。

- LangChain：`877ad8c7bfa3f74377caa6fd33cbc20687e0052f`
- LangGraph：`1afaca35a0d4962fb0203a0e9133a07ffd6a553c`
- `langchain==1.4.2`，`langchain-core==1.6.4`
- `langgraph==1.2.12`，`langgraph-checkpoint==4.2.0`

本地源码位于 `sources/repos/`。统计口径与包版本见 `sources/inventory.json`。

## 一手材料

1. LangChain 官方仓库 README、`langchain-core`、`langchain` 1.x、测试。
2. LangGraph 官方仓库 README、Graph、Pregel、checkpoint、store、prebuilt 与测试。
3. 官方文档：模型、消息、工具、结构化输出、Agent、中间件、上下文、记忆与流式输出。
4. 官方文档：Graph API、Functional API、Pregel、持久化、中断、子图、容错与工作流模式。
5. 官方发布记录与仓库内版本声明。

抓取页面与原始 URL 的映射保存在 `sources/web/sources.tsv`，正文保存在同目录的 Markdown 文件。

## 二手材料如何使用

- LangChain 官方博客的 LangGraph 介绍用于核对项目最初要解决的问题。
- Real Python 的 LangGraph 教程只用于观察教学顺序，例如先状态、再节点、再条件边、最后持久化。
- 不复用其段落、比喻、示例业务或代码。全书例子统一为“本地研究助手”，并由本书自行实现。

## 核心结论

### 1. 两个框架不是替代关系

LangChain 提供模型、消息、工具、Runnable、Agent 工厂和集成层；LangGraph 提供有状态、可循环、可暂停、可恢复的编排运行时。当前 `langchain` 包直接依赖 `langgraph`，`create_agent` 返回的是编译后的 `StateGraph`。

### 2. 最重要的抽象不是 Chain，而是状态转换

对新项目，学习重点应从“把组件串起来”迁移到：

- 消息与工具调用协议；
- 每一步读什么状态、写什么增量；
- reducer 如何合并并行写入；
- 下一步由固定边、条件边还是 `Command` 决定；
- 哪些数据属于 thread checkpoint，哪些属于跨 thread store。

### 3. `StateGraph` 是构建器，`Pregel` 才是执行层

`StateGraph` 收集 schema、节点和边，`compile()` 生成 `CompiledStateGraph`。其底层是 Pregel/Bulk Synchronous Parallel：Plan、Execution、Update 三阶段循环。同一 super-step 的节点并行运行，写入在下一步才可见。

### 4. Agent 是受约束的模型工具循环

`create_agent` 的主循环是 model -> tools -> model。工程价值主要来自循环外的 harness：系统提示、可用工具、动态上下文、中间件、结构化输出、检查点、store、中断和流式事件。

### 5. 持久化有两个边界

- checkpointer：保存一个 thread 的图状态，用于短期记忆、恢复、中断和 time travel；
- store：保存跨 thread 的业务数据，用于用户画像、事实和共享知识。

混淆两者会造成状态无限膨胀，或让不同会话无法共享真正需要长期保留的数据。

### 6. 人工审批不是在节点外弹一个对话框

`interrupt()` 会把暂停点写入 checkpoint。恢复时，同一节点可能从头重放，因此中断前的副作用必须幂等，或移动到中断之后。恢复值通过 `Command(resume=...)` 回到中断调用点。

### 7. 版本边界必须写进书里

源码快照包含较新的 API，例如 LangGraph 1.2 的 `DeltaChannel` 与 event streaming v3。书中对 beta 或可能变化的接口单独标注，示例优先使用稳定的 `StateGraph`、`Command`、checkpointer 与 store。

## 章节决策

采用“先协议，再运行时，最后工程”的顺序，而不是按官网菜单平铺：

1. 先解释 LangChain 与 LangGraph 的边界。
2. 用不调用付费模型的最小循环建立 Agent 心智模型。
3. 依次拆消息、工具、Runnable 和 `create_agent`。
4. 再拆 StateGraph、reducer、路由和 Pregel。
5. 持久化、中断、流式输出、子图建立在执行模型之后。
6. 以一个可运行的本地研究助手收束，并给出源码阅读路线。

## 明确不宣称的内容

- 不宣称所有 provider 行为一致。
- 不把 mock 示例的结果当作模型能力评测。
- 不把 InMemorySaver/InMemoryStore 当作生产数据库。
- 不把源文件归属统计当作逐行覆盖。
- 不替代官方 API reference，也不保证未来版本仍保持同一签名。
