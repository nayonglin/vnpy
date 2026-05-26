# Stage032 C3已有仓位风险释放真实引擎筛查

- 记录时间：`2026-05-26 00:54 CST`
- 当前模式：`day`
- 所属研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：真实回测引擎 A/C 筛查，不修改正式 Stage78-1，不修改 AI 池、品种池、入场 alpha 或供需强逆风过滤。
- 目标：在 `C3_supply_headwind` 底座上，把最大回撤压到 `30%` 以内，同时全周期收益保留 C3 至少 `80%`。

## 调研和判断

- 外部研究方向上，趋势策略的回撤控制常见方法包括波动率目标、组合风险预算、浮盈回吐保护和低相关收益源叠加。
- 本线 Stage031 的本地归因更关键：2021 最大回撤中 `96.7337%` 的亏损来自高点日已有仓位，回撤后新增/交易仓位只占 `3.2663%`。
- 因此本阶段不再继续优化新增开仓质量/数量，而是验证“已有仓位风险释放”能否触及主因。

## 本阶段新增内容

- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage332_c3_existing_position_release_screen.py`
- 新增结果文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage332_c3_existing_position_release_screen_summary_stage332_c3_existing_position_release_screen_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage332_c3_existing_position_release_screen_comparison_stage332_c3_existing_position_release_screen_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage332_c3_existing_position_release_screen_daily_stage332_c3_existing_position_release_screen_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage332_c3_existing_position_release_screen_decision_stage332_c3_existing_position_release_screen_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage332_c3_existing_position_release_screen_report_stage332_c3_existing_position_release_screen_v1.md`

## 参数与候选

- A 基准：`A_c3_supply_headwind`
  - C_pressure040 叠加供需强逆风过滤。
  - 资金 `500,000`
  - `base_risk_ratio=0.045`
- C 候选1：`C_profit_giveback_default`
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.08`
  - `profit_giveback_retain_ratio=0.70`
  - `profit_giveback_min_lock_pct=0.03`
  - 复用既有默认结构，不扫参数。
- C 候选2：`C_dd_delev_05_15_floor90`
  - `enable_portfolio_drawdown_deleverage=True`
  - `portfolio_drawdown_deleverage_start=0.05`
  - `portfolio_drawdown_deleverage_full=0.15`
  - `portfolio_drawdown_deleverage_floor=0.90`
- C 候选3：`C_dd_delev_05_15_floor85`
  - `enable_portfolio_drawdown_deleverage=True`
  - `portfolio_drawdown_deleverage_start=0.05`
  - `portfolio_drawdown_deleverage_full=0.15`
  - `portfolio_drawdown_deleverage_floor=0.85`
- C 候选4：`C_dd_delev_10_30_floor85`
  - `enable_portfolio_drawdown_deleverage=True`
  - `portfolio_drawdown_deleverage_start=0.10`
  - `portfolio_drawdown_deleverage_full=0.30`
  - `portfolio_drawdown_deleverage_floor=0.85`

## 全样本结果

| 版本 | 期末权益 | 总收益 | 收益保留 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | 触发次数 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `A_c3_supply_headwind` | `30,925,650` | `6085.1300%` | `100.0000%` | `-31.0767%` | `1.3663` | `1,556,750` | `757` | `45.3826%` | `0` | 基准 |
| `C_profit_giveback_default` | `22,021,210` | `4304.2420%` | `70.7338%` | `-30.3431%` | `1.2502` | `1,516,950` | `758` | `45.3826%` | 盈利回吐更新 `124` 次 | 未通过 |
| `C_dd_delev_05_15_floor90` | `10,353,130` | `1970.6260%` | `32.3843%` | `-37.2188%` | `0.9842` | `687,620` | `1089` | `52.8996%` | 降仓 `347` 次 | 未通过 |
| `C_dd_delev_05_15_floor85` | `8,893,225` | `1678.6450%` | `27.5860%` | `-34.0966%` | `0.9566` | `662,150` | `1090` | `53.8897%` | 降仓 `351` 次 | 未通过 |
| `C_dd_delev_10_30_floor85` | `9,773,690` | `1854.7380%` | `30.4798%` | `-36.9393%` | `0.9656` | `723,840` | `1023` | `50.8607%` | 降仓 `274` 次 | 未通过 |

## 阶段判断

- 决策标签：`screen_fail_no_full_sample_candidate`
- 没有候选同时满足：
  - 最大回撤进入 `30%` 以内；
  - 总收益保留 C3 至少 `80%`。
- 默认盈利回吐是最接近的候选，但最大回撤仍为 `-30.3431%`，且收益保留只有 `70.7338%`，收益牺牲过大。
- 组合回撤降仓形状在 C3 底座上明显破坏复利，并且最大回撤反而恶化，说明“回撤后被动降仓”不是这条线的答案。

## 修改/删除

- 新增参数：无正式参数；仅在独立筛查脚本中使用候选参数。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：见全样本结果表。
- 修改回测结果：无。
- 删除回测结果：无。

## 过拟合反思

- 运行前判断：不是过拟合。
- 原因：候选来自已有机制或粗档位组合回撤规则，没有新增品种黑名单、单窗口补丁或小数搜索。
- 运行后判断：继续围绕这批形状微调会变成过拟合。
- 原因：默认盈利回吐和回撤降仓均未满足全样本硬条件；如果继续把 `8%/70%/3%` 或 `5/15/85` 调成更细小数，本质是在救单次结果，而不是发现稳健结构。

## 继续价值反思

- 运行前判断：有价值。
- 原因：Stage031 显示剩余回撤来自高点已有仓位，必须验证已有仓位风险释放是否能触及主因。
- 运行后判断：研究线仍有价值，但本形状方向价值下降。
- 下一步：
  - 不继续扫默认盈利回吐参数。
  - 不继续扫组合回撤降仓阈值。
  - 若继续策略内方向，只能研究更低自由度、非回撤滞后的持仓风险释放机制。
  - 更现实的方向是账户/部署层锁盈、分账户或真正独立低相关收益源，而不是继续给 C3 加小阈值补丁。
