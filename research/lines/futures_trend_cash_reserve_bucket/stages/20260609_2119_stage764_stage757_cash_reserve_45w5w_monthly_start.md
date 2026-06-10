# Stage002 / Script764 Stage757 + 45万交易桶/5万备用金逐月启动验证

- line_id：`futures_trend_cash_reserve_bucket`
- 当前模式：`day`
- 记录时间：`2026-06-09 21:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：用户指定资金结构复验，A/B 月度启动审计
- 是否重要突破：否，关键负结论
- 是否触发A/B：是，资金结构可能被误接为正式增强，按 A/B 纪律处理

## 外部调研与判断

- 参考资料：
  - `https://journalplus.co/learn/glossary/fixed-fractional`
  - `https://tradevae.com/academy/risk-management/position-sizing/fixed-dollar-risk-explained/`
  - `https://www.stator-afm.com/tutorial/fixed-fractional-position-sizing/`
  - `https://arxiv.org/abs/2309.09094`
- 我的判断：
  - 固定比例/固定风险 sizing 的第一性原理是 `账户权益 * 风险比例 / 每手止损风险` 决定可开手数，早期亏损会机械压低后续风险预算。
  - 备用金是资金管理与路径风险工具，不是 alpha；它只有在多起点上普遍降低路径依赖、且不显著牺牲强趋势参与度时才有正式价值。
  - 本次 `45/5` 是用户指定结构；为了避免从 `40/10` 失败后继续扫参救窗口，本阶段只跑单点，不继续展开 `42/8`、`47/3` 等比例。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `candidate_total_capital=500000`
  - `candidate_trading_bucket_capital=450000`
  - `candidate_reserve_capital=50000`
  - `enable_cash_reserve_bucket=True`
  - `cash_reserve_bucket_trading_target=450000`
  - `cash_reserve_bucket_initial_reserve=50000`
- 修改参数：
  - C 相对 Stage757 只把 `c3_capital` 从 `500000` 改为 `450000`，并增加 5万备用金补款桶。
  - Stage757 原有 `risk_multiplier=0.40`、OI 命中恢复到等效 `0.80`、关闭连败缩放和 recovery sleeve 均不变。
- 删除参数：无

## 回测/归因参数

- 数据区间：逐月独立起点 `2020-01` 至 `2026-05`，统一终点 `2026-05-29`。
- 账户规模：总资金 `500,000`；A 交易资金 `500,000`；C 交易桶 `450,000` + 备用桶 `50,000`。
- 成本口径：沿用现有手续费/滑点，另输出成本压力表。
- 样本过滤：无；全 77 个逐月起点。
- 策略/归因口径：
  - A：Stage757 `stage526_500k_force95_to80_r040_oi_confirm_r080_no_streak_no_recovery_stage757`。
  - C：`stage526_500k_total_450k_bucket_50k_reserve_oi_restore_stage764`。

## 结果

- A `2020-01` 起点：期末权益 `9,171,130`，总收益 `1734.2260%`，最大回撤 `-41.6458%`，Sharpe `1.4222`，总滑点 `901,820`，总交易次数 `691`，胜率 `52.5192%`。
- C `2020-01` 起点：期末权益 `8,554,870`，总收益 `1610.9740%`，最大回撤 `-42.6206%`，Sharpe `1.3998`，总滑点 `852,290`，总交易次数 `689`，胜率 `52.4618%`。
- 逐月全体 `77` 起点：
  - A 正收益 `67/77=87.0130%`，中位收益 `130.7660%`，p10 `-7.0682%`，最差 `2026-02=-17.4900%`，最佳 `2020-05=2569.0680%`，DD40失败 `24/77`。
  - C 正收益 `67/77=87.0130%`，中位收益 `126.4710%`，p10 `-7.1868%`，最差 `2026-02=-16.9380%`，最佳 `2020-03=2338.7380%`，DD40失败 `23/77`。
  - C 收益胜出 `33/77=42.8571%`，回撤胜出 `47/77=61.0390%`，中位收益差 `-1.6720pp`，中位收益保留 `95.9911%`，备用金使用 `65/77`，中位使用 `36,135`。
- 成熟 `>=252` 交易日 `65` 起点：
  - A `65/65` 正收益，中位收益 `181.7670%`，p10 `65.9120%`，最差 `2025-05=44.5380%`，DD40失败 `24/65`。
  - C `65/65` 正收益，中位收益 `161.6840%`，p10 `78.7112%`，最差 `2025-05=37.0860%`，DD40失败 `23/65`。
  - C 收益胜出 `24/65=36.9231%`，回撤胜出 `39/65=60.0000%`，中位收益差 `-5.1900pp`，中位收益保留 `96.4104%`，备用金使用 `53/65`。
- 重点 `2022-05`：
  - A `1,306,475/161.2950%/-35.9487%/Sharpe0.8743`。
  - C `1,305,795/161.1590%/-36.4887%/Sharpe0.8762`，备用金 `2022-05-06` 一次补满 `50,000`。
  - C 相对 A 收益 `-0.1360pp`，回撤 `-0.5400pp`，没有修复价值。
- 最伤收益的起点：`2020-07 -668.557pp`、`2020-06 -561.446pp`、`2020-05 -356.763pp`、`2020-10 -250.120pp`、`2020-04 -228.026pp`。
- 收益改善最大的起点：`2020-02 +363.250pp`、`2024-01 +30.274pp`、`2023-05/06 +25.456pp`、`2025-01 +20.299pp`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_report_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_summary_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_comparison_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_curves_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.csv`
- reserve_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_reserve_events_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_chart_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.png`
- heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage764_stage757_cash_reserve_45w5w_monthly_start_heatmap_stage764_stage757_cash_reserve_45w5w_monthly_start_v1.png`

## 结论

- 本阶段结论：`45万交易桶/5万备用金` 不晋级，决策 `stage757_cash_reserve_45w5w_not_promoted`。
- 是否进入下一步：不沿这个比例继续扫参。
- 下一步：
  - 停止在备用桶比例上救参数。
  - 如果继续账户层路径依赖研究，优先考虑不降低初始交易能力的“外层风险准备金/出金锁盈/生存线”，而不是把交易桶从 50万缩小。

## 过拟合反思

- 运行前判断：中等过拟合风险。
- 运行后判断：本轮单点验证本身不是过拟合，但继续扫比例会过拟合。
- 原因：`45/5` 是 `40/10` 失败后的相邻资金结构，容易围绕个别路径救参；结果显示它只是收益和回撤之间的资金管理权衡，没有形成跨周期 alpha 或质量选择。

## 继续价值反思

- 运行前判断：有有限价值。
- 运行后判断：本形态无继续价值，但账户层路径依赖研究仍有价值。
- 原因：C 的回撤胜率较高、DD40 少 1 个，说明资金分层确实能改变路径风险；但成熟样本收益胜出仅 `24/65`，且 2020 强趋势路径大幅损失，不能替代 Stage757 或正式口径。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，避免频繁改总索引；待合入整理时统一更新。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
