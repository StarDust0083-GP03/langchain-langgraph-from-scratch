# LangChain × LangGraph：从工具调用到可恢复 Agent

一本基于 LangChain 与 LangGraph 官方源码编写的中文电子书。重点不是 API 罗列，而是消息、工具循环、状态图、Pregel、持久化、中断和生产边界之间的完整执行路径。

## 在线阅读与部署

- 阅读：<https://StarDust0083-GP03.github.io/langchain-langgraph-from-scratch/>
- 仓库：<https://github.com/StarDust0083-GP03/langchain-langgraph-from-scratch>

推送到 `main` 后，GitHub Actions 安装锁定依赖、构建网页、运行校验和标准库示例，再将 `wiki/` 部署到 GitHub Pages。首次部署需在仓库 Pages 设置中选择 GitHub Actions。

公开仓库保留书稿、网页、示例和来源版本记录，不包含第三方源码克隆、下载的全文资料、虚拟环境与缓存。网页构建不依赖这些本地资料。

## 本地阅读

本地服务已加入统一启动脚本：

```bash
~/Work/ebooks-serve.sh start
```

打开：<http://localhost:8003/wiki/>

- `wiki/index.html`：分章目录
- `wiki/book.html`：离线合订本
- `wiki/search.html`：全文搜索

## 内容

- 16 章正文与 2 个附录
- 连贯讲解消息、状态与任务的执行过程，补充合并算例、审批推演及失败边界
- 无远程模型也可运行的最小 Agent 与 LangGraph 审批示例
- 字号调整、深浅色、阅读进度、章内目录、全文搜索和移动端布局
- 本地归档 26 篇官方文档与参考材料

章节源文件在 `book/chapters/`，研究结论在 `RESEARCH_NOTES.md`，章节与材料映射在 `book/SUMMARY.md`。

正文以本地研究助手贯穿工具请求、并行更新、checkpoint 与审批恢复。速查表作为回看辅助；教学推演与离线控制流验证不等同于真实模型、生产持久化或外部服务的端到端测试。

## 源码快照

生成日期：2026-09-22。

| 项目 | 本地目录 | Commit | 包版本 |
| --- | --- | --- | --- |
| LangChain | `sources/repos/langchain` | `877ad8c7bfa3` | `langchain 1.4.2`、`langchain-core 1.6.4` |
| LangGraph | `sources/repos/langgraph` | `1afaca35a0d4` | `langgraph 1.2.12`、`langgraph-checkpoint 4.2.0` |

两个仓库均从官方 GitHub 地址浅克隆。完整 commit、文件与行数统计见 `sources/inventory.json`。源码遵循原项目 MIT License，本书不复制大段实现。

## 构建与校验

```bash
cd wiki
npm ci
npm run build
npm run verify

cd ..
python3 examples/mini_agent.py
.venv/bin/python examples/research_assistant.py
```

网页构建需要 Node.js 22 和 Python 3。`mini_agent.py` 不需要第三方依赖；`research_assistant.py` 需要另行安装与快照兼容的 LangGraph 包。研究用本地 `.venv` 以 editable 方式安装两套源码，不随仓库上传。若自行按附录版本获取源码到 `sources/repos/`，可用以下方式创建环境：

```bash
uv venv .venv
uv pip install --python .venv/bin/python \
  -e sources/repos/langgraph/libs/checkpoint \
  -e sources/repos/langgraph/libs/sdk-py \
  -e sources/repos/langgraph/libs/prebuilt \
  -e sources/repos/langgraph/libs/langgraph \
  -e sources/repos/langchain/libs/core \
  -e sources/repos/langchain/libs/langchain_v1
```

## 边界

- 聚焦 Python 的 LangChain 1.x 与 LangGraph 1.x，不覆盖 JavaScript 版本。
- 示例验证控制流，不代表模型能力评测。
- `InMemorySaver` 与 `InMemoryStore` 只用于教学和测试。
- 文档与源码会继续更新，导入路径和 beta API 以当前官方 reference 为准。
- 外部教程仅用于比较教学顺序，正文、示例和图解均独立撰写。
