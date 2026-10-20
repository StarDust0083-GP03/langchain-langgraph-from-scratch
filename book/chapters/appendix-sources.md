# 附录 B：来源、版本与原创性说明

## 正文中的证据怎样区分

阅读技术结论时，应问它来自哪种证据。归档源码可支持对象关系、签名和特定分支的执行机制；官方网页用于说明公开合同与后续能力；天文台申请中的 `SIM-` 资料、预算和审批轨迹则是本书设计的教学模型。

两个 CLI 使用固定资料和确定性逻辑，离线断言核对状态与分支。它们没有评测真实模型研究质量，没有查询天文台排班，也没有完成 GPU 或远程沙箱实验。1500 秒仅由列出的模拟开销算出，不能推广为真实望远镜所需时长。

将片段接入产品后，需要另测 provider 消息合同、服务授权、跨进程持久化和外部写入防重。正文中的设计建议不冒充框架内置保证，来源路径和版本信息帮助读者自行验证。

## 本地源码

核心实现归档在两个独立目录：

```text
sources/repos/langchain
sources/repos/langgraph
```

对应完整提交为 LangChain `877ad8c7bfa3f74377caa6fd33cbc20687e0052f` 和 LangGraph `1afaca35a0d4962fb0203a0e9133a07ffd6a553c`。短 hash 用于正文定位，完整 hash 用于核对快照身份。浅克隆只包含有限历史，不宜据此推断某项能力最早出现在哪次提交。

`sources/inventory.json` 记录归档清单。源码及其 MIT 许可证保留原项目权属，本书不改第三方资料，也不把框架内部实现大段搬入正文。代码示例为本书重新设计，API 名称和必要接口形状则作为事实引用。

## 官方文档

网页索引在 `sources/web/sources.tsv`，归档正文在 `sources/web/*.md`。本地记录用于说明写作依据，在线页面可能继续变化；出现差异时，先比较页面日期、包版本和源码快照，而不是混用不同年代的例子。

以下链接按阅读对象分组，每条说明它承担的事实范围：

- [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview)：组件与 Agent 的总体入口。
- [Component architecture](https://docs.langchain.com/oss/python/langchain/component-architecture)：模型、消息和工具之间的组件关系。
- [Messages](https://docs.langchain.com/oss/python/langchain/messages)：结构消息、内容块与工具观察。
- [Models](https://docs.langchain.com/oss/python/langchain/models)：聊天模型调用表面与能力差异。
- [Tools](https://docs.langchain.com/oss/python/langchain/tools)：工具转换、参数与运行注入。
- [Agents](https://docs.langchain.com/oss/python/langchain/agents)：标准循环与工厂用法。
- [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)：原生和工具形式的输出策略。
- [Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)：请求调整、调用包装与 hooks。
- [Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：上下文组织及选择范围。
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)：运行时与持久工作流入口。
- [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)：状态、节点、边和可见范围。
- [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)：函数式组织任务的另一种表面。
- [Pregel runtime](https://docs.langchain.com/oss/python/langgraph/pregel)：同步步骤、actor 与 channel。
- [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：检查点、历史和恢复。
- [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)：动态暂停、恢复值与重放约束。
- [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)：流模式和事件接口，注意页面后续重命名或版本差异。
- [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)：父子图映射及保存边界。
- [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)：失败恢复和任务结果保存。
- [Deep Agents：从零搭建数据分析 Agent](https://docs.langchain.com/oss/python/langchain/deep-agent-from-scratch)：通用 harness 的逐步组装参考，不采用其分析业务。
- [Memory（add-memory）](https://docs.langchain.com/oss/python/langgraph/add-memory)：短期和长期数据的组合方式。
- [Stores](https://docs.langchain.com/oss/python/langgraph/stores)：namespace、item 与检索索引。
- [Multi-agent](https://docs.langchain.com/oss/python/langchain/multi-agent/index)：委托、路由、交接和技能模式。
- [MCP](https://docs.langchain.com/oss/python/langchain/mcp/index)：工具适配、连接与认证的文档入口。

Deep Agents、记忆扩展、multi-agent、MCP 和较新事件流还使用快照之后的文档补充。它们不都由两个归档仓库完整覆盖，相关导入与生命周期应以实际安装的独立包 reference 为准。

## 结构参考

比较教学路线时曾参考 [LangGraph announcement](https://blog.langchain.com/langgraph/) 和 [Real Python: Build Stateful AI Agents With LangGraph](https://realpython.com/langgraph-python/)。前者提供设计背景，后者提供面向学习者的讲解顺序，不能用作当前 API 的唯一证据。

本次正文保留既有章节层级与导航关系，解释、教学场景、代码和图表围绕天文台申请重新创作。案例标题与正文统一使用观测业务，不将其他教程的场景改名后继续沿用。

## 事实强度

遇到争议时，优先检查同版本源码与测试是否直接体现该行为，再核对公开文档承诺。官方博客可解释设计动机，本书的工程建议则说明适用条件和风险，不提升为框架自动保证。

教学推演需要给出输入、规则和状态结果，但不等于实测服务。比如 8 帧得到 1900 秒可由本地公式验证，真实观测质量、吞吐和沙箱隔离则需要另行实验。embedding 召回排序也不构成事实可信度证明。

同样，离线回归通过只覆盖执行过的断言。它不能证明并发恢复、所有 provider 或未来版本都兼容。报告结果时应连同解释器、包版本和测试入口一起保留，便于复现。

## 版本限制

核心讲解以 `langchain 1.4.2`、`langchain-core 1.6.4`、`langgraph 1.2.12` 与 `langgraph-checkpoint 4.2.0` 的快照关系为基线。实际运行其他版本时，应先核对依赖和关键签名；成功 import 只能说明入口存在，不能证明所有语义不变。

本书不展开 JavaScript 版本差异、0.x 的全部兼容类、每家模型的参数全集或 LangSmith 托管服务运维。beta channel 与事件格式尤其依赖版本，不提供跨版本读写兼容承诺。

`deepagents`、`langmem` 和 `langchain-mcp-adapters` 属于独立发布的包。章节讨论其职责与接入边界，示意片段若没有完整依赖与服务配置，会明确说明前提，不把它们算作两个离线 CLI 已验证的功能。

## 更新本书时的核对顺序

先记录新快照和各包依赖，保留旧版本定位信息；再检索弃用与破坏性变更，比较工厂图形、状态 channel、检查点和事件合同。不要更新一个导入名后就宣称全部示例已适配。

运行 `examples/mini_agent.py`、`examples/research_assistant.py` 与 `examples/test_examples.py`，另在隔离环境恢复旧 checkpoint。页面由主构建流程生成后，再运行 `wiki/verify.py` 检查阅读器与本地链接。源码事实、离线断言和页面验证分别报告，避免将其中一项成功当成全书所有层面已经验证。

若变更影响批准版本或副作用，补充失败输入与领域测试；若更改教学资料，同步核对计算、图表和代码输出。这样更新依据落在可重复对象上，而不依赖上一次阅读的记忆。
