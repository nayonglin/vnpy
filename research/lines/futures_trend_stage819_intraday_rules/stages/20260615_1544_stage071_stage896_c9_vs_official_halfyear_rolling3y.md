# Stage071 Stage896 C9 vs 正式版半年步进3年滚动测试

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 15:44`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：多起点独立回放、鲁棒性审计；不新增交易规则、不调参。
- 是否重要突破：否。C9 收益右尾继续成立，但风险尾部不能替代正式版。
- 是否触发A/B：否。结果不满足正式替代或 A/B 候选闸门。

## 外部调研与判断

- 参考资料：
  - Interactive Brokers Campus 关于 walk-forward analysis 的说明：https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/
  - vn.py 官方 GitHub：https://github.com/vnpy/vnpy
- 我的判断：外部资料只确认方法论边界，即滚动/走步验证应使用预声明窗口与多段指标汇总；本次不能换成外部框架或简单净值切片。C9 与 Stage372 都有权益、持仓、连败、保证金等路径依赖，必须复用仓库内 vn.py portfolio engine 做每个窗口的独立冷启动回放。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage896_c9_vs_official_halfyear_rolling3y.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `DATA_START=2020-01-01`
  - `DATA_END=2026-05-29`
  - `ROLL_YEARS=3`
  - 步进：`6 months`
  - 完整窗口：`7` 个，`2020-01-01` 到 `2023-01-01` 半年步进。
  - 末端补充窗口：`2023-07-01 -> 2026-05-29`，标记为 `terminal_partial`，不参与主决策。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：完整窗口从 `2020-01-01 -> 2022-12-31` 到 `2023-01-01 -> 2025-12-31`；另含末端补充 `2023-07-01 -> 2026-05-29`。
- 账户规模：
  - A 正式版：`official_live_stage372_20w_recovery_sleeve`，本金 `200000`。
  - C9：`stage847_stage819_c4_05r_stop_retry_once`，来源 `official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`，本金 `300000`。
- 成本口径：沿用各自引擎配置的手续费、滑点、合约乘数和 broker10 保证金口径。
- 样本过滤：主判断只使用完整 3 年窗口；terminal partial 只作最近路径观察。
- 策略/归因口径：A 使用当前官方正式 Stage372 20万口径；C9 使用冻结的 `0.5R` 实时止损 + 原入场价重试一次语义，不改 R 倍数、不改重试次数、不改分钟窗口。

## 结果

- 主决策：`stage896_c9_right_tail_with_risk_tail_not_official_replacement`
- 完整 3 年窗口胜负：
  - C9 收益胜：`7/7`
  - C9 回撤胜：`1/7`
  - C9 Sharpe 胜：`6/7`
  - C9 broker10 胜：`0/7`
  - C9 收益+回撤双胜：`1/7`
- A 正式版完整窗口聚合：
  - 期末权益：窗口 raw 值范围约 `233,885 -> 2,559,330`，本金不同，主判定不使用绝对期末权益。
  - 总收益：中位 `259.6375%`，p10 `49.2075%`，最小 `16.9425%`，最大 `1179.6650%`。
  - 最大回撤：中位 `-36.9793%`，最差 `-39.1172%`。
  - Sharpe：中位 `1.3596`，p10 `0.6415`，最小 `0.3629`。
  - 总滑点：`305,250`
  - 总交易次数：`1,701`
  - 胜率：本脚本未额外聚合窗口非零日胜率；详见 summary CSV 的 `nonzero_daily_win_rate_pct`。
  - 其他关键指标：DD40 失败 `0`，DD50 失败 `0`，broker100 失败 `0`，peak broker10 `78.5348%`。
- C9 完整窗口聚合：
  - 期末权益：窗口 raw 值范围约 `746,325.1 -> 5,992,789.4`，本金不同，主判定不使用绝对期末权益。
  - 总收益：中位 `474.7780%`，p10 `213.4370%`，最小 `148.7750%`，最大 `1897.5965%`。
  - 最大回撤：中位 `-44.7242%`，最差 `-53.5522%`。
  - Sharpe：中位 `1.6840`，p10 `1.2321`，最小 `1.0151`。
  - 总滑点：`1,502,090`
  - 总交易次数：`1,917`
  - 胜率：本脚本未额外聚合窗口非零日胜率；详见 summary CSV 的 `nonzero_daily_win_rate_pct`。
  - 其他关键指标：DD40 失败 `5`，DD50 失败 `3`，broker100 失败 `3`，peak broker10 `122.0570%`；stop/retry events `231`，broker10 cap events `88`。
- 完整窗口相对差：
  - C9 收益中位优势：`+147.4604pp`
  - C9 回撤中位劣势：`-12.2722pp`
  - C9 Sharpe 中位优势：`+0.2393`
  - C9 broker10 中位劣势：`+25.9048pp`
- 末端补充窗口 `2023-07 -> 2026-05-29`：
  - A：收益 `6.1775%`，回撤 `-25.8102%`，Sharpe `0.2089`，broker10 `53.3787%`。
  - C9：收益 `169.8608%`，回撤 `-17.9153%`，Sharpe `1.2671`，broker10 `69.3362%`。
  - 判断：最近补充窗口 C9 收益/回撤都赢，但不足 3 年，不改变主决策。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_report_stage896_c9_vs_official_halfyear_rolling3y_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_summary_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_curves_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_decision_stage896_c9_vs_official_halfyear_rolling3y_v1.json`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_comparison_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_aggregate_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`

## 曲线图补充

- 补充时间：`2026-06-15 15:53`
- 新增脚本：`examples/portfolio_backtesting/plot_stage896_c9_vs_official_each_window_curves.py`
- 图表目录：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_charts_stage896_c9_vs_official_halfyear_rolling3y_v1/`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_charts_stage896_c9_vs_official_halfyear_rolling3y_v1/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_curve_charts_manifest_stage896_c9_vs_official_halfyear_rolling3y_v1.csv`
- 归一净值总览：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_charts_stage896_c9_vs_official_halfyear_rolling3y_v1/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_all_windows_nav_grid_stage896_c9_vs_official_halfyear_rolling3y_v1.png`
- 绝对权益总览：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_charts_stage896_c9_vs_official_halfyear_rolling3y_v1/qmt_roll_stage896_c9_vs_official_halfyear_rolling3y_all_windows_equity_grid_stage896_c9_vs_official_halfyear_rolling3y_v1.png`
- 每个周期单图：`8` 张，每张上半部分为 `rebased_nav` 归一净值、下半部分为 `rebased_equity` 绝对权益。

## 结论

- 本阶段结论：C9 的收益右尾和 Sharpe 优势真实存在，且多起点完整窗口 `7/7` 正收益并赢过正式版；但它不是正式版替代品，因为 `5/7` 完整窗口 DD40 失败、`3/7` DD50 失败、`3/7` broker100 失败，且 broker10 从未优于正式版。C9 更像高进攻性的右尾放大结构，不是穿越周期的生存线。
- 是否进入下一步：不进入正式 A/B，不替换 Stage372。只允许继续做风险尾部归因，重点看 C9 的 broker100/DD50 窗口是否来自持仓后产品方向簇、权益分母高水位回撤、或 stop/retry 后风险再使用。
- 下一步：若继续，应围绕 `2020-01/2020-07/2021-01` 这些 C9 DD50 与 broker100 失败窗口做只读归因；不要扫 `R` 倍数、重试次数、月份、品种、方向或窗口长度。

## 过拟合反思

- 运行前判断：否。本次窗口、步进、指标都在运行前固定，且不调参。
- 运行后判断：作为正式替代候选存在过拟合/路径依赖风险。C9 多赚但回撤和 broker10 尾部明显更差，说明此前全周期优势可能依赖右尾扩张和更高杠杆暴露。
- 原因：C9 改变了入场日止损/重试后的资金再使用路径，收益右尾被放大，但持仓后风险尾部没有被同步约束；这不是一个能穿越周期的单独交易规则。

## 继续价值反思

- 运行前判断：有价值。C9 曾是本线唯一正价值骨架，需要用多起点冷启动确认它是否只是单一路径优势。
- 运行后判断：有价值但方向收窄。继续价值不在推广 C9，而在解释 C9 的风险尾部，并把经验转成更上层、低自由度的账户/持仓风险约束。
- 原因：C9 收益胜 `7/7` 说明信号不是噪声，但 broker10 胜 `0/7` 和 DD50 失败 `3/7` 说明不能按交易规则层继续救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage071 摘要。
- 是否更新 `research/registry.md`：否，不涉及研究线新增、正式候选晋级或路线迁移。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破，不改正式候选。
