# 《LangChain × LangGraph：从工具调用到可恢复 Agent》

## 章节与材料映射

1. [读前说明：这本书怎么读](chapters/00-preface.md)  
   来源：两个仓库 README、版本文件、`sources/inventory.json`
2. [两层框架，一条执行链](chapters/01-two-layers.md)  
   来源：官方 overview、component architecture、两个仓库依赖声明
3. [不用框架，先写出 Agent 循环](chapters/02-loop-from-scratch.md)  
   来源：官方 Agents 文档、`create_agent` docstring 与路由源码
4. [消息是运行时协议，不是聊天字符串](chapters/03-messages.md)  
   来源：Messages 文档、`langchain_core/messages/`
5. [工具调用：Schema、执行与结果回填](chapters/04-tools.md)  
   来源：Tools、Structured output、`BaseTool`、`ToolNode`
6. [Runnable 与 LCEL：统一调用表面](chapters/05-runnables.md)  
   来源：`Runnable`、`RunnableSequence`、`RunnableParallel` 源码
7. [create_agent 到底创建了什么](chapters/06-create-agent.md)  
   来源：`langchain/agents/factory.py`、Middleware、Context engineering
8. [StateGraph：状态、节点、边与 reducer](chapters/07-stategraph.md)  
   来源：Graph API、`graph/state.py`、分支源码
9. [路由、循环与 Command](chapters/08-control-flow.md)  
   来源：Graph API、Workflows and agents、`types.py`
10. [Pregel：图在运行时如何前进](chapters/09-pregel.md)  
    来源：Pregel 文档、`pregel/main.py`、`_loop.py`、`_algo.py`
11. [检查点与 Store：两种记忆边界](chapters/10-persistence.md)  
    来源：Persistence、短期/长期记忆文档、checkpoint/store 源码
12. [中断、重放与人工审批](chapters/11-interrupts.md)  
    来源：Interrupts、Fault tolerance、`interrupt` 与 checkpoint 源码
13. [流式输出不是一种流](chapters/12-streaming.md)  
    来源：LangChain/LangGraph Streaming、事件流源码
14. [子图与多 Agent：先隔离上下文](chapters/13-subgraphs.md)  
    来源：Subgraphs、Multi-agent、Context engineering
15. [端到端：本地研究助手](chapters/14-project.md)  
    来源：前述章节、本书 `examples/research_assistant.py`
16. [生产检查表与源码阅读路线](chapters/15-production.md)  
    来源：测试、可观测性、容错、仓库布局与版本策略

## 附录

- [术语与 API 速查](chapters/appendix-glossary.md)
- [来源、版本与原创性说明](chapters/appendix-sources.md)
