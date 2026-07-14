# Stage001 第二轮独立审查 NO-GO 与 runtime 证据闸门修复

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：研究候选 / canary 前第二轮代码审计
- 记录时间：`2026-07-12 20:11 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：固定字节独立复审、负例复现、证据闸门修复；未运行收益回测
- 是否重要突破：否
- 是否触发A/B：是；仍未进入 canary

## 独立审查

- 审查员：独立 agent `Hegel`
- 审查对象：旧 review manifest SHA256 `06128b6245eb18c46c5ac6b9a86f0b9d8455dbe520c7990e00b0dbd6f870e522`
- 结论：`NO-GO`，`P0=0`、`P1=2`、`P2=2`，置信度 `97%`；旧 manifest 未获签认并立即作废。
- P1-1：审计直接信任 `pos_change`，没有验证逐行 `end_pos - start_pos == pos_change`；构造误差4手时其余三项 reconciliation 仍可为0。
- P1-2：空 `entry_candidates` 被包装成全零 runtime audit，判定未要求真实 opened row/batch 证据。
- P2-1：保证金只做结果列间恒等式，没有从 positions、size 和 margin ratio 独立重算，也未验证 broker10 1.10 multiplier。
- P2-2：缺少真实 LedoitWolf 零方差、runtime 缺列/缺锚点/重复、空证据和逐行 position identity 的持久化负例。

## 修复

- 新增 `position_row_identity_max_error`，逐行验证 `end_pos-start_pos-pos_change == 0`。
- `runtime_mrc_audit` 对空 snapshot、缺列、非有限/非整数关键字段返回显式 evidence/schema error，不再返回可通过的全零证据。
- runtime gate 强制每个锚点 opened rows 和 batch count 大于0；available/unavailable 必须完整分割 batch；空 batch id、非法 `mrc_available`、重复/缺锚点均阻断。
- 新增从每日 positions 的 `abs(end_pos) * close_price * size * margin_ratio` 独立重算 `c3_margin_exact`，metadata 缺失或非法直接报错。
- 新增 broker10 `1.10` multiplier 恒等式；保留 broker10/equity 比率恒等式。
- 零方差测试改为真实常数收益矩阵经过 LedoitWolf 和风险计算，不再 mock `compute_batch_adjustments`。
- 增加 summary/runtime 缺列、锚点缺失/重复、空 runtime evidence、逐行 position identity、独立 margin 和 broker10 multiplier 负例。

## 验证

- 修复前新增负例：`25` 项中 `2 failure + 2 error`，复现两项 P1 和 margin 审计缺口。
- 修复后：`.py311/bin/python tests/test_candidate_marginal_risk_contribution_stage001.py`，`26/26` 通过。
- 未运行 canary，未观察候选收益。

## 回测结果

- 期末权益：N/A（未运行）
- 总收益：N/A（未运行）
- 最大回撤：N/A（未运行）
- Sharpe：N/A（未运行）
- 总滑点：N/A（未运行）
- 总交易次数：N/A（未运行）
- 胜率：N/A（未运行）

## 结论

- 本阶段结论：第二轮独立审查再次正确阻断；两项 P1 已有先失败后通过的持久化负例，P2 保证金与测试覆盖同步修复。
- 是否进入下一步：否；必须重新生成 manifest 并由新的独立 agent 签认。
- 下一步：新审查若 `P0=P1=0` 才允许用其签认的 manifest SHA 启动四锚点 1x canary。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：没有看收益，也没有改 MRC 数学、窗口、锚点、门槛或产品规则；全部改动是 fail-close 和恒等式审计。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有，但仍只允许一次冻结 canary。
- 原因：发现的是可复现的证据完整性 bug，修复后能显著提高回测结论可信度；未获独立签认前没有运行价值。

## 合入建议

- 是否更新本线 `LINE.md`：canary 和结果审查后统一更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
