# Stage117 Stage103股指60/120一致性Overlay审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 22:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：低自由度结构审计；固定 Stage079 与 Stage103，不修改 C3/Stage079/Stage103 规则，不增加账户资金。
- 是否重要突破：否。重要反证：60/120一致性过滤固定路径好看，但仍无法通过冷启动硬闸门。
- 是否触发A/B：是。A=Stage079，C0=Stage103，C1/C2/C3=中金所股指 60/120 趋势一致性 overlay。

## 外部调研与判断

- 参考资料：
  - managed futures / TSMOM 文献支持跨资产趋势收益源，但也强调波动管理与路径稳健性。参考：https://people.stern.nyu.edu/lpederse/papers/DemystifyingManagedFutures.pdf
  - momentum / trend 的风险管理研究提示，波动缩放和风险管理可以改善尾部，但必须防止把少数历史路径当成可泛化规律。参考：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3448995
- 我的判断：
  - Stage116 证明 Stage115 `best1_tsmom60` 收益优势过于集中，本阶段不能继续救单一60日窗口。
  - 60/120一致性是一个低自由度结构：60日负责当前趋势强度，120日负责慢确认；它不是小数扫描，也不是日期/品种补丁。
  - 结果显示一致性过滤仍打不穿 `start_2022` 冷启动风险，因此股指 overlay 子路线不应继续通过窗口组合救援。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage417_stage103_cffex_index_consensus_overlay.py`
- 修改脚本：无正式策略脚本修改；该脚本仅生成只读审计输出。
- 删除脚本：无。
- 新增参数：
  - 股指品种：`IF/IH/IC/IM`
  - 趋势一致性：60日 TSMOM 与 120日 TSMOM 方向必须一致且非零。
  - `consensus_best1`：每天只取60日绝对动量最强的1个一致性信号，最多1手。
  - `consensus_short1`：每天只取60/120一致为空头的最强1个信号，最多1手。
  - `consensus_all`：所有一致性信号各最多1手，仅作为过暴露对照组。
  - 执行闸门：沿用 Stage103/115 的 `1.10x` 保证金闸门。
  - 鲁棒性附加：任意启动收益/风险相对胜率、顶部相对贡献日剔除。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：Stage117 summary/score/gate/fresh_start/cost/pairwise/topday/report/chart。
- 修改回测结果：无。
- 删除回测结果：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`615,000`，不增加 Stage079 资金占用。
- 成本口径：正常成本 + `2x/3x/5x` 滑点压力。
- 样本过滤：无新增日期过滤；所有候选统一跑 full、多起点、弱窗口、年度/季度、滚动与成本压力。
- 策略/归因口径：只读 A/B/C 审计；不写入正式交易入口。

## 结果

- Stage079：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：沿用 Stage079/C3 交易口径 `45.3826%`
- Stage103：
  - 期末权益：`31,730,915`
  - 总收益：`5059.4984%`
  - 最大回撤：`-28.9792%`
  - Sharpe：`1.3681`
  - Ulcer：`14.3132`
  - 3个月/6个月体验分：`121.2041 / 134.4513`
- `consensus_best1`：
  - 期末权益：`32,929,095`
  - 总收益：`5254.3244%`
  - 最大回撤：`-26.3312%`
  - Sharpe：`1.4017`
  - Ulcer：`13.1184`
  - 3个月/6个月体验分：`146.3638 / 175.6379`
  - 3个月改善项：`7/8`
  - 6个月改善项：`8/8`
  - 成本压力 `1x/2x/3x/5x` 最大回撤：`-26.3312% / -27.6875% / -29.9034% / -39.1469%`
  - 失败项：`start_2022` 冷启动最大回撤 `-39.4695%`，`fresh_start_dd30_pass=0`；`phase_2024_2025/start_2024` 的 `1.10x` 经纪商保证金相对 Stage079/Stage103 更差。
- `consensus_short1`：
  - 期末权益：`31,937,495`
  - 总收益：`5093.0886%`
  - 最大回撤：`-28.8911%`
  - Sharpe：`1.3814`
  - Ulcer：`13.6684`
  - 3个月/6个月体验分：`137.6582 / 135.1160`
  - 3个月改善项：`7/8`
  - 6个月改善项：`7/8`
  - 成本压力 `1x/2x/3x/5x` 最大回撤：`-28.8911% / -30.3136% / -31.8576% / -39.1469%`
  - 失败项：`start_2022` 冷启动最大回撤 `-36.8361%`，`fresh_start_dd30_pass=0`；`phase_2024_2025/start_2024` 的 `1.10x` 经纪商保证金相对 Stage079/Stage103 更差。
- `consensus_all`：
  - 期末权益：`33,021,955`
  - 总收益：`5269.4236%`
  - 最大回撤：`-37.6707%`
  - Sharpe：`1.3073`
  - Ulcer：`14.5164`
  - 结论：过暴露对照组直接淘汰。
- 任意启动相对 Stage103：
  - `consensus_best1` 的 `90/180/252/504` 日收益胜率为 `59.48% / 58.52% / 57.65% / 48.37%`，短中期有增量，但长期胜率仍不足50%。
  - `consensus_short1` 的 `90/180/252/504` 日收益胜率为 `52.99% / 50.77% / 51.04% / 54.68%`，更均衡，但固定收益改善较小且冷启动失败。
- 顶部贡献日剔除：
  - `consensus_best1` 固定路径相对 Stage103 有增量，但不解决 `start_2022` 硬失败，因此不进入晋级。
  - `consensus_short1` 剔除最大 `1` 个相对贡献日后仍高于 Stage103 `+21.0211pp`，但剔除 `3` 个后转为 `-1.7854pp`，收益稳定性不够强。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_report_stage417_stage103_cffex_index_consensus_overlay_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_summary_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_horizon_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_score_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_gate_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- fresh_start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_fresh_start_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_cost_stress_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_pairwise_rolling_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- topday：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_top_edge_day_ablation_stage417_stage103_cffex_index_consensus_overlay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_decision_stage417_stage103_cffex_index_consensus_overlay_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage417_stage103_cffex_index_consensus_overlay_chart_stage417_stage103_cffex_index_consensus_overlay_v1.png`

