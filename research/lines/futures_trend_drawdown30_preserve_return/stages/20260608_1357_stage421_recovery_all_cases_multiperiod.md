# Stage421 Stage372 all-cases recovery 多起点验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 13:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式版 Stage372/20万现有连败恢复机制的低自由度结构验证；只读回测，不改正式配置。
- 是否重要突破：否，但属于目前“连败 0.1 机制过粗”方向里最强的简单风控线索。
- 是否触发A/B：触发。已读取 `skills/version-ab-experiment/SKILL.md`，因为该机制可能接入正式版或作为 A/B 候选。

## 外部调研与判断

- 参考资料：趋势跟踪组合和风控文献/行业材料普遍强调两点：一是要保留右尾趋势机会，二是风控应尽量基于波动、风险预算和多市场分散，而不是针对单一历史窗口补丁。参考过 Man Group 关于 trend-following 市场组合、AQR trend following 白皮书、Concretum 关于趋势跟踪 position sizing 的比较、Aspect Capital 关于分散化的材料。
- 我的判断：本阶段不是继续救 Stage407 的鸡蛋窗口，而是把 Stage414 里“正式版 D 分支看起来有价值”的 all-cases recovery 单独拿出来做多起点反证。这个方向的第一性逻辑是：既然主账户三连败后的 `0.1` 是防守层，就不应无差别禁止干净账本、低相关、已满足原生趋势入场条件的新机会恢复仓位；但任何进一步按 2026、按 case 子集、按品种调参都会迅速变成过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage707_recovery_all_cases_multiperiod.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`RECOVERY_SIGNALS=long_case1a,long_case2,long_case3,short_case1a,short_case2,short_case3`。
- 修改参数：C 分支仅把既有 clean-book recovery lift 从 `long_case1a,short_case1a` 扩到所有原生趋势入场 case；`streak_risk_multipliers` 保持 `1,1,1,0.1` 不变。
- 删除参数：无。
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`，并拆分 `since_2021` 至 `since_2026` 起始年份窗口，以及 `2020-2021`、`2022-2023`、`2024-2025`、`2026_latest` 独立阶段窗口。
- 账户规模：`200,000`。
- 成本口径：正常成本，并额外输出 `2x/3x` 成本压力。
- 样本过滤：沿用当前正式 Stage372/20万 `official_live_stage372_20w_recovery_sleeve`。
- 策略/归因口径：
  - A：当前正式 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
  - C：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_recovery_all_cases_stage707`。
  - 使用独立窗口新启动资金回放，不用全周期曲线切片假装 OOS。

## 结果

