# Stage121 Stage074 cold-start ramp true engine

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-06T14:24:03
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：上游 Stage074 cold-start ramp 真引擎 A/C 验证。
- 是否重要突破：否，真引擎未通过晋级条件
- 是否触发A/B：是；A=正式 C9/15w，C=正式 C9/15w + Stage074 cold-start ramp。

## 外部调研与判断

- TqSdk/vn.py/PySystemTrade 等资料支持用可复验 backtest 和 capital correction 检查资金层，但交易信号和资金层要分开看。
- 我的判断：Stage074 是账户/资金层，不是 alpha；必须用真实引擎验证整数手、保证金、止损重试事件顺序后才有意义。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage121_stage074_cold_start_ramp_true_engine.py`
- 修改脚本：无正式入口修改。
- 删除脚本：无。
- 新增参数：`enable_stage121_cold_start_ramp=True`、`stage121_cold_start_ramp_floor=0.35`、`stage121_cold_start_ramp_trading_days=252`。
- 修改参数：无正式交易信号参数；只改变研究候选的 sizing/risk equity。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01` 到 `2026-01` 逐半年起点，统一终点 `2026-06-30`。
- 账户规模：A/C 均 `150,000`。
- 成本口径：沿用正式真实引擎成本。
- 样本过滤：无。
- 策略/归因口径：真实引擎；ramp 在每日风控刷新后进入 sizing/risk equity，不是事后曲线乘数。

## 结果

| version                              | variant_label                        |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   min_return_retention_ratio |   median_return_retention_ratio |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_consecutive_below_initial_days |   total_slippage_sum |   total_trade_count_sum |
|:-------------------------------------|:-------------------------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|-----------------------------:|--------------------------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|----------------------------------------:|---------------------:|------------------------:|
| official_c9_15w_reference            | Official C9/15w                      |            13 |               13 |          1.90107 |             126.199 |          3886.19 |                     1        |                         1       |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                                      16 |          1.85368e+06 |                    3673 |
| stage074_cold_start_ramp_true_engine | Stage074 cold-start ramp true engine |            13 |               13 |          2.53387 |             156.485 |          2783.18 |                     0.412294 |                         0.73501 |             -54.8258 |              -23.4285 |                      467 |                          33 |                                  330 |                                      26 |          1.1595e+06  |                    3478 |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_report_stage121_stage074_cold_start_ramp_true_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_per_start_summary_stage121_stage074_cold_start_ramp_true_engine_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_curves_stage121_stage074_cold_start_ramp_true_engine_v1.csv.gz`
- orders：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_candidate_trades_stage121_stage074_cold_start_ramp_true_engine_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_candidate_ai_month_audit_stage121_stage074_cold_start_ramp_true_engine_v1.csv`
- chart：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage121_stage074_cold_start_ramp_true_engine/rebuilt_c9_v2_stage121_stage074_cold_start_ramp_true_engine_equity_focus_from_2021_07_stage121_stage074_cold_start_ramp_true_engine_v1.png`

## 结论

- 本阶段结论：`stage121_stage074_ramp_true_engine_not_promoted`。
- 是否进入下一步：`False`。
- 下一步：若未通过，停止 cold-start ramp floor/days 救参；若通过，先做独立 review，再考虑更密日级起点。

## 过拟合反思

- 运行前判断：否。floor 和 ramp_days 固定继承 Stage074，没有根据本次结果调整。
- 运行后判断：否。本次是冻结验证；失败后继续扫 floor/days 会变成过拟合。
- 原因：本阶段只验证 proxy 能否穿过真实引擎，不按坏窗口反推参数。

## 继续价值反思

- 运行前判断：有。Stage074 proxy 是上游有防守效果的账户外层，必须补真实引擎证据。
- 运行后判断：有限，不建议继续救这个线性 ramp 形状。
- 原因：真引擎结果决定整数手、保证金和止损重试顺序是否保留 proxy 优势。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录本阶段结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要条目。
