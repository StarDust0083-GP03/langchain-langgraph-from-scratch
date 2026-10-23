# 检查点与 Store：两种记忆边界

申请 A 等待批准时，系统需要记住待审草稿和下一步任务；申请 B 开始时，系统可能还要读取同一课题组常用的滤镜偏好。前者属于一次流程的恢复，后者属于跨流程的业务数据，不能用一个含糊的“记忆对象”代替。

Checkpointer 与 Store 分别服务这两个范围。它们都可以使用内存或持久实现，但跨 thread 共享和跨进程存活是不同维度。选择接口后，还要决定数据如何确认、更新、检索和删除。

## checkpointer 保存什么

下面的片段假定 `builder` 已定义状态和节点：

```python
from langgraph.checkpoint.memory import InMemorySaver

saver = InMemorySaver()
graph = builder.compile(checkpointer=saver)
address = {"configurable": {"thread_id": "proposal-SIM-OBS-17"}}
paused = graph.invoke({"question": "研究 Halpha 申请", "notes": []}, address)
snapshot = graph.get_state(address)
```

运行时利用 channel 值、版本、任务和元数据等信息描述恢复位置。应用看到的 `StateSnapshot` 可用来检查当前值、待执行节点及相关任务，而不是只找一份聊天文本。

`thread_id` 是寻址的一部分。每次换新 ID 会启动不同实例，所有用户共用一个 ID 则可能混合状态。服务端应先核对申请归属，再映射到 thread，不能把客户端提交的任意 ID 当成访问许可。

## store 保存什么

比如某课题组确认今后的模拟研究默认使用中文、常选 Halpha，可保存为一条版本化偏好：

```text
namespace: ("observatory", "team-cedar", "preferences")
key:       "proposal-defaults"
value:     {"language": "zh", "filter": "Halpha", "confirmed": true}
```

namespace 划分访问和组织范围，key 标识同一条业务记录。新申请会显式查询这项偏好，旧 thread 的待审位置却不能从偏好里恢复。Store 不会自动从聊天中判断哪句话应长期记住，也不会自动把一次临时方案提升为默认值。

写入策略要说明确认来源、覆盖规则和失效条件。偏好被改正时应更新同一业务键，而不是每次追加一条互相冲突的自然语言记忆，再依赖相似度猜哪条最新。

## Runtime 与 context_schema：节点如何访问 store

身份来自可信调用上下文，store 由编译图注入。以下为一个可用于已配置 store 的节点片段，输入字段与节点由应用接入：

```python
from dataclasses import dataclass
from langgraph.runtime import Runtime

@dataclass(frozen=True)
class Context:
    team_id: str

def load_defaults(state, runtime: Runtime[Context]):
    if runtime.store is None:
        raise RuntimeError("preference store is required")
    namespace = ("observatory", runtime.context.team_id, "preferences")
    item = runtime.store.get(namespace, "proposal-defaults")
    return {"defaults": item.value if item else {"language": "zh"}}
```

构建时使用 `StateGraph(State, context_schema=Context)`，编译时传入 `store=store`，调用时传 `context=Context(team_id=trusted_team)`。其中 `trusted_team` 由应用认证得来，不是模型选择的字符串。thread 地址继续放在 config，用于恢复，与业务身份分开校验。

连接、用户身份等通常只在本次运行使用，不宜直接序列化进 state。节点输出 `defaults` 后，是否保存到 checkpoint 取决于状态设计；若希望审批依据固定，应保存本轮读取的偏好版本，而非每次恢复悄悄换成当前值。

### store 自带语义检索

带 embedding 索引的 Store 可以按 query 检索相关值。下面构造一个两维教学 embedding，用来说明接口，不代表真实语义模型或检索质量：

```python
from langgraph.store.memory import InMemoryStore

def teaching_embed(texts):
    return [[1.0, 0.0] if "Halpha" in text else [0.0, 1.0] for text in texts]

store = InMemoryStore(index={"embed": teaching_embed, "dims": 2, "fields": ["text"]})
ns = ("observatory", "team-cedar", "rules")
store.put(ns, "filter", {"text": "Halpha 教学滤镜说明", "revision": "r1"})
store.put(ns, "timing", {"text": "逐帧读出开销", "revision": "r1"})
hits = store.search(ns, query="Halpha", limit=1)
assert hits[0].key == "filter"
```

真实 embedding 需与 `dims` 一致，字段选择决定嵌入哪些内容。单项可设置索引字段或 `index=False`，避免把无需语义召回的值加入索引。相似度只是召回信号，不能证明某条规则仍有效；结果还需核对 namespace、版本和批准状态。

