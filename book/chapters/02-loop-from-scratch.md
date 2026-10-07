# 不用框架，先写出 Agent 循环

最小 Agent 只有四个动作：把消息交给模型、检查工具请求、执行工具、把结果塞回消息。循环直到模型不再请求工具，或达到步数上限。

```python
messages = [{"role": "user", "content": question}]

for _ in range(max_steps):
    reply = model(messages, tool_schemas)
    messages.append(reply)

    if not reply.get("tool_calls"):
        return messages

    for call in reply["tool_calls"]:
        result = execute(call["name"], call["arguments"])
        messages.append({
            "role": "tool",
            "tool_call_id": call["id"],
            "content": result,
        })

raise RuntimeError("step limit exceeded")
```

这段代码已经包含 `create_agent` 的核心形状：`model -> tools -> model`。框架增加的是 schema 转换、并发、错误处理、中间件、持久化、事件和 provider 兼容。

## 一次调用的完整轨迹

用户问：“LangChain 与 LangGraph 分别做什么？”

```text
[1] user
    content = 问题

[2] assistant
    tool_calls = [{id: call-1, name: search_notes,
                   arguments: {query: 问题}}]

[3] tool
    tool_call_id = call-1
    content = 本地检索结果

[4] assistant
    content = 根据检索结果生成的回答
```

`tool_call_id` 不是装饰。模型可能在一次响应里并行请求多个工具，返回结果必须和请求一一对应。只按工具名匹配会在重复调用同一工具时失去关联。

### 模型为什么还要再读一次工具结果

第一次响应的工具请求表示“需要材料”，并非已经回答。执行器把资料变成工具消息后，模型才有这次观察可用。如果应用调用了工具，却没有把结果送入下一轮，模型无法凭外部函数已经运行而自动知道内容。消息列表就是循环的交接记录，每一轮都要保持请求与结果完整。

一次模型响应也可能提出两个工具调用。两份结果都要回填，不能收到第一份就误判全部完成。结果抵达顺序可以不同，但各自调用 ID 必须准确；这个身份关系比结果文本中的工具名字更可靠。

## 工具 schema 是合同

模型看到的不是 Python 函数本身，而是描述：

```json
{
  "name": "search_notes",
  "description": "Search the local notes",
  "parameters": {
    "query": {"type": "string"}
  }
}
```

函数签名决定参数结构，docstring 或 description 决定模型何时选择它。描述太泛会导致误调用，参数过多会增加填错概率。工具设计的第一原则不是“能做多少”，而是“输入和副作用是否清楚”。

## 错误也是下一轮输入

工具抛异常时有三种常见策略：

1. 终止整个 run，适合不可恢复的系统错误。
2. 把错误转成 `ToolMessage`，让模型修正参数或换工具。
3. 在执行层自动重试，适合限流和瞬时网络错误。

不要把所有异常都交给模型。认证失败、权限拒绝和数据损坏不是换个措辞就能解决的问题。自动重试也必须有上限，否则 Agent 只是更昂贵的死循环。

### 哪些错误应该让模型改计划

“没有找到资料”是合法搜索结果，可以促使模型换查询；“数据库连接超时”是执行故障，适合有限重试或明确降级。若把两者都包装成空字符串，下一轮可能编造答案，或者不断换关键词试图修复网络。错误消息应给足行动依据，但不要暴露凭据、内部地址或完整异常堆栈。

业务拒绝还应有稳定含义，比如未经授权的路径不能读取。模型可以解释拒绝，不能通过换个同义参数绕过它。循环灵活性只作用于允许的行动空间。

## 步数上限是安全边界

模型可能不断调用同一工具，两个 Agent 也可能互相转交。任何循环都应有停止条件：

- 模型返回无工具调用的最终消息；
- 达到最大步数或时间预算；
- 达到 token 或费用预算；
- 命中人工中断；
- 业务状态表明任务已经结束。

LangGraph 的 recursion limit 负责图步数边界，但业务预算仍应单独记录。一次图步不一定等于一次模型调用。

## 副作用应在哪里发生

“模型请求发送邮件”和“邮件已经发送”是两个事件。前者只是消息，后者是外部副作用。执行层应在调用前完成参数校验、权限检查和必要审批，再记录结果。

```text
模型生成 tool_call
        │
        ▼
参数校验 -> 权限策略 -> 人工审批 -> 幂等键检查 -> 真正执行
        │
        ▼
ToolMessage 回填结果
```

如果把权限判断写在系统提示里，模型仍可能产生危险调用。提示是行为引导，不是授权系统。

## 离线运行本章示例

```bash
python3 examples/mini_agent.py
```

示例用确定性的 `scripted_model()` 代替远程模型，因此验证的是控制流，而不是模型质量。自检会确认角色序列为 `user -> assistant -> tool -> assistant`。

### 停止条件要与任务进展一起看

没有工具请求通常表示模型准备回答，并不证明资料充足。应用还可要求回答带来源，资料不足时明确说明。步骤上限则处理模型一直循环的最坏情况；它不应替代当前检索是否产生新证据、费用是否超限等业务判断。

跟做离线示例时，记下每轮新增消息和调用次数。重复搜索完全相同内容却没有新证据，是计划停滞；不同工具逐步补齐材料，则可能是合理长流程。两者都很长，处理方法却不同。

## 与框架的对应关系

| 手写循环 | LangChain / LangGraph |
| --- | --- |
| `model(...)` | `BaseChatModel.invoke()` |
| `tool_schemas` | `BaseTool` 与 provider schema 转换 |
| `execute(...)` | `ToolNode` |
| `messages.append(...)` | `add_messages` reducer |
| `for max_steps` | 图循环与 recursion limit |
| 错误包装 | middleware、retry policy、tool error handler |
| 进程内列表 | checkpointer 保存的 thread state |

后面所有高级能力都没有改变这条主线，只是在每个边界上补上工程约束。
