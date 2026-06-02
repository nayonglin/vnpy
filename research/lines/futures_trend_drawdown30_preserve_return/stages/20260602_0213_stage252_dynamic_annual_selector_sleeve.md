# Stage252 连续动态年度选品卫星仓审计

- 时间：2026-06-02 02:13 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：Stage251 语义偏差复核；A=`stage526_r080_pc25_maxpos4`，C=Stage526 核心不动 + 连续动态年度选品卫星仓。
- 是否重要突破：是，研究级。Stage251 的年度重启收益被明显压缩，但 `prev_year_top6/r050` 在连续动态语义下仍通过硬不劣化和材料性门槛。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage552_dynamic_annual_selector_sleeve.py`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage552_dynamic_annual_selector_sleeve_chart_stage552_dynamic_annual_selector_sleeve_v1.png`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage552_dynamic_annual_selector_sleeve_report_stage552_dynamic_annual_selector_sleeve_v1.md`
- 决策：`dynamic_annual_selector_promotion_candidate_found`。我的实际判断：进入下一验证阶段，不直接替代 Stage526。

## 版本变更

- 新增脚本：`analyze_qmt_roll_stage552_dynamic_annual_selector_sleeve.py`。
- 新增数据输出：
  - `qmt_roll_stage552_dynamic_annual_selector_sleeve_noncore_commodity_universe_stage552_dynamic_annual_selector_sleeve_v1.csv`
  - `qmt_roll_stage552_dynamic_annual_selector_sleeve_annual_eligibility_stage552_dynamic_annual_selector_sleeve_v1.csv`
- 新增参数：
  - 连续动态年度白名单通过已有 `enable_ai_product_pool_filter=True` 实现。
  - `ai_product_pool_strategy=dynamic_prevpos_r050_pc15_maxpos3/dynamic_prevtop6_r050_pc15_maxpos3`
  - `eval_date=YYYY-01-01`，只用上一年已知选择结果。
  - `risk_multiplier=0.50`、`product_cap_ratio=0.15`、`max_concurrent_positions=3`、`max_single_trade_capital_usage_ratio=0.35`
  - 同向相关性门控沿用 `lookback20/start0.60/full0.80/floor0.50`
- 修改参数：无正式策略默认参数修改；复用现有 AI 产品池过滤能力做年度白名单。
- 删除参数：无。
- 执行语义：非核心商品全集进入引擎，但每年 1 月 1 日只允许上一年已知选中产品新开仓；已有持仓不在年末强平，按原策略自然退出或换月。

## 关键结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 2x回撤 | 3x回撤 | 卫星PnL | 63日p05改善 | 126日p05改善 | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 | 23,369,505 | 3699.9195% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | -39.0565% | -42.0555% | 0 | 0.0000pp | 0.0000pp | 1,342,190 | 905 | 53.6330% |
| dynamic prevpos r050 | 23,362,305 | 3698.7488% | -36.4579% | 14.4880 | 1.6380 | 99.4407% | -39.2742% | -42.3026% | -7,200 | -0.0508pp | -0.0922pp | 1,345,590 | 1,064 | 53.3526% |
| dynamic top6 r050 | 23,422,160 | 3708.4813% | -36.0822% | 14.3839 | 1.6432 | 98.7159% | -38.8577% | -41.8410% | 52,655 | 0.2678pp | 0.2852pp | 1,346,350 | 1,105 | 53.7130% |

## 多窗口与持有体验

- `dynamic top6 r050` 全周期最大回撤 `-36.0822%`，仍低于 Stage526 的 `-36.2670%`。
- 2021-2022 弱窗口回撤 `-36.0822%`，未新增 broker10 穿越。
- 任意启动 63 日 p05 从 `-18.2169%` 改到 `-17.9491%`，改善 `0.2678pp`。
- 任意启动 126 日 p05 从 `-10.9700%` 改到 `-10.6848%`，改善 `0.2852pp`。
- 2x 成本最大回撤从 `-39.0565%` 改到 `-38.8577%`；3x 仍失败但从 `-42.0555%` 小幅改到 `-41.8410%`。

## 图表目检

- 权益曲线：动态 top6 与 Stage526 几乎重合，但 2022 后有轻微抬升；dynamic prevpos 在 2022 后逐渐走弱。
- 回撤曲线：dynamic top6 在 2021-2022 最深水下段略浅；没有出现额外深坑。
- 卫星PnL：dynamic top6 在 2021、2022、2024 贡献主要正收益，2023、2025 回吐；2026 没有明显贡献，说明 Stage251 的 2026 `lu` 放大效应被连续动态语义消掉。
- 年度PnL：dynamic top6 年度卫星PnL约为 2021 `20,300`、2022 `21,240`、2023 `-4,235`、2024 `20,010`、2025 `-4,660`、2026 `0`。
- 单产品集中度：最大贡献 `al.SHFE +17,300`，占卫星总PnL约 `32.86%`，低于 Stage251 中 `lu.INE` 的 `46.85%`。

## 结论

- `dynamic_prevtop6_r050_pc15_maxpos3` 是当前“选品 + 扩池 + 降单笔风险”方向里第一个值得继续验证的真实连续语义候选。
- 它不是大幅提升版本：总收益只比 Stage526 多 `8.5618pp`，账户层收益改善约 `0.2314%` 相对 Stage526；3/6个月左尾改善也只有 `0.27/0.29pp`。
- 它的价值在于：不劣化现有核心指标，同时用 11.5 万低风险卫星仓带来可见但很小的正 edge，并降低 broker10 最大占用到 `98.7159%`。
- `prev_year_positive` 不成立：扩得太宽后卫星PnL为负，说明“扩大品种池”不能无脑扩，必须保留选择压力。

## 后续规划

- 下一步只允许做验证，不允许调参：
  - 剔除最大贡献产品/年份的脆弱性审计。
  - 检查动态白名单 exact entry 记录，确认未在白名单生效日前开仓。
  - 对 `dynamic top6 r050` 做持仓连续性、产品族暴露和最大保证金日复盘。
  - 如仍通过，再考虑把年度白名单作为 paper 候选，不直接进入实盘。

## 反思

- 过拟合反思：运行前不是过拟合，因为只验证 Stage251 已筛出的结构，并复用已有年度白名单机制；运行后仍不能判为过拟合，但结果很窄，任何继续调 `topN/risk/cap` 都会进入过拟合。
- 继续价值反思：有价值，但价值从“找更高收益”收缩为“验证一个小而真实的低风险卫星 edge 是否可稳定 paper”。如果下一层剔除/白名单时点审计失败，应立即降级。
