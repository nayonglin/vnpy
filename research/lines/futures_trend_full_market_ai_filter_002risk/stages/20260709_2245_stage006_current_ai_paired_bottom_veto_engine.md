# Stage006 当前官方 AI 同口径配对 bottom25 veto 真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 22:38 CST`
- 阶段性质：Stage005 审计阻塞修复 / 最小 A0/C 真实引擎配对
- 是否重要突破：待独立 review；若通过则可进入逐半年多周期
- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + full-market bottom25 veto

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage006_current_ai_paired_bottom_veto_engine.py`
- 新增参数：无；继承 Stage005 的 `BOTTOM_VETO_QUANTILE=0.25` 和 `MIN_ACTIVE_PRODUCTS_FOR_VETO=12`。
- 修改参数：A0 与 C 均使用当前磁盘官方 AI 文件并通过同一真实引擎运行。
- 删除参数：删除 Stage005 与冻结 Stage167 曲线直接对比的口径。

## 回测参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。

## 结果

- A0 期末权益：`5,996,631.00`；总收益 `3897.7540%`；最大回撤 `-55.3701%`；Sharpe `1.3967`
- C 期末权益：`4,407,585.30`
- C 总收益：`2838.3902%`
- C 最大回撤：`-46.1580%`
- C Sharpe：`1.3541`
- C 总滑点：`524,860.00`
- C 总交易次数：`585`
- C 胜率：`52.2876%`，口径为非零交易日胜率，不是逐笔胜率。
- 收益保留率：`0.7282`
- C 相对 A0 收益差：`-1059.3638` 百分点；回撤差：`9.2121` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_report_stage006_current_ai_paired_bottom_veto_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_ac_summary_stage006_current_ai_paired_bottom_veto_engine_v1.csv`
- A0 eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_a0_eligibility_stage006_current_ai_paired_bottom_veto_engine_v1.csv`
- C eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_candidate_eligibility_stage006_current_ai_paired_bottom_veto_engine_v1.csv`
- overlay_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_official_overlay_audit_stage006_current_ai_paired_bottom_veto_engine_v1.csv`
- risk_restore_audit：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_risk_restore_audit_stage006_current_ai_paired_bottom_veto_engine_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage006_current_ai_paired_bottom_veto_engine/full_market_ai002_stage006_current_ai_paired_bottom_veto_engine_equity_drawdown_stage006_current_ai_paired_bottom_veto_engine_v1.png`

## 结论

- 本阶段结论：`stage006_continue_to_halfyear_if_independent_review_passes`
- 是否进入下一步：等待独立 agent review 后决定。
- 下一步：若审计通过并保持收益保留/回撤改善，再进入逐半年多周期。

## 过拟合反思

- 运行前判断：低到中等。修复评估口径，不新增救参。
- 运行后判断：等待独立 review。

## 继续价值反思

- 运行前判断：有价值。它是 Stage005 进入多周期前必须补的同口径验证。
- 运行后判断：等待独立 review。
