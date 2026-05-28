# Stage119 Stage103 Basis-Momentum期限结构Overlay审计

- 时间：2026-05-27 23:33 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：文献驱动固定结构审计；固定 Stage079 与 Stage103，不修改 C3/Stage079/Stage103 交易规则，不增加账户资金。
- 是否重要突破版本：否。重要结论是反证：期限结构 basis-momentum 与价格动量 rank blend 有局部价值，但没有形成新的晋级版本。
- 是否触发 A/B/C：是，已按 `skills/version-ab-experiment/SKILL.md` 执行。A=`Stage079`；C0=`Stage103 broker10_guard`；C1/C2=期限结构变化动量；C3/C4=期限结构变化动量与60日价格动量等权 rank blend。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage419_stage103_basis_momentum_overlay.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage419_stage103_basis_momentum_overlay_report_stage419_stage103_basis_momentum_overlay_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage419_stage103_basis_momentum_overlay_chart_stage419_stage103_basis_momentum_overlay_v1.png`
- 决策 JSON：`no_new_promotion`

## 运行前反思

- 是否在过拟合：否。原因是本阶段先用外部可解释的 basis-momentum/term-structure 思路，固定 `105/252` 两个长窗口、月频再平衡、top/bottom 各3个品种和 `1.10` 倍保证金闸门，不根据失败窗口调阈值、日期、品种或权重。
- 是否仍有价值继续做：是。Stage104 已显示 Stage103 的短持有缺口来自趋势暴涨后反转/水下恢复，期限结构变化可能是不同于价格动量的风险源，值得一次固定结构审计。

## 外部调研与判断

- `Basis-Momentum` 文献明确提出商品期货基差/期限结构变化与未来收益存在可研究关系：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1127213
- `Tactical Allocation in Commodity Futures Markets: Combining Momentum and Term Structure Signals` 这类研究显示动量与期限结构信号可组合使用：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3459861
- GitHub/Python 开源实现里也常见商品期货动量、carry/term-structure、basis 类组合回测，但大多没有我们的整数手、保证金、冷启动和短持有体验闸门。
- 我的判断：这个方向有经济含义，不能因为 Stage068 的简单斜率卫星失败就完全否定；但如果 fixed basis-momentum 在 `start_2022` 冷启动和相对 Stage103 任意启动风险胜率上失败，就不能继续扫 lookback、rank blend 比例或日期过滤救结果。

## 版本变更

- 新增参数：
  - `basis_mom105`：使用 `curve_slope` 的 `105` 交易日变化，全部 `shift(1)`，月频再平衡，强者多、弱者空，各 `top_n=3`。
  - `basis_mom252`：使用 `curve_slope` 的 `252` 交易日变化，全部 `shift(1)`，月频再平衡，强者多、弱者空，各 `top_n=3`。
  - `basis_mom105 + price_mom60 rank blend`：期限结构变化分位 rank 与60日价格动量分位 rank 等权相加。
  - `basis_mom252 + price_mom60 rank blend`：期限结构变化分位 rank 与60日价格动量分位 rank 等权相加。
  - 保持 Stage103 的 `1.10` 倍 broker 保证金闸门。
- 修改参数：无正式策略参数修改。
- 删除参数：无正式策略参数删除。
- 新增回测结果：全周期、3/6个月持有体验、多起点冷启动、成本压力、10%保证金缓冲、Stage104底部5%坏窗口贡献、任意启动 pairwise、顶部相对贡献日剔除。
- 修改回测结果：无。
- 删除回测结果：无。

## 核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 48.3478% |
| Stage103 | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 50.3432% |
| basis105 | 31,634,830 | 5043.8748% | -29.1241% | 1.3753 | 14.1777 | 1,589,905 | 1,909 | 51.1659% |
| basis252 | 31,702,070 | 5054.8081% | -29.3797% | 1.3596 | 14.3278 | 1,586,435 | 1,801 | 50.5693% |
| basis105 + price60 | 32,036,215 | 5109.1407% | -28.2748% | 1.3905 | 13.9567 | 1,591,715 | 1,977 | 51.2991% |
| basis252 + price60 | 32,154,010 | 5128.2943% | -29.3998% | 1.3756 | 14.0718 | 1,588,285 | 1,859 | 50.6702% |

## 3个月/6个月体验

- Stage103：3个月分 `121.2041`，6个月分 `134.4513`。
- basis105：3个月分 `128.4956`，6个月分 `146.2264`，但低于 Stage103 总收益且冷启动失败。
- basis252：3个月分 `135.3835`，6个月分 `135.2628`，但低于 Stage103 多项指标且冷启动失败。
- basis105 + price60：3个月分 `130.2349`，6个月分 `154.4285`，90/180日目标改善均为 `7/8`，全周期总收益、最大回撤、Sharpe、Ulcer 都优于 Stage079 和 Stage103；但 `fresh_start_dd30_pass=0`。
- basis252 + price60：3个月分 `128.7437`，6个月分 `141.8194`，全周期收益最高，但最大回撤不如 Stage103，且冷启动失败。

## 硬失败点

- Stage405 闸门下无任何新增版本通过 `research_promotion_pass` 或 `execution_relative_pass`。
- 主要失败原因：
  - `fresh_start_dd30_pass`：所有新增版本在 `start_2022` 至少一个口径穿越30%回撤。
  - `cost_stress_not_worse_than_stage103`：纯 basis105/basis252 与 basis252+price60 在相对 Stage103 的成本压力中不稳定。
  - `bad_window_not_worse_than_stage103`：basis105+price60 的 90日底部5%坏窗口相对 Stage103 平均 `-0.0365pp`，没有稳定覆盖最差短窗口。
- 典型冷启动：
  - `start_2022` Stage079 `565.5902%/-29.9039%`，Stage103 `641.6878%/-28.5161%`。
  - `start_2022` basis105 `623.1537%/-38.4721%`，basis252 `656.1797%/-43.1571%`。
  - `start_2022` basis105+price60 `670.7220%/-31.7549%`，basis252+price60 `657.7130%/-44.2438%`。

## 任意启动相对 Stage103

- basis105 相对 Stage103 的 `90/180/252/504` 日收益胜率为 `55.83%/59.74%/56.48%/63.86%`，但最大回撤不劣化率仅约 `34.85%/38.62%/40.46%/48.70%`，收益来自承担更差路径风险。
- basis252 收益胜率为 `61.77%/70.20%/66.49%/63.31%`，但最大回撤不劣化率仅 `35.52%/30.55%/25.06%/12.40%`，风险代价过高。
- basis105+price60 收益胜率仅 `50.92%/47.25%/41.14%/45.71%`，风险不劣化率较好，但不能证明任意启动收益端优于 Stage103。
- basis252+price60 收益胜率为 `63.89%/59.64%/56.19%/61.43%`，风险不劣化率中等，但 `start_2022` 和全周期最大回撤相对 Stage103 失败。

## 顶部贡献日剔除

- basis105+price60 相对 Stage103 全周期多 `49.6423pp` 收益；剔除最大 `10` 个相对贡献日后仍多 `3.2789pp`，剔除 `20` 个后低于 Stage103 `-29.4496pp`。
- basis252+price60 相对 Stage103 全周期多 `68.7959pp` 收益；剔除最大 `20` 个相对贡献日后仍多 `0.9285pp`，但最大回撤仍劣于 Stage103。
- 结论：basis blend 不是“只靠一天”的脆弱结果，但收益韧性不能覆盖冷启动和风险胜率失败。

## 决策

- 不晋级任何 Stage119 新版本。
- 如果允许“不按目标晋级”，我的判断仍是不晋级：basis105+price60 是本阶段最接近的强研究候选，但它失败在 `start_2022` 的 `-31.7549%` 回撤和10%保证金上浮拒单；这正是用户要改善的“任何时候启动”的体验，而不是可忽略的小瑕疵。
- 当前主执行相对候选仍是 Stage103：`xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- 期限结构 basis-momentum 保留为“经济含义成立、固定路径有局部增益、但当前承载不适合本线硬目标”的经验，不继续救 `105/252`、rank blend 权重、top_n、月频/周频、日期、品种或保证金小数。

