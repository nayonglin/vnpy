# Stage426 连败严重档权益均线门控反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 15:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前正式 Stage372/20万连败风控账户状态门控验证
- 是否重要突破：否，关键负结论
- 是否触发A/B：是，A/C 隔离验证

## 外部调研与判断

- 参考资料：
  - JournalPlus equity curve glossary：权益曲线可以衡量账户路径健康度，也常见用权益均线作为交易/风险过滤。
  - Quantified Models `The Capital Curve`：capital/equity curve feedback 常用 30/60/90 周期均线开关，但作者也强调行业内并没有一致结论，核心难点是何时关、何时开。
  - Build Alpha `Equity Curve Trading Strategies`：权益曲线过滤可以作为资金管理技术，但不同策略适用方向不同，均线长度优化本身容易变成策略专属调参。
- 我的判断：用账户权益状态约束三连败严重 `0.1` 有第一性原理价值，因为单纯连败次数没有描述账户是否真的“生病”；但权益曲线均线是滞后状态变量，容易把强势期的防守关掉，也容易通过窗口长度拟合历史。因此本阶段只测一个预声明 `200` 交易日版本，不扫 `100/150/250`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod.py`
- 修改脚本：无正式策略修改；仅新增 wrapper，并在回测期间 monkeypatch，运行结束恢复原方法。
- 删除脚本：无
- 新增参数：
  - `EQUITY_MA_MODE=stage712_loss_streak_equity_ma_gate`
  - `EQUITY_MA_LOOKBACK=200`
  - `GATE_AUDIT` 审计计数
- 修改参数：
  - C 分支保持 `streak_risk_multipliers=1.0,1.0,1.0,0.1` 不变。
  - C 分支仅在账户权益低于前 `200` 个交易日权益均线时，才保留三连败后的严重 `0.1`；若权益高于均线，则三连败严重档暂按 `1.0` 处理。
  - 权益历史只使用上一交易日及以前的策略权益；历史不足 `200` 天时保持正式 `0.1` 行为，避免短样本硬拟合。
  - 通过 `streak_profit_recovery_mode=stage712_loss_streak_equity_ma_gate` 作为候选哨兵启用，A 正式分支不启用。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本，并补 `2x/3x` 滑点压力
- 样本过滤：Stage707 同口径多起点与阶段独立启动窗口
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：A + 连败严重 `0.1` 的权益 MA200 门控，正式配置不变、不连接 CTP、不调用下单

## 结果

- 决策：`loss_streak_equity_ma_gate_not_promoted`
- hard_fail_checks：`full_return_retention_ge80`、`full_dd30_pass`、`cost2_full_dd40_pass`、`start_years_min_retention_ge70`、`start_years_dd_not_worse_by_3pp`、`start_years_dd40_all_pass`
- watch_checks：`full_sharpe_not_lower`
- A 全周期：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次 / `299` 手
- C 全周期：
  - 期末权益 `4,549,425`
  - 总收益 `2174.7125%`
  - 最大回撤 `-43.7752%`
  - Sharpe `1.3746`
  - 总滑点 `366,170`
  - 总交易次数 `648`
  - 胜率 `52.2847%`
  - broker10 峰值 `80.6569%`
  - 强制减仓 `6` 次 / `278` 手
- C 相对 A：
  - 收益保留 `51.0000%`
  - 期末权益少 `4,178,860`
  - 最大回撤恶化 `5.1039pp`
  - Sharpe 少 `0.2533`
  - 交易多 `15` 笔
  - 2x 成本全周期 DD 从 A 的 `-40.6555%` 恶化到 C 的 `-46.3242%`
- 多起点关键结果：
  - `since_2021`：A `2221.3050%/-38.1656%/Sharpe1.5636`；C `1062.4250%/-41.5029%/Sharpe1.2629`，收益保留 `47.8289%`
  - `since_2022`：A `133.8550%/-28.0550%/Sharpe0.8895`；C `161.0000%/-28.0550%/Sharpe0.8576`
  - `since_2023`：A `70.2100%/-24.5662%/Sharpe0.7818`；C `157.4425%/-22.7019%/Sharpe1.0206`
  - `since_2024`：A `33.3550%/-29.4347%/Sharpe0.5945`；C `151.6775%/-25.4740%/Sharpe1.1683`
  - `since_2025`：A `17.9975%/-17.6662%/Sharpe0.6589`；C `89.2100%/-23.1815%/Sharpe1.3001`
  - `since_2026`：A/C 完全一致 `1.1450%/-16.3027%/Sharpe0.2783`，因为历史不足 `200` 天保持原规则
- 分段关键结果：
  - `phase_2020_2021`：A `441.4650%/-24.2699%/Sharpe2.1114`；C `294.1700%/-30.4394%/Sharpe1.7685`
  - `phase_2022_2023`：A `0.2975%/-28.0550%/Sharpe0.1053`；C `12.5825%/-28.0550%/Sharpe0.4007`
  - `phase_2024_2025`：A `33.2675%/-29.4347%/Sharpe0.6398`；C `130.4850%/-25.4740%/Sharpe1.2492`
  - `phase_2026_latest`：A/C 完全一致 `1.1450%/-16.3027%/Sharpe0.2783`
- 年度全路径：
  - C 在 2020 小幅好于 A：`+159,600` vs `+144,230`
  - C 在 2021 明显少赚：`+428,740` vs A `+738,700`
  - C 在 2022 转负：`-19,940` vs A `+172,115`
  - C 在 2023-2025 仍能赚钱，但因为早期底座被打低，全周期追不上 A
- 门控审计：
  - `equity_ma_mode_calls=31,303`
  - `severe_tier_calls=8,568`
  - `insufficient_history_keep_calls=80`
  - `below_ma_keep_calls=4,696`
  - `above_ma_bypass_calls=3,792`
  - `min_equity_to_ma_ratio=0.7471`
  - `max_equity_to_ma_ratio=1.8151`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_report_stage712_loss_streak_equity_ma_gate_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_summary_stage712_loss_streak_equity_ma_gate_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_comparison_stage712_loss_streak_equity_ma_gate_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_checks_stage712_loss_streak_equity_ma_gate_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_decision_stage712_loss_streak_equity_ma_gate_multiperiod_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage712_loss_streak_equity_ma_gate_multiperiod_chart_stage712_loss_streak_equity_ma_gate_multiperiod_v1.png`

