# Stage018 低相关收益腿库存审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 记录时间：2026-07-02 05:41 CST
- 阶段性质：只读输入链/复用可行性审计，不产生策略候选，不改官方实盘。
- 决策：`stage018_rebuild_xsmom_inputs_first_keep_readonly`

## 调研判断

- 外部资料支持趋势系统通过跨规则、跨市场、低相关收益源提升稳健性；但公开简化回测不能替代本仓库的整数手、保证金、成交约束。
- 历史 Stage208 说明 xsmom 低相关腿有过正向路径价值；Stage214 说明旧候选在精确保证金下不能直接部署。
- 因此本阶段只判断输入链是否可复用，不把旧 Stage079 口径硬套到当前 C9/15w。

## 缺失项

| name                              | group                            | required_for                                 | status   | missing_columns                                                   | path                                                                                                                                                                     |
|:----------------------------------|:---------------------------------|:---------------------------------------------|:---------|:------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| stage352_combo_daily              | old_xsmom_output                 | 旧 Stage402/403 xsmom 复用输入               | missing  |                                                                   | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_combo_daily_stage352_xsmom_overlay_cash_multiperiod_v1.csv              |
| stage352_margin                   | old_xsmom_output                 | 旧 Stage402/403 xsmom 保证金输入             | missing  |                                                                   | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage352_xsmom_overlay_cash_multiperiod_margin_stage352_xsmom_overlay_cash_multiperiod_v1.csv                   |
| stage508_true_xsmom_daily         | old_xsmom_output                 | 旧 Stage508 真承载日度输出                   | missing  |                                                                   | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage508_xsmom_true_carry_replay_daily_stage508_xsmom_true_carry_replay_v1.csv                                  |
| stage513_exact_margin_daily       | old_xsmom_output                 | 旧 Stage513 精确保证金输出                   | missing  |                                                                   | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage513_stage208_exact_position_margin_audit_margin_daily_stage513_stage208_exact_position_margin_audit_v1.csv |
| stage345_product_returns          | xsmom_raw_input                  | 重建 standalone xsmom 的产品收益输入         | missing  | date,product_vt_symbol,main_contract_vt,main_close,product_return | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage345_cross_sectional_momentum_satellite_product_returns_stage345_cross_sectional_momentum_satellite_v1.csv  |
| stage345_satellite_daily          | xsmom_raw_input                  | 重建 standalone xsmom 的横截面信号输入       | missing  | date,long_products,short_products                                 | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage345_cross_sectional_momentum_satellite_satellite_daily_stage345_cross_sectional_momentum_satellite_v1.csv  |
| stage847_c9_full_period_positions | current_c9_full_period_positions | 当前 C9 全周期逐日持仓，用于真组合保证金叠加 | missing  | date,vt_symbol,end_pos,margin                                     | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_positions_stage847_stage830_c4_stop_retry_engine_v1.csv                  |

## 可用项

| name                    | group                     | required_for                       |   size_bytes | path                                                                                                                                                       |
|:------------------------|:--------------------------|:-----------------------------------|-------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------|
| stage208_record         | historical_xsmom_evidence | 历史 xsmom 真承载正向证据          |         6736 | research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1809_stage208_xsmom_true_carry_replay.md                                           |
| stage214_record         | historical_xsmom_evidence | 历史 xsmom 精确保证金否决证据      |         8847 | research/lines/futures_trend_drawdown30_preserve_return/stages/20260601_1851_stage214_stage208_exact_position_margin_audit.md                              |
| stage167_c9_curves      | current_c9_margin         | 当前重建 C9 多起点曲线和保证金字段 |     40593773 | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage167_c9_live_15w_multiperiod_ai_audit_curves_stage167_c9_live_15w_multiperiod_ai_audit_v1.csv |
| stage847_c9_curve       | current_c9_curve          | 当前 C9 单母本曲线                 |      3574923 | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_curve_stage847_stage830_c4_stop_retry_engine_v1.csv        |
| stage847_c9_closed_lots | current_c9_trade_lots     | 当前 C9 成交 lot 归因              |       253607 | examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv  |

## 结论

- 能否直接复用旧 xsmom 输出：`False`。
- 能否现在重建 standalone xsmom：`False`。
- 当前 C9 曲线/保证金字段是否可用：`True`。
- 当前 C9 全周期逐日 positions 是否可用：`False`。
- 能否现在跑当前 C9 + xsmom 真组合：`False`。
- 下一步：先重建 Stage345 product_returns/satellite_daily，再按当前 C9 独立资金袖做非挤占 proxy。

## 过拟合反思

- 运行前判断：否。原因：本阶段不调参数、不筛日期/品种/方向，只审计输入链和历史证据。
- 运行后判断：否。原因：负向缺口被保留，没有为了目标强行把旧输出当现成候选。

## 继续价值反思

- 运行前判断：是。原因：目标需要低相关收益源或新外生 PIT 信息，xsmom 是已有历史正向线索。
- 运行后判断：是，但必须先补输入链。原因：当前缺的是可复验的当前口径 xsmom 原始输入和 C9 全周期持仓，而不是再扫 C9 风控小参数。
