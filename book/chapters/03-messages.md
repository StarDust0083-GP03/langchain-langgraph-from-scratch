# 消息是运行时协议，不是聊天字符串

把消息理解成 `role + content` 只够完成第一次模型调用。工具、流式、多模态、结构化输出和状态恢复都需要更完整的协议。

## 常见消息类型

| 类型 | 发送者 | 关键字段 |
| --- | --- | --- |
| `SystemMessage` | 应用 | 行为约束、稳定背景 |
| `HumanMessage` | 用户 | 文本或多模态输入 |
| `AIMessage` | 模型 | 文本、`tool_calls`、usage、响应元数据 |
| `ToolMessage` | 工具执行层 | `tool_call_id`、结果、可选 artifact |
| `AIMessageChunk` | 流式模型 | 可合并的增量内容与调用参数片段 |

`AIMessage` 是模型响应的标准容器，不代表内容一定是自然语言。一个只包含工具请求的响应，其 `content` 可以为空。

### 同一句文字放进不同消息，会改变含义

“检查数据库迁移”作为 HumanMessage 是用户要求，作为 ToolMessage 是工具返回的观察，作为 AIMessage 则是模型陈述。把它们全拼成没有角色的字符串，模型和执行器就失去了来源边界。消息类型帮助保持协议身份，但它不会认证文字真假，工具读取到的外部文档仍可能不可信。

空 content 的 AIMessage 也不应丢弃。它可能完整携带一个工具请求，删掉它以后只留下 ToolMessage，下一轮就没有对应的请求。处理历史时要看对象字段，而非用“文本为空”判断消息无用。

## 内容块与元数据

不同供应商对图片、音频、推理内容和文件的表示不同。LangChain 消息允许标准内容块，也保留 provider 原生内容。应用代码应优先读取标准字段，只在确实需要某个供应商特性时访问 `additional_kwargs` 或响应元数据。

一个稳妥的边界是：

- 业务逻辑读取标准消息与标准 content block；
- 观测层记录 usage 和 provider metadata；
- 适配层处理供应商特有字段。

这样更换模型时，变化集中在适配层，而不是散落在每个节点里。

## 工具调用必须闭环

一次工具请求包含名称、参数和调用 ID。执行结果必须以 `ToolMessage` 返回，并携带同一个 ID。

```python
from langchain_core.messages import AIMessage, ToolMessage

request = AIMessage(
    content="",
    tool_calls=[{
        "name": "search_notes",
        "args": {"query": "LangGraph persistence"},
        "id": "call-7",
        "type": "tool_call",
    }],
)

result = ToolMessage(
    content="checkpointer is thread-scoped",
    tool_call_id="call-7",
)
```

在支持并行工具调用的模型中，一个 `AIMessage` 后面可能需要多条 `ToolMessage`。遗漏结果、ID 错配或顺序不符合 provider 要求，都会在下一次模型调用时失败。

### 调用 ID 为什么比工具名称更重要

假设同一轮分别搜索“检查点”和“长期记忆”，两次都调用 search_notes。返回文本只标工具名，无法确定哪份对应哪个问题；调用 ID 把每个结果配到具体参数。超时重试时也要保持结果与请求身份清楚，不把旧尝试的结果填给新调用。

删减历史需要以闭环为单位。保留工具请求却删掉结果，或保留结果却删掉请求，都可能违反 provider 的消息合同。摘要可以压缩较早经历，但保留在当前工具交互中的请求和结果应完整配对。

## artifact 不等于 content

工具有时会返回大对象，例如完整文档、二进制引用或调试信息。模型只需要摘要，应用却需要保留原对象。此时可把给模型看的文本放入 `content`，把下游程序使用的数据放入 `artifact`。

这能避免把数 MB 的原始数据反复塞进上下文。需要注意，artifact 仍可能进入状态和 checkpoint，不能因为模型看不到就忽略存储成本。

## 消息 reducer 为什么特殊

普通列表 reducer 常写成 `operator.add`，只会追加。对话消息还需要按 ID 更新、处理删除标记和规范化输入，因此 LangGraph 提供 `add_messages` 与 `MessagesState`。

```python
from langgraph.graph import MessagesState

class State(MessagesState):
    user_id: str
```

节点只返回本次新增或修正的消息，reducer 负责合并。不要每次都返回整段历史，否则可能重复追加，也会让并行写入语义变得含糊。

## 流式 chunk 如何变成最终消息

模型流式返回的通常是 `AIMessageChunk`。工具参数可能被拆成若干字符串片段，只有合并后才是完整 JSON。消费端不应在每个 chunk 上直接执行工具。

```text
chunk 1: name=search, args='{"que'
chunk 2:                args='ry":"la'
chunk 3:                args='nggraph"}'
                    ↓ 合并
AIMessage(tool_calls=[完整调用])
```

框架会处理常见合并，但自定义事件转发层仍要区分“展示增量”和“可执行的最终对象”。

## 上下文不是越长越好

把全部历史消息原样交给模型，会带来费用、延迟和注意力稀释。更合理的状态可以同时保存：

- 最近若干轮原始消息；
- 更早历史的摘要；
- 从 store 检索出的用户偏好；
- 当前任务需要的文档片段；
- 不发给模型但用于审计的运行元数据。

上下文工程的重点是按当前步骤选择信息，而不是让一个 `messages` 列表无限增长。

### 用消息 ID 区分修正与新增

消息 reducer 可以按身份合并修改，普通列表相加则把两份内容都留下。修订草稿如果是替换同一条消息，保留稳定 ID 有助于表达更新；如果是新一轮观察，就应成为新消息。不要把不同经历随意赋成相同 ID，否则正确历史可能被覆盖。

同样，状态里保存了 artifact，不意味着它会发给模型；但事件流或 checkpoint 导出可能仍包含它。设计消息时同时标明模型可见、客户端可见和恢复需要三个范围，避免将“不在 content 中”误读成“不含敏感数据”。

## 源码入口

- `langchain_core/messages/base.py`：消息公共字段与序列化。
- `langchain_core/messages/ai.py`：`AIMessage`、工具调用和 chunk。
- `langchain_core/messages/tool.py`：工具结果。
- `langgraph/graph/message.py`：`add_messages` 与 `MessagesState`。

下一章继续沿着消息中的 `tool_calls`，看它如何变成一次受控执行。
