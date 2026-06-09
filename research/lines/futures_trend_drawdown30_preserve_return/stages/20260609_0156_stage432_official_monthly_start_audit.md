# Stage432 当前正式版月度冷启动审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-09 01:56 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：正式版只读鲁棒性审计；从 2020 年开始每个月作为独立启动实验，统一跑到 `2026-04-30`
- 是否重要突破：是。本阶段直接回答当前正式 Stage372/20万是否依赖 `2020-01` 单一起点，以及月度冷启动下收益/回撤是否稳健。
- 是否触发A/B：否。本阶段不产生新候选，不改正式参数，只审计当前正式版。

## 外部调研与判断

- 参考资料：外部 walk-forward / rolling-window 验证资料和 GitHub 示例普遍强调，不应只看单条全周期曲线，应该用多个滚动起点检验路径稳定性；Backtrader sizer 文档也把仓位规模视作账户层资金管理问题，而不是单独 alpha。
- 我的判断：本阶段不做优化、不重训 AI、不选择参数，所以不是过拟合式调参；它是对正式版路径依赖的压力测试。结果应分开解释：盈利穿越性是否足够、回撤生存线是否足够。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage744_official_monthly_start_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`MONTH_STARTS=2020-01..2026-04`、`ANALYSIS_END=2026-04-30`、`INITIAL_CAPITAL=200000`、`BASE_OUTPUT_TAG=stage744_official_monthly_start_audit_v1`。
- 修改参数：无；正式 profile 保持 `official_live_stage372_20w_recovery_sleeve` / `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：逐月独立起点 `2020-01-01` 至 `2026-04-01`，统一终点 `2026-04-30`，共 `76` 个启动月。
- 账户规模：`200,000`。
- 成本口径：正式正常成本，并额外做 `2x` 成本压力回撤审计。
- 样本过滤：全样本、`>=63`、`>=126`、`>=252` 交易日四个成熟度桶；重点看 `>=252` 交易日成熟样本。
- 策略/归因口径：当前正式 Stage372/20万，AI、品种池、`streak_risk_multipliers=1,1,1,0.1`、recovery sleeve、maxpos4、强制减仓全部保持正式版。

## 结果

- 期末权益：这是多起点审计，不用单一期末权益代表全部结果；官方 `2020-01` 起点仍为 `8,728,285`。
- 总收益：全体月度起点中位数 `129.9425%`；`>=252` 成熟样本中位数 `200.97375%`。
- 最大回撤：全体最差 `-40.781843%`，来自 `2020-07` 起点；`>=252` 成熟样本同样最差 `-40.781843%`。
- Sharpe：全体月度起点中位数 `1.136491`；`>=252` 成熟样本中位数 `1.223327`。
- 总滑点：多起点各自不同；官方 `2020-01` 起点为 `506,220`。
- 总交易次数：多起点各自不同；官方 `2020-01` 起点为 `633`。
- 胜率：多起点各自不同；官方 `2020-01` 起点为 `52.2586%`。
- 其他关键指标：
  - 全体 `76` 个启动月：`73/76` 正收益，正收益率 `96.0526%`；DD30 失败 `28` 个，DD40 失败 `1` 个，deployable 失败 `1` 个；最差收益起点 `2025-09`，收益 `-12.9250%`。
  - `>=63` 交易日成熟样本：`72/73` 正收益，正收益率 `98.6301%`；最差收益仍为 `2025-09`，收益 `-12.9250%`。
  - `>=126` 交易日成熟样本：`69/70` 正收益，正收益率 `98.5714%`。
  - `>=252` 交易日成熟样本：`64/64` 正收益，正收益率 `100.0000%`；收益 p10 `29.13575%`，最小收益 `17.9975%`，最差成熟收益起点 `2025-01`；DD30 失败 `28` 个，DD40 失败 `1` 个。
  - 起始年份聚合：2020、2021、2022、2023、2024 各年 `12/12` 正收益；2025 为 `11/12` 正收益；2026 为 `2/4` 正收益但样本很短。
  - 2020 年启动月全部盈利但回撤压力最高：2020 年 12 个启动月中 DD30 失败 `12` 个，DD40 失败 `1` 个，最差 DD `-40.781843%`。
  - 2x 成本压力：`>=252` 成熟样本 DD40 失败 `6` 个，说明正式版不是高滑点极端稳健口径。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_report_stage744_official_monthly_start_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_summary_stage744_official_monthly_start_audit_v1.csv`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_checks_stage744_official_monthly_start_audit_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_cost_stress_stage744_official_monthly_start_audit_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_curves_stage744_official_monthly_start_audit_v1.csv`
- maturity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_maturity_summary_stage744_official_monthly_start_audit_v1.csv`
- year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_year_summary_stage744_official_monthly_start_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_decision_stage744_official_monthly_start_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage744_official_monthly_start_audit_chart_stage744_official_monthly_start_audit_v1.png`

## 结论

- 本阶段结论：`official_monthly_start_audit_has_hard_fail`。正式版盈利穿越性比单一起点更可靠：`>=252` 交易日成熟启动月 `64/64` 全部正收益，说明它不是只靠 `2020-01` 这个起点。但是它不能被描述成严格 DD30 或完美 DD40 策略：成熟样本 DD30 失败 `28/64`，DD40 失败 `1/64`，2x 成本成熟样本 DD40 失败 `6` 个。
- 是否进入下一步：不进入新策略候选，不改正式版。
- 下一步：继续用当前正式 Stage372/20万跑实盘/影子盘默认流程；若继续研究，应转向账户层出金/锁盈、成本/TCA、保证金生存线或真正独立外生信息源，不要为了某个启动月做月份、品种、阈值补丁。

## 过拟合反思

- 运行前判断：否。本阶段是预声明的多起点审计，不根据结果选择参数。
- 运行后判断：审计本身不是过拟合；但如果拿 `2020-07`、`2025-09`、`2026-02/04` 等最差起点去倒推月份/品种/方向过滤，就会过拟合。
- 原因：月度冷启动用于暴露路径依赖，不用于拟合路径。结果说明正式版的收益稳健性较强，但回撤尾部和成本压力仍是真问题。

## 继续价值反思

- 运行前判断：有价值。用户要求从 2020 年开始每个月启动，能直接验证正式版是否只靠单一起点。
- 运行后判断：本审计问题已回答；继续“更多起点重复验证”边际价值低，但继续做账户层生存线和成本压力治理仍有价值。
- 原因：76 个启动月已足够说明收益稳定性与回撤尾部的边界；下一步应处理风险标签和执行生存线，而不是继续按月度路径补丁化。

## 合入建议

- 是否更新本线 `LINE.md`：是，加入 Stage432 正式版月度冷启动审计结论。
- 是否更新 `research/registry.md`：是，这是当前正式版的重要鲁棒性审计。
- 是否追加根目录 `memory.md/back_log.md`：是，结论影响正式版风险标签与后续研究方向。
