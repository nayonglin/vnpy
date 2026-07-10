# Stage008 guarded official-tail bottom25 veto 逐半年验证

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 23:33 CST`
- 阶段性质：Stage007 失败后的 guarded 结构验证
- 是否重要突破：否
- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + guarded tail bottom25 veto

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage008_guarded_official_tail_bottom_veto_halfyear_engine.py`
- 新增参数：`PROTECTED_OFFICIAL_RANK_MAX=4`。
- 修改参数：full-market bottom25 veto 只允许作用于 official rank 5 及以后。
- 删除参数：无。

## 回测参数

- 起点：`2020-01` 到 `2026-01`，共 `13` 个。
- 终点：`2026-06-30`
- 账户规模：`150,000`
- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。

## 结果

- C 正收益数：`12/13`
- 收益保留 >=50%：`12/13`
- 回撤改善：`11/13`
- 最小/中位收益保留：`-2.4461` / `0.7892`
- C 最小/中位/最大收益：`-7.5856%` / `99.0173%` / `3111.2607%`
- C 最差/中位回撤：`-47.0256%` / `-23.7180%`
- 回撤变化最小/中位：`-1.4209` / `1.1359` 百分点

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage008_guarded_official_tail_bottom_veto_halfyear_engine/full_market_ai002_stage008_guarded_official_tail_bottom_veto_halfyear_engine_report_stage008_guarded_official_tail_bottom_veto_halfyear_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage008_guarded_official_tail_bottom_veto_halfyear_engine/full_market_ai002_stage008_guarded_official_tail_bottom_veto_halfyear_engine_ac_summary_stage008_guarded_official_tail_bottom_veto_halfyear_engine_v1.csv`
- pair_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage008_guarded_official_tail_bottom_veto_halfyear_engine/full_market_ai002_stage008_guarded_official_tail_bottom_veto_halfyear_engine_pair_summary_stage008_guarded_official_tail_bottom_veto_halfyear_engine_v1.csv`
- stats：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage008_guarded_official_tail_bottom_veto_halfyear_engine/full_market_ai002_stage008_guarded_official_tail_bottom_veto_halfyear_engine_stats_stage008_guarded_official_tail_bottom_veto_halfyear_engine_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage008_guarded_official_tail_bottom_veto_halfyear_engine/full_market_ai002_stage008_guarded_official_tail_bottom_veto_halfyear_engine_equity_drawdown_stage008_guarded_official_tail_bottom_veto_halfyear_engine_v1.png`

## 结论

- 本阶段结论：`stage008_stop_or_attribution_before_more_runs`
- 独立 review：`2026-07-09 23:43 CST` 完成；无 P0/P1，确认 A0/C 同 AI 文件、同引擎，C 是 A0 子集，rank<=4 保护生效，PIT/AI 接线/summary/风险口径自洽。
- 是否进入下一步：不晋级，不继续扫 `PROTECTED_OFFICIAL_RANK_MAX`、bottom quantile、月份、品种或权重；转 Stage009 做 2026-01 失败窗口只读归因。

## 过拟合反思

- 运行前判断：中等。只做一个结构保护版本，不扫参数。
- 运行后判断：中等偏高。Stage008 修复了 2022-01 的过度否决，但 2026-01 仍负收益且回撤恶化；继续救 rank/分位会围绕少数窗口过拟合。

## 继续价值反思

- 运行前判断：有价值。它直接验证 full-market veto 是否应只作用于 official 尾部。
- 运行后判断：作为经验有价值，但作为晋级候选价值不足；后续只做失败归因，不再参数实验。
