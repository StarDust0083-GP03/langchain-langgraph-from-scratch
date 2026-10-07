# 中断、重放与人工审批

`interrupt()` 把“等待外部决定”变成图运行时的一等状态。它不是阻塞一个 Python 线程直到用户点击按钮，而是保存 checkpoint、返回暂停信息，让当前进程可以释放资源。之后用同一个 thread 恢复。

## 基本流程

节点内发起中断：

```python
from langgraph.types import interrupt

def approval(state: State) -> dict:
    decision = interrupt({
        "kind": "approve_publish",
        "preview": state["draft"],
    })
    return {"approved": bool(decision["approved"])}
```

首次调用到达这里时，payload 暴露给调用方，图暂停。应用把 payload 渲染成审批 UI。用户提交后：

```python
from langgraph.types import Command

graph.invoke(
    Command(resume={"approved": True}),
    {"configurable": {"thread_id": "thread-42"}},
)
```

恢复值成为 `interrupt()` 的返回值，节点继续产生更新。

<figure class="concept-diagram" tabindex="0">
<svg viewBox="0 0 760 250" role="img" aria-labelledby="approval-title approval-desc" xmlns="http://www.w3.org/2000/svg">
<title id="approval-title">审批中断和恢复的执行边界</title><desc id="approval-desc">首次运行在审批节点中断并保存检查点；收到同一 thread ID 的恢复命令后，审批节点从头执行，中断返回审批值，再进入扣款节点。扣款使用稳定幂等键。</desc>
<g fill="none" stroke="currentColor" stroke-opacity=".45" stroke-width="2"><path d="M148 90h42m153 0h42m153 0h42"/><path d="m182 83 8 7-8 7m187-14 8 7-8 7m187-14 8 7-8 7"/></g>
<g fill="none" stroke="currentColor" stroke-width="2"><rect x="12" y="46" width="136" height="90" rx="8"/><rect x="190" y="46" width="153" height="90" rx="8"/><rect x="385" y="46" width="153" height="90" rx="8"/><rect x="580" y="46" width="168" height="90" rx="8"/></g>
<g fill="currentColor" font-size="16" font-weight="600" text-anchor="middle"><text x="80" y="80">首次调用</text><text x="266" y="80">interrupt()</text><text x="461" y="80">Command(resume)</text><text x="664" y="80">后续副作用</text></g>
<g fill="currentColor" fill-opacity=".7" font-size="13" text-anchor="middle"><text x="80" y="109">进入审批节点</text><text x="266" y="109">保存 checkpoint</text><text x="461" y="109">同一 thread_id</text><text x="664" y="109">稳定幂等键</text></g>
<path d="M463 145v28H266v-28" fill="none" stroke="currentColor" stroke-opacity=".65" stroke-width="2"/><path d="m259 156 7-11 7 11" fill="none" stroke="currentColor" stroke-width="2"/><text x="365" y="207" fill="currentColor" font-size="14" text-anchor="middle">恢复会重放审批节点；中断前的代码也可能再次执行</text>
</svg><figcaption>图：checkpoint 恢复图状态，不会替外部服务撤销或去重。</figcaption>
</figure>

## 最关键的规则：节点可能从头重放

恢复并不等于 Python 从暂停行原地继续。运行时根据 checkpoint 重放节点，`interrupt()` 之前的代码可能再次执行。

危险写法：

```python
def approve_and_send(state):
    charge_credit_card()       # 可能重复
    ok = interrupt("approve")
    if ok:
        send_receipt()
```

安全方向有两种：

1. 把不可重复副作用移到中断之后。
2. 使用稳定幂等键，让中断前操作重复调用也只生效一次。

```python
def approve(state):
    return {"decision": interrupt({"amount": state["amount"]})}

def charge(state):
    charge_credit_card(idempotency_key=state["order_id"])
    return {"charged": True}
```

审批和扣款成为不同节点，恢复边界一眼可见。

### 两次请求之间没有一条永远挂起的调用栈

