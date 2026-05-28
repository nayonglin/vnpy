# Stage116 Stage115鲁棒性与反过拟合审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 22:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定 Stage115 的只读鲁棒性/反过拟合审计；不新增交易规则，不修改 Stage079、Stage103、Stage115 参数。
- 是否重要突破：是。重要性不是新高收益，而是纠偏：Stage115 固定路径很强，但严格鲁棒性不足，不建议进一步晋级。
- 是否触发A/B：是。A=Stage079，C0=Stage103，C1=Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`。

## 外部调研与判断

- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu 关于 backtest overfitting / PBO 的研究：多次试验后，单一漂亮回测可能来自选择偏差，需要看扰动路径和贡献集中度。参考：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2308659
  - walk-forward / rolling holding 分析：用于回答“任何时候启动、持有多久”的体验问题。
  - 时间序列动量文献支持跨资产 futures 趋势效应，但不能替代本地合约粒度、保证金和滑点审计。参考：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- 我的判断：
  - 股指 TSMOM 作为低相关风险源有理论合理性，Stage115 的风险改善也是真实线索。
  - 但 Stage115 相对 Stage103 的收益优势过于依赖少数交易日；如果把它当作主晋级版本，过拟合/路径选择风险偏高。
  - 因此本阶段不继续救 `best1_tsmom60`，不扫股指窗口、指数选择、动量阈值、保证金小数或日期/贡献日补丁。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage416_stage115_robustness_overfit_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 任意启动持有窗口：`21/63/90/126/180/252/504` 日。
  - pairwise 对照：Stage115 分别对 Stage079、Stage103。
  - moving block bootstrap：块长 `20/60/120` 日，各 `2000` 次。
  - 月份顺序重排：`2000` 次。
  - 顶部相对贡献日剔除：`0/1/3/5/10/20/40/80/120` 日。
  - 晋级闸门：硬指标、相对 Stage103 增量、成本压力、短持有分、rolling 风险/收益、resample 风险/收益、顶部贡献日、绝对保证金。
- 修改参数：无。
- 删除参数：无。
- 修改结果：Stage115 从“新的 Stage103 后继执行相对候选”降级为“固定路径强、风险体验强，但严格鲁棒性不足的研究/paper 候选”。
- 删除结果：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：Stage079/Stage103/Stage115 均按 `615,000` 账户口径比较，其中 Stage079 为 `50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本与 Stage115 源输出的 `1x/2x/3x/5x` 滑点压力。
- 样本过滤：无新增过滤；使用 Stage115 v2 已生成的日度权益、成本压力、冷启动、保证金与评分输出。
- 策略/归因口径：只读审计，不新增交易信号；重点验证固定路径是否经得起任意启动、路径重排和顶部贡献日剔除。

## 结果

- Stage079：
  - 期末权益：`31,040,650`
  - 总收益：`4947.2602%`
  - 最大回撤：`-29.7007%`
  - Sharpe：`1.3188`
  - Ulcer：`15.0874`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：日胜率 `36.2924%`，非零收益日胜率 `48.3899%`
- Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`：
  - 期末权益：`31,730,915`
  - 总收益：`5059.4984%`
  - 最大回撤：`-28.9792%`
  - Sharpe：`1.3681`
  - Ulcer：`14.3132`
  - 总滑点：`1,569,265`
  - 总交易次数：`1,217`
  - 3个月/6个月体验分：`121.2041 / 134.4513`
- Stage115 `stage103_plus_cffex_index_best1_tsmom60_guard`：
  - 期末权益：`33,607,695`
  - 总收益：`5364.6659%`
  - 最大回撤：`-23.5184%`
  - Sharpe：`1.4810`
  - Ulcer：`12.0786`
  - 总滑点：`1,594,705`
  - 总交易次数：`1,719`
  - 胜率：日胜率 `52.5457%`，非零收益日胜率 `53.8462%`
  - 3个月/6个月体验分：`183.4601 / 210.3930`
  - `1x/2x/3x/5x` 滑点压力最大回撤：`-23.5184% / -25.9791% / -29.9034% / -39.1469%`
  - 多起点最差最大回撤：`-29.5919%`
  - `1.10x` 保证金绝对口径：`1` 天穿线，最大需额外现金 `7,137.64`
- 晋级闸门：
  - 通过：`hard_vs_stage079`、`incremental_vs_stage103`、`cost_not_worse`、`short_score_pass`、`rolling_risk_strong`、`resample_risk_strong`、`resample_return_strong`
  - 未通过：`rolling_return_strong`、`topday_not_single_spike`、`absolute_margin_pass`
- 任意启动相对 Stage103：
  - 风险体验很强：`90/180/252/504` 日最大回撤不劣化率为 `95.2183% / 100.0000% / 100.0000% / 100.0000%`，Ulcer 不劣化率为 `98.5447% / 98.5957% / 100.0000% / 100.0000%`。
  - 收益优势不稳：`90/180/252/504` 日收益胜率仅 `44.2134% / 37.8418% / 38.3294% / 26.7250%`；`504` 日中位收益差为 `-16.6079pp`。
- 路径扰动相对 Stage103：
  - moving block bootstrap 收益胜率在 `20/60/120` 日块下为 `55.45% / 58.65% / 58.80%`，风险与 Ulcer 胜率高。
  - 但 bootstrap 中 Stage115 自身 DD30 breach rate 仍为 `52.45% / 48.20% / 38.90%`，说明路径重排后绝对回撤体验不能直接照搬固定路径。
- 顶部相对贡献日剔除：
  - 相对 Stage103，原始收益差为 `+305.1675pp`。
  - 剔除最大 `1` 个相对贡献日后，Stage115 调整后总收益降至 `5046.0926%`，相对 Stage103 变为 `-13.4058pp`。
  - 剔除最大 `3/5/20` 个相对贡献日后，相对 Stage103 收益差分别为 `-461.8914pp / -783.4822pp / -2165.7126pp`。
  - 结论：风险改善不靠少数日，但“收益优于 Stage103”靠少数日过重。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_report_stage416_stage115_robustness_overfit_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_summary_stage416_stage115_robustness_overfit_audit_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_rolling_holding_stage416_stage115_robustness_overfit_audit_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_pairwise_rolling_stage416_stage115_robustness_overfit_audit_v1.csv`
- bootstrap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_block_bootstrap_stage416_stage115_robustness_overfit_audit_v1.csv`
- month permutation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_month_permutation_stage416_stage115_robustness_overfit_audit_v1.csv`
- top edge day ablation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_top_edge_day_ablation_stage416_stage115_robustness_overfit_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_decision_stage416_stage115_robustness_overfit_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage416_stage115_robustness_overfit_audit_chart_stage416_stage115_robustness_overfit_audit_v1.png`

## 结论

- 本阶段结论：`robustness_gap_do_not_promote_further`。
- 是否进入下一步：Stage115 不建议进一步晋级。保留为研究/paper 候选；当前主执行相对候选回到 Stage103。
- 下一步：
  - 固定 Stage103 做工程化复跑、paper/影子盘和真实券商保证金接入。
  - Stage115 只能作为研究观察或后续真实券商保证金数据到位后的 paper 对照。
  - 不继续用小参数、日期、贡献日、保证金小数或指数选择救 Stage115。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段不是优化参数，而是对固定 Stage115 做反证审计。
- 运行后判断：Stage116 本身不是过拟合；但 Stage115 若继续作为主晋级版本，会有明显过拟合/路径选择风险。
- 原因：Stage115 的全周期收益和风险指标很好，但相对 Stage103 的收益优势剔除最大 `1` 个相对贡献日后即转负；任意启动的中长持有收益胜率也不足。继续救这条路径会从“验证新风险源”变成“拟合历史少数贡献日”。

## 继续价值反思

- 运行前判断：有价值。Stage115 固定路径足够强，必须用更严审计确认能否晋级。
- 运行后判断：总目标仍有价值；Stage115 子路线不值得继续救。
- 原因：它证明股指 TSMOM 能改善账户风险体验，但收益端不够稳健，且绝对保证金仍未过。更务实的下一步是回到 Stage103 的工程化/影子盘，或另找真正不同、低参数、可解释的收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是。写入 Stage116 降级约束。
- 是否更新 `research/registry.md`：是。最新关键阶段更新为 Stage116。
- 是否追加根目录 `memory.md/back_log.md`：是。属于重要候选降级和反过拟合边界确认。
