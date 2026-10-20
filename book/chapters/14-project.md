# 完整案例：观测申请的证据与审批

本章将天文台观测申请组织成一个可运行的研究与审批流程。它读取两条教学资料，计算预算，生成待审草稿，拒绝后修订，批准后生成本地回执。模型行为全部由确定性代码代替，LangGraph 的状态、检查点和中断则是真实 API。

完整入口仍为 `examples/research_assistant.py`，离线测试在 `examples/test_examples.py`。示例不占用真实望远镜资源，也不根据天文坐标判断可见性。

## 需求

默认输入研究 Halpha 申请，采用 6 帧、每帧 180 秒、1800 秒窗口。教学规则 `SIM-TIME-4@r1` 给出读出 20 秒和校准 300 秒，结果为 1500 秒。另一个来源 `SIM-FILTER-2@r1` 记录需要核对真实滤镜配置。

图要区分四种结束：获批后本地发布、无资料、预算超限、三版均被拒绝。审批前回执必须为空，拒绝修订不得重复检索材料。状态的关键部分如下，其余可选字段见完整文件：

```python
from operator import add
from typing import Annotated, TypedDict

class Finding(TypedDict):
    source: str
    revision: str
    text: str

class ResearchState(TypedDict, total=False):
    question: str
    proposal_id: str
    notes: Annotated[list[Finding], add]
    draft: str
    total_s: int
    revision: int
    approved: bool
    receipt: str
    status: str
```

`total=False` 允许最初只提供少数字段，并不自动补默认值。`plan()` 校验参数后写入默认值，后续节点才能读取。`notes` 累计新增资料，当前草稿与修订号则覆盖更新。

## 图形

用状态转换表列出每条有业务含义的出口：

| 当前节点 | 条件或结果 | 后继 |
| --- | --- | --- |
| plan | 参数校验完成并选择研究项 | search |
| search | 返回版本化资料记录 | draft |
| draft | 有证据且 1500 不超过 1800 | review |
| draft | 无证据或预算超限 | cancel，再结束 |
| review | 严格布尔批准，版本匹配 | publish，再结束 |
| review | 拒绝且 revision 小于 3 | revise，再回 review |
| review | 第三版仍被拒绝 | cancel，再结束 |

`review` 使用 `Command`，因此没有通往 publish 的无条件固定边。若误加这条边，拒绝也可能调度发布，测试必须检查这项负面行为。

## 为什么计划和检索分开

计划节点选择 `filter` 与 `timing` 两个研究项，检索节点只按这些项读取 fixture。尽管代码很短，它们代表不同合同：计划决定研究范围，检索提供实际观察。换成模型或远程资料库后，两者会有不同的错误与重试政策。

本例只在问题包含 Halpha 时生成研究项，未知问题得到空计划，不使用万能默认资料。这样无命中分支可直接验证，也不会把与问题无关的内容包装成研究成功。

### 沿一份草稿跟踪状态怎样变化

输入只有 `question` 和空 `notes`。plan 写默认申请号、帧数、曝光、窗口、revision=1 和空回执；search 新增两条资料；draft 写 total_s=1500、草稿与 awaiting_review。

审阅节点首次中断，尚未写 approved=True。拒绝 v1 后，意见写入状态，revise 把 revision 变为 2，并在草稿中增加具体意见和待核验条件，notes 仍为两条。批准 v2 后，publish 生成 `local:SIM-OBS-17:v2`。这是稳定的本地结果标识，不是数据库幂等实现或远程申请确认。

## 首次运行

下面可在项目根目录和已安装 LangGraph 的解释器中运行：

```python
from examples.research_assistant import build_graph

graph = build_graph()
config = {"configurable": {"thread_id": "proposal-walkthrough"}}
paused = graph.invoke({"question": "研究 Halpha 申请", "notes": []}, config)
assert paused["total_s"] == 1500
assert paused["receipt"] == ""
assert paused["__interrupt__"]
assert graph.get_state(config).next == ("review",)
```

`next` 表示待恢复工作，不能据此断言 review 从未执行。它已经到达中断位置，恢复会重入节点。计算与草稿放在前序节点，有助于保持审批预览稳定。

## 恢复审批

沿用前面的 graph 和 config，先拒绝再批准：

