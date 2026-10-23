# 不用框架，先写出 Agent 循环

先把天文台助手缩到两个能力：查教学规则、估算拍摄时长。模型只决定请求什么，Python 执行器真正调用函数，再把观察交回模型。即便模型由固定脚本代替，请求、执行和回填三者也不能省略。

下面是控制结构的伪代码，不是某个 provider 的请求格式：

```python
history = [user_question]
remaining = 4
while remaining > 0:
    remaining -= 1
    proposal = model(history, exposed_tools)
    history.append(proposal)
    if not proposal.calls:
        break
    observations = [dispatch(call) for call in proposal.calls]
    history.extend(observations)
else:
    raise RuntimeError("model turn budget exhausted")
```

一次模型响应里可以有多个调用，所以预算扣的是模型轮次，不是工具数。先把该轮所有观察补齐，再进入下一轮，能避免模型在缺了一半结果时做结论。

## 一次调用的完整轨迹

固定输入为“研究 Halpha 观测申请：6 帧，每帧 180 秒”。示例的脚本模型产生资料查询和预算计算两个请求，执行器依次处理它们。

| 位置 | 消息身份 | 可检查的内容 |
| --- | --- | --- |
| 0 | user | 用户问题与固定教学场景 |
| 1 | assistant | `obs-rule` 请求 `search_notes`，`obs-time` 请求 `estimate_time` |
| 2 | tool | `obs-rule` 对应 `SIM-FILTER-2` 与 `SIM-TIME-4` |
| 3 | tool | `obs-time` 对应总时长 1500 秒及计算式 |
| 4 | assistant | 用资料编号说明预算，同时声明未提交真实申请 |

执行器检查调用名称属于注册集合，并保留每个请求的 ID。工具消息即使调换到达顺序，也能靠 ID 还原关系；不过实际 provider 对消息排列的额外要求仍需适配层满足。

### 模型为什么还要再读一次工具结果

第一次响应没有计算结果，只表达需要规则和预算。如果工具在 Python 中算出 1500，却只打印到终端而不回填消息，下一次模型调用依然没有这项观察。外部函数执行成功不会自动改变模型上下文。

完整结果还应包括适用范围。这里的 1500 只覆盖曝光、读出和校准，不涵盖真实排班。模型读到这条限制，才能把结论写成模拟预算建议。如果两项工具只返回其中一个，最终消息应该等待或报告缺失，不能用另一项代替。

<figure class="concept-diagram" tabindex="0" data-review-figure="lg-message-pair">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 576" role="img" aria-labelledby="lg-message-pair-title lg-message-pair-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="lg-message-pair-title">两个请求，各有一项对应观察</title>
<desc id="lg-message-pair-desc">执行器向脚本模型：输入：6 帧，每帧 180 秒；脚本模型向执行器：obs-rule 与 obs-time；执行器向教学工具：search_notes / estimate_time；教学工具向执行器：两项结果，原调用 ID 不变；执行器向脚本模型：回填资料与 total_s=1500；脚本模型向执行器：说明预算与未提交边界</desc>
<rect width="960" height="576" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">两个请求，各有一项对应观察</text><path d="M160 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M480 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M800 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M480 164 L160 164" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M167 159 L160 164 L167 169" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="128" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="146" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">输入：6 帧，每帧 180 秒</text><path d="M160 224 L480 224" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M473 219 L480 224 L473 229" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="188" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="206" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">obs-rule 与 obs-time</text><path d="M480 284 L800 284" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M793 279 L800 284 L793 289" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="248" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="266" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">search_notes / estimate_time</text><path d="M800 344 L480 344" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M487 339 L480 344 L487 349" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="308" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="326" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">两项结果，原调用 ID 不变</text><path d="M480 404 L160 404" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M167 399 L160 404 L167 409" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="368" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="386" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">回填资料与 total_s=1500</text><path d="M160 464 L480 464" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M473 459 L480 464 L473 469" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="428" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="446" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">说明预算与未提交边界</text><rect x="48" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="160" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">脚本模型</text><rect x="368" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="480" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">执行器</text><rect x="688" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="800" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">教学工具</text><path d="M40 520H920" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="40" y="552" font-size="18" fill="var(--muted,#536772)" text-anchor="start">脚本代替模型；一次模型响应可请求多个工具。</text></g>
</svg>
<figcaption>图：脚本代替模型；一次模型响应可请求多个工具。</figcaption>
</figure>

## 工具 schema 是合同

预算函数的 schema 可以把数值范围直接告诉模型。以下为示例中的工具定义形状，不是远程请求的完整外壳：

```json
{
  "name": "estimate_time",
  "description": "估算教学申请时长，不查询真实排班",
  "parameters": {
    "type": "object",
    "properties": {
      "frames": {"type": "integer", "minimum": 1, "maximum": 30},
      "exposure_s": {"type": "integer", "minimum": 1, "maximum": 600}
    },
    "required": ["frames", "exposure_s"],
    "additionalProperties": false
  }
}
```

