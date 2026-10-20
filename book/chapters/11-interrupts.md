# 中断、重放与人工审批

值班员明天才有空审阅申请，服务不应为此一直保留一个 HTTP 请求和 Python 线程。`interrupt()` 让图交出待决定的信息，保存可恢复状态，本轮调用返回；之后另一轮调用带着决定找到同一个流程。

这种暂停适合等待，不等于已经批准，也不保证外部条件保持不变。恢复时要检查草稿版本、身份和资源状态，才能把人的决定用到正确对象上。

## 基本流程

以下为已配置持久化的状态图中的节点片段：

```python
from langgraph.types import Command, interrupt

def review(state):
    decision = interrupt({
        "kind": "observatory.review",
        "proposal_id": state["proposal_id"],
        "revision": state["revision"],
        "draft": state["draft"],
    })
    if type(decision.get("approved")) is not bool:
        raise ValueError("approval must be boolean")
    if decision.get("revision") != state["revision"]:
        raise ValueError("stale draft decision")
    return {"approved": decision["approved"]}
```

首次到达中断时，返回结果中的暂停信息交给应用展示。收到审核决定后，用原配置调用 `graph.invoke(Command(resume={"approved": True, "revision": 1}), config)`。这份值成为重放过程中 `interrupt()` 的返回值。完整示例还会检查决定是字典、revision 为整数，以及拒绝后的调度。

<figure class="concept-diagram" tabindex="0">
<svg viewBox="0 0 820 330" role="img" aria-labelledby="approval-title approval-desc" xmlns="http://www.w3.org/2000/svg">
<title id="approval-title">观测申请 v1 与 v2 的审批账目</title>
<desc id="approval-desc">图以三个参与方的泳道记录两次调用。第一次图保存 v1 后向审阅端交出预览并结束请求；第二次审阅端返回 v1 的拒绝，图重入审批节点后生成 v2，再等待决定。外部排班尚无任何提交。</desc>
<g fill="none" stroke="currentColor" stroke-opacity=".3"><path d="M150 54H800M150 125H800M150 205H800M150 285H800M320 35V305M555 35V305"/></g>
<g fill="currentColor" font-size="15" text-anchor="middle"><text x="235" y="25">审阅端</text><text x="438" y="25">图与检查点</text><text x="682" y="25">外部排班</text></g>
<g fill="currentColor" font-size="14"><text x="10" y="87">调用 A</text><text x="10" y="167">等待期间</text><text x="10" y="248">调用 B</text><text x="350" y="80">保存资料与草稿 v1</text><text x="170" y="112">收到 v1 预览</text><text x="350" y="160">待恢复：review</text><text x="170" y="192">人决定拒绝 v1</text><text x="350" y="240">重入节点，核对版本</text><text x="350" y="272">修订为 v2，再暂停</text><text x="594" y="165">未预留窗口</text><text x="594" y="246">仍未提交</text></g>
<g fill="none" stroke="currentColor" stroke-width="2"><path d="M425 92H225m8-5-8 5 8 5M230 218H420m-8-5 8 5-8 5"/><circle cx="681" cy="105" r="13"/><path d="m672 96 18 18M670 294h25"/></g>
<text x="414" y="322" fill="currentColor" font-size="13" text-anchor="middle">拒绝只推进当前申请的修订，不撤销或伪造任何外部资源状态</text>
</svg>
<figcaption>审批期间保存的是草稿与待恢复任务。图中外部排班始终未被写入，v1 的拒绝不能当成 v2 的批准。</figcaption>
</figure>

## 最关键的规则：节点可能从头重放

恢复不是原调用栈在某一行醒来。运行时重新进入节点，利用保存信息和恢复值推进，所以 `interrupt()` 之前的普通代码可能再次执行。

把“预留真实时段”写在中断之前会有风险。首次调用已经预留，恢复再次进入又预留一次。可以把研究和预览准备留在可重放步骤，将外部提交放在审批通过后的单独节点，并在领域服务中使用稳定业务键。

下面是阶段划分的伪代码，不代表框架自带排班 API：

```python
def approval_node(state):
    return {"decision": interrupt(preview_of(state))}

def reservation_node(state):
    # 应用服务再次检查批准版本，并按业务键返回已有或新建的回执。
    receipt = scheduling_service.reserve_once(state["proposal_id"], state["revision"])
    return {"reservation_id": receipt.id}
```

即使移到中断之后，提交节点也可能因故障重试。阶段拆分让风险可见，幂等才处理外部重复生效。

### 两次请求之间没有一条永远挂起的调用栈