```python
from langgraph.types import Command

revised = graph.invoke(Command(resume={
    "approved": False, "revision": 1,
    "feedback": "说明未核验真实目标高度。",
}), config)
assert revised["revision"] == 2
assert revised["receipt"] == ""
finished = graph.invoke(Command(resume={"approved": True, "revision": 2}), config)
assert finished["receipt"] == "local:SIM-OBS-17:v2"
assert graph.get_state(config).next == ()
```

申请地址不能更换，revision 必须对应当前草稿。示例还拒绝 `approved="false"` 这种字符串，防止 Python 真值转换误判。完整授权不在例子内，真实 API 应先验证审阅者资格，再调用图。

### 拒绝并不意味着从头重跑

普通文字修订只需处理当前草稿和意见，已确认规则不必再查。示例返回 review 时，检索计划和两条 notes 保持不变，测试断言材料数量仍为 2。

如果意见指出规则错误，真实产品应增加重新研究分支，而非仅附加说明。图的合同应区分“表达修改”和“证据失效”；本例只演示前者，修订不意味着已经修正任何真实观测可行性问题。

## 替换成真实模型

可以先替换 draft，保持它只返回 `draft` 等约定字段。以下是应用接口伪代码，不是可直接运行的 provider 示例：

```python
def model_draft(state):
    request = compose_research_request(
        question=state["question"], findings=state["notes"],
        computed_total_s=state["total_s"],
    )
    response = configured_model.invoke(request)
    return {"draft": extract_text(response)}
```

数值预算继续由确定性代码计算，不让模型随意改公式；模型补充解释和未核验项。接入后做输出 schema、引用完整性和 provider 合同测试，不能只检查文字流畅。

## 替换成真实检索

真实资料结果至少包含稳定来源、revision 和文本，必要时再有 URI、内容指纹和召回分数。图应保留足以复核审批依据的字段，不能只返回“找到了相关文档”。

召回分数用于排序，不等于规则真实或适用。检索服务要按可信组身份授权，明确空结果、权限拒绝与超时；原文过大时保留受控外部引用，并固定版本，避免审批等待期间 URI 指向另一份内容。

## 从内存切到生产存储

当前 `build_graph()` 每次创建新 `InMemorySaver`，因此新对象看不到旧实例，进程退出也无法恢复。切换持久 saver 需要调整构造与连接生命周期，而不只是更换一个导入名。

应测试初始化和迁移、连接池、序列化、同 thread 并发策略、数据保留以及旧图版本恢复。真实发布还需要独立业务记录和幂等服务，本地 `receipt` 字段不能代替跨系统事务。

### 接上真实依赖后，先保持图的合同不变

一次只替换一个边界：模型仍产出受限草稿，检索仍返回版本化 findings，审批仍提交严格布尔值和 revision。保留原离线回归，有助于区分控制流回退和外部能力差异。

持久性验证必须跨进程：进程 A 跑到 review 后退出，进程 B 用同一保存地址和兼容图继续。外部提交则注入响应丢失，确认重试读取原回执。完成这些之前，只能说接入了依赖，不能说恢复和副作用已可靠。

## 测试分层

### 节点测试

直接检查 plan 的默认值与拒绝输入，search 的来源记录，draft 的 1500 秒计算，以及 publish 在未批准时抛错。这些断言固定领域含义，不需要驱动整张图。

### 图测试

使用内存 saver 检查首次暂停、拒绝后 v2、批准后结束、thread 隔离、三次拒绝上限、无资料和超预算直接退出。错误批准值与过期 revision 必须不产生回执。

### 集成测试

接真实资料库、模型和持久 saver 后，分别核对权限、消息协议、序列化与进程恢复。真实模型测试应限制请求和费用，并评估来源与未决项，不能用它替代确定性路由回归。

## 运行

在具备 LangGraph 依赖的环境中保留原 CLI，并运行新增测试入口：

```bash
python examples/research_assistant.py
python examples/test_examples.py
```

第一个命令演示拒绝 v1 后批准 v2，打印草稿和本地回执；第二个使用标准库 unittest 运行离线断言。若使用项目虚拟环境，可将 `python` 改为 `.venv/bin/python`。安装依赖不属于离线测试本身，准备好环境后，这两个入口不访问远程模型或天文台服务。
