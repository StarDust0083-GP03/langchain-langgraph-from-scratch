# StateGraph：状态、节点、边与 reducer

`StateGraph` 的公开心智模型很小：State 是当前快照，Node 做工作并返回状态增量，Edge 决定下一步。但真正决定图是否可靠的是 reducer，因为它定义“增量如何变成下一份状态”。

## StateGraph 是构建器

源码 docstring 明确提醒：`StateGraph` 不能直接执行，必须先 `compile()`。构建阶段允许继续添加节点和边；编译阶段验证结构，并把 schema、channel、节点和路由转换成可运行的 `CompiledStateGraph`。

```python
from typing_extensions import TypedDict
from langgraph.graph import START, END, StateGraph

class State(TypedDict):
    question: str
    answer: str

def answer(state: State) -> dict:
    return {"answer": state["question"].upper()}

builder = StateGraph(State)
builder.add_node("answer", answer)
builder.add_edge(START, "answer")
builder.add_edge("answer", END)
graph = builder.compile()
```

节点返回 partial state，不必复制整个对象。返回整份旧状态既浪费，也容易让并行更新覆盖彼此。

## State、Input 与 Output 可以不同

图可以声明总状态、输入 schema 和输出 schema。输入只暴露调用方允许提供的字段，输出只返回调用方需要看到的字段，内部状态仍可包含计划、重试计数和中间产物。

这是一种接口约束，不是保密机制。当前官方文档特别提醒，`stream_mode="values"` 默认可能包含私有 channel。敏感数据不应仅依赖 output schema 隐藏，事件出口也必须过滤。

## 默认 reducer 是覆盖

未标注 reducer 的字段使用 last value 语义：节点返回的新值覆盖旧值。

```python
class State(TypedDict):
    status: str
```

若两个并行节点在同一 super-step 写 `status`，运行时无法确定哪一个应该赢，通常会报告并发更新冲突。解决方案不是赌执行顺序，而是重新设计：

- 两个节点写不同字段；
- 给字段定义可合并 reducer；
- 让聚合节点在下一步做显式选择。

## reducer 是二元合并函数

```python
from operator import add
from typing import Annotated

class State(TypedDict):
    notes: Annotated[list[str], add]
```

节点返回 `{"notes": ["new"]}`，运行时计算 `add(old, update)`。好的 reducer 应尽量满足：

- 确定性：同样输入得到同样结果；
- 无副作用：不修改外部状态；
- 能处理并行写入顺序，必要时自行建立稳定排序；
- 语义明确：追加、集合并集、最大值与覆盖不能混用。

空列表也不一定表示清空。对追加 reducer 而言，`old + []` 仍是 old。需要绕过 reducer 时使用当前 API 提供的 `Overwrite`，或重新设计独立的 reset 字段。

### 用两个检索节点手算一次合并

旧 notes 为 `["原材料"]`，并行节点分别返回 `["文档 A"]` 与 `["文档 B"]`。追加 reducer 合并后保留三份材料，但 A、B 的排列不能被当作业务优先级。若要求按日期或证据等级排序，应保存稳定 ID 和属性，由聚合步骤显式整理。

若节点每次返回旧 notes 加新增项，reducer 又把整份列表追加到旧状态，就会重复原材料。partial update 表达本次新增，reducer 表达历史如何累积，两个职责不能同时各做一次追加。修订一个值则应考虑覆盖语义，不要把所有字段都设成累计。

## Node 只是函数，但签名有层次

最简单的节点只接收 state。需要不可变运行上下文时接收 `Runtime[Context]`，需要 config 时可接收 Runnable config。依赖注入应保持可见，不要从全局变量偷偷读取用户身份或数据库连接。

节点粒度可以用一个判断标准：这个步骤是否值得独立重试、观测或恢复？如果答案都是否，可能不需要拆成节点。

## Edge 表示调度，不表示数据复制

固定边让目标节点在源节点完成后运行。条件边根据路由函数返回值选择目标。多个出边可以激活并行节点，多个入边则要区分“任一完成即可触发”与“等待全部完成”的语义。

图的共享 state 由 channel 维护，不是沿每条边复制一份字典。节点在同一 super-step 中看不到彼此本步刚写入的数据，这一规则要到 Pregel 章节详细解释。

### 边的含义是安排工作，不是传递专属字典

search 到 draft 的边告诉运行时何时激活 draft，draft 读取的是符合 schema 的状态视图。如果两条并行支路都需要 question，它们可以读取同一步快照；一条支路不能靠先执行几毫秒让另一条读到新 notes。

聚合节点若必须等两个来源都完成，应明确表达等待关系。只画两条普通入边，不能在不了解触发规则时假定它们等价于“全部到齐”。图形相似，调度合同仍需用执行轨迹验证。

## compile 做的不只是画图

编译阶段会：

- 校验节点和边引用；
- 为状态字段建立 channel；
- 把节点转成 Pregel actor；
- 建立触发器和写入通道；
- 绑定 checkpointer、store、cache 与 interrupt 配置；
- 生成可调用的 Runnable 图。

因此 builder 与 compiled graph 应视为两个阶段。运行后再修改 builder，不会自动改变已经编译出的对象。

## 一个状态设计检查表

为每个字段写下：

1. 谁能写？
2. 是覆盖还是累计？
3. 两个并行节点同时写会怎样？
4. 是否需要进入 checkpoint？
5. 是否会被发给模型或流给客户端？
6. 如何清理，最大会增长到多大？

如果这些问题答不出来，先不要添加节点。多数图问题最初都是状态模型问题。

### 状态字段越多，恢复合同越大

保存完整检索文档，恢复时资料可用，但每次 checkpoint 和事件输出都更重。保存文档 ID 更小，却要确保重读得到同一版本且仍有权限。两种设计都有代价，应根据是否需要精确重现来决定，不能统一选最短 state。

编译时绑定的图结构、节点名称和状态 schema 也参与恢复。上线后直接改字段含义，旧 checkpoint 可能仍能反序列化，却被新逻辑错误解释。版本测试要验证语义，而不仅验证数据能读出来。

## 源码入口

- `langgraph/graph/state.py`
- `langgraph/graph/_branch.py`
- `langgraph/channels/last_value.py`
- `langgraph/channels/binop.py`
- `langgraph/graph/message.py`
