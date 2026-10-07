# 端到端：本地研究助手

本章把前面的概念装进一个不依赖远程模型的工作流。目标不是展示生成质量，而是验证状态、路由、checkpoint 和 interrupt 的真实行为。

完整代码位于 `examples/research_assistant.py`。

## 需求

输入一个问题，系统完成：

1. 从问题生成检索计划；
2. 查询本地小型语料；
3. 生成草稿；
4. 暂停并等待人工审阅；
5. 通过则发布，拒绝则修订后再次审阅。

状态如下：

```python
class ResearchState(TypedDict):
    question: str
    plan: list[str]
    notes: Annotated[list[str], operator.add]
    draft: str
    approved: bool
```

`notes` 使用追加 reducer，其余字段使用默认覆盖。`question` 在输入后保持稳定，`draft` 可被修订节点覆盖。

## 图形

```text
START -> plan -> search -> draft -> review(interrupt)
                                      │
                         approve ─────┴──── reject
                            │                  │
                            ▼                  ▼
                         publish            revise
                            │                  │
                            ▼                  └──> review
                           END
```

review 返回 `Command`，同时写入 `approved` 并选择下一节点。这比在外部再写一个条件函数更贴近“审阅决定就是本节点结果”的业务含义。

## 为什么计划和检索分开

当前离线实现很短，合并成一个函数也能工作。仍然拆开，是因为它们有不同的工程边界：

- plan 可由模型生成，需要结构化输出与预算；
- search 访问资料系统，需要超时、权限和引用；
- 两者的重试策略不同；
- 调试时要判断是计划错了还是检索没命中。

节点不是按代码行数拆，而是按恢复、观测和失败语义拆。

### 沿一份草稿跟踪状态怎样变化

输入时只有问题；plan 写检索意图，search 为 notes 增加材料，draft 根据它们生成正文。review 不负责重新检索，它把当前草稿交给人决定。批准后进入 publish；示例中的这个节点不实际对外发布。拒绝后 revise 覆盖草稿，再回到 review。

notes 是累计字段，draft 是当前视图，所以同样一次更新使用不同 reducer。若 revise 又追加全部旧 notes，材料会重复；若 draft 也累计，发布端就难以确认哪份是当前版本。状态设计直接影响最后的业务结果。

## 首次运行

```python
config = {"configurable": {"thread_id": "demo-thread"}}
paused = graph.invoke(
    {"question": "LangChain 和 LangGraph 如何分工？", "notes": []},
    config,
)
```

执行到 review 时，`interrupt()` 让图暂停。此时草稿已经进入 checkpoint，但 publish 没有运行。

```python
snapshot = graph.get_state(config)
assert snapshot.next == ("review",)
```

这里 `next` 表示待恢复任务，不是“review 从未开始”。节点在恢复时可能重放，所有 interrupt 前的代码都应满足重放安全。

## 恢复审批

```python
finished = graph.invoke(
    Command(resume={"approved": True}),
    config,
)

assert finished["approved"] is True
assert graph.get_state(config).next == ()
```

必须使用同一个 `thread_id`，否则运行时找不到原暂停点，只会把它当作另一条 thread。

### 拒绝并不意味着从头重跑

恢复拒绝决定后，已有计划和材料仍在状态中，流程可进入修订，而非重新执行整套研究。若审阅意见指出材料错误，才应选择重检索的路径。这个示例主要验证审批控制流，真实产品还需把意见和版本作为状态保存。

同一个 thread 代表同一流程实例，不意味着任何请求都能提交 resume。API 应验证审阅者和对象版本，再构造 Command。图负责暂停位置，应用负责批准资格。

## 替换成真实模型

把 plan 与 draft 替换为模型节点时，保持状态合同不变：

```python
def draft(state: ResearchState) -> dict:
    prompt = build_prompt(state["question"], state["notes"])
    response = model.invoke(prompt)
    return {"draft": response.content}
```

不要让模型节点顺便写 store、发送通知和决定权限。纯生成步骤更容易重试，也更容易用 fake model 测试。

## 替换成真实检索

真实 search 节点应返回带来源的记录，而不是裸字符串：

```python
class Finding(TypedDict):
    text: str
    uri: str
    revision: str | None
    score: float | None
```

最终草稿引用 URI，审批 UI 才能回到证据。embedding 相似度是排序信号，不是事实置信度。

## 从内存切到生产存储

示例使用 `InMemorySaver`，仅验证当前进程。生产替换 checkpointer 时，图代码可以保持不变，但需要额外验证：

- saver 的 `setup()` 或 migration；
- 多实例并发和连接池；
- thread ID 长度与索引；
- 数据加密与保留策略；
- 旧 checkpoint 在新图版本下是否可恢复。

### 接上真实依赖后，先保持图的合同不变

模型计划仍应输出受限检索条目，检索器仍返回带引用的材料，草稿节点仍写同一字段。先固定这些合同，再替换底层实现，便能区分模型表达变化与图逻辑错误。工具超时、空结果和资料拒绝分别返回明确状态。

换持久 saver 后，应在暂停点退出进程，再用原 thread 恢复。只在同一 Python 对象上跑批准分支，无法验证数据库连接、序列化和升级兼容。将空的 publish 节点换成真实发布后，还要用业务幂等身份保护，而非相信示例只调用一次。

## 测试分层

### 节点测试

直接调用 plan、search、draft，输入固定 state，断言 partial update。

### 图测试

使用内存 saver，断言暂停点、状态合并、approve/reject 路由和最终输出。

### 集成测试

接真实模型或检索服务，但保留调用次数和费用上限。不要把所有单元测试都变成在线模型评测。

## 运行

项目验证脚本会创建本地虚拟环境并安装浅克隆源码。也可以在已安装 LangGraph 的环境里直接执行：

```bash
python examples/research_assistant.py
```

它会完成一次暂停和恢复，并打印最终草稿。拒绝分支可把 resume 值改为 `{"approved": False}` 观察再次暂停。
