# Stage109 Stage103鲁棒性与反过拟合审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-27 20:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定 Stage103 的只读鲁棒性审计；不新增交易规则。
- 是否重要突破：否。重要边界确认：Stage103 仍是当前最强执行相对候选，但不应进一步宣称为绝对部署/正式替代版本。
- 是否触发A/B：否。本阶段不是新候选 A/B，只审计 Stage079 与既有 Stage103。

## 外部调研与判断

- 参考资料：
  - Bailey 与 Lopez de Prado 的 [Deflated Sharpe Ratio](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2460551_code87814.pdf?abstractid=2460551&mirid=1) 和 [Probability of Backtest Overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)：提醒多次试验和非正态收益会让单一 Sharpe/回测收益被高估。
  - [walk-forward robustness](https://quanthop.com/learn/validation-robustness/walk-forward-analysis)：使用滚动/扩展窗口检验单一路径外的稳定性。
  - GitHub [pysystemtrade](https://github.com/robcarver17/pysystemtrade)：系统化期货框架强调多市场、风险预算、可执行路径和持续复跑。
- 我的判断：Stage109 不是优化参数，而是反证式审计。若 Stage103 只能在固定路径好看、路径扰动后失真，就不能继续晋级；若风险体验稳定改善但收益端路径依赖明显，就只能作为相对候选进入工程化/影子盘观察。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage409_stage103_robustness_overfit_audit.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - 审计窗口：`21/63/90/126/180/252/504` 交易日。
  - block bootstrap：`20/60/120` 日块长，每档 `2000` 次。
  - 月份顺序重排：`2000` 次。
  - 极端相对贡献日剔除：剔除 Stage103 相对 Stage079 最大正贡献的 `1/3/5/10/20/40/80/120` 天。
- 修改参数：无。未修改 Stage103 的 `scale>=0.5`、`target_vol=10%`、`63日`、`broker10_guard=1.10`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：`615,000`，即 `50万C3下单 + 11.5万外部现金`。
- 成本口径：复用 Stage403 已冻结日度成本与成本压力输出。
- 样本过滤：只比较 `Stage079` 与 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- 策略/归因口径：只读日度权益；用任意启动持有期、路径扰动和贡献日剔除检验鲁棒性。

## 结果

Stage079 基准：

- 期末权益：`31,040,650`
- 总收益：`4947.2602%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.3188`
- Ulcer：`15.0874`
- 总滑点：`1,556,750`
- 总交易次数：`757`
- 胜率：`45.3826%`（C3逐笔交易口径；本阶段未重新定义组合逐笔胜率）

Stage103 `broker10_guard`：

- 期末权益：`31,730,915`
- 总收益：`5059.4984%`
- 最大回撤：`-28.9792%`
- Sharpe：`1.3681`
- Ulcer：`14.3132`
- 总滑点：`1,569,265`
- 总交易次数：约 `1217`
- 胜率：本阶段未新增逐笔胜率定义；仅用日度权益、滚动窗口和路径扰动审计。
- 3个月体验分：`121.2041`
- 6个月体验分：`134.4513`
- 成本压力最大回撤 `1x/2x/3x/5x`：`-28.9792%/-30.4073%/-31.9135%/-39.1469%`，均不差于 Stage079。

任意启动持有期：

- Stage103 在 `90/180/252/504` 日窗口的 Ulcer 不劣化率分别为 `95.2876%/98.4479%/100%/100%`，最大回撤不劣化率分别为 `87.6646%/86.8441%/91.5691%/100%`。
- 但 Stage103 的收益胜率不强：`90/180/252/504` 日窗口仅 `45.8766%/40.7243%/31.8501%/29.9320%`，中位收益差分别为 `0.0000pp/-0.7356pp/-1.7534pp/-7.1841pp`。

路径扰动：

- moving block bootstrap `20/60/120` 日块长下，Stage103 收益胜率仅 `55.20%/58.55%/57.75%`，不是强收益支配。
- 同样三档下，Stage103 最大回撤不劣化率为 `84.65%/87.15%/90.45%`，Ulcer 不劣化率为 `97.45%/98.95%/99.30%`，风险体验优势更稳定。
- 月份顺序重排下，Stage103 收益胜率 `100%`、最大回撤不劣化率 `83.75%`、Ulcer 不劣化率 `99.40%`；但重排路径下二者破30概率都很高，Stage103 仍不能被称作厚安全垫版本。

极端相对贡献日剔除：

- 不剔除时 Stage103 相对 Stage079 总收益高 `112.2382pp`，最大回撤改善 `0.7215pp`，Ulcer 改善 `0.7792pp`。
- 只剔除最大 `1` 个相对贡献日后，收益优势缩到 `4.9927pp`。
- 剔除最大 `3` 个相对贡献日后，Stage103 总收益反而低 Stage079 `159.7885pp`。
- 剔除最大 `20` 个相对贡献日后，Stage103 总收益为 `3910.5013%`，低 Stage079 `1036.7588pp`，但最大回撤和 Ulcer 仍优于 Stage079。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_report_stage409_stage103_robustness_overfit_audit_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_chart_stage409_stage103_robustness_overfit_audit_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_summary_stage409_stage103_robustness_overfit_audit_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_rolling_holding_stage409_stage103_robustness_overfit_audit_v1.csv`
- pairwise：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_pairwise_rolling_stage409_stage103_robustness_overfit_audit_v1.csv`
- bootstrap：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_block_bootstrap_stage409_stage103_robustness_overfit_audit_v1.csv`
- month permutation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_month_permutation_stage409_stage103_robustness_overfit_audit_v1.csv`
- top edge day ablation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_top_edge_day_ablation_stage409_stage103_robustness_overfit_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage409_stage103_robustness_overfit_audit_decision_stage409_stage103_robustness_overfit_audit_v1.json`

## 结论

- 本阶段结论：`retain_primary_relative_candidate_no_absolute_promotion`。
- 是否进入下一步：进入工程化复跑 / paper影子盘观察可以；不进入“绝对部署/正式替代Stage079”。
- 我的判断：如果按“值不值得保留”看，Stage103 值得，它在固定路径、冷启动、成本压力、回撤和 Ulcer 上优于 Stage079；如果按“能不能不管任何时候启动都收益体验更好”看，不够，因为收益胜率不足且收益端高度依赖少数强贡献日。
- 下一步：不要继续调 Stage103 小参数；下一步应做工程化复跑配置、paper/影子盘日更和真实券商保证金接入。若还要改善理想3/6个月收益体验，只能寻找更不同风险暴露的外生/跨资产收益源。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段不新增交易规则，只审计既有 Stage103。
- 运行后判断：不是过拟合，但也暴露了 Stage103 的收益端路径依赖。
- 原因：Stage103 风险体验优势在多种扰动下较稳，但收益优势并非均匀分布；继续用日期、品种、贡献日或阈值补这个缺口会转向过拟合。

## 继续价值反思

- 运行前判断：有价值。原因是用户要求我自己判断是否值得晋级，必须先做反过拟合审计。
- 运行后判断：有价值，但价值不在继续优化 Stage103 参数。
- 原因：Stage109 给出更清楚边界：Stage103 是当前最强执行相对候选，但不是“任何窗口收益体验都更好”的绝对版本。后续继续价值在 paper/影子盘和真实执行验证，或换更不同的收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage109 边界。
- 是否更新 `research/registry.md`：是，当前最新阶段应更新到 Stage109。
- 是否追加根目录 `memory.md/back_log.md`：建议只追加 `back_log.md`，不追加 `memory.md`。
