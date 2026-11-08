# Stage002 基本面 Skill 独立代码审核

- 审核日期：2026-11-08，北京时间。
- 审核者：独立 agent `skill_code_review`。
- 范围：`skills/futures-fundamental-bias/` 的 Skill、三份参考合同、标准库助手、测试及 UI 元数据；发现符号链接、README 和 HANDOFF_MANIFEST 新增条目。
- 本轮只写审核文件，不修改实现，不安装依赖，不读取凭证，不运行金融回测或交易接口。
- 开始反思：不存在按收益拟合。本次检查的是证据准入边界而非方向预测；值得继续，因为免费公开研究仍需要防止旧闻、时间泄漏、同源重复和代理冒充直接事实。

## 最终代码复验结论

初审 `P0=0 / P1=0 / P2=3`，以下三项均由主 agent 修复并经本 agent 独立复验关闭；**最终未关闭 `P0=0 / P1=0 / P2=0`**。修复后的 18 个测试全部通过。助手只输出证据审计与缺口，不生成多空、胜率、交易或历史 PIT 认证；这部分边界清楚。以下保留原始复现，便于追溯。

复验细节：同日精确观测晚于精确发布得到 `observation_after_publication` 并排除，正常先观测后发布仍可准入；纽约日期源通过新的实际字段 `source_timezone=America/New_York` 计算出北京时间次日 13 点，在 01 点排除、13 点边界准入；`required_axes` 内 dict/list/null/number 均得到约定的 `ValueError`。证据合同已明确实际 `source_timezone` 与解释性 `source_timezone_assumption` 的区别。

初审时 7 个新增文件 manifest hash/mode 和发现入口均匹配。修复修改了脚本、测试、证据合同，其最终 manifest 由主 agent 收尾统一刷新；本审核不会把初审摘要验证误称为修复后的摘要验证。

### P2-1：精确观测晚于同日精确发布仍被准入

位置：`scripts/audit_evidence.py` 初审第 100—108 行，使用 `observed.date() > published.date()`。

复现：同一条合成事实设置 `published_at=2026-11-06T08:00:00+08:00`、`observed_at=2026-11-06T23:00:00+08:00`，截止设为 `2026-11-08T16:00:00+08:00`。实测仍有 `eligible=true`、没有任何原因，并得到 `manual_synthesis_required`。这会让在发布后才发生的同日实际快照被当作此前已经发布的事实。

建议：当两者均有精确时刻，比较完整带时区时刻；日期级观测与日期级发布另按可证明的区间处理。新增同日“观测晚于发布”和正常顺序回归测试，不能把日期级的不确定性机械应用到已经给定的精确时间。

### P2-2：日期级境外源使用截止时区，早于源当地的保守可用时点

位置：`scripts/audit_evidence.py` 初审第 57、82、94 行；`references/evidence-contract.md` 第 26—28 行；免费目录包含 USDA、EIA、CFTC 等境外来源。

合同写明日期级发布按“当地次日零点”可用，但助手所有日期均使用顶层时区。每行的 `source_timezone_assumption` 只是推荐备注、不会参与解析；同一事实包无法正确表达混合源日期的当地界限。

复现：顶层 `timezone=Asia/Shanghai`、`as_of=2026-11-09T01:00:00+08:00`；事实 `published_at=2026-11-08`、`source_timezone_assumption=America/New_York`。实测得到 `publication_available_at=2026-11-09T00:00:00+08:00` 并准入。纽约当地 11 月 9 日零点实际对应北京时间 11 月 9 日 13 点；保守日期规则被提前 13 小时。该问题不影响已明确使用北京时间的国内日期事实，但影响 Skill 承诺的通用境外锚。

建议：支持每行来源时区并转换后比较；或明确限制“所有日期字段已经统一为顶层时区的保守可用日期”，要求研究者先转换并保留原日期/源时区。不能在跨时区未明确时自动声称已保守处理。

### P2-3：不合法 required_axes 导致未处理 TypeError

位置：`scripts/audit_evidence.py` 初审第 65—67、144—148 行。

复现：合法包仅改 `required_axes=[{}]`，实际抛出 `TypeError: unhashable type: 'dict'`；CLI 的异常捕获不包含该异常。因此不能满足合同所述“错误字段返回 2”，会以 traceback/非约定退出码结束。不会错误准入事实，但会破坏上层根据审计返回码处理失败的约定。

建议：先验证轴元素是字符串，再判断集合成员；对于 JSON 中错误的数组元素类型，转换为统一 `ValueError`。新增 dict/list/null/number 等非法元素回归，不需要放宽为吞掉所有异常。

## 已完成验证

实际两次执行 `.py311/bin/python -m unittest discover -s skills/futures-fundamental-bias/tests -v`：初审 15 个测试全部通过，修复后 18 个全部通过。覆盖未来发布、日期级发布时间、旧观测不被新文章刷新、代理不能解锁全品种判断、传闻/搜索摘要不准入、公开摘要范围提示、同源转载去重、不同样本保留、供应商晚到、无时区时间排除、未来观测、重复 ID、布尔新鲜度、结构背景及历史 PIT 不认证，并新增同日精确先后、跨时区日期和错误轴元素三个回归。

另行运行 6 个拒绝准入检查：空包、付费正文、缺发布时间、旧发布配新观测、context、proxy，均得到 `insufficient_current_direct_evidence`。同源事实的重复条目不会增加来源数；未观察到免费来源约束、交易接口隔离或预测边界失效。

初审 7 个新增文件的实际 SHA256 均与 manifest 的 `installed_sha256` 一致，文件 mode 也一致。`.agents/skills/futures-fundamental-bias` 为仓库内相对符号链接，解析到唯一维护目录。README 计数 12 及新增条目、manifest 的本仓原创来源说明相互一致。最终修复后的摘要刷新需由主 agent 再确认。

检查了 Skill frontmatter 的名称/非空描述、Skill 内三条 reference 路径和 UI 元数据三个带引号字符串，均通过；UI `short_description` 为 31 字符。此为简单结构检查，不冒称完成宿主 `quick_validate.py` 的完整 YAML 验证。主 agent 已说明 `.py311` 缺 PyYAML；本轮未为此安装环境或绕开验证。

脚本明确无法验证来源真伪、忠实引用、样本独立性、单位、direct/proxy 标签和新鲜度选择；这些人工限制在 Skill、证据合同和审计输出均有披露。仅有一条直接事实会进入 `manual_synthesis_required`，该状态自身不构成方向认证，因此不把缺四轴覆盖当作脚本预测漏洞。

## 限制与后续

本轮为实现与契约的独立审核，未重新抓取目录中所有来源，也未审阅尚未交付的最终焦煤事实包和结论。具体行情事实、原文日期、引用是否忠实及方向推断仍需另行审阅。

结束反思：没有收益目标、方向阈值或模型投票，不构成策略过拟合。继续完善上述时间与错误输入边界有价值；在没有事实包和来源审核前，不应把单元测试通过解释为焦煤判断已经正确。