- 决策：`recovery_all_cases_multiperiod_not_promoted`。
- 硬失败项：`start_years_min_retention_ge70`。
- 观察项：`phase_min_retention_ge65`。
- A 全周期：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`，broker10 保证金峰值 `79.6015%`。
- C 全周期：期末权益 `7,289,850`，总收益 `3544.9250%`，最大回撤 `-28.6384%`，Sharpe `1.6631`，总滑点 `359,770`，总交易次数 `600`，胜率 `52.0188%`，broker10 保证金峰值 `69.2871%`。
- 全周期收益保留 `83.1334%`，回撤改善 `10.0330pp`，Sharpe 提升 `0.0352`；全周期、DD30、Sharpe、broker10、2x成本压力均通过。
- 2x 成本 C 全周期：期末权益 `6,930,080`，总收益 `3365.0400%`，最大回撤 `-29.9650%`，Sharpe `1.5893`，broker10 峰值 `74.3592%`，仍可部署。
- 3x 成本 C 全周期：期末权益 `6,570,310`，总收益 `3185.1550%`，最大回撤 `-31.3760%`，Sharpe `1.5162`，broker10 峰值 `80.2326%`，风险未穿 broker100，但 DD30 不再满足。
- 起始年份窗口：
  - `since_2021`：A `2221.3050%/-38.1656%/1.5636`，C `1724.6275%/-29.3670%/1.5831`，收益保留 `77.6403%`。
  - `since_2022`：A `133.8550%/-28.0550%/0.8895`，C `391.2675%/-24.3359%/1.2403`，收益保留 `292.3070%`。
  - `since_2023`：A `70.2100%/-24.5662%/0.7818`，C `308.5725%/-25.9973%/1.3623`，收益保留 `439.4994%`。
  - `since_2024`：A `33.3550%/-29.4347%/0.5945`，C `146.3275%/-29.4347%/1.2372`，收益保留 `438.6973%`。
  - `since_2025`：A `17.9975%/-17.6662%/0.6589`，C `27.5925%/-19.0647%/0.7730`，收益保留 `153.3130%`。
  - `since_2026`：A `1.1450%/-16.3027%/0.2783`，C `-2.9550%/-17.5348%/-0.1388`，收益保留 `-258.0786%`，触发硬失败。
- 分段窗口：
  - `phase_2020_2021`：A `441.4650%/-24.2699%/2.1114`，C `418.0300%/-24.0367%/2.0338`，收益保留 `94.6915%`。
  - `phase_2022_2023`：A `0.2975%/-28.0550%/0.1053`，C `83.0350%/-24.3359%/1.1102`。
  - `phase_2024_2025`：A `33.2675%/-29.4347%/0.6398`，C `140.2675%/-29.4347%/1.3488`。
  - `phase_2026_latest`：A `1.1450%/-16.3027%/0.2783`，C `-2.9550%/-17.5348%/-0.1388`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_report_stage707_recovery_all_cases_multiperiod_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_summary_stage707_recovery_all_cases_multiperiod_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_comparison_stage707_recovery_all_cases_multiperiod_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_checks_stage707_recovery_all_cases_multiperiod_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_decision_stage707_recovery_all_cases_multiperiod_v1.json`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_curves_stage707_recovery_all_cases_multiperiod_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage707_recovery_all_cases_multiperiod_chart_stage707_recovery_all_cases_multiperiod_v1.png`

## 结论

- 本阶段结论：all-cases recovery 是目前最像“通用机制”的连败风控修正。它不靠新增品种、不靠小数扫参、不关闭 `0.1` 防守，只允许符合原生趋势 case 且满足 clean-book recovery 条件的机会恢复风险；全周期确实把回撤压到 `-28.6384%`，同时保留 `83.1334%` 收益并略升 Sharpe。
- 但它不能直接晋级正式版：`since_2026/phase_2026_latest` 独立冷启动为负，且 2026 样本虽短但足以说明不能把这个规则当作已经穿越周期的正式风控。决策保持 `not_promoted`。
- 是否进入下一步：可以作为强线索继续做只读归因或 paper watch；不能继续用 `case2 only/case3 only/排除2026/品种过滤/月份过滤` 去救。
- 下一步：做 Stage422 只读归因，拆出 2026 负贡献来自哪些 recovery-all-case 交易，以及 2022-2025 改善来自哪些交易；如果 2026 亏损无法用更上游、事前可解释的状态区分，则只保留 paper 观察，不接正式。

## 过拟合反思

- 运行前判断：不是过拟合。本次只验证 Stage414 中已经出现的结构线索，并预声明多起点、分段、成本压力硬门槛。
- 运行后判断：当前测试本身不是过拟合，但结果不能晋级；如果继续按 2026 失败窗口微调 case 子集、日期或品种，就会过拟合。
- 原因：趋势策略的收益来自稀疏右尾，all-cases recovery 逻辑与“保留右尾、控制暴露”一致；但 2026 独立冷启动失败提醒我们，这个规则仍可能只是提高了某些历史阶段的参与率，不一定是稳定 edge。

## 继续价值反思

- 运行前判断：有价值。当前 `1,1,1,0.1` 连败机制确实会在无关新品种和共享 AI rerank 下压掉右尾，需要找低自由度替代结构。
- 运行后判断：仍有研究价值，但没有直接部署价值。
- 原因：它是至今唯一一个在正式版全周期同时满足收益保留 `80%+`、DD30、Sharpe 不降、2x成本可部署的简单机制；但多起点硬失败说明必须先做归因和 forward/paper，而不是直接改正式版。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录为“强线索但未晋级”。
- 是否更新 `research/registry.md`：暂不更新，当前正式默认仍是 Stage372/20万。
- 是否追加根目录 `memory.md/back_log.md`：是，作为连败风控机制的重要阶段摘要。
