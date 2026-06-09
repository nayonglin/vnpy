# Stage006 C50 逐月独立启动验证

- line_id：`futures_trend_quarter_risk_no_streak`
- 当前模式：`day`
- 记录时间：2026-06-09 10:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：C50 逐月独立启动稳健性验证
- 是否重要突破：否，重要负结论
- 是否触发A/B：是；已读取并遵循 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- 参考资料：
  - `https://www.stator-afm.com/tutorial/fixed-fractional-position-sizing/`
  - `https://protraderdashboard.com/blog/fixed-fractional-sizing/`
  - `https://crosstrade.io/learn/risk-management/position-sizing`
- 我的判断：固定比例/固定风险 sizing 的核心是先算账户风险预算，再除以止损距离与合约乘数得到手数；期货整数手会让小本金账户产生明显颗粒度误差。逐月启动不是优化参数，而是扰动起点验证路径依赖，因此适合检验 C50 的改善是否普遍。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare.py`
- 修改脚本：无正式策略修改；脚本内新增并行隔离逻辑 `_install_stable_c3_overrides`，避免多个 worker 同时重建共享 universe/eligibility CSV 导致读空文件。
- 删除脚本：无
- 新增参数：`MODEL_TAG=stage749_half_risk_no_streak_500k_monthly_start_compare_v1`、`MAX_WORKERS=4`、`A_ARM=A_official_20w`、`C_ARM=C50_r040_no_streak`
- 修改参数：C50 沿用 Stage748，`account_capital/c3_capital=500000`，`risk_multiplier=0.40`，`streak_risk_multipliers=1.0,1.0,1.0,1.0`，关闭 `enable_streak_entry_structure_risk_recovery` 和 `enable_recovery_sleeve`
- 删除参数：无
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单

## 回测/归因参数

- 数据区间：`2020-01` 至 `2026-04` 共 `76` 个逐月独立启动，统一终点 `2026-04-30`
- 账户规模：A 正式 `200,000`；C50 `500,000`；C20 对照复用 Stage747 `200,000`
- 成本口径：正常成本、2x成本、3x成本压力结果均输出
- 样本过滤：A 正式逐月结果复用 Stage744；C20 逐月结果复用 Stage747；C50 重新逐月回测
- 策略/归因口径：A vs C50 使用收益率、NAV、回撤、Sharpe、交易次数对比；C50 vs C20 用于检验本金粒度改善是否普遍

## 结果

- 决策：`half_risk_no_streak_500k_monthly_start_not_promoted`
- 硬失败项：`full_2020_01_return_retention_lt35`、`full_2020_01_c_dd30_fail`、`mature252_c_return_wins_lt45pct`、`mature252_median_return_delta_negative`
- 观察项：`all_c_both_wins_not_more_than_a_both_wins`
- 2020-01 起点 A：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`
- 2020-01 起点 C50：期末权益 `5,565,350`，总收益 `1013.0700%`，最大回撤 `-39.7082%`，Sharpe `1.3285`，总滑点 `470,250`，总交易次数 `686`，胜率 `52.7165%`；收益保留 `23.7579%`
- 全体 `76` 个起点：C50 收益胜出 `23/76`，回撤胜出 `35/76`，收益和回撤同时胜出 `10/76`；A 收益和回撤同时胜出 `28/76`。C50 正收益 `67/76`，A 正收益 `73/76`；C50 DD40 失败 `5/76`，A DD40 失败 `1/76`。
- 全体中位数：C50-A 收益差 `-21.7448pp`，收益保留中位数 `70.5096%`，回撤差中位数 `-0.5518pp`。
- 成熟 `>=252` 交易日样本 `64` 个：C50 收益胜出 `21/64`，回撤胜出 `31/64`，收益和回撤同时胜出 `9/64`；C50/A 均 `64/64` 正收益；C50 DD40 失败 `5/64`，A DD40 失败 `1/64`；收益差中位数 `-40.7663pp`，收益保留中位数 `77.4442%`，回撤差中位数 `-0.1245pp`。
- 年份结构：`2020` 起点 C50 收益胜出 `0/12`、收益保留中位数 `26.5201%`、DD40 失败 `5/12`；`2021` 收益胜出 `2/12`；`2022` 收益胜出 `3/12`、回撤胜出 `9/12`；`2023` 收益胜出 `6/12`、回撤胜出 `12/12`、收益保留中位数 `95.1322%`；`2024` 收益胜出 `8/12`、收益保留中位数 `211.3870%`，但回撤差中位数 `-0.8705pp`；`2025` 收益胜出 `3/12`、C50 正收益仅 `7/12`；`2026` 收益胜出 `1/4`、C50 正收益 `0/4`。
- C50 vs C20：全体起点 C50 收益胜出 `73/76`，回撤胜出 `20/76`，收益差中位数 `+18.2448pp`，回撤差中位数 `-0.6969pp`，交易数差中位数 `+34`；成熟样本 C50 收益胜出 `62/64`，回撤胜出 `11/64`，收益差中位数 `+24.0095pp`，回撤差中位数 `-0.7927pp`，交易数差中位数 `+35`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_report_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_summary_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- candidate_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_candidate_summary_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_comparison_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- comparison_c20：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_comparison_c20_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_cost_stress_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_curves_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_chart_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.png`
- heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_heatmap_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.png`
- c20_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage749_half_risk_no_streak_500k_monthly_start_compare_c20_chart_stage749_half_risk_no_streak_500k_monthly_start_compare_v1.png`

## 结论

- 本阶段结论：C50 对 C20 的改善非常稳定，说明 20万 C 版本确实受到小本金和整数手颗粒度压制；但 C50 与正式 A 相比仍不稳，尤其 `2020/2021` 起点明显破坏复利底座，`2025/2026` 短样本也弱。
- 是否进入下一步：不进入正式版，不继续用本金放大救参。
- 下一步：停止固定低风险关闭连败路线。若继续低回撤体验，应转账户层资金分层、出金/锁盈、生存线或独立 sleeve；如果继续研究资金粒度，只能作为“账户规模适配”研究，而不能当作 alpha 改进。

## 过拟合反思

- 运行前判断：不是过拟合。逐月启动是稳健性检验，只扰动起点，不新增信号条件或历史阈值。
- 运行后判断：结论不是过拟合，但若根据 `2023/2024` 局部强势继续调本金、倍率或年份门控，会变成过拟合。
- 原因：C50 的优势主要来自资金粒度和可开仓手数改善，而不是更强的机会识别；它没有穿越早期高复利路径和 2025/2026 短样本。

## 继续价值反思

- 运行前判断：有价值，因为 Stage005 只看少数窗口，仍需确认 C50 是否对不同启动月份普遍改善。
- 运行后判断：本阶段有价值，但路线本身没有继续推广价值。
- 原因：C50 几乎普遍强于 C20，但仍不能打败正式版；问题已经从“本金太小”转化为“关闭连败低风险壳本身牺牲右尾复利”。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是