描述限定用途，schema 限定结构，执行函数再次校验范围。手写例子没有引入 JSON Schema 校验器，参数的最终保障来自 `estimate_time()` 中的显式判断。Python 的 `bool` 是 `int` 子类，因此函数用 `type(value) is int` 排除 `True` 被当作一帧，避免演示程序在边界输入上悄悄通过。

## 错误也是下一轮输入

模型请求了不存在的工具时，执行器返回 `unknown_tool`；帧数为负数时返回 `invalid_arguments`。这些是可理解的观察，模型可以停止或调整方案。错误结果仍要带原调用 ID，不能因为执行失败就跳过回填。

依赖故障则不应全转成“参数不对”。示例只捕获 `TypeError` 和 `ValueError`，意外运行故障会传播出去，方便测试暴露真实问题。接入远程服务后，应另行定义有限重试、失败分类与脱敏信息，而不是用一个宽泛 `except Exception` 把所有故障写进聊天记录。

### 哪些错误应该让模型改计划

资料查询返回 `no_match`，意味着当前允许搜索的语料没有命中。示例最后会说明证据不足，即使时长算得出来也停止建议。它没有偷偷退回一份默认资料，让未知问题看起来已研究完成。

若真实资料服务超时，应用尚未得到可解释的检索结果。此时应该按依赖故障处理，而不是诱导模型换同义词查询。权限拒绝也不能靠改写 query 绕过，重试策略要保留原授权主体和允许范围。错误文字只提供行动依据，不应泄露连接信息或内部堆栈。

## 步数上限是安全边界

例子默认允许四次模型响应，正常轨迹只用两次。若把上限改为 1，工具可以已经返回，但模型还没得到最后一次组织答案的机会，函数会抛出预算耗尽异常。应用应把这种结果显示为未完成，而非截取最后一条工具文本充当最终答案。

实际程序还需要墙钟截止时间、工具调用额度和费用预算。模型轮次、工具数与图 super-step 是不同计数器：一轮可以请求多个工具，一次模型工具循环也会跨多个图步骤。为每个预算标明计数口径，告警才不会把合理并行误认成失控。

## 副作用应在哪里发生

本章工具都是只读或纯计算，不会占用观测窗口。若以后增加 `submit_proposal`，执行器要在调用领域服务前检查申请版本、批准人和业务幂等身份。

| 执行阶段 | 收到的对象 | 可以作出的判断 |
| --- | --- | --- |
| 解析请求 | 工具名、参数、调用 ID | 是否是完整、已注册的调用 |
| 领域校验 | 申请编号、当前版本、服务端身份 | 该主体是否可提交该版本 |
| 副作用提交 | 稳定业务键 | 重试时返回原结果还是新建 |
| 结果回填 | 回执或明确失败 | 下一轮模型可据此解释什么 |

工具调用 ID 标识一次模型请求，业务键标识一次申请动作，两者不必相同。模型重新规划可能生成新 ID，但同一批准版本不能因此占用两次时段。系统提示中的“不要重复提交”无法提供这项保证。

## 离线运行本章示例

保留原命令入口：

```bash
python3 examples/mini_agent.py
```

程序先运行内置断言，再打印 JSON 轨迹。正常角色序列是 `user、assistant、tool、tool、assistant`，其中两项工具观察分别包含资料记录和 `total_s=1500`。所有输入资料和模型响应都在本地构造，不需要密钥，也没有验证语言模型的推理能力。

### 停止条件要与任务进展一起看

“没有工具调用”只意味着脚本或模型给出终止响应。资料是否够用，要从结果状态判断。未知问题应返回缺证据说明；已命中规则的申请才能给模拟时长建议。把这两条路径都跑一遍，比只检查正常答案更能发现默认回退掩盖缺失的问题。

若模型反复查询同一资料，比较本轮新增的来源和已尝试参数。没有新证据且预算下降，适合停止并请求澄清；补到了不同版本规则，可能有继续研究的必要。上限负责兜底，进展检查决定是否值得花掉下一轮。

## 与框架的对应关系

| 手写例子的责任 | 框架中的相应位置 | 不应遗漏的应用责任 |
| --- | --- | --- |
| `scripted_model` | 聊天模型 `invoke` | provider 能力核验 |
| `Tool.schema` | 工具 schema 转换 | 描述与范围准确 |
| `execute` | `ToolNode` 或工具 wrapper | 授权与副作用政策 |
| 本地消息列表 | 消息状态与 `add_messages` | 历史清理不破坏调用闭环 |
| 模型轮次计数 | 图循环与步数限制 | 独立费用和时间预算 |
| 观察中的失败状态 | 工具错误处理 | 业务空结果与依赖故障区分 |
| 当前进程保存 | Checkpointer | 选择持久实现并保护 thread 归属 |

迁移时可以逐个替换这些责任，保留同一批离线断言。不要在换入框架时顺便把所有权限判断移进 prompt，否则控制循环更完善了，执行边界却变弱了。