## 结论

- 本阶段结论：不晋级，不接正式版，不继续扫权益均线窗口。
- 关键原因：该机制在 `2023/2024/2025` 起点明显改善，说明“连败严重档太机械”确实有局部问题；但全周期收益只保留 `51.0000%`，最大回撤恶化到 `-43.7752%`，`since_2021` 也恶化到 `-41.5029%`，2x 成本 DD 恶化到 `-46.3242%`。它本质上把 2020-2021 强势期的正式防守关掉，破坏早期复利底座，不能穿越周期。
- 机制含义：账户状态门控方向仍有思想价值，但权益 MA 这种滞后单变量不够稳。它能在某些后段窗口恢复被 `0.1` 压住的机会，但会在另一条启动路径里放大坏交易，属于路径依赖强的风险开关。
- 是否进入下一步：否。
- 下一步：不要继续扫 `100/150/250` 日权益均线，不要改成权益 EMA 或均线斜率救参。若继续总目标，应从更上游的账户级 selector、真实 paper/forward 准入、或“固定 quarterly forward watch 的 Stage421 all-cases recovery”入手，而不是继续改主账户连败触发器。

## 过拟合反思

- 运行前判断：否。候选是固定 `200` 日账户权益状态门控，不按品种、年份、鸡蛋、红框窗口或收益结果筛选，也不扫窗口。
- 运行后判断：继续救该形态会过拟合。
- 原因：它在 `since_2023/2024/2025` 和 `phase_2024_2025` 很好，但在 `full/since_2021/phase_2020_2021` 坏掉；如果继续调均线长度、EMA、斜率或双阈值，就是用历史路径挑开关。

## 继续价值反思

- 运行前判断：有价值，因为它直接验证“单纯连败次数不应决定严重降仓，账户整体状态应参与判断”的低自由度版本。
- 运行后判断：该版本无继续价值，但总目标仍有价值。
- 原因：它证明账户状态有局部解释力，也证明滞后权益 MA 不够稳。下一步不应继续在主账户连败门控上加条件，而应转向更上游的信号质量/账户级 selector，或只做预声明 forward watch。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage426 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为“权益均线门控不再扫参”的重要边界。