调用 A 到达待审点后可以结束，应用只需把申请地址和审批预览关联起来。第二天调用 B 使用同一 thread 和恢复值继续流程，不要求同一个 Web 进程存活。

因此审批前生成随机编号、读当前时间或刷新草稿都要审慎。重放时这些值若变化，UI 上批准的内容可能与实际处理不一致。先把稳定预览写入 state，再在审批节点只读并中断，通常更容易固定版本关系。

## payload 是 UI 合同

审批 payload 应让客户端知道展示什么和允许做什么。申请编号、修订号、安全预览、动作集合和必要警告比一句“同意吗”更有用。需要编辑的字段还应有受限 schema，不应让客户端回传整份内部 state。

payload 会经过序列化、保存和网络边界，不能带连接对象、秘密或其他申请记录。UI 显示的草稿与服务端批准校验应使用同一 revision 或内容指纹，避免预览和提交对象错位。

对 `approved` 应严格检查布尔类型，`bool("false")` 在 Python 中为真。示例专门测试这种输入，防止看似拒绝的文本值成为批准。客户端校验不能代替服务端校验。

## 多个并行中断

规则审核和时间审核可以同时暂停。调用方需识别每个 interrupt 的 ID 和业务对象，收集对应决定；不能只取第一个暂停信息就认为整份申请只有一项待处理。

多个恢复值可按中断身份映射，具体输入形状应核对目标版本。相同问题文本不能作唯一键，两个节点都问“通过吗”时仍是不同任务。恢复后还要核对审批是否过期，不能让延迟到达的决定覆盖更新后的申请。

### 审批的是哪个版本，也应进入合同

v1 被拒绝后产生 v2，旧页面上的“批准 v1”不应自动批准新草稿。服务端检查业务版本，图节点也检查当前 state revision，不匹配时拒绝使用决定。

版本校验还需覆盖外部变化。即使草稿内容没变，窗口可能已被取消，提交服务仍要确认当前可用性。保存了 v1 预览仅证明当时的草稿，没有冻结排班系统或授权。

## 静态断点与动态中断

`interrupt_before=["tools"]` 在节点边界暂停，适合调试或整体门控。继续这种静态断点通常用同一配置传 `None`。它并没有在节点内部留下一个等待返回业务值的 `interrupt()` 调用。

动态中断有业务 payload，恢复时传 `Command(resume=...)`。需要解释批准对象、动作和版本时，动态方式更合适。两种暂停都依赖保存机制，但客户端恢复协议不能混用。

## 故障恢复与中断的共同基础

故障和人工等待都需要找回既有状态与后续工作。前者通常没有合法业务决定，只能按保存结果重试；后者则还需一个外部恢复值。保存地址、图版本和节点边界决定能否继续。

使用内存 saver，进程结束后待审任务随之消失。生产中跨日审批必须选择持久实现并测试新进程恢复，同时考虑等待期间图升级的兼容性。即使 checkpoint 完整，已失效的工具权限也需要重新验证。

## 一个审批测试应验证什么

可以从可观察状态编写断言：首次暂停有草稿但无回执，`next` 指向 review；拒绝后版本增加且仍无回执；批准当前版本才进入本地发布；第三次拒绝结束为额度耗尽；错误布尔值和过期版本不被接受。

`examples/test_examples.py` 覆盖这些进程内路径以及预算不足、资料缺失的直接结束。它不连接真实数据库或排班服务，不能据此宣称完成了跨进程恢复、并发审批或外部副作用防重测试。

<a id="怎样验证拒绝分支没有偷偷执行发布"></a>

### 拒绝审批后如何确认没有生成提交回执

只检查草稿变了不够，还要断言回执为空、发布计数为零，以及审核意见进入了正确版本。若领域服务被替换为可计数测试桩，拒绝前后计数都应不变，批准后才允许一次逻辑提交。

真实服务还应注入“写入成功但响应丢失”，再用同一业务键查询与重试。重复 HTTP 决定在应用层去重，图状态与外部记录共同核对，才能验证没有重复预留。离线例子只有稳定本地回执，不冒充这项保证。

## 源码入口

- `langgraph/types.py`：核对中断值、恢复命令和中断身份。
- `langgraph/_internal/_scratchpad.py`：追踪重放时如何找到已有恢复信息。
- `langgraph/pregel/_loop.py`：检查本轮暂停和下一轮恢复的推进。
- `langgraph/checkpoint/`：查看保存实现承担的持久性边界。

读中断实现时，要同时查看调用它的节点和 saver 配置；只看一行 `interrupt()` 无法判断副作用是否可重放。
