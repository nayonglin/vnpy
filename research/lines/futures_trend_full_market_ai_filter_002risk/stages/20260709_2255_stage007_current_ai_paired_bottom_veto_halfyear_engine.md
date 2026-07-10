# Stage007 当前官方 AI 同口径 bottom25 veto 逐半年验证

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 23:04 CST`
- 阶段性质：Stage006 通过独立审计后的逐半年 A0/C 真实引擎验证
- 是否重要突破：待独立 review
- 是否触发A/B：是，A0=当前官方 AI 无 veto；C=当前官方 AI + full-market bottom25 veto

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage007_current_ai_paired_bottom_veto_halfyear_engine.py`
- 新增参数：无；继承 Stage006/005 的 bottom25 veto。
- 修改参数：起点从单一 `2020-01` 扩展为 `2020-01` 到 `2026-01` 逐半年，终点固定 `2026-06-30`。
- 删除参数：无。

## 回测参数

- 起点：`2020-01` 到 `2026-01`，共 `13` 个。
- 终点：`2026-06-30`
- 账户规模：`150,000`
- 成本/风险口径：沿用官方 C9 真实引擎原成本、风险和 OI restore。
- 输入 hash：official_ai `fc50e035cd66b65e`，A0 `2a68be6d3ac22894`，C `4072c013d80e6fa3`。

## 结果

- 样本数：`13`
- C 正收益数：`12`
- 收益保留 >=50%：`11/13`
- 回撤改善：`12/13`
- 最小/中位收益保留：`-1.9044` / `0.7450`
- C 最小/中位/最大收益：`-5.9056%` / `93.1737%` / `2838.3902%`
- C 最差/中位回撤：`-46.1580%` / `-23.4005%`
- 回撤变化最小/中位：`-1.2296` / `1.2857` 百分点
- 总交易减少：`543`，总滑点减少：`584,240.00`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_report_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_ac_summary_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.csv`
- pair_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_pair_summary_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.csv`
- stats：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_stats_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_ac_curves_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.csv.gz`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage007_current_ai_paired_bottom_veto_halfyear_engine/full_market_ai002_stage007_current_ai_paired_bottom_veto_halfyear_engine_equity_drawdown_stage007_current_ai_paired_bottom_veto_halfyear_engine_v1.png`

## 结论

- 本阶段结论：`stage007_stop_or_attribution_before_more_runs`
- 是否进入下一步：等待独立 agent review 后决定；若通过，下一步做成本敏感与弱窗口归因。

## 过拟合反思

- 运行前判断：低到中等。扩展样本，不新增参数。
- 运行后判断：等待独立 review。

## 继续价值反思

- 运行前判断：有价值。多周期是必要门槛。
- 运行后判断：等待独立 review。