首次执行生成审批问题，运行时把暂停信息交回应用；应用可以结束 HTTP 请求。第二天收到决定，是一次新的调用，依靠同一个 thread 与保存状态找到原流程。恢复节点重新进入，interrupt 使用恢复值继续产生结果。

这解释了中断之前的代码为何要安全重放：在那里重新生成同一预览通常可接受，重新扣款则不可接受。把草稿生成、审批与发布拆成独立边界，可以更清楚地检查每一步是否可能重复。

## payload 是 UI 合同

不要只传一句字符串。稳定 payload 可包含：

- `kind`：UI 选择哪个组件；
- `title` 与安全摘要；
- 可编辑字段及 schema；
- 风险说明；
- 业务对象 ID；
- 允许动作，例如 approve、reject、edit。

不要把秘密或完整内部 state 暴露给客户端。payload 会经过持久化和网络边界，应按外部 API 对待。

## 多个并行中断

同一 super-step 的并行节点可能同时暂停。客户端不能假设只有一个 interrupt，应按 ID 收集并逐个或批量恢复。恢复数据要明确映射到对应中断，尤其在多个审批问题文本相同时。

UI 还要处理过期决策：审批期间业务对象可能已经被取消或修改。恢复后的副作用节点应重新验证当前业务状态，而不是盲信一天前的预览。

### 审批的是哪个版本，也应进入合同

同意发布草稿 v1 后，业务系统若已生成 v2，不能将同意自动套给 v2。payload 可以引用流程和草稿版本，恢复端校验当前对象仍匹配，否则请求重新审阅。图保存了旧预览，不代表外部世界在等待期间没有变化。

并行中断还应按各自 ID 匹配决定，不能用审批问题文字作唯一键。两个专家都问“通过吗”，却可能审核不同材料；错误匹配会让图正确恢复到错误业务结论。

## 静态断点与动态中断

`interrupt_before=["tools"]` 之类的编译配置可以在节点边界统一暂停，适合调试或对全部工具调用做粗粒度门控。节点内 `interrupt()` 能携带业务 payload，并根据状态决定是否暂停。

前者简单但信息有限，后者表达力更强。敏感操作通常需要节点内或工具中间件提供详细审批合同。

## 故障恢复与中断的共同基础

两者都依赖 checkpoint：

```text
完成 super-step
      │
      ▼
写 checkpoint ──> 正常继续
      │
      ├─> 进程故障后用 thread_id 恢复
      └─> interrupt 返回，等待 Command(resume)
```

这也意味着没有持久 checkpointer，就没有跨进程、跨时间的可靠人工审批。内存 saver 只适合当前开发进程。

## 一个审批测试应验证什么

1. 首次 invoke 确实暂停，不执行后续副作用。
2. checkpoint 的 `next` 指向待恢复节点。
3. approve 走成功分支，reject 走取消或修订分支。
4. 重复 resume 不产生重复副作用。
5. 进程重启后仍能用 thread ID 恢复。
6. 未授权用户不能提交别人的审批结果。

本书 `examples/research_assistant.py` 覆盖前 3 项。生产系统还需要真实数据库和授权层测试。

### 怎样验证拒绝分支没有偷偷执行发布

测试先运行到暂停，断言发布副作用计数为零；提交拒绝后，检查修订状态与新审批，计数仍为零；批准正确版本后才允许一次发布。再重复发送相同决定，确认业务幂等层没有重复产出。

这类测试不需要高能力模型，确定性节点更容易暴露恢复错误。进程重启与未授权恢复则必须用真实持久化和服务身份层补测，内存示例只能证明当前进程中的控制流。

## 源码入口

- `langgraph/types.py`：`interrupt()`、`Command`、`Interrupt`。
- `langgraph/_internal/_scratchpad.py`：中断重放所需的运行时记录。
- `langgraph/pregel/_loop.py`：暂停与恢复循环。
- `langgraph/checkpoint/`：持久化基础。
