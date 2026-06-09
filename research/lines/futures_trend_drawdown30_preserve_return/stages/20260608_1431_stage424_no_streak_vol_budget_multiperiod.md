# Stage424 关闭全局连败 0.1 + 60日组合波动预算替代验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 14:31 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式 Stage372/20万风控结构替代反证
- 是否重要突破：否。该阶段明确反证“关闭连败 cliff，用组合波动预算替代”的简单结构。
- 是否触发A/B：是，属于可能替代正式风控机制的候选。

## 外部调研与判断

- 参考资料：
  - CME `Quantifying CTA Risk Management`：趋势组合通常把信号与风险管理分离，再用波动、相关性和组合约束设定仓位。
  - AQR `Trend Following`：趋势跟踪长期价值来自多市场趋势暴露和规则化风险控制，不能用短窗口补丁替代长期稳健性。
  - Kim/Tse/Wald 及 Moreira/Muir 相关波动管理研究：波动缩放有理论依据，但必须落在真实交易仓位和成本路径上验证。
- 我的判断：用组合层 60日实现波动预算替代全局连败 cliff，有明确第一性逻辑：连续亏损是噪声且会误伤后续右尾，组合实现波动是更连续的风险状态。但它必须在当前 Stage372/20万正式口径、多起点和成本压力下通过；若失败，不应继续扫 lookback、目标波动或最低 scale。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage710_no_streak_vol_budget_multiperiod.py`
- 修改正式策略：无。
- 删除脚本：无。
- 新增参数：
  - `enable_portfolio_volatility_budget=True`
  - `portfolio_volatility_budget_lookback=60`
  - `portfolio_volatility_budget_target_annual_vol=0.60`
  - `portfolio_volatility_budget_min_scale=0.50`
  - `portfolio_volatility_budget_entry_contexts=flat_entry,reverse_entry,rollover_reopen,regular_add,donchian_add`
- 修改参数：
  - C 分支运行期 `streak_risk_multipliers` 从 `1.0,1.0,1.0,0.1` 改为 `1.0,1.0,1.0,1.0`
  - `enable_portfolio_volatility_budget_deleverage=False`，不强平已有仓位，只缩放新开仓/反手/换月重开/加仓。
- 删除参数：无。
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本，另输出 `2x/3x` 成本压力。
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：关闭全局连败 cliff + 60日组合波动预算 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_no_streak_vol60_t60_min50_stage710`

## 结果

- 决策：`no_streak_vol_budget_not_promoted`
- 硬失败项：`full_return_retention_ge80`、`full_dd30_pass`、`cost2_full_dd40_pass`、`start_years_min_retention_ge70`、`start_years_dd_not_worse_by_3pp`、`start_years_dd40_all_pass`
- 观察项：`full_sharpe_not_lower`、`phase_min_retention_ge65`

### 全周期

- A 当前正式版：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次，`299` 手
- C 无连败 + 60日组合波动预算：
  - 期末权益 `4,140,580`
  - 总收益 `1970.2900%`
  - 最大回撤 `-47.2713%`
  - Sharpe `1.2906`
  - 总滑点 `394,770`
  - 总交易次数 `674`
  - 胜率 `51.8010%`
  - broker10 峰值 `75.5687%`
  - 强制减仓 `9` 次，`446` 手
- C 全周期收益保留仅 `46.2060%`，最大回撤比 A 恶化 `8.6000pp`。
- C `2x/3x` 成本回撤为 `-50.4061%/-53.8542%`，均不可部署。

### 多起点与分段

- `since_2021`：A `2221.3050%/-38.1656%/Sharpe1.5636`；C `1297.1050%/-41.9783%/Sharpe1.2988`。
- `since_2022`：A `133.8550%/-28.0550%/Sharpe0.8895`；C `288.9975%/-38.0125%/Sharpe0.9574`，收益更高但回撤恶化近 `10pp`。
- `since_2023`：A `70.2100%/-24.5662%/Sharpe0.7818`；C `162.9325%/-33.7163%/Sharpe0.9839`，收益更高但 DD30 失败。
- `since_2024`：A `33.3550%/-29.4347%/Sharpe0.5945`；C `118.5025%/-25.8493%/Sharpe1.0307`，后段窗口明显改善。
- `since_2025`：A `17.9975%/-17.6662%/Sharpe0.6589`；C `75.8325%/-25.0274%/Sharpe1.1879`，收益提升但回撤加深。
- `since_2026`：A `1.1450%/-16.3027%/Sharpe0.2783`；C `-6.8400%/-22.3020%/Sharpe-0.2569`，独立启动失败。
- `phase_2020_2021`：A `441.4650%/-24.2699%/Sharpe2.1114`；C `278.1375%/-25.6420%/Sharpe1.7684`。
- `phase_2022_2023`：A `0.2975%/-28.0550%/Sharpe0.1053`；C `45.2575%/-38.0125%/Sharpe0.6800`，收益改善但明显提高保证金/回撤压力。
- `phase_2024_2025`：A `33.2675%/-29.4347%/Sharpe0.6398`；C `134.2350%/-25.4740%/Sharpe1.2781`。
- `phase_2026_latest`：A `1.1450%/-16.3027%/Sharpe0.2783`；C `-6.8400%/-22.3020%/Sharpe-0.2569`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage710_no_streak_vol_budget_multiperiod_report_stage710_no_streak_vol_budget_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage710_no_streak_vol_budget_multiperiod_summary_stage710_no_streak_vol_budget_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage710_no_streak_vol_budget_multiperiod_comparison_stage710_no_streak_vol_budget_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage710_no_streak_vol_budget_multiperiod_checks_stage710_no_streak_vol_budget_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage710_no_streak_vol_budget_multiperiod_chart_stage710_no_streak_vol_budget_multiperiod_v1.png`

## 结论

- 本阶段结论：不晋级正式版，不继续围绕 `lookback/target_vol/min_scale` 扫参。
- C 的问题不是保证金爆掉，而是关闭全局连败后新增交易和风险暴露显著增加，波动预算的缩放不够前置，也不能识别趋势假突破质量；它在 `2024-2025` 后段窗口更好，但牺牲了 `2020-2021`、全周期和 2026 独立启动。
- 这说明“连败 0.1 很粗糙”是真的，但直接拿组合实现波动预算替代也不是答案。当前最强的简单机制仍是 Stage421 all-cases recovery，但它也因 2026 独立启动失败不能接正式版。
- 后续应停止沿主账户内部风控小结构继续历史救参；更有价值的路径是 paper/forward 观察 Stage421，或者转向真正外生/账户级 selector，而不是继续在连败倍率附近调参。

## 过拟合反思

- 运行前判断：不是过拟合；这是一个单点粗档、组合层、事前可解释的风控替代。
- 运行后判断：本阶段不是过拟合，但继续扫 `20/40/60/90` lookback、`50/60/70%` 目标波动、`0.3/0.5/0.7` 最低 scale 会变成过拟合。
- 原因：候选在多个窗口呈现结构性矛盾：后段好、全周期和 2026 差，说明不是小参数没调准，而是风险状态变量不能替代连败防守。

## 继续价值反思

- 运行前判断：有价值；它直接回答“能不能不用连败 0.1，换成更连续的组合风险预算”。
- 运行后判断：该形状没有继续优化价值；总目标仍有价值，但应换方向。
- 原因：候选全周期收益保留只有 `46.2060%`，最大回撤恶化到 `-47.2713%`，2x 成本穿 `-50%`，2026 独立启动转负。继续在这个框架内调参只是在救历史。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage424 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为连败风控替代关键反证追加。
