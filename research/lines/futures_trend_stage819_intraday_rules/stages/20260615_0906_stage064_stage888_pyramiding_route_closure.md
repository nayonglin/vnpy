# Stage064 Stage888 pyramiding/sleeve 路线收束审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：day
- 记录时间：2026-06-15 09:06 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage881-887 pyramiding/sleeve 分支收束；只读归纳，不新增交易规则，不重跑新引擎。
- 是否重要突破：否。这是路线关闭记录，不是正式候选或 A/B 候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - vn.py / VeighNa 官方 GitHub：`https://github.com/vnpy/vnpy`
  - CME Group open interest 教育资料：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest.html`
  - 趋势跟随 pyramiding / portfolio heat 资料：用于确认“盈利后加仓”是经典思路，但必须受组合热度和生存线约束。
- 我的判断：
  - pyramiding 的第一性逻辑是让已证明方向的仓位参与右尾；这在 Stage881 proxy 和 Stage882 true engine 中确实成立。
  - 但期货组合的约束不是单笔方向正确，而是保证金/权益路径能不能活下来。Stage882/883 已显示真实加仓后 broker10 和 Sharpe 不穿越周期。
  - OI/成交量/压力状态可以解释参与度或风险状态，但 Stage885-887 已反证它们不能低误伤地变成退出、减仓或禁加仓规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage888_stage887_pyramiding_route_closure.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无；本阶段不新增交易参数，只读取 Stage881-887 既有输出。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage881-887 已生成的全周期输出，不新增数据切片。
- 账户规模：沿用 Stage819 候选 30w / C9、C16、C17 既有口径。
- 成本口径：沿用 Stage881-887 输出；本阶段不重算交易成本。
- 样本过滤：读取 Stage881-887 决策、comparison、bucket、shape、gate、manifest 文件。
- 策略/归因口径：路线收束 scorecard，核心检查 true engine 生存、small sleeve 风险调整收益、pressure exit、pressure gate 与视觉证据。

## 结果

- 期末权益：本阶段不新增组合回测；源结果引用 Stage882 C16 `134,885,396.7`、Stage883 C17 `51,683,814.65`。
- 总收益：本阶段不新增组合回测；源结果引用 Stage882 C16 `44,861.7989%`。
- 最大回撤：本阶段不新增组合回测；源结果引用 Stage882 C16 `-61.6881%`、Stage883 C17 `-41.1625%`。
- Sharpe：本阶段不新增组合回测；源结果引用 Stage882 C16 `1.5740`、Stage883 C17 `1.6223`。
- 总滑点：本阶段不新增组合回测；源结果引用 Stage882 C16 `8,279,150`、Stage883 C17 `3,921,000`。
- 总交易次数：本阶段不新增组合回测；源结果引用 Stage882 C16 `1,045`、Stage883 C17 `1,051`。
- 胜率：本阶段不新增组合回测；源结果引用 Stage882 C16 `51.6784%`、Stage883 C17 `53.4863%`。
- 其他关键指标：
  - Stage881 proxy：`176` 个候选，proxy delta `+34,513,422.10`。
  - Stage882 C16：相对 C9 期末权益 `+84,248,252.10`，但 max broker10 `203.4450%`，最大回撤相对 C9 恶化 `-19.0568pp`，Sharpe 相对 C9 `-0.0572`。
  - Stage883 C17：相对 C9 期末权益 `+1,046,670.05`，最大回撤改善 `+1.4687pp`，但 Sharpe 相对 C9 `-0.008835`，max broker10 `127.4316%`。
  - Stage884：C17 top10 broker10 峰值 `10/10` 为 `exposure_numerator_expansion`。
  - Stage885：C17 pressure days `25`，median next20 return `16.9511%`，negative next20 share `8.0000%`。
  - Stage886：`price_failure_shape` EOD proxy delta `-2,853,650.00`，winner cut `-3,353,030.00`，median next20 return `22.1098%`。
  - Stage887：`G4_prev_pressure_or_projected_after_heat80` skip proxy `-114,051.15`，loser saved `56,695.80`，winner cut `-170,746.95`。
  - Stage888 decision：`stage888_pyramiding_sleeve_route_closed_no_more_param_rescue`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_report_stage888_stage887_pyramiding_route_closure_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_route_summary_stage888_stage887_pyramiding_route_closure_v1.csv`
- scorecard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_scorecard_stage888_stage887_pyramiding_route_closure_v1.csv`
- visual index：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_visual_index_stage888_stage887_pyramiding_route_closure_v1.csv`
- summary chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_summary_chart_stage888_stage887_pyramiding_route_closure_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage888_stage887_pyramiding_route_closure_decision_stage888_stage887_pyramiding_route_closure_v1.json`

## 结论

- 本阶段结论：Stage881-887 pyramiding/sleeve 分支关闭。`+0.5R progress` 是真实右尾参与标签，但从同手数加仓到 1 手 sleeve，再到 pressure exit / pressure gate，均不能形成可推广、低误伤、能穿越保证金生存线的规则。
- 是否进入下一步：本分支不进入下一步。
- 下一步：
  - 不再扫 progress R、加仓比例、1/2/3 手 sleeve、止损位置、heat 阈值、产品方向、年份或分钟窗口。
  - 若继续本线，应回到 C9 本体，寻找新的低自由度外生信息源，或研究账户级非交易层生存线，而不是继续新增仓救参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只汇总既有冻结测试和只读证据，不产生新参数、不挑年份品种、不按峰值样本反推规则。真正会过拟合的是继续围绕 sleeve 手数、progress R、heat 阈值、产品方向和年份做补丁式救参。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：pyramiding/sleeve 分支继续价值低；整条候选分钟规则研究线仍有价值。
- 原因：本阶段把一条连续反证分支正式收束，能减少重复探索。继续价值应转移到 C9 本体的新信息源或账户层非交易生存线，而不是继续在已反证形状上微调。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage064 当前状态和后续规划。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为本线分支关闭记录，不是正式候选或重要合入摘要。
