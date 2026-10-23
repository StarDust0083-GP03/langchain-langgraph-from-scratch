# 多 Agent 与 MCP：协作模式与工具互联

研究助手可能需要仪器专家、归档检索和远程资料服务。前两个是工作怎样分配，后一个是工具怎样连接，它们不应混成同一种架构选择。多 Agent 模式组织控制与上下文，MCP 标准化客户端和工具服务之间的协议。

本章继续使用观测申请，分别检查协作和连接的边界。无论封装多少层，人工批准、最终授权和外部副作用仍需有明确归属。

## 多 Agent 官方模式

官方文档介绍 handoff、router、subagents、skills 等模式，也允许混合自定义流程。选择时先描述控制权是否转移、任务是否独立、知识是否只需按需加载，再对应封装。

### Handoff

资料研究结束后，把当前处理阶段交给值班审核角色。转移记录应包含申请身份、草稿 revision、必要摘要和允许动作，下一条交互才能由正确处理者响应。

这不同于主助手临时调用一个专家。交接后谁接收用户输入、失败时回到哪里、是否允许原角色继续修改，都要在状态中明确。仅输出“请联系值班员”不会改变程序控制权。

### Router

路由器将“滤镜配置”交给仪器研究，“既往观测记录”交给归档研究，无法分类时进入澄清。输出使用受限类别，保留未知路径，比让字符串任意匹配节点名更可靠。

混合问题可以拆成多个任务，不必强制只能选一位专家。路由测试要包含模糊和不支持的问题，避免未知内容因关键词碰巧匹配而被错误处理。

### Subagents

主助手保留控制，只委托“核验规则 r1 的开销项”等窄任务。子 Agent 返回引用、限制和完成状态，主助手据此继续计算与审批。

委托合同要说明何时结束以及失败如何返回。若子 Agent 无法访问来源，不能生成一个看似正常的结论来满足格式；主层应能区分缺证据和服务故障。

### Skills

重复的研究流程可写成技能元数据和正文，需要时加载，不需要每次把全部仪器手册放进 prompt。技能共享的是知识或步骤，不必新增一个持续对话的角色。

共享也带来版本责任。同一流程更新了开销规则，旧申请仍应保留原研究依据。技能加载改变上下文，不应悄悄修改批准状态或获得新增权限。

### Custom workflow

固定预算节点、仪器子 Agent、归档子图和人工 review 可以组合在同一状态图中。业务确定的顺序由图表达，模型负责适合它的研究与解释。

这种方式适合“不满足预算就不能申请”的约束。无需让多个角色协商一个代码可以直接判断的不等式，也不必为保持纯 Agent 风格隐藏确定性节点。

## 多 Agent 的记忆边界不变

委托内部观察保存在子任务范围，父图只接收需要长期保留的结果，待恢复位置由 checkpointer 保存，跨申请偏好或规则索引用 store。角色数量增加不改变这些职责。

应固定共享数据的权威来源。若每个专家都记住一份不同版本的读出开销，再由多数意见决定，会形成难以解释的冲突。可传递资料 ID 与 revision，让专家明确基于哪项记录作结论，而不是复制整段历史。

## MCP：让工具连接标准化

MCP 通过标准交互发现和调用服务暴露的能力，LangChain 的适配包可以把这些能力转为工具对象。它减少连接与协议转换工作，不替应用决定哪些服务可信、哪些能力应对当前用户开放。

| 接入关注点 | 天文台场景的问题 | 应保存或验证的证据 |
| --- | --- | --- |
| 工具发现与转换 | 服务提供哪些资料查询 | 工具 schema、名称、描述和变更 |
| 连接生命周期 | 会话是逐调用建立还是长期保持 | 超时、清理与服务状态依赖 |
| 认证 | 谁在访问远程归档 | 授权主体、范围、令牌生命周期 |
| 执行政策 | 是否只读、是否允许提交 | 服务端授权与业务版本核验 |

下面是适配接口片段，需已安装 `langchain-mcp-adapters`，并由应用提供审核过的连接配置与模型；它不包含可直接访问的真实服务：

```python
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

async def make_archive_agent(approved_connections, model):
    client = MultiServerMCPClient(approved_connections)
    discovered = await client.get_tools()
    read_only = [t for t in discovered if t.name in {"archive_lookup"}]
    if not read_only:
        raise RuntimeError("approved archive tool was not discovered")
    return create_agent(model=model, tools=read_only)
```

实际转换后的工具名可能有前缀或配置差异，应核对发现结果，不照猜名称。需要有状态 MCP 会话时，还应按当前适配包的 session 生命周期使用方式接入，不能假定上述简单工厂保留了任意服务状态。

认证不等于授权，工具描述也属于外部输入。服务更新了描述或返回内容，可能引入不可信指令，应保持资料与系统规则分离。令牌不放入模型 schema 或日志，远程服务返回的执行结果也要按同一工具闭环回填。

