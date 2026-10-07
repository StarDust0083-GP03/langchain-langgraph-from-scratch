# 路由、循环与 Command

有状态图真正区别于普通 pipeline 的地方，是下一步可以由运行结果决定，而且节点能够回到之前的步骤。控制流越灵活，停止条件和状态语义就越需要显式。

## 固定边与条件边

固定边适合确定顺序：

```python
builder.add_edge("search", "draft")
```

条件边把路由与节点更新分开：

```python
def route(state: State) -> str:
    return "publish" if state["score"] >= 0.8 else "revise"

builder.add_conditional_edges(
    "review",
    route,
    {"publish": "publish", "revise": "revise"},
)
```

路由函数最好是纯函数。若它同时写数据库、调用模型或修改状态，就很难解释重放时发生了什么。

## `Command` 合并更新与跳转

当节点的业务结果同时决定状态更新和下一节点时，可以返回 `Command`：

```python
from typing import Literal
from langgraph.types import Command

def review(state: State) -> Command[Literal["publish", "revise"]]:
    passed = state["score"] >= 0.8
    return Command(
        update={"approved": passed},
        goto="publish" if passed else "revise",
    )
```

类型参数列出可能目标，便于图可视化和静态理解。`Command` 适合“决定本身就是节点结果”的场景；独立条件边适合“状态已经写好，另一个纯函数负责解读”。

不要在同一路径上既添加固定边，又从节点返回 `goto`，除非确实希望两个目标都被调度。

### 更新与跳转为什么应来自同一个决定

审核通过时，状态写 approved=True 并调度 publish；拒绝时写 False 并调度 revise。Command 将两者放在一次节点结果里，便于检查它们一致。若一处按 score 更新、另一处按过时字段路由，就可能出现“状态说拒绝，流程却发布”。

Command 也没有删除已有固定边的意思。节点同时设置静态后继和 goto，可能激活多个目标。控制流设计应先写清允许后继，再选择一种表达，不把动态图命令误当成自动覆盖所有边。

## `Send` 表示动态 fan-out

并行任务数量在运行时才知道时，可以为每个任务发送独立输入。例如把多个资料条目并行摘要，再通过 reducer 汇总结果。

```text
          ┌─ summarize(item 1) ─┐
items ────┼─ summarize(item 2) ─┼─ reducer -> report
          └─ summarize(item 3) ─┘
```

fan-out 节点不要把完整大状态复制到每个任务，只发送子任务真正需要的字段。否则内存、序列化和 trace 体积会按任务数放大。

## 循环要有业务不变量

常见循环包括：

- model 与 tools 循环，直到没有工具调用；
- draft 与 review 循环，直到分数达标；
- plan 与 execute 循环，直到任务列表为空；
- retry 与 fallback 循环，直到预算耗尽。

每个循环至少需要一个单调变化的量，例如剩余步数减少、待办数减少、已尝试方案集合增加。只依赖模型说“完成了”并不可靠。

```python
if state["attempts"] >= 3:
    return Command(update={"status": "needs_human"}, goto="escalate")
```

LangGraph 的 recursion limit 是最后保险，不是业务停止条件。命中它通常意味着图设计没有表达完成状态。

### 修订循环需要一个可观察的前进条件

草稿被拒绝后，可以带回具体修改意见、增加 revision_count，再生成新版本。仅从 revise 无条件回 review，模型可能不断输出同样草稿。比较版本变化、材料是否增加和剩余预算，才能判断下一轮有没有意义。

停止时也应区分成功、无法补证据和预算耗尽。把三者都接 END，图确实停了，用户却不知道任务完成到什么程度。结束状态要保存原因，供 UI 与测试读取。

## 并行不是竞态自由

同一 super-step 的节点并行运行，它们都读取上一步结束时的状态。两个节点不能通过“谁先写完”互相通信。本步写入统一在 Update 阶段合并，然后下一步才可见。

如果两个分支都写同一个默认覆盖字段，结果不是最后完成者获胜，而是并发更新冲突。用 reducer 只是解决合并方式，不会自动解决业务冲突。

## 错误路由与异常不是一回事

“检索没有命中”通常是合法业务状态，适合写入 state 后走条件边。“数据库连接断开”是运行异常，适合 retry policy 或 error handler。把所有异常转成 `status="failed"` 会丢失 traceback 和重试语义；把所有业务空结果抛异常又会制造虚假告警。

建议区分：

- 业务分支：节点正常返回，图显式路由；
- 可重试故障：抛异常，由有限重试处理；
- 不可恢复故障：终止并保留 checkpoint；
- 需要决策：interrupt，等待人或外部系统。

## 父图与子图的跳转

节点返回 `Command.PARENT` 可把更新和控制交给父图。这对 handoff 有用，但会增加局部阅读难度。跨图跳转应保持少量且命名清楚，通用数据交换优先通过共享 schema 或明确的输入输出完成。

### 错误分支与异常恢复分别表达什么

检索没有结果，可以路由到澄清问题；检索服务超时，则应按依赖故障有限重试。前者是合法业务状态，后者可能根本没有得到观察。吞掉异常并写成“无资料”，会让之后的路由基于假状态做决定。

父子图跳转同样应保持边界。子图只回传已审核 findings，父图决定发布，不必让专家直接改变所有父状态。将需要跨域修改的字段列出来，比让 Command 任意跳转更容易测试。

## 源码入口

- `langgraph/types.py`：`Command`、`Send`、`interrupt`。
- `langgraph/graph/_branch.py`：条件分支。
- `langgraph/graph/state.py`：边与编译。
- `langgraph/pregel/_algo.py`：任务准备与写入应用。
