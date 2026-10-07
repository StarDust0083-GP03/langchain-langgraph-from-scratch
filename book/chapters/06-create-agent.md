# create_agent 到底创建了什么

`create_agent()` 看上去是一行工厂函数，返回值却不是一个神秘 Agent 类，而是 `CompiledStateGraph`。理解这一点后，记忆、中断、流式和子图就都能沿用 LangGraph 的概念。

## 默认图形

最小形状如下：

```text
START
  │
  ▼
model ── 无 tool_calls ──> END
  │
  └──── 有 tool_calls ──> tools ──> model
```

model 节点读取消息并调用聊天模型。tools 节点执行请求并追加 `ToolMessage`。路由函数检查模型输出，决定结束还是继续循环。

源码 docstring 明确描述了这一过程：模型产生工具调用，工具节点执行并回填结果，模型再次运行，直到响应里不再包含工具调用。

## 工厂阶段做了什么

简化后的组装过程是：

1. 字符串模型名通过 `init_chat_model()` 变成模型实例。
2. 字符串 system prompt 变成 `SystemMessage`。
3. Python callable 转成工具，provider 内置工具与普通工具分开处理。
4. response schema 变成 provider strategy 或 tool strategy。
5. 收集中间件声明的工具、状态 schema、上下文 schema 和 hooks。
6. 组合 model call 与 tool call wrapper。
7. 构建 `StateGraph`，添加 model、tools 与中间件节点。
8. 添加条件边和前后 hooks。
9. 带 checkpointer、store、interrupt 配置执行 `compile()`。

这里最值得注意的是，图形会随配置变化。没有工具时可以只有模型节点；中间件可能插入新节点或改变调用包装；结构化输出可能引入额外工具与路由。

### 工厂构建发生一次，模型选择发生多次

调用 create_agent 时，框架把模型、工具、schema 和 hooks 组装为图；每次执行 model 节点，才根据当前消息产生下一步请求。修改一次模型输出不会修改图的基础结构，添加一个运行时工具请求也不会让未注册的 Python 函数突然成为可执行能力。

理解这一区别后，配置问题与决策问题就可以分开。工具未注册，应检查构建；工具已注册而模型没选，应检查描述、上下文与模型；执行被领域服务拒绝，应检查权限，而非一律增加 prompt 强度。

## middleware 的四种作用

### 改模型请求

动态添加 system prompt、裁剪消息、切换模型、选择工具。它回答“这一步给模型看什么”。

### 包模型调用

实现重试、fallback、限额、缓存或审计。wrapper 像洋葱一样组合，顺序会影响行为。

### 包工具调用

统一处理工具错误、重试、审批和 trace。敏感工具仍需自己的领域授权。

### 在循环前后执行

某些 middleware 声明 before/after model 或 before/after agent hooks。它们可能成为图节点，因此也会影响状态和恢复边界。

### wrapper 的顺序会改变你观察到什么

设外层是审计、内层是重试。审计可能记录一次调用以及最终结果，内层实际尝试多次；把重试放外层，审计则可能每次都记录。缓存的位置也会决定命中时是否经过后续检查。中间件列表相同，组合顺序不同，行为就可能不同。

对安全策略，不能让缓存短路掉最终授权；对成本指标，应分别记逻辑调用与真实尝试。wrapper 提供组合能力，不替你选择正确顺序，应通过超时、命中和拒绝三个案例验证。

## context、state 与 store

这三个对象经常被混在一起：

| 容器 | 生命周期 | 例子 |
| --- | --- | --- |
| State | 随图步骤变化，可 checkpoint | messages、当前计划、草稿 |
| Runtime context | 单次 run 注入，通常视为只读 | user ID、DB 连接、环境配置 |
| Store | 跨 thread 持久化 | 用户偏好、长期事实、共享知识 |

`context_schema` 描述运行时上下文。旧的 `config_schema` 在当前 StateGraph 源码中已标为 deprecated。新代码应避免继续围绕旧名字设计。

## 结构化输出的选择

传入 `response_format=MySchema` 时，工厂保留“自动选择”意图。支持原生结构化输出的模型可走 ProviderStrategy，否则可用 ToolStrategy。显式指定策略时，应用承担兼容性判断。

最终对象通常写入 Agent state 的 `structured_response`。它不是自动替代消息历史，调用方要读取正确字段。

## 高级工厂并没有消除图

下面的能力仍使用 LangGraph 语义：

```python
agent = create_agent(
    model=model,
    tools=tools,
    checkpointer=checkpointer,
    store=store,
    interrupt_before=["tools"],
)
```

- `thread_id` 仍决定 checkpoint 线程；
- interrupt 后仍通过 `Command(resume=...)` 恢复；
- stream mode 仍决定看到 messages、updates 还是 events；
- Agent 仍能作为节点嵌入更大的 StateGraph。

工厂只是提供了常用图形，不是另一套运行时。

## 何时离开 `create_agent`

出现以下需求时，直接构建 StateGraph 往往更清楚：

- 工具循环之外还有确定性的审核、结算或补偿步骤；
- 多个节点要并行，随后聚合；
- 不同失败类型走不同恢复路径；
- 模型不是每一轮的中心；
- 需要明确展示和测试业务状态机。

也可以把 `create_agent` 返回的图作为一个子图节点，而不是重写它的工具循环。

### 结构化结果应该从正确字段读取

模型最终自然语言可以说“已通过”，但业务应读取经过 schema 校验的 structured_response，再核对实际材料。结构正确只保证字段满足类型，不保证结论真实；缺证据时仍要允许未知或拒答，而不是强迫模型填一个审批值。

若业务要求检索、独立核验和审批按明确顺序发生，可以离开标准循环建自定义图。仅仅希望回答用 JSON，通常还不需要重写运行时；先确定需求改变的是输出合同还是控制流。

## 源码入口

- `langchain/agents/factory.py`：工厂和图组装。
- `langchain/agents/middleware/types.py`：hook 与 schema 合同。
- `langchain/agents/structured_output.py`：输出策略。
- `langgraph/prebuilt/tool_node.py`：标准工具执行。
