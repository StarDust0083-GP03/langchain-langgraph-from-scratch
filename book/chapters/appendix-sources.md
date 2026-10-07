# 附录 B：来源、版本与原创性说明

## 正文中的证据怎样区分

源码入口对应本书锁定版本中的结构与调用路径；状态合并、审批故障等推演用于解释机制，不表示所有场景都经过在线服务实测。离线示例验证确定性控制流，没有验证真实模型质量、供应商兼容、生产持久化或外部发布事务。

将示例接入产品时，需要另外做目标 provider 合同、进程重启恢复与业务权限测试。正文指出的幂等键、版本核验和数据清理是应用设计责任，不能因图能继续运行就认定这些能力已经自动完成。

## 本地源码

```text
sources/repos/langchain
sources/repos/langgraph
```

下载方式为官方 GitHub 仓库的浅克隆。生成本书时的提交：

- LangChain `877ad8c7bfa3f74377caa6fd33cbc20687e0052f`
- LangGraph `1afaca35a0d4962fb0203a0e9133a07ffd6a553c`

完整统计保存在 `sources/inventory.json`。源码版权和许可证归原项目所有，两个仓库均包含各自的 MIT LICENSE。本书不复制大段实现，只引用 API 名称、文件路径和必要的短代码形状。

## 官方文档

本地归档及 URL 索引：

- `sources/web/sources.tsv`
- `sources/web/*.md`

重点页面包括：

1. [LangChain overview](https://docs.langchain.com/oss/python/langchain/overview)
2. [Agents](https://docs.langchain.com/oss/python/langchain/agents)
3. [Component architecture](https://docs.langchain.com/oss/python/langchain/component-architecture)
4. [Messages](https://docs.langchain.com/oss/python/langchain/messages)
5. [Models](https://docs.langchain.com/oss/python/langchain/models)
6. [Tools](https://docs.langchain.com/oss/python/langchain/tools)
7. [Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
8. [Middleware](https://docs.langchain.com/oss/python/langchain/middleware/overview)
9. [Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
10. [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview)
11. [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)
12. [Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
13. [Pregel runtime](https://docs.langchain.com/oss/python/langgraph/pregel)
14. [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
15. [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
16. [Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)
17. [Subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
18. [Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)

网页会更新，本地归档用于说明本书写作时看到的版本，不代替最新官方文档。

## 结构参考

以下二手材料只用于比较教学顺序和读者常见疑问：

- [LangGraph announcement](https://blog.langchain.com/langgraph/)
- [Real Python: Build Stateful AI Agents With LangGraph](https://realpython.com/langgraph-python/)

本书没有复用这些页面的段落、示例业务、标题体系或插图。章节以本地源码调用链重新组织，贯穿案例和可运行代码为本书原创。

## 事实强度

正文中的信息按以下优先级判断：

1. 当前源码和测试直接体现的行为；
2. 当前官方文档承诺的公开语义；
3. 官方博客给出的设计背景；
4. 本书基于前述材料给出的工程建议。

工程建议使用“建议、适合、通常”等措辞，不伪装成框架保证。provider 能力、云部署和价格等易变信息不做静态大全。

## 版本限制

本书重点覆盖 Python 版本：

- `langchain 1.4.2`
- `langchain-core 1.6.4`
- `langgraph 1.2.12`
- `langgraph-checkpoint 4.2.0`

不覆盖：

- LangChain.js 与 LangGraph.js 的 API 差异；
- 0.x 时代所有 legacy chain 和 memory 类；
- LangSmith 托管服务的完整运维；
- 每个模型 provider 的全部参数；
- 未来版本对 beta 接口的修改。

## 更新本书时的核对顺序

1. `git pull` 后记录新 commit，不覆盖旧快照事实。
2. 比较各 `pyproject.toml` 版本和依赖范围。
3. 搜索 deprecated 与 breaking change。
4. 运行 `examples/` 和 `wiki/verify.py`。
5. 检查 Agent 工厂图形、StateGraph channel、checkpoint 格式和 stream event。
6. 只修改受影响章节，在版本说明中记录差异。

读者应把本书当作源码导读和工程心智模型，而不是固定版本 API reference。
