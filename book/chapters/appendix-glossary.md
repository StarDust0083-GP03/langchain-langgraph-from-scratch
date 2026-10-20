# 附录 A：术语与 API 速查

查术语时可以先写出申请助手中的症状，再找相关对象。比如“拒绝 v1 后仍生成回执”涉及路由与批准版本，“两条资料变四条”涉及增量与 reducer，“关掉进程审批消失”涉及保存实现。名称的用途是定位合同，不是替代运行证据。

本页代码均采用新观测场景。独立可运行的例子使用确定性输入；需要应用已有对象的部分会注明衔接条件。包路径按本书基线与补充文档解释，实际环境仍需核对版本。

## 核心术语

| 名称 | 在观测申请里的具体含义 |
| --- | --- |
| Agent | 根据已有观察选择下一项工具请求的循环，可因完成或额度而停止 |
| Harness | 决定上下文、工具、提示和运行策略的外围组合 |
| Message | 带来源和结构字段的交互对象，不能简单替代为显示文字 |
| Tool call | 模型提出的动作及参数，尚未代表资源被预留 |
| Runnable | 给组件提供单次、异步、批量和增量调用的共同表面 |
| State | 某一步可见的申请数据，如资料引用与当前草稿 |
| Partial update | 节点这一次产生的变化，如新增两项来源 |
| Reducer | 将旧值与更新合成新值的规则，决定追加或其他累计含义 |
| Node | 有输入快照和输出更新的工作单元，可以不含模型 |
| Edge | 安排后继任务的关系，不是独立数据包传输通道 |
| Super-step | 一组任务读取同一前步快照、执行并合并结果的同步步骤 |
| Channel | 底层保存值并处理更新的对象，由 schema 等配置映射而来 |
| Checkpoint | 定位一个 thread 在某边界的值、版本与后续工作信息 |
| Checkpointer | 保存、读取与管理检查点的实现，内存与持久版本保证不同 |
| Store | 用 namespace 与 key 组织跨申请可查询数据的接口 |
| Interrupt | 将等待外部决定的任务交出，并允许之后恢复 |
| Command | 表达更新、跳转或恢复输入的控制对象 |
| Subgraph | 可嵌入父流程、有自身状态合同的图 |
| Thread | 由 `thread_id` 寻址的流程实例，不等于用户身份 |
| Deep Agents | 将文件、计划、技能和委托等能力预装到标准循环上的组合 |
| Runtime | 节点运行时可获得的 context、store 等注入依赖 |
| context_schema | 描述单次调用注入依赖的形状，不替代状态 schema |
| Semantic store search | 借 embedding 索引召回相关记录，结果仍需核对版本和范围 |
| langmem | 提供摘要与记忆管理相关组件的独立库，需另核对版本 |
| MCP | 客户端与外部工具或数据服务交互的标准协议 |
| Handoff | 正式改变当前处理角色或控制位置，不只是转述一句话 |
| Event-streaming v3 | 较新文档描述的统一事件表面，使用前核对目标 API 与版本 |

工具调用 ID、业务申请号、图 checkpoint ID 和草稿 revision 各有用途。调用 ID 匹配一次请求与观察，业务号关联领域对象，checkpoint ID 定位运行历史，revision 绑定审阅内容。混用它们会使重复请求和旧批准难以辨认。

## 最常用导入

可按任务选取对应包，而不必一次导入所有层。下面展示组件、图运行和可选扩展的常用入口，不表示这些包在每个环境都已安装：

```python
# 组件与标准 Agent。
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

# 状态图、注入与进程内保存。
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.types import Send, Command, interrupt
from langgraph.runtime import Runtime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

# 独立安装的可选 harness。
from deepagents import create_deep_agent
```

只运行本书标准库循环不需要这些依赖；端到端图需要 LangGraph。MCP adapters、deepagents 和 langmem 不属于离线例子必须安装的范围，缺少它们不应妨碍核心回归。

## 最小 StateGraph 模板

这个独立例子把固定申请号与预算组成可执行图，不访问外部服务：

```python
from typing import TypedDict
from langgraph.graph import START, END, StateGraph

class Proposal(TypedDict):
    proposal_id: str
    frames: int
    total_s: int

def budget(state: Proposal):
    return {"total_s": state["frames"] * 200 + 300}

builder = StateGraph(Proposal)
builder.add_node("budget", budget)
builder.add_edge(START, "budget")
builder.add_edge("budget", END)
graph = builder.compile()
result = graph.invoke({"proposal_id": "SIM-QUICK-8", "frames": 8})
assert result["total_s"] == 1900
```

