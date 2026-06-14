# Stage824 线上版 vs Stage819 30万候选月度 3 年滚动对比

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-12 16:06 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方线上版与 primary official candidate 的同窗口月度滚动多周期验证
- 是否重要突破：否，是候选边界确认
- 是否触发A/B：是，A/C 对比

## 外部调研与判断

- 参考资料：
  - vn.py 官方 README：portfolio strategy 模块支持多合约组合策略的历史回测与实盘自动交易。
  - Interactive Brokers Campus / QuantInsti / GitHub walk-forward 资料：rolling / walk-forward 的核心价值是用固定窗口前移，减少固定终点和单一起点偏差。
- 我的判断：
  - 本次不复制外部策略，只采用 walk-forward 的验证纪律。
  - 线上版和候选版必须在同一月度 3 年窗口上比较收益、回撤、Sharpe、保证金、生存线和失败尾部；不能只看候选早期右尾收益。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `DATA_START=2020-01-01`
  - `DATA_END=2026-05-29`
  - `ROLL_YEARS=3`
  - `TERMINAL_START=2023-06-01`
  - `STAGE824_MAX_WORKERS=6`
  - A：`official_live_stage372_20w_recovery_sleeve`，`account_capital/c3_capital=200000`
  - C：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`，`account_capital/c3_capital=300000`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：完整月度 3 年窗口从 `2020-01-01 -> 2022-12-31` 滚动到 `2023-05-01 -> 2026-04-30`，共 `41` 个；另加 terminal partial `2023-06-01 -> 2026-05-29`，合计 `42` 个窗口。
- 账户规模：线上版 `20万`；候选版 `30万`。
- 成本口径：沿用各自策略回测默认手续费/滑点；不做 2x/3x 成本压力。
- 样本过滤：只用双方共同可解释的 `2020-01` 起窗口；不把候选更早 `2018-2019` 样本混入线上版对比。
- 策略/归因口径：
  - A 当前线上默认：Stage372/Stage526 20w `force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
  - C 当前 primary official candidate：Stage819 30w，继承 Stage813 的 `AM41`、基础等效风险 `0.40`、`OI上升+价格沿方向` 恢复到 `0.80`、旧正式 AI、maxpos4、Stage804 多头更紧初始止损、`RSI95` 半平。

## 结果

### 聚合结果

| 版本 | 窗口数 | 正收益 | 收益中位数 | 收益 p10 | 最小收益 | 最大收益 | 回撤中位数 | 最差回撤 | DD40失败 | DD50失败 | Sharpe中位数 | Sharpe p10 | 总滑点 | 总交易次数 | 胜率中位数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 线上 Stage372 20w | 42 | 42 | `258.6550%` | `17.9935%` | `0.2175%` | `1179.6650%` | `-32.0894%` | `-39.1172%` | 0 | 0 | `1.3747` | `0.3748` | `1,561,175` | `9,599` | `51.3840%` |
| C 候选 Stage819 30w | 42 | 42 | `212.7592%` | `55.1280%` | `28.9200%` | `2228.7500%` | `-38.7314%` | `-44.7648%` | 18 | 0 | `1.2390` | `0.6849` | `5,307,760` | `9,601` | `52.7423%` |

### 同窗口对比

- C 收益胜出 `32/42`，收益差中位 `+98.9025pp`。
- C 回撤胜出仅 `5/42`，回撤差中位 `-6.0133pp`。
- C Sharpe 胜出 `25/42`，Sharpe 差中位 `+0.0345`。
- C 收益+回撤双胜仅 `3/42`。
- C 的 DD40 失败 `18/42`，A 为 `0/42`；C/DD50 与 A 均为 `0/42`。
- C 总滑点为 A 的约 `3.40x`，交易次数基本相同，说明主要不是“多交易”而是候选单笔/手数与路径风险更重。

### Terminal partial 窗口

| 版本 | 窗口 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 线上 Stage372 20w | `2023-06 -> 2026-05-29` | `440,265` | `120.1325%` | `-24.0477%` | `1.0629` | `14,610` | `161` | `50.4478%` | `59.3843%` |
| C 候选 Stage819 30w | `2023-06 -> 2026-05-29` | `820,645` | `173.5483%` | `-25.2356%` | `1.2205` | `46,160` | `156` | `52.7174%` | `63.1170%` |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_report_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_summary_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_curves_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_comparison_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_aggregate_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_decision_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.json`
- 资金曲线图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_selected_curves_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.png`
- return heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_return_heatmap_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.png`
- drawdown heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_dd_heatmap_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.png`
- sharpe heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_sharpe_heatmap_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.png`
- winner heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage824_official_vs_stage819_candidate_monthly_rolling3y_winner_heatmap_stage824_official_vs_stage819_candidate_monthly_rolling3y_v1.png`

## 结论

- 本阶段结论：`stage824_candidate_not_live_default_keep_stage372`。Stage819 30w 候选保留为 primary official candidate / shadow 观察臂，但不能替代当前线上默认 Stage372 20w。
- 是否进入下一步：进入候选 shadow / dry-run / 风险复核；不进入 live default。
- 下一步：
  - 若继续候选验证，只做最新交易日 shadow、执行 dry-run、broker-state reconciliation 和 DD40 容忍度风险复核。
  - 不继续扫本金、RSI 阈值、OI 倍率、AM 根数、AI topN、训练窗或 horizon。
  - 若目标是线上默认升级，必须先解决候选 2020/2021 起点穿越 2022 时的 DD40 失败，而不是用右尾收益覆盖回撤尾部。

## 过拟合反思

- 运行前判断：否，风险低到中等；本次窗口、指标和 A/C 臂在看结果前固定，且候选已提前登记。
- 运行后判断：否，本次验证本身不是过拟合；但如果据 30w 在 `32/42` 窗口收益胜出就切 live default，或继续扫本金/阈值救 DD40，就是过拟合。
- 原因：候选右尾强，但回撤胜率只有 `5/42`，DD40 失败 `18/42`；这不是单一窗口噪声，而是 2020/2021 起点穿越 2022 时的系统性左尾。

## 继续价值反思

- 运行前判断：有价值，因为这是当前线上默认与 primary candidate 的同窗口公平验证。
- 运行后判断：仍有价值，但范围要收缩。
- 原因：候选在 terminal partial 和多个后期窗口有收益/Sharpe 优势，说明可作为 shadow 观察臂；但回撤失败过多，不能继续用调小参数方式硬救。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage824 最新候选边界。
- 是否更新 `research/registry.md`：是，最新关键阶段更新为 Stage824。
- 是否追加根目录 `memory.md/back_log.md`：是，属于官方候选与线上默认的关键边界结论。
