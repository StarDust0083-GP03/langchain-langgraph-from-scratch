# 附录 A：术语与 API 速查

速查页用来找回已经读过的执行关系，不能代替正文。比如看到“reducer”，应想到节点返回增量如何变成新 state；看到“interrupt”，应想到首次暂停与下一次恢复之间的保存边界。只背名称，容易误把暂停当作仍在原调用栈中等待。

遇到问题先描述具体对象：哪条工具消息没有请求、哪个字段重复、哪个副作用发生两次，再找术语和源码。这样查到的是行为原因，而不是一个听起来相关的 API。

## 核心术语

| 术语 | 本书中的含义 |
| --- | --- |
| Agent | 模型在循环中选择并调用工具，直到完成或停止 |
| Harness | 围绕 Agent 循环的提示、工具、middleware、上下文与策略 |
| Message | 模型、用户和工具之间的结构化协议对象 |
| Tool call | 模型提出的结构化执行请求，不代表动作已经发生 |
| Runnable | 统一 invoke、batch、stream 与组合的执行接口 |
| State | 图在某一步可见的业务快照 |
| Partial update | 节点返回的局部状态更新 |
| Reducer | 把旧值与一个或多个更新合并为新值的函数 |
| Node | 读取状态、执行工作并产生更新的单元 |
| Edge | 定义下一步调度关系，不负责复制数据 |
| Super-step | Pregel 的一个同步步骤，包含 Plan、Execution、Update |
| Channel | Pregel 中保存值并合并写入的通信对象 |
| Checkpoint | 某个 thread 在步骤边界的可恢复状态 |
| Checkpointer | checkpoint 的保存与查询实现 |
| Store | 跨 thread 的应用数据存储 |
| Interrupt | 保存暂停点并把决策交给外部调用方 |
| Command | 同时表达状态更新、跳转或恢复值的对象 |
| Subgraph | 作为节点嵌入父图的编译图 |
| Thread | 一条可持续和恢复的工作流实例，由 `thread_id` 标识 |

## 最常用导入

```python
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.types import Command, Send, interrupt
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
```

导入路径对应本书源码快照。若未来版本变化，以当前官方 reference 为准。

## 最小 StateGraph 模板

```python
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph

class State(TypedDict):
    value: str

def work(state: State) -> dict:
    return {"value": state["value"].upper()}

builder = StateGraph(State)
builder.add_node("work", work)
builder.add_edge(START, "work")
builder.add_edge("work", END)
graph = builder.compile()

assert graph.invoke({"value": "ok"}) == {"value": "OK"}
```

## 带 reducer 的状态

```python
import operator
from typing import Annotated
from typing_extensions import TypedDict

class State(TypedDict):
    items: Annotated[list[str], operator.add]
```

节点返回新增列表，不返回完整累计列表。

## Checkpointer 模板

```python
checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
config = {"configurable": {"thread_id": "stable-business-id"}}
result = graph.invoke(input_state, config)
state = graph.get_state(config)
```

内存实现只用于开发测试。

## Interrupt 模板

```python
def approve(state):
    answer = interrupt({"kind": "approval", "preview": state["draft"]})
    return {"approved": answer["approved"]}

paused = graph.invoke(input_state, config)
finished = graph.invoke(Command(resume={"approved": True}), config)
```

中断之前的代码必须可安全重放。

## 选型速查

| 需求 | 首选 |
| --- | --- |
| 单次模型调用 | provider SDK 或 `init_chat_model` |
| 无环组件变换 | Runnable / LCEL |
| 标准工具 Agent | `create_agent` |
| 自定义状态机 | `StateGraph` |
| 现有函数加持久化 | Functional API |
| 研究底层 actor/channel | Pregel |
| 会话短期状态 | checkpointer |
| 跨会话用户知识 | store |
| 人工审批 | interrupt + persistent checkpointer |

## 故障速查

| 现象 | 先查哪里 |
| --- | --- |
| 工具从不被调用 | 工具名称、描述、schema、模型能力 |
| 同一字段并行更新报错 | reducer 与节点写集合 |
| 恢复后重复外部操作 | checkpoint 边界与幂等键 |
| 会话没有延续 | `thread_id` 与 checkpointer |
| 不同会话无法共享偏好 | 是否误把长期数据只放 checkpoint |
| stream 泄露内部字段 | stream mode 与输出白名单 |
| token 正常但页面不增量 | 中间 Runnable 与网络缓冲 |
| 循环直到 recursion limit | 缺少业务停止条件或状态不单调 |