## 后续规划

1. 固定 Stage103 做工程化复跑、paper/影子盘和真实券商保证金接入。
2. 若继续追理想3/6个月体验，不应继续商品动量、股指 TSMOM 或 basis-momentum 的相邻窗口/比例救援；应转向更不同的风险源，或把问题拆到“C3本体暴涨后反转的仓位释放/组合保护”但必须先设低自由度规则再验证。
3. 对 basis-momentum 只保留只读经验：它能改善部分全周期指标，但不能解决最关键的冷启动水下路径。

## 运行后反思

- 是否在过拟合：否。本阶段没有因为 basis105+price60 接近通过而继续调窗口、比例、日期或品种过滤，主动拒绝了全周期漂亮但冷启动失败的版本。
- 是否还有价值继续做：basis-momentum 子路线继续主动优化价值低；总目标仍有价值，但应该停止这类相邻商品横截面风格因子救援，回到 Stage103 执行落地或寻找真正不同的风险源。

## 合入建议

- 更新本线 `LINE.md`：是，追加 Stage119 约束。
- 更新 `research/registry.md`：是，最新关键阶段改为 Stage119。
- 追加根目录 `memory.md/back_log.md`：是。本阶段是“停止 basis-momentum/basis+price rank blend 子路线”的重要反证。