## 结论

- 本阶段结论：`no_new_promotion`
- 是否进入下一步：不进入。Stage117 没有新晋级版本。
- 下一步：
  - Stage103 继续作为当前主执行相对候选。
  - Stage115/117 股指 overlay 子路线整体降级为研究经验，不继续扫 `60/120`、`best1/short1/all`、指数选择、日期或保证金小数。
  - 若继续追求理想 3/6 个月体验，必须换新的低相关风险源或新的执行承载，而不是继续救股指 TSMOM。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段只测试一个低自由度结构确认：60/120 趋势一致，不做相邻小数、日期、品种黑名单或弱窗口补丁。
- 运行后判断：本阶段不是过拟合；如果继续救 `start_2022`，就会转为过拟合。
- 原因：`consensus_best1/short1` 固定路径和短持有分都很好，但硬失败集中在冷启动路径。继续通过窗口组合或附加条件排除该段，属于按历史路径补丁。

## 继续价值反思

- 运行前判断：有价值。Stage116 暴露单窗口/贡献日问题，60/120一致性是合理的下一步反证。
- 运行后判断：总目标仍有价值；股指 TSMOM overlay 子路线继续主动优化价值低。
- 原因：一致性过滤已经是低自由度降噪尝试，但仍不能通过最基本的多起点硬闸门。下一步应转向真正不同的风险源、真实执行承载或 Stage103 的工程化/paper。

## 合入建议

- 是否更新本线 `LINE.md`：是。写入 Stage117 反证约束。
- 是否更新 `research/registry.md`：是。最新关键阶段更新为 Stage117。
- 是否追加根目录 `memory.md/back_log.md`：是。属于股指 overlay 子路线停止/降级的关键记录。
