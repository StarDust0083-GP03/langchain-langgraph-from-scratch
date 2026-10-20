# 路由、循环与 Command

6 帧方案需要 1500 秒，8 帧方案需要 1900 秒，两者面对 1800 秒窗口应走不同路径。状态图的路由把这种结果变成调度决定：预算满足才等待审阅，预算超限则停下解释或请求新参数。

下一步由状态决定时，必须明确决定读取的是哪个值、是否已经更新，以及进入循环后靠什么停止。否则图虽然有条件边，实际仍可能使用旧判断或无限修订。

## 固定边与条件边

资料搜索完成后总要生成草稿，可以使用固定边；草稿形成后是否进入审批，则适合条件边。以下为 builder 和相应节点已经定义后的片段：

```python
builder.add_edge("search", "draft")

def after_draft(state):
    if state["status"] == "needs_evidence":
        return "halt"
    return "review" if state["total_s"] <= state["window_s"] else "halt"

builder.add_conditional_edges(
    "draft", after_draft, {"review": "review", "halt": "cancel"}
)
```

路由只解释已写入状态，不在这里另查排班或发送通知。这样同一输入能得到相同选择，状态历史也能解释为何走到某条分支。真实资源状态若需要再核验，应作为明确节点，而非隐藏在路由函数里。

## `Command` 合并更新与跳转

审核决定同时改变 `approved` 和后继位置时，用 `Command` 可以把这项决定放在一起。以下片段假定 `decision` 已由可信外部输入获取并校验：

```python
from typing import Literal
from langgraph.types import Command

def apply_decision(state, decision) -> Command[Literal["publish", "revise"]]:
    accepted = decision["approved"]
    return Command(
        update={"approved": accepted, "feedback": decision.get("feedback", "")},
        goto="publish" if accepted else "revise",
    )
```

这展示更新和调度表达，不是可直接注册的完整节点，因为应用还要负责提供 `decision`。第 14 章的真实节点在内部调用 `interrupt()` 获得它。类型参数标明目标，有助于检查和可视化，不代替运行时业务校验。

### 更新与跳转为什么应来自同一个决定

拒绝 v1 后，状态应写 `approved=False` 并进入修订。如果另一处路由仍读取旧的 `approved=True`，就可能错误发布。让更新和跳转使用同一份已验证决定，能减少这种分离判断。

`goto` 不会抹去原有静态边。若 `review` 同时有通向 `publish` 的固定边，又返回 `goto="revise"`，两个目标都可能被调度。测试时应断言拒绝分支没有发布，不只断言修订出现了。

## `Send` 表示动态 fan-out

一份申请可能附带任意数量的参考记录，适合为每条记录安排一个核验任务。下面是已定义 `check_record` 节点后的路由片段：

```python
from langgraph.types import Send

def fan_out(state):
    return [Send("check_record", {"source": source, "proposal_id": state["proposal_id"]})
            for source in state["sources"]]
```

每个任务只拿当前资料和申请身份，避免复制整段会话。结果应带来源 ID 写入可合并字段，再由下一步按来源排序、去重和检查缺项。任务数量为零时也应定义行为，比如直接输出证据不足，不能假定聚合节点必定被唤醒。

| 输入集合 | 子任务载荷 | 聚合必须核对的内容 |
| --- | --- | --- |
| 2 个规则来源 | 各自编号与版本 | 两项都已返回且版本正确 |
| 1 个被拒绝来源 | 拒绝原因与来源身份 | 是否允许缺项继续 |
| 空来源集合 | 没有动态任务 | 另一路径表达证据不足 |

这张表强调基数和完成状态，动态并行并不自动给出“所有证据齐全”的业务结论。

## 循环要有业务不变量

修订循环会消耗版本和预算。示例只允许审阅 v1、v2、v3，拒绝第三版后进入 `review_limit`，不再生成 v4。状态中始终保持已研究资料不因单纯修订而重复追加。

```python
next_node = "revise" if state["revision"] < 3 else "cancel"
```

实际循环也可以跟踪待核验来源、已尝试查询、费用或截止时间。每轮必须说明什么在向停止推进，不能只依赖模型宣称完成。框架 recursion limit 保护图步骤，业务上限则给出用户可理解的原因。

### 修订循环需要一个可观察的前进条件

拒绝 v1 的意见若是“注明尚未核验目标高度”，修订节点应保存这项意见、增加 revision，并写入新草稿。没有修改意见或新资料时，反复生成相同文本没有研究收益。

判断进展可比较来源集合、草稿指纹和未解决项。三次拒绝后结束，并不表示申请失败的所有原因都已查清，而是当前修订额度耗尽。将 `published_locally`、`needs_evidence`、`over_budget` 和 `review_limit` 分开，用户和测试才知道流程停在哪里。

## 并行不是竞态自由

规则节点和时间节点同一步运行时，都只能读取前一步状态。规则节点不会因为快一些就让时间节点看到新字段，所有本步写入等合并后才对下一步可见。

reducer 解决的是写入合并，不能自动解决领域冲突。两个专家对可行性一赞一反，应保存两份独立判断和证据，让聚合节点显式处理。把布尔值改成列表只能保住信息，仍需定义怎样作决定。

## 错误路由与异常不是一回事

`needs_evidence` 表示搜索已完成但无匹配，`over_budget` 表示计算得到超限结果，都适合正常返回并路由。连接断开则可能尚未获得结果，应保留故障和有限重试语义。

当人必须作选择时使用中断；当权限被拒绝时，不应通过不断换工具绕开。分类决定图如何继续，也决定观测如何计数。把服务故障伪装成无资料，会让模型错误解释成知识缺口；把正常超预算抛成系统错误，又会制造无意义重试。

## 父图与子图的跳转

子图可以通过 `Command(graph=Command.PARENT, ...)` 将更新和控制交到父图。适合明确 handoff，但更新的共享字段需要父层可接受的合并语义，不能假定子图能任意重写父状态。

研究专家通常只需要回传 findings，父图负责预算与审批。若没有正式控制权转移需求，输入输出映射更容易测试。跨图跳转应少量且有明确目标，避免读一个局部函数却无法知道它会跳到整个应用的哪里。

### 错误分支与异常恢复分别表达什么

假设子图核验来源 A 成功、来源 B 超时。父图可以保留 A，仅重试 B；也可以以资料未齐终止。无论选择哪条，都要区别“B 没支持结论”和“B 尚未被观察”，否则聚合得到虚假的反对证据。

跨图时还应把失败身份带回来。只返回 `failed=True` 无法判断该重试哪个来源，直接把子图全部历史复制到父层又扩大上下文。窄结果对象可以同时包含来源、完成状态和失败类型，使路由有足够依据。

## 源码入口

- `langgraph/types.py`：阅读 `Send`、`Command` 和动态中断的字段定义。
- `langgraph/graph/_branch.py`：跟踪路由返回目标如何转换成调度信息。
- `langgraph/graph/state.py`：对比固定边和等待多个来源的边。
- `langgraph/pregel/_algo.py`：观察任务准备和写入应用的时序。

用一次批准、一次拒绝和一次预算不足的轨迹比较，会比单看图像更容易发现多余固定边或缺失结束状态。
