# Stage075 official C9 month-end buffer top-up true engine

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T15:39:01
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式 C9 30w 月末缓冲补款真实引擎 A/C
- 是否重要突破：否，真实引擎未通过新目标
- 是否触发A/B：是；A=正式 C9/15w，C=正式 C9 + 30w 月末缓冲补款资金治理

## 外部调研与判断

- CPPI/TIPP 和 capital correction 支持资金安全垫思路，但 Stage074 已显示单纯降风险会拉长水下；本阶段只验证月末补回交易袖。
- 新目标：收益率保留 `50%`，同时减少水下时间和最大回撤。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage075_official_c9_monthend_buffer_topup_true_engine.py`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`enable_stage075_monthend_buffer_topup`、`stage075_initial_reserve_capital=150000`、`stage075_topup_floor_equity=150000`。
- 修改参数：无正式交易信号参数；只改变研究候选的资金治理层。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01` 到 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：A `150,000`；C 总账户 `300,000=150,000交易袖+150,000储备`。
- 成本口径：沿用正式真实引擎成本。
- 样本过滤：无。
- 策略/归因口径：C 的补款发生在月末收盘后，只影响后续 sizing；补款不计入收益。

## 结果

| version                           | variant_label                       |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   total_slippage_sum |   total_trade_count_sum |
|:----------------------------------|:------------------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|---------------------:|------------------------:|
| official_c9_15w_reference         | Official C9 15w reference           |            13 |               13 |          1.90107 |             126.199 |          3886.19 |                            1 |                               1 |             -55.3701 |               -24.469 |                      500 |                          20 |                                  387 |          1.85368e+06 |                    3673 |
| monthend_buffer_topup_true_engine | Month-end buffer top-up true engine |            13 |                0 |          0       |               0     |             0    |                            0 |                               0 |               0      |                 0     |                        0 |                           0 |                                    0 |          0           |                       0 |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_report_stage075_official_c9_monthend_buffer_topup_true_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_per_start_summary_stage075_official_c9_monthend_buffer_topup_true_engine_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_curves_stage075_official_c9_monthend_buffer_topup_true_engine_v1.csv.gz`
- orders：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_candidate_trades_stage075_official_c9_monthend_buffer_topup_true_engine_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage075_official_c9_monthend_buffer_topup_true_engine/rebuilt_c9_v2_stage075_official_c9_monthend_buffer_topup_true_engine_candidate_ai_month_audit_stage075_official_c9_monthend_buffer_topup_true_engine_v1.csv`

## 结论

- 本阶段结论：`stage075_true_engine_not_promoted`。
- 是否进入下一步：`False`。
- 下一步：若通过，拉独立 agent 做代码与统计口径 review，再决定是否做更密集逐月起点；若未通过，停止补款频率/比例救参。

## 过拟合反思

- 运行前判断：否。资金结构由实际 30w/15w+15w 给定，月末频率来自低频资金治理，不按亏损窗口调参。
- 运行后判断：见结论；不按失败起点继续调补款日期或金额。
- 原因：继续扫补款频率、floor 或储备比例会变成资金曲线救参。

## 继续价值反思

- 运行前判断：有。Stage074 代理通过新目标，值得真实引擎确认。
- 运行后判断：有限，若未通过应停止该形状。
- 原因：真实引擎决定补款是否真的改善整数手和保证金路径。

## 合入建议

- 是否更新本线 `LINE.md`：独立 review 后再更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：独立 review 后再决定。
