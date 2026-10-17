# Stage016 受影响旧源的完整入场日资格修正

- line_id：futures_trend_triple_screen；冻结时间2026-10-18 00:44 CST。
- 原因：Stage014已确认Stage859 producer按新datetime保存iloc[-1]且seen_ids阻止后续更新，不满足completed合同。A0实际消费859为0，不能把此发现泛化为A0收益已错，也不能把旧覆盖ready等同盘中H/L合格。
- 范围由来源和固定Stage010 full需求决定，不按PnL选择：cu2010/2020-08-27（284个859键）、fu2205/2022-03-30（225）、AP210/2022-04-06（225）、cu2507/2025-06-11（1），共735键/4session。FG209旧冲突仅anchor，原open相同，继续隔离其非open字段，不因本阶段擅改。

## 固定修正合同

1. 现已SHA核过的completed替代：cu2010 Stage462 local_0382、fu2205 Stage459/462 local_0527/0528、cu2507 Stage462 local_0492；完整唯一合法且原同SHA CSV七字段匹配。AP210现有两源目标日无行，必须等Stage017真实数据及独立资格，不能拿旧225根覆盖当价格通过。
2. 实施前先做少量合成测试与原source指纹绑定；真实构建只一次，在四个参考齐备后执行。不修改原base/002/011/015或旧receipt，输出独立research correction table和append-only新增表、逐key旧/新值及原source/新source证据。
3. 候选完整session按原CSV七字段/网格核验；只能替换原base中明确source859且位于上述full网格的现有键。非859旧键必须逐字段一致；open及openOI若不一致则拒绝并报告，不能借已知H/L问题修其他价差。任何跨源冲突拒绝，未获真实替代的旧键保持不合格，不能默许进入盘中扫描。
4. correction仅含实际有差异键；session中新缺的分钟另做append-only。核所有实际变更键（包括删除/替换而非只新增）与A0实际106731读取集交集0，才能按明确因果依据复用A0；若交集非0则停止并报告，不伪造路径等价。
5. 提供最小可复用研究loader上下文：仅按已签qualification和原key旧值前置条件应用修正，再叠加已验append-only，退出时恢复loader/cache；正式策略/原数据不改。AP若未齐必须用显式质量gate阻止full-session读取，不能用daily-open fallback。
6. readiness在继承Stage015基础上显式区分物理覆盖与完整价格资格；fu/AP原ready须有新的completed资格才保留。输出局部变化和剩余数据约束，不把8077的旧覆盖数量当全部价格审查。

## 边界与反思

仅对有直接producer缺陷证据的来源及其4个full需求做统一修正，不全量重洗其他来源，不重跑旧账户。独立agent审源/全部更改键范围/A0交集/少量具体差异后才能用于下一研究回放。金融指标N/A，无新alpha/资金/AI/0.5R参数。过拟合判断：否，数据源缺陷及七字段决定修正；继续价值：是，避免在不完整H/L上判断0.5R效果，且一次处理整个已知受影响范围。

## AP210真实来源更换（2026-10-18 01:06 CST，首次构建前）

- 原Stage017唯一连接64.247秒失败、raw0、AP210不合格；原工具、失败receipt及qualified_precise_sessions=0结论完整保留，不能作为本阶段补数来源。
- Stage018保留原017完全相同的8合约/39session/12945目标，只修正公开wait_update短时False的总预算控制；root唯一连接117.012秒exit0，idle_waits=2后在同一api完成12945分钟及39session，AP210原CSV七字段/完整后继225分钟通过，35输入未变。实际独立review仍是本阶段构建前必要门。
- 因此未执行过的Stage016显式改用outputs/stage018_provider_wait_budget/network_attempt1及outputs/stage018_independent_review/review_receipt.json。CLI为--stage018-review-sha256；不覆盖或改写Stage017失败身份。
- 新独立门除P0/P1=0、qualified_precise_sessions>0外，还须required_AP210_accepted=true及qualified_research_data=true；五项raw/evidence/quality/parent/worker资产SHA、parent exit0/input未变、provider1、AP225后继和原CSV七字段仍逐项验证。Stage016此前未真实构建，待root提供实际独立receiptSHA后唯一执行；没有新增金融尝试或alpha参数。
