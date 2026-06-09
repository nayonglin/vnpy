# Stage423 Stage372 all-cases recovery 加 15% 回撤门槛多起点验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 14:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage421 强线索的低自由度结构反证
- 是否重要突破：否。该阶段证明“浅回撤才允许 all-cases recovery”的硬门槛不能晋级。
- 是否触发A/B：是，属于可能接入正式版的风控结构候选。

## 外部调研与判断

- 参考资料：
  - Man Group `A Trend Following Deep Dive: The Optimal Market Mix for a Trend Follower`：趋势跟踪的市场组合和风险预算会改变右尾捕捉效率。
  - AQR `Trend Following`：趋势跟踪长期收益依赖规则化、多市场趋势暴露，不能用单一坏窗口修补规则。
  - GitHub `quantiacs/strategy-futures-trend-following`：公开多资产趋势模板强调先定义可交易市场、趋势信号和风险控制，不支持事后按窗口补丁。
- 我的判断：浅回撤放开恢复、深回撤保留 `0.1` 防守有第一性合理性，因为账户已经处于深回撤时不应无差别恢复风险。但固定 `15%` 硬门槛仍是一个粗糙假设，必须用多起点反证，不能继续扫 `10/12/20%` 救历史曲线。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage709_recovery_all_cases_dd15_multiperiod.py`
- 修改正式策略：无。
- 删除脚本：无。
- 新增参数：
  - `streak_entry_structure_recovery_max_portfolio_drawdown_pct=0.15`
  - `RECOVERY_SIGNALS=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`
- 修改参数：
  - C 分支保持 `streak_risk_multipliers=1.0,1.0,1.0,0.1` 不变。
  - 仅把 Stage421 all-cases clean-book recovery 限定为账户回撤不超过 `15%` 时才允许恢复。
- 删除参数：无。
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本，另输出 `2x/3x` 成本压力。
- 策略/归因口径：
  - A：当前正式 Stage372/20万 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：Stage421 all-cases recovery + `15%` 账户回撤门槛 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_dd15_stage709`

## 结果

- 决策：`recovery_all_cases_dd15_not_promoted`
- 硬失败项：`full_dd30_pass`、`cost2_full_dd40_pass`、`start_years_min_retention_ge70`、`start_years_dd_not_worse_by_3pp`、`start_years_dd40_all_pass`
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
- C all-cases recovery + DD15：
  - 期末权益 `8,879,180`
  - 总收益 `4339.5900%`
  - 最大回撤 `-38.8730%`
  - Sharpe `1.6214`
  - 总滑点 `473,230`
  - 总交易次数 `635`
  - 胜率 `52.1114%`
  - broker10 峰值 `83.3212%`
- 全周期 C 收益保留 `101.7693%`，但回撤仍未进 `30%`，2x 成本最大回撤为 `-41.3142%`。

### 多起点与分段

- `since_2021`：A `2221.3050%/-38.1656%/Sharpe1.5636`；C `1841.7150%/-49.1004%/Sharpe1.4926`，回撤恶化 `10.9348pp`。
- `since_2022`：A `133.8550%/-28.0550%/Sharpe0.8895`；C `-19.6200%/-34.2150%/Sharpe-0.2795`，收益保留 `-14.6577%`。
- `since_2023`：A `70.2100%/-24.5662%/Sharpe0.7818`；C `323.9125%/-32.1857%/Sharpe1.4263`，收益改善但 DD30 失败。
- `since_2024`：A `33.3550%/-29.4347%/Sharpe0.5945`；C `170.0175%/-27.8942%/Sharpe1.3784`。
- `since_2025`：A `17.9975%/-17.6662%/Sharpe0.6589`；C `31.8675%/-17.3664%/Sharpe0.8562`。
- `since_2026`：A `1.1450%/-16.3027%/Sharpe0.2783`；C `1.9600%/-13.9446%/Sharpe0.3598`。
- `phase_2022_2023`：A `0.2975%/-28.0550%/Sharpe0.1053`；C `-32.2300%/-32.2300%/Sharpe-2.0381`。
- `phase_2024_2025`：A `33.2675%/-29.4347%/Sharpe0.6398`；C `148.8050%/-27.8942%/Sharpe1.4151`。
- `phase_2026_latest`：A `1.1450%/-16.3027%/Sharpe0.2783`；C `1.9600%/-13.9446%/Sharpe0.3598`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage709_recovery_all_cases_dd15_multiperiod_report_stage709_recovery_all_cases_dd15_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage709_recovery_all_cases_dd15_multiperiod_summary_stage709_recovery_all_cases_dd15_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage709_recovery_all_cases_dd15_multiperiod_comparison_stage709_recovery_all_cases_dd15_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage709_recovery_all_cases_dd15_multiperiod_checks_stage709_recovery_all_cases_dd15_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage709_recovery_all_cases_dd15_multiperiod_chart_stage709_recovery_all_cases_dd15_multiperiod_v1.png`

## 结论

- 本阶段结论：不晋级正式版，不继续围绕 `15%` 门槛扫参。
- DD15 修好了 Stage421 的 2026 短样本问题，但代价是把 2022-2023 的早期恢复右尾过度过滤掉；`phase_2022_2023` 从 Stage421 的 `+83.0350%` 变成 Stage423 的 `-32.2300%`。
- 全周期收益变高不是足够理由，因为最大回撤仍 `-38.8730%`，2x 成本穿 `-40%`，并且 `since_2021` 冷启动回撤恶化到 `-49.1004%`。
- 后续不做 `10/12/20%`、按年份、按品种或按 case 的门槛救援。若继续风控研究，应停止历史救参，转向 paper/forward 预声明观察，或寻找不在主账户连败倍率内部做补丁的结构。

## 过拟合反思

- 运行前判断：不是过拟合；这是一个预声明单点阈值，用于验证“浅回撤恢复、深回撤防守”的结构假设。
- 运行后判断：本阶段本身不是过拟合，但继续扫回撤阈值会变成过拟合。
- 原因：失败集中在多起点和 2022-2023 独立分段，说明问题是硬门槛结构过度审查，不是 `15%` 这个小数没调好。

## 继续价值反思

- 运行前判断：有价值；它验证 Stage421 强线索能否用简单账户回撤门槛修复 2026 硬失败。
- 运行后判断：作为正式候选没有继续价值；作为风控机制边界经验有价值。
- 原因：DD15 只是在 2026 局部更好，却牺牲了 2022-2023 和 `since_2021` 生存边界。当前更有价值的方向不是继续历史回测救参，而是 paper/forward 验证或重新设计账户级 selector。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage423 当前状态。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage421 后续关键反证追加。