这里固定每帧 200 秒包含 180 秒曝光与 20 秒读出。真实输入要另做范围校验，不能从 TypedDict 推断所有值已经验证。

## 带 reducer 的状态

累计资料时只返回新项，可以用下列纯 Python 计算核对合同：

```python
from operator import add
from typing import Annotated, TypedDict

class Evidence(TypedDict):
    sources: Annotated[list[str], add]

old = ["SIM-REQUEST-1"]
update = ["SIM-TIME-4"]
assert add(old, update) == ["SIM-REQUEST-1", "SIM-TIME-4"]
assert add(old, []) == old
```

空更新不会清空历史，两个并行列表的顺序也不表示证据权重。需要去重或按来源替换时，应选择相应数据结构和 reducer，而非盲目继续追加。

## Checkpointer 模板

沿用最小模板中的 builder，可观察保存的值与终态：

```python
from langgraph.checkpoint.memory import InMemorySaver

saved_graph = builder.compile(checkpointer=InMemorySaver())
config = {"configurable": {"thread_id": "quick-budget-8"}}
saved_graph.invoke({"proposal_id": "SIM-QUICK-8", "frames": 8}, config)
snapshot = saved_graph.get_state(config)
assert snapshot.values["total_s"] == 1900
assert snapshot.next == ()
```

新建 saver 或退出进程都会失去这里的内存记录。真实持久性测试必须使用持久实现，并在另一个进程恢复相同地址。

## Interrupt 模板

下面是 review 节点的局部模板，前提是 state 已有稳定草稿、revision，且图绑定 checkpointer。节点后继由应用另行连接：

```python
from langgraph.types import Command, interrupt

def approval(state):
    decision = interrupt({"kind": "proposal.review", "revision": state["revision"],
                          "draft": state["draft"]})
    if type(decision.get("approved")) is not bool:
        raise ValueError("expected a boolean decision")
    if decision.get("revision") != state["revision"]:
        raise ValueError("decision is for another revision")
    return {"approved": decision["approved"]}

# 首次 invoke 暂停后，使用原 thread 配置恢复动态中断。
resume_input = Command(resume={"approved": False, "revision": 1})
```

它只演示动态恢复值，不调用远程服务。静态 `interrupt_before` 断点通常通过 `None` 继续，不能照搬这份业务决定；中断前的代码也必须允许重放。

## 选型速查

| 当前缺口 | 优先考虑 | 不附带的保证 |
| --- | --- | --- |
| 一次文本生成 | 原生模型 SDK 或聊天模型接口 | 自动恢复整个业务 |
| 固定组件变换 | Runnable 与 LCEL | 隔天等待的流程保存 |
| 反复查资料 | `create_agent` | 最终答案一定可信 |
| 文件、技能和委托通用组合 | `create_deep_agent` | 所有 backend 都安全隔离 |
| 固定核验与人工审批 | `StateGraph` | 外部资源操作恰好一次 |
| 函数式组织可持久步骤 | Functional API | 任意 Python 栈原地续跑 |
| 特殊 actor/channel 实验 | Pregel | 更低维护成本 |
| 申请恢复位置 | Checkpointer | 跨申请偏好自动共享 |
| 组内长期数据 | Store | 自动判断与纠正记忆 |
| 外部资料服务接入 | MCP adapters | 服务授权与内容可信 |

## 故障速查

| 可观察症状 | 先收集的证据 | 重点位置 |
| --- | --- | --- |
| 从不请求预算工具 | 当轮可见 schema 和模型响应 | 描述、能力与中间件筛选 |
| 资料条数翻倍 | 节点增量及旧 notes | reducer 与完整历史回传 |
| 并行更新报错 | 同一步全部写入者 | 单值 channel 与聚合设计 |
| v1 批准作用到 v2 | payload、恢复值、当前 revision | 审批合同与版本校验 |
| 重启后没有待审申请 | saver 类型与保存地址 | 持久实现、thread 和图兼容 |
| 预算正确但重复预留 | 业务键与外部回执 | 副作用幂等与超时查询 |
| 用户看到内部计划 | 用户事件原始载荷 | stream mode 和白名单 |
| 草稿最后一次性显示 | 各阶段首个增量时刻 | 缓冲解析器与网络消费 |
| 一直修订不结束 | 版本、未决项和剩余额度 | 循环前进条件与业务上限 |

先用最小失败输入复现，再跟对象跨越的边界查实现。把修复后的输入与断言留下，比记住一个临时配置值更能帮助后续升级。
