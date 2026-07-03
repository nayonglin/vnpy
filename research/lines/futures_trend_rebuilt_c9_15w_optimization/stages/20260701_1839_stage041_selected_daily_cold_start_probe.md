# Stage041 - 关键日期独立日级冷启动探针

- 记录时间：`2026-07-01T18:39`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage041_selected_daily_cold_start_probe_v1`
- 是否重要突破版本：`否`
- 决策：`stage041_selected_daily_cold_start_confirms_left_tail_not_only_subwindow_artifact`

## 本次版本变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage041_selected_daily_cold_start_probe.py`
- 新增参数：`PROBE_START_LIMIT=8`；诊断常量 `MIN_PERIOD_CALENDAR_DAYS=366`。
- 修改参数：无，Stage013/Stage039/官方 C9 配置未改。
- 删除参数：无。
- 新增回测结果：关键日期 Stage013 真实日级冷启动探针 + Stage039 top8 closed-lot proxy。
- 本阶段不连接 CTP，不调用订单 API，不触发 A/B。

## 调研和判断结论

- 趋势跟随和 managed futures 文献都强调滚动回撤会持续较久；因此 Stage041 不做参数修复，先用精确日级冷启动确认严格子窗口失败是否是真实可复验问题。

## 结果

- 探针起点数：`8`。
- Stage013 有负结束日的探针起点：`8`。
- Stage041 proxy 有负结束日的探针起点：`8`。
- Stage013 探针最差收益：`-31.0300%`。
- Stage041 proxy 探针最差收益：`-30.7717%`。
- Stage041 proxy delta：`139,380.40`。

## 探针起点

|   probe_rank | requested_start   |
|-------------:|:------------------|
|            1 | 2022-07-15        |
|            2 | 2022-07-19        |
|            3 | 2021-10-26        |
|            4 | 2022-03-07        |
|            5 | 2022-07-14        |
|            6 | 2022-07-18        |
|            7 | 2022-03-09        |
|            8 | 2021-10-27        |

## 探针审计

| requested_start   | variant                                          | actual_start   | actual_end   |   window_count |   negative_count |   negative_rate_pct |   min_return_pct | worst_end_date   |   to_final_return_pct |   end_equity |   max_dd_pct |   sharpe |
|:------------------|:-------------------------------------------------|:---------------|:-------------|---------------:|-----------------:|--------------------:|-----------------:|:-----------------|----------------------:|-------------:|-------------:|---------:|
| 2022-07-15        | stage013_daily_cold_start_engine                 | 2022-07-15     | 2026-06-30   |            715 |              185 |             25.8741 |         -31.03   | 2023-07-17       |              125.219  |       337828 |     -33.0399 |   0.827  |
| 2022-07-15        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-07-15     | 2026-06-30   |            715 |              185 |             25.8741 |         -30.7717 | 2023-07-17       |              137.398  |       356098 |     -32.7854 |   0.8654 |
| 2022-07-19        | stage013_daily_cold_start_engine                 | 2022-07-19     | 2026-06-30   |            712 |              182 |             25.5618 |         -29.0367 | 2023-07-24       |              125.219  |       337828 |     -33.0399 |   0.8279 |
| 2022-07-19        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-07-19     | 2026-06-30   |            712 |              182 |             25.5618 |         -28.7783 | 2023-07-24       |              137.398  |       356098 |     -32.7854 |   0.8664 |
| 2021-10-26        | stage013_daily_cold_start_engine                 | 2021-10-26     | 2026-06-30   |            890 |              386 |             43.3708 |         -28.25   | 2024-03-05       |               63.1754 |       244763 |     -32.4006 |   0.5395 |
| 2021-10-26        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2021-10-26     | 2026-06-30   |            890 |              386 |             43.3708 |         -28.0125 | 2024-03-05       |               72.7442 |       259116 |     -32.4209 |   0.5859 |
| 2022-03-07        | stage013_daily_cold_start_engine                 | 2022-03-07     | 2026-06-30   |            802 |              271 |             33.7905 |         -24.6467 | 2023-07-17       |              131.555  |       347333 |     -35.1409 |   0.8006 |
| 2022-03-07        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-03-07     | 2026-06-30   |            802 |              271 |             33.7905 |         -23.6925 | 2023-07-17       |              144.536  |       366804 |     -34.7827 |   0.841  |
| 2022-07-14        | stage013_daily_cold_start_engine                 | 2022-07-14     | 2026-06-30   |            715 |              185 |             25.8741 |         -31.03   | 2023-07-17       |              125.219  |       337828 |     -33.0399 |   0.8266 |
| 2022-07-14        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-07-14     | 2026-06-30   |            715 |              185 |             25.8741 |         -30.7717 | 2023-07-17       |              137.398  |       356098 |     -32.7854 |   0.865  |
| 2022-07-18        | stage013_daily_cold_start_engine                 | 2022-07-18     | 2026-06-30   |            713 |              183 |             25.6662 |         -29.0367 | 2023-07-24       |              125.219  |       337828 |     -33.0399 |   0.8275 |
| 2022-07-18        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-07-18     | 2026-06-30   |            713 |              183 |             25.6662 |         -28.7783 | 2023-07-24       |              137.398  |       356098 |     -32.7854 |   0.8659 |
| 2022-03-09        | stage013_daily_cold_start_engine                 | 2022-03-09     | 2026-06-30   |            800 |              271 |             33.875  |         -28.1    | 2023-07-17       |              122.082  |       333123 |     -36.2174 |   0.7611 |
| 2022-03-09        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2022-03-09     | 2026-06-30   |            800 |              271 |             33.875  |         -27.0392 | 2023-07-17       |              134.166  |       351249 |     -35.8069 |   0.8004 |
| 2021-10-27        | stage013_daily_cold_start_engine                 | 2021-10-27     | 2026-06-30   |            889 |              385 |             43.3071 |         -28.25   | 2024-03-05       |               63.1754 |       244763 |     -32.4006 |   0.5397 |
| 2021-10-27        | stage041_daily_cold_start_stage039_ai_top8_proxy | 2021-10-27     | 2026-06-30   |            889 |              385 |             43.3071 |         -28.0125 | 2024-03-05       |               72.7442 |       259116 |     -32.4209 |   0.5862 |

## 输出

- probe_starts：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_probe_starts_stage041_selected_daily_cold_start_probe_v1.csv`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_summary_stage041_selected_daily_cold_start_probe_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_curves_stage041_selected_daily_cold_start_probe_v1.csv`
- lot_deltas：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_lot_deltas_stage041_selected_daily_cold_start_probe_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_decision_stage041_selected_daily_cold_start_probe_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage041_selected_daily_cold_start_probe/rebuilt_c9_stage041_selected_daily_cold_start_probe_report_stage041_selected_daily_cold_start_probe_v1.md`

## 反思

- 运行前过拟合反思：否。探针日期来自 Stage040 失败窗口，不新增交易规则、不按日期优化，只检验审计口径。
- 运行后过拟合反思：否。本阶段结果不能用于按这些日期写规则；只能决定是否扩大真实日级冷启动审计。
- 运行前继续价值反思：有。若子窗口失败不是日级冷启动失败，后续优化方向会完全不同。
- 运行后继续价值反思：有。独立日级冷启动探针也有负结束日，下一步应扩大日级 start 样本或转账户外层/外生源。
