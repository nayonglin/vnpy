# Stage021 - 入场后质量确认仓真实 A/C 反证

- 时间：2026-06-08 23:24 CST
- 研究线：`futures_trend_winner_trade_forensics`
- 是否重要突破版本：否，属于重要反证版本。
- 决策：`postentry_quality_add_real_ac_not_promoted_global_lock_interaction`

## 调研与判断

- 外部/GitHub 调研结论：趋势跟随中的 pyramiding / add-to-winners 有通用第一性原理支持，即只在市场证明方向后增加风险；但资料也强调必须有独立风险控制，不能把代理收益当真实成交收益。
- 本次判断：Stage020 overlay 还没有处理真实策略反身影响，因此必须做 A/C。运行前不是明显过拟合，因为只验证两个预声明特征和固定 `0.5x`；运行后证明 overlay 明显高估，不能上线。

## 版本改动

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage738_postentry_quality_add_real_ac.py`
- 修改策略：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增参数：
  - `enable_post_entry_quality_add`
  - `post_entry_quality_add_feature`
  - `post_entry_quality_add_volume_multiplier=0.5`
  - `post_entry_quality_add_max_layers=1`
  - `post_entry_quality_add_use_day_extreme_stop=True`
  - `post_entry_quality_add_body_pct_min=0.60`
  - `post_entry_quality_add_body_ratio_min=0.50`
  - `post_entry_quality_add_directional_close_strength_min=0.60`
  - `post_entry_quality_add_short_wick_ratio_min=0.50`
  - `post_entry_quality_add_long_wick_ratio_max=0.20`
  - `post_entry_quality_add_adverse_wick_pct_max=0.25`
- 修改参数：Stage738 候选显式使用 `post_entry_quality_add_triggers_add_profit_lock=True`，复刻首版真实接入时确认仓触发原有成熟加仓锁盈的行为。
- 删除参数：无。

## A/C 定义

- A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- C1：A + `post1_body60_ratio_ge50` 确认仓，手数 `floor(base_volume * 0.5)`
- C2：A + `post1_avg_directional_close_strength_ge60` 确认仓，手数 `floor(base_volume * 0.5)`

## 回测结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 确认仓信号 | 不足一手 | 实际确认仓 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式 | 8,728,285 | 4264.1425% | -38.6713% | 1.6279 | 506,220 | 633 | 52.2586% | 0 | 0 | 0 |
| C1 body60 | 1,880,045 | 840.0225% | -37.3279% | 1.2248 | 141,720 | 660 | 51.4815% | 76 | 18 | 38 |
| C2 dirclose | 721,720 | 260.8600% | -38.5074% | 0.8202 | 90,010 | 686 | 51.6811% | 125 | 26 | 75 |

## 多起点要点

- C1 全周期收益保留仅 `19.6997%`，`since_2022` 收益保留 `28.7849%`，`phase_2020_2021` 收益保留 `44.4112%`。
- C2 全周期收益保留仅 `6.1175%`，`since_2022` 收益保留 `55.3080%`，`phase_2024_2025` 收益保留 `71.9170%` 且回撤恶化 `-9.1891pp`。
- C1/C2 都未通过预声明闸门：全周期权益增量、Sharpe、多起点收益保留、部分阶段回撤。

## 归因

- 真实确认仓不是被交易成本拖垮：C1/C2 总滑点反而显著低于正式版。
- 核心失败来自路径反身影响：一旦有 `post_quality` 加仓层，原策略的 `_apply_add_position_profit_lock` 会把所有 layer 的止损抬/压到加仓后均价附近，等价于“第一根确认 K 后过早锁主仓”，导致后续大趋势右尾被提前截断。
- 因此 Stage020 overlay 的假设缺口很大：overlay 只叠加确认仓 PnL，没有模拟它对主仓止损、退出、强制减仓、后续复利的影响。

## 过拟合反思

- 运行前：否。只测试两个预声明特征，固定 `0.5x`，没有按红框调阈值。
- 运行后：继续救 Stage738 形状会过拟合；但“解耦确认仓和成熟加仓锁盈”是结构性归因验证，不属于调参，可单独做 Stage022。

## 继续价值

- 本 Stage738 形状无继续价值，不晋级。
- 仍有一次机制复验价值：确认仓是否只是不应触发全局成熟加仓锁盈。后续进入 Stage022。

## 输出

- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage738_postentry_quality_add_real_ac_chart_stage738_postentry_quality_add_real_ac_v1.png`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage738_postentry_quality_add_real_ac_report_stage738_postentry_quality_add_real_ac_v1.md`
- 决策：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage738_postentry_quality_add_real_ac_decision_stage738_postentry_quality_add_real_ac_v1.json`