<figure class="concept-diagram" tabindex="0" data-review-figure="lg-mcp-boundary">
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 576" role="img" aria-labelledby="lg-mcp-boundary-title lg-mcp-boundary-desc" style="display:block;width:100%;min-width:620px;height:auto">
<title id="lg-mcp-boundary-title">MCP 连接工具，不替应用作授权</title>
<desc id="lg-mcp-boundary-desc">应用宿主向MCP 适配器：审核过的连接配置；MCP 适配器向资料服务：发现工具及 schema；资料服务向MCP 适配器：工具目录；MCP 适配器向应用宿主：转换为工具对象；应用宿主向MCP 适配器：允许名单内的 archive_lookup；MCP 适配器向资料服务：携带授权主体执行查询</desc>
<rect width="960" height="576" fill="var(--paper,#faf8f1)"/>
<g font-family="'IBM Plex Sans','Noto Sans CJK SC',system-ui,sans-serif"><text x="40" y="48" font-size="28" fill="var(--ink,#243b48)" text-anchor="start">MCP 连接工具，不替应用作授权</text><path d="M160 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M480 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M800 128V504" stroke="var(--line,var(--rule,#bfc8c3))" stroke-dasharray="5 5"/><path d="M160 164 L480 164" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M473 159 L480 164 L473 169" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="128" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="146" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">审核过的连接配置</text><path d="M480 224 L800 224" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M793 219 L800 224 L793 229" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="188" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="206" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">发现工具及 schema</text><path d="M800 284 L480 284" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M487 279 L480 284 L487 289" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="248" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="266" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">工具目录</text><path d="M480 344 L160 344" fill="none" stroke="var(--muted,#536772)" stroke-width="2" stroke-dasharray="6 5"/><path d="M167 339 L160 344 L167 349" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="308" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="326" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">转换为工具对象</text><path d="M160 404 L480 404" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M473 399 L480 404 L473 409" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="176" y="368" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="320" y="386" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">允许名单内的 archive_lookup</text><path d="M480 464 L800 464" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><path d="M793 459 L800 464 L793 469" fill="none" stroke="var(--muted,#536772)" stroke-width="2"/><rect x="496" y="428" width="288" height="24" fill="var(--paper,#faf8f1)"/><text x="640" y="446" font-size="18" fill="var(--ink,#243b48)" text-anchor="middle">携带授权主体执行查询</text><rect x="48" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="160" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">应用宿主</text><rect x="368" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="480" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">MCP 适配器</text><rect x="688" y="80" width="224" height="48" rx="6" fill="var(--paper-2,var(--paper-deep,#ffffff))" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="800" y="111" font-size="20" fill="var(--ink,#243b48)" text-anchor="middle">资料服务</text><path d="M40 520H920" stroke="var(--line,var(--rule,#bfc8c3))"/><text x="40" y="552" font-size="18" fill="var(--muted,#536772)" text-anchor="start">只示意发现与调用；服务端授权和连接清理由应用明确配置。</text></g>
</svg>
<figcaption>图：只示意发现与调用；服务端授权和连接清理由应用明确配置。</figcaption>
</figure>

## 协作模式的共同风险

### 多数意见不是独立证据

三位专家都读 `SIM-TIME-4@r1` 并同意 1500 秒，只能说明同一输入下结论一致。若资料不适用于真实仪器，投票无法纠正适用性问题。

聚合应按来源身份、版本和推断关系整理证据。数值争议可重算，规则争议要回到权威资料或人工核验，不能用角色数量替代独立验证。

### 部分成功要成为明确的聚合状态

仪器核验完成、归档服务超时，应保存两项独立状态。产品可以返回带缺项的研究草稿，也可以坚持等待，但不能默认为全部通过。

只重跑失败任务可减少重复费用，合并前仍要检查成功结果是否过期。远程连接恢复不代表先前会话状态仍存在，任务输入需足以安全重建或识别需要重新开始。

### 失败隔离与预算

每个子任务、每个远程工具和父图都可能有重试。应计算最坏尝试数，并分配总时长、费用和调用额度；超时后明确降级、终止或请求人工处理。

子任务暂停要让父 UI 可辨认，不能只是一个永不返回的工具调用。版本升级也要带着旧 checkpoint 和连接合同验证，避免图恢复成功但远程工具名称或 schema 已改变。

## 选型：子图、子 Agent、还是多 Agent 模式

| 实际需要改变的部分 | 合适的起点 | 需要验证的边界 |
| --- | --- | --- |
| 固定审批与恢复顺序 | 显式子图或父工作流 | 状态映射、待恢复任务 |
| 独立长研究的上下文 | 子 Agent 委托 | 窄输入、结果与预算 |
| 问题类型分配 | Router | 未知、混合与误路由 |
| 下一轮由其他处理者接手 | Handoff | 控制状态与回退 |
| 按需补领域流程 | Skills | 加载范围、版本和可信性 |
| 连接外部工具服务 | MCP adapters | 认证、授权与连接生命周期 |

这些选择可以并存。先用一个失败场景证明需要哪条边界，再引入相应封装；MCP 不迫使应用采用多 Agent，多 Agent 也不必须通过 MCP 相互通信。

## 源码入口

- 官方 `multi-agent/*` 页面：对照各模式的控制和上下文关系。
- 官方 `mcp/*` 的 tools、connections、auth：核对适配及生命周期合同。
- `langchain-mcp-adapters`：按安装版本查看工具转换与客户端实现。
- `deepagents/middleware/`：检查委托和技能的实际组合。

先用受控测试服务验证工具发现、拒绝和断连，再考虑真实归档接入。未运行远程连接时，只能描述接入设计，不能把示意配置写成服务已可用的证明。