<figure class="concept-diagram" tabindex="0" data-review-figure="lg-storage-scope">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 456" role="img" aria-labelledby="lg-storage-scope-title lg-storage-scope-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="lg-storage-scope-title">执行位置与跨申请偏好分开保存</title>
<desc id="lg-storage-scope-desc">申请节点向Store：按可信组身份读偏好；Store向申请节点：语言 zh 与偏好版本；申请节点向Checkpointer：保存草稿 v1 与待恢复任务；Checkpointer向申请节点：同一 thread 获取恢复状态</desc>
<rect width="960" height="456" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">执行位置与跨申请偏好分开保存</text><path d="M160 128V384" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M480 128V384" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M800 128V384" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M480 164 L800 164" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M793 159 L800 164 L793 169" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="128" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="146" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">按可信组身份读偏好</text><path d="M800 224 L480 224" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M487 219 L480 224 L487 229" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="188" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="206" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">语言 zh 与偏好版本</text><path d="M480 284 L160 284" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M167 279 L160 284 L167 289" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="248" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="266" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">保存草稿 v1 与待恢复任务</text><path d="M160 344 L480 344" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M473 339 L480 344 L473 349" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="308" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="326" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">同一 thread 获取恢复状态</text><rect x="48" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="160" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">Checkpointer</text><rect x="368" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="480" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">申请节点</text><rect x="688" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="800" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">Store</text><path d="M40 400H920" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="40" y="432" font-size="18" fill="var(--muted,#536772)" text-anchor="start">内存实现随进程退出丢失；跨 thread 共享不等于持久化。</text></g>
</svg>
<figcaption>图：内存实现随进程退出丢失；跨 thread 共享不等于持久化。</figcaption>
</figure>

## 选择边界

| 申请助手要回答的问题 | 应查询的位置 | 为什么 |
| --- | --- | --- |
| A 正等谁审阅哪个草稿 | A 的 checkpoint | 执行位置属于实例 |
| B 是否可用组内默认语言 | 可信组 namespace 的 store | 数据跨申请共享 |
| A 的工具参数是什么 | A 的状态或审计记录 | 需要追踪特定执行 |
| 某条规则何时失效 | 版本化业务资料与 store 索引 | 不能只依赖历史对话 |
| 进程重启后还能否继续 A | 持久 saver 与兼容图版本 | 内存内容不足以恢复 |

Store 是外部读写依赖，不与每一步 checkpoint 自动形成统一事务。若节点先写偏好再失败，恢复可能再次写入，需要稳定键与更新规则，不能把每次重试都当成一条新记忆。

### 用换会话和换进程区分两种保存

在进程内，A 的状态保存默认中文，B 不会因此自动获得它；写到组 namespace 并让 B 主动读取后，才实现跨 thread 共享。反过来，即使 B 读到中文偏好，也不知道 A 暂停在 v2 的审批处。

退出进程后，内存 saver 和 store 都消失。验证持久性需要启动一个新进程，通过相同地址重新读取；同一对象第二次调用成功只证明当前进程内的连续性。测试记录应明确这两个条件，避免把内存演示写成灾后恢复证明。

## 一次审批请求的两条时间线

用一份申请和一条偏好记录分别列出事件：

| 时点 | thread `proposal-SIM-OBS-17` | 组偏好 store |
| --- | --- | --- |
| 开始研究 | 保存问题和参数 | 读取默认语言及其版本 |
| 生成 v1 | 保存资料与草稿 | 不因生成而自动更新 |
| 等待审批 | checkpoint 留下待恢复任务 | 其他申请仍可独立查询 |
| 收到拒绝 | 同一 thread 写入意见，生成 v2 | 只有明确业务请求才改偏好 |
| 批准后 | 生成本地回执 | 不保存 Python 执行位置 |

恢复时节点可能重入，审批前读取外部偏好也可能再次发生。若重新读取会改变预览，就需要将研究时采用的版本固定在 state。checkpoint 不会冻结外部世界，store 更新也不会自动使旧批准失效，这些关系需要业务合同定义。

## InMemory 只适合开发

`InMemorySaver` 和 `InMemoryStore` 易于构造和清空，适合隔离测试；进程退出即丢失，也不解决多实例共享。示例选择它们是为了让控制流测试不依赖数据库。

切换到持久实现时，要检查连接初始化、迁移方式、索引与序列化、租户隔离和保留政策。还应定义同一 thread 的并发写入策略，避免两个恢复请求同时推进同一待审版本。数据库能保存数据，不等于业务可以无条件并行恢复。

备份需要覆盖 checkpoint、store 与必要外部对象引用；恢复演练要在新进程验证。包含敏感资料的字段应有加密和访问控制，不能因为只有内部图读取就忽略保存责任。

## 状态为什么会无限增长

每轮完整资料、模型消息和重试记录都追加到 state，会使后续 checkpoint 反复携带更大的累计值。某个节点若返回旧列表加新增项，再经追加 reducer 合并，增长还会被重复放大。

先检查记录是否重复和是否真的需要恢复。原始图像、整份手册与长堆栈通常适合放外部存储，state 留版本化引用；模型只需要摘要时，也不必反复发送原文。随后再决定近期窗口、摘要和 checkpoint 保留范围，最后才评估增量存储优化。

### 压缩状态之前先确定恢复还需要什么

审批等待期间，草稿引用的资料 r1 不能在清理后只剩一个会变化的 URL。可保留来源、revision 和指纹，或在受控存储中留原始版本。否则批准后无法解释当时依据，也无法准确复现计算。

清理当前 state 不一定删除历史 checkpoint，工具闭环和待审批预览也不能随意裁掉。应分别设计模型上下文压缩、当前恢复状态清理和历史数据删除。它们有不同风险，不能用一个“保留最近两条”同时解决。

## 短期记忆管理：裁剪、删除与摘要

上下文窗口有限，短期记忆需要按用途压缩。裁剪通常作用于本次模型输入，删除修改消息状态，摘要则建立一个新的信息表示。三者的持久影响不同，必须说明到底改了哪里。

### 裁剪（trim）

下面为模型调用前的消息准备片段：

```python
from langchain_core.messages.utils import trim_messages, count_tokens_approximately

visible = trim_messages(
    state["messages"],
    token_counter=count_tokens_approximately,
    max_tokens=800,
    strategy="last",
    start_on="human",
    end_on=("human", "tool"),
)
```

`visible` 是本次输入视图，并没有自动删除 state 中的原消息。近似 token 计数适合预算预检，不是 provider 精确计费；还需检查近期工具请求与观察是否完整，以及保留系统规则的策略是否满足应用要求。

### 删除（RemoveMessage）

若要修改当前消息状态，可以返回删除标记。以下为使用 `add_messages` 的节点片段：

```python
from langchain_core.messages import RemoveMessage

def remove_obsolete_summary(state):
    targets = [m.id for m in state["messages"] if m.id == "obsolete-budget-summary"]
    return {"messages": [RemoveMessage(id=message_id) for message_id in targets]}
```

删除按消息身份工作，需要相应 reducer 支持。不要只按列表下标删旧消息而破坏工具轮次。当前删除也不会擦除已有历史检查点，涉及隐私删除请求时，必须继续清理保存层和日志中的副本。

### 摘要（summarize）

摘要可以保存“当前采用规则 r1，6 帧预算 1500 秒，目标高度未核验”，再缩小较早原始消息窗口。应区分已确认事实、临时方案和否定意见，避免把“未验证可见”压成“可见”。

`langmem` 提供 `SummarizationNode`、`RunningSummary` 等相关封装；也可自己增加 `summary` 字段并定义更新。无论哪种方式，都要保存来源与未决项，检查摘要错误如何纠正。摘要改变上下文，若同时删除旧消息也改变恢复状态，但不会改变 checkpointer 的职责或自动清除旧历史。

## time travel 不是修改过去

从某个历史 checkpoint 继续，可以重新研究 8 帧方案并产生新分支。旧的本地回执或真实外部占用并不会因此消失，外部世界不跟随图历史回滚。

调试时应把重放分支与真实提交环境隔离，或者让副作用服务按业务身份防重。比较两条分支可以解释不同参数如何导致 1500 与 1900 秒，却不能把其中一条从图里删去就认为真实资源已释放。

## 一个实用命名策略

让地址可以解释业务，又不将敏感内容直接暴露其中。thread 表示一份工作流实例，checkpoint ID 定位该实例历史点；namespace 从可信组织和领域构造，key 用稳定业务名而非整句问题。

申请重新开启时，是继续原流程还是创建新实例，应有明确规则。草稿 revision 也不要混同于 checkpoint ID：前者是领域版本，后者是运行存储定位，一份草稿可能跨越多个检查点。

### 一个地址正确，还不代表访问被授权

知道 `proposal-SIM-OBS-17` 的人不应自动有权读取或恢复它。服务端需要核对组织、申请归属、可执行动作与当前批准版本，再使用内部地址访问图。

删除组数据时，要覆盖相关 threads、store namespace、资料对象和观测记录。删除当前一项 key 不代表整个用户历史已清空。若业务允许保留脱敏审计，应明确保留字段和期限，避免删除功能只改变界面显示。

## 源码入口

- `langgraph/checkpoint/base/__init__.py`：查看 saver 合同、元数据和地址结构。
- `langgraph/checkpoint/memory/__init__.py`：核对内存实现保存范围。
- `langgraph/store/base/__init__.py`：检查 namespace、item 和搜索接口。
- `langgraph/store/memory/__init__.py`：理解索引配置与过滤行为。
- `langgraph/pregel/_checkpoint.py`：连接运行时保存内容与恢复机制。

先区分“我在查哪个实例”与“我在读哪条业务数据”，再沿对应接口查找，能避免在错误存储里寻找审批或偏好。
