# Stage009 2026-01 tail veto failure attribution

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 23:45 CST`
- 阶段性质：Stage008 失败窗口只读归因
- 是否重要突破：否
- 是否触发A/B：否，仅复跑 2026-01 A0/C 诊断

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage009_2026_tail_veto_failure_attribution.py`
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/诊断参数

- 起点：`2026-01-01`
- 终点：`2026-06-30`
- 账户规模：`150,000`
- 成本/风险口径：沿用 Stage008 A0/C 真实引擎原口径。

## 结果

- A0 期末权益：`154,651.60`，总收益 `3.1011%`，最大回撤 `-14.2479%`，Sharpe `0.3734`。
- C 期末权益：`138,621.60`，总收益 `-7.5856%`，最大回撤 `-15.6688%`，Sharpe `-0.4790`。
- C-A0 期末权益差：`-16,030.00`。
- A0 有、C 没有的实际开仓：`4` 笔；核心机会成本 `AP.CZCE` 产品层 C-A0 `-21,300.00`；主要抵消项 `MA.CZCE` `3,310.00`、`SM.CZCE` `1,760.00`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage009_2026_tail_veto_failure_attribution/full_market_ai002_stage009_2026_tail_veto_failure_attribution_report_stage009_2026_tail_veto_failure_attribution_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage009_2026_tail_veto_failure_attribution/full_market_ai002_stage009_2026_tail_veto_failure_attribution_summary_stage009_2026_tail_veto_failure_attribution_v1.csv`
- missing_entries：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage009_2026_tail_veto_failure_attribution/full_market_ai002_stage009_2026_tail_veto_failure_attribution_a0_entries_missing_in_c_stage009_2026_tail_veto_failure_attribution_v1.csv`
- product_pnl_diff：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage009_2026_tail_veto_failure_attribution/full_market_ai002_stage009_2026_tail_veto_failure_attribution_product_pnl_diff_stage009_2026_tail_veto_failure_attribution_v1.csv`
- daily_diff：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage009_2026_tail_veto_failure_attribution/full_market_ai002_stage009_2026_tail_veto_failure_attribution_daily_diff_stage009_2026_tail_veto_failure_attribution_v1.csv`

## 结论

- 本阶段结论：Stage008 失败主要来自 `AP.CZCE` 被 veto 后错过单笔右尾，不建议继续扫 rank/分位救参。
- 独立 review：`2026-07-09 23:50 CST` 完成；无 P0/P1，确认 Stage009 只读、A0/C 与 Stage008 一致、missing entry 归因和产品 PnL diff 闭合。
- 是否进入下一步：收束本分支；除非引入真正外生新信息源，不继续围绕 rank/分位救参。

## 过拟合反思

- 运行前判断：低，只做失败窗口归因。
- 运行后判断：高风险在于把 2026-01 的 AP 个案反推成参数，所以不继续扫参。

## 继续价值反思

- 运行前判断：有价值，用于确认 guarded veto 的失败机制。
- 运行后判断：继续做参数实验价值低；除非引入外生新信息源，否则本分支应收束。
