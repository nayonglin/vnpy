# Stage004 `risk_multiplier=0.40` 无连败逐月启动对比正式版

- line_id：`futures_trend_quarter_risk_no_streak`
- 当前模式：`day`
- 记录时间：`2026-06-09 03:28 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：逐月独立启动稳健性验证 / A vs C
- 是否重要突破：否，重要负结论
- 是否触发A/B：是；C 仍是正式版替代候选的稳健性验证

## 外部调研与判断

- 参考资料：
  - Fixed fractional / position sizing 资料强调，仓位由账户风险预算和止损距离决定，降低风险倍率会直接压低复利斜率，不一定线性保留收益。
  - Walk-forward / 多起点验证资料强调，交易系统不能只看单一起点，应观察不同时间起点下的稳定性和路径依赖。
- 我的判断：
  - 本阶段不新增交易参数、不按月份救参，只把 Stage746 C 版从 `2020-01` 到 `2026-04` 每月独立启动，属于稳健性验证，不是优化。
  - 如果 C 只是回撤更浅但大多数起点收益落后正式版，说明它是保守降风险壳，不是正式替代。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage747_half_risk_no_streak_monthly_start_compare.py`
- 修改脚本：无正式策略修改；脚本中先生成一次 metadata/spec 后并行跑月起点，避免 worker 并发生成 Stage78 静态品种池文件。
- 删除脚本：无
- 新增参数：`MODEL_TAG=stage747_half_risk_no_streak_monthly_start_compare_v1`，`MAX_WORKERS=4`
- 修改参数：
  - A：复用 Stage744 当前正式版逐月结果。
  - C：复用 Stage746 候选，`risk_multiplier=0.40`，`streak_risk_multipliers=1.0,1.0,1.0,1.0`，关闭 `enable_streak_entry_structure_risk_recovery` 与 `enable_recovery_sleeve`。
- 删除参数：无
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 回测/归因参数

- 数据区间：每月独立起点 `2020-01` 至 `2026-04`，统一终点 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常滑点；同时输出 1x/2x/3x cost stress CSV
- 样本过滤：全部 `76` 个逐月起点；成熟样本定义为 `>=252` 交易日，共 `64` 个
- 策略/归因口径：
  - A：当前正式 Stage372/20w `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - C：Stage746 `stage526_200k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage746`

## 结果

- A 正式 `2020-01` 起点：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`。
- C `2020-01` 起点：期末权益 `1,639,200`，总收益 `719.6000%`，最大回撤 `-38.7135%`，Sharpe `1.2214`，总滑点 `139,780`，总交易次数 `659`，胜率 `52.0034%`。
- 全体 `76` 个起点：
  - C 收益胜出 `15/76`，回撤胜出 `43/76`，收益和回撤同时胜出 `8/76`。
  - A 收益和回撤同时胜出 `26/76`。
  - C 正收益 `67/76`，A 正收益 `73/76`。
  - C DD30 失败 `26/76`，A DD30 失败 `28/76`；C/A DD40 均失败 `1/76`。
  - C 相对 A 的收益差中位数 `-52.0988pp`，收益保留中位数 `61.9470%`，回撤改善中位数 `+1.0454pp`。
- 成熟 `>=252` 交易日样本 `64` 个：
  - C 收益胜出 `14/64`，回撤胜出 `41/64`，收益和回撤同时胜出 `7/64`。
  - A 收益和回撤同时胜出 `16/64`。
  - C/A 均为 `64/64` 正收益。
  - C DD30 失败 `26/64`，A DD30 失败 `28/64`；C/A DD40 均失败 `1/64`。
  - C 相对 A 的收益差中位数 `-63.0050pp`，收益保留中位数 `67.0652%`，回撤改善中位数 `+2.5468pp`。
- 按年份看：
  - `2020` 起点 C 收益胜出 `0/12`，收益保留中位数仅 `18.3022%`，复利底座严重被压低。
  - `2022` 起点 C 收益胜出 `0/12`，但回撤胜出 `10/12`。
  - `2023` 起点 C 收益胜出 `4/12`，回撤胜出 `12/12`。
  - `2024` 起点 C 收益胜出 `6/12`，但回撤胜出仅 `5/12`。
  - `2025` 起点 C 收益胜出 `2/12`，回撤胜出 `1/12`，短期体验反而弱。
- 最伤收益起点：`2020-07`，A `6415.0475%`，C `883.0925%`，C-A `-5531.9550pp`。
- C 收益相对最好起点：`2023-04`，A `44.7275%`，C `136.6200%`，C-A `+91.8925pp`，回撤改善 `+14.4293pp`。
- C 回撤相对最差起点：`2025-08`，A 回撤 `-7.6673%`，C 回撤 `-19.8842%`，C-A `-12.2169pp`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_report_stage747_half_risk_no_streak_monthly_start_compare_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_summary_stage747_half_risk_no_streak_monthly_start_compare_v1.csv`
- candidate_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_candidate_summary_stage747_half_risk_no_streak_monthly_start_compare_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_comparison_stage747_half_risk_no_streak_monthly_start_compare_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_curves_stage747_half_risk_no_streak_monthly_start_compare_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_cost_stress_stage747_half_risk_no_streak_monthly_start_compare_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_chart_stage747_half_risk_no_streak_monthly_start_compare_v1.png`
- heatmap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage747_half_risk_no_streak_monthly_start_compare_heatmap_stage747_half_risk_no_streak_monthly_start_compare_v1.png`

## 结论

- 本阶段结论：`half_risk_no_streak_monthly_start_not_promoted`。
- 核心判断：C 的确在不少起点降低回撤，尤其 `2022-2024`；但收益胜率太低，`2020` 复利底座被严重压低，`2025` 后短样本回撤还变差。它不是正式版的通用替代，只是一个收益被明显削弱的保守风险壳。
- 是否进入下一步：不进入正式替代验证。
- 下一步：停止“固定降低风险 + 关闭连败机制”路线；若继续低回撤体验，转账户层资金分层、出金/锁盈、生存线或成本/TCA。

## 过拟合反思

- 运行前判断：不是过拟合。逐月启动是对单一起点敏感性的稳健性验证，不是新增参数寻优。
- 运行后判断：继续沿 `0.30/0.35/0.45` 或按 `2023/2024` 好窗口补丁会过拟合。
- 原因：结果显示 C 的优势集中在局部启动年份和回撤维度，不能解释为穿越周期的更优风险机制。

## 继续价值反思

- 运行前判断：有价值。用户关心 C 扩大风险后是否可以作为更朴素的低回撤替代，逐月起点能验证路径依赖。
- 运行后判断：本路线本身无继续优化价值，但结论有价值。
- 原因：C 回撤改善来自机械降风险，不是更好地识别机会质量；收益和复利底座损失太大。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要负结论和后续停止原则。
