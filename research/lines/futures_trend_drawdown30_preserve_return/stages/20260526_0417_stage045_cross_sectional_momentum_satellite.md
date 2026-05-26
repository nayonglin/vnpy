# Stage045 商品横截面动量卫星净值层筛查

- 时间：`2026-05-26 04:17 CST`
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：低相关收益源净值层筛查；不修改78-1/C3正式信号、品种池、AI池、开平仓逻辑。
- 是否重要突破：是，出现新的净值层严格候选；但尚未进入真实资金/保证金/整数手数验证。

## 调研与判断

- 外部调研结论：商品期货横截面动量/相对强弱是成熟研究方向，经典思路是用过去一段时间收益排名做多强者、做空弱者；它和第78-1的单品种时间序列趋势不完全同源，因此有资格作为低相关卫星筛查。
- 我的判断：可以研究，但不能直接用结果去挑行业、删品种或微调窗口；本阶段只允许 `12-1个月`、`6-1个月` 两个粗窗口和低权重组合，避免把历史路径拟合成漂亮曲线。

## 版本变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage345_cross_sectional_momentum_satellite.py`
- 新增输出：
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_product_returns_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_features_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_satellite_daily_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_combo_daily_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_summary_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_window_summary_stage345_cross_sectional_momentum_satellite_v1.csv`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_decision_stage345_cross_sectional_momentum_satellite_v1.json`
  - `qmt_roll_stage345_cross_sectional_momentum_satellite_report_stage345_cross_sectional_momentum_satellite_v1.md`

## 参数

- 新增参数：
  - 动量窗口：`mom_12m_skip1m = 252日回看、跳过21日`；`mom_6m_skip1m = 126日回看、跳过21日`
  - 月度调仓：使用上一交易日可见特征
  - 多头数量：`TOP_N=3`
  - 空头数量：`BOTTOM_N=3`
  - 最少有效品种：`MIN_VALID_PRODUCTS=8`
  - 成本档位：`0/5/10/20bp`
  - 卫星权重：`2.5%/5%/7.5%/10%/20%/30%`
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 基准

- C3基准：期末权益 `30,925,650`，总收益 `6085.1300%`，最大回撤 `-31.0767%`，Sharpe `1.3663`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。

## 关键结果

- 卫星独立结果：
  - `xsmom_mom_12m_skip1m_cost0bps`：总收益 `85.1955%`，最大回撤 `-26.3948%`，Sharpe `0.8926`
  - `xsmom_mom_12m_skip1m_cost20bps`：总收益 `73.4987%`，最大回撤 `-26.4441%`，Sharpe `0.8051`
  - `xsmom_mom_6m_skip1m_cost0bps`：总收益 `0.9981%`，最大回撤 `-35.2714%`，Sharpe `0.0719`
- 最强候选：
  - `c3_92p5_xsmom_mom_12m_skip1m_7p5_cost0bps`：总收益 `4905.0924%`，收益保留 `80.6078%`，最大回撤 `-29.5320%`，Sharpe `1.6334`
  - `c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps`：期末权益约 `24,903,994`，总收益 `4880.7988%`，收益保留 `80.2086%`，最大回撤 `-29.5427%`，Sharpe `1.6317`
- 另一个净值层通过形状：
  - `c3_95_xsmom_mom_6m_skip1m_5_cost20bps`：总收益 `5097.8011%`，收益保留 `83.7747%`，最大回撤 `-29.9390%`，Sharpe `1.6171`
  - 但 `6-1个月` 卫星独立收益几乎为零，经济质量弱于 `12-1个月`，暂不作为主候选。

## 多周期

- `c3_92p5_xsmom_mom_12m_skip1m_7p5_cost20bps` 多周期全部通过：
  - `full_2020_2026`：收益保留 `80.2086%`，最大回撤 `-29.5427%`
  - `since_2021`：收益保留 `80.9906%`，最大回撤 `-29.5427%`
  - `since_2022`：收益保留 `85.0110%`，最大回撤 `-28.0163%`
  - `since_2023`：收益保留 `87.2498%`，最大回撤 `-17.2982%`
  - `since_2024`：收益保留 `91.0100%`，最大回撤 `-17.2982%`
  - `phase_2024_2025`：收益保留 `91.4710%`，最大回撤 `-17.2982%`
  - `ytd_2026`：收益保留 `93.5210%`，最大回撤 `-10.6133%`

## 决策

- 决策标签：`xsmom_satellite_screen_pass_requires_true_engine`
- 判断：`92.5% C3 + 7.5% 12-1个月横截面动量卫星` 是新的净值层候选。
- 但当前仍不能合入78-1，因为它只是日收益净值混合，未验证真实资金切分、保证金占用、合约整数手数、实际手续费滑点和持仓冲突。
- 下一步：用真实引擎做 `46.25万 C3 + 3.75万 卫星` 或等价名义风险拆分验证；若资金太小导致卫星腿整数手数失真，再评估是否只能作为账户级ETF/指数化对冲思路而非期货实盘腿。

## 过拟合反思

- 运行前判断：不是过拟合。横截面动量有独立经济含义，且我们没有按品种、年份、亏损窗口做黑名单。
- 运行后判断：当前候选有过拟合风险但尚可继续验证。风险来自 `7.5%` 是边界权重，虽然它来自粗粒度档位而非小数扫描；后续不得继续扫 `6.5%/7%/8%`，必须直接进入真实引擎反证。

## 继续价值反思

- 运行前判断：有价值，因为前面 Carry 和旧卫星都失败，仍需要寻找真正正收益、低相关的独立收益源。
- 运行后判断：有价值继续做下一关。`12-1个月` 卫星自身为正收益且低回撤，和 C3 组合多周期过线；但只有真实引擎验证后才可能成为正式候选。
