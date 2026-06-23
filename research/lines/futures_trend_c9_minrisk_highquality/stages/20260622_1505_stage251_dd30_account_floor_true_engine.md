# Stage251 dd30 账户地板真引擎反证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:05 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结 A/C 真实组合引擎回测；验证 Stage250 的 `dd30_half_risk` 日级路径代理是否能落地
- 是否重要突破：否，重要反证与路线终止
- 是否触发A/B：是，因 Stage250 有潜在正式候选价值，本阶段已按 A/B 纪律做隔离验证；结果不进入正式候选

## 外部调研与判断

- 参考资料：
  - Concretum Group, Position Sizing in Trend-Following: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - Rob Carver, vol targeting and trend following: https://qoppac.blogspot.com/2018/07/vol-targeting-and-trend-following.html
  - Quantpedia, CPPI introduction: https://quantpedia.com/introduction-to-cppi-constant-proportion-portfolio-insurance/
  - AXA IM, CPPI/TIPP 资料: https://core.axa-im.com/document/9914/view
  - SSRN, trade sizing and drawdown/tail risk: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3231836_code1554519.pdf?abstractid=2063848&mirid=1
- 我的判断：动态仓位、波动目标和账户地板是有普世风险管理价值的，但趋势跟随收益高度依赖右尾复利。CPPI/TIPP 类账户地板存在现金锁定、跳空和恢复段错失的同构风险；对当前 C9 来说，真正的风险不是日线代理能不能把回撤曲线抬高，而是整数手、主动持仓缩放、保证金分母和恢复段复利是否被切断。因此 Stage250 只能作为线索，必须由真引擎裁决。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage251_dd30_account_floor_true_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_portfolio_drawdown_gate=True`
  - `portfolio_drawdown_gate_start_pct=0.30`
  - `portfolio_drawdown_gate_full_pct=0.300001`
  - `portfolio_drawdown_gate_weight_floor=0.50`
  - `portfolio_drawdown_gate_entry_contexts="*"`
  - `enable_portfolio_drawdown_deleverage=True`
- 修改参数：无正式参数修改；仅 C 臂在研究 wrapper 内开启既有组合回撤 gate 与 active deleverage
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-06-15`，实际交易日 `2018-01-02 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：基础 `cost_multiplier=1.0`，并对 C 臂做 `2x/3x` 成本压力
- 样本过滤：无品种、年份、方向、月份、事件豁免；A 为官方 C9/15w，C 只叠加固定 `DD>=30% -> 0.5x` 账户地板
- 策略/归因口径：
  - A：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - C：同一 C9/15w 信号与执行语义，加固定账户 drawdown floor，入场和 active 持仓都按既有引擎降到 `0.5x`
  - 不改 official config、不连接 CTP/SimNow、不调用订单 API

## 结果

- A 期末权益：`39,176,437.60`
- A 总收益：`26017.6251%`
- A 最大回撤：`-45.0827%`
- A Sharpe：`1.6331`
- A 总滑点：`2,730,130`
- A 总交易次数：`787`
- A 胜率：`53.2560%`
- A broker10 峰值：`111.7365%`
- A days_over_100pct：`5`
- C 期末权益：`5,067,690.00`
- C 总收益：`3278.4600%`
- C 收益保留：`12.6009%`
- C 最大回撤：`-37.3041%`
- C 回撤改善：`7.7785pp`
- C Sharpe：`1.2979`
- C Sharpe 变化：`-0.3352`
- C 总滑点：`555,340`
- C 总交易次数：`689`
- C 胜率：`53.3621%`
- C broker10 峰值：`78.7799%`
- C days_over_100pct：`0`
- C drawdown floor active deleverage：`50` 次、`990` 手
- C drawdown gate entry：`61` 次、entry volume reduction `3332` 手
- C 3x 成本压力最大回撤：`-41.7407%`
- promotion gate：`3/6`，通过 `drawdown_improvement_5pp`、`broker10_not_worse`、`official_side_effect_isolation`，失败 `return_retention_80pct`、`sharpe_not_materially_worse`、`cost_3x_dd40_survival`
- 决策：`stage251_dd30_account_floor_true_engine_failed_return_retention_stop_route`

## 视觉分析

- path chart：C 的红线不是少掉一段噪声，而是从 `2021` 开始整个复利台阶被压扁；`2022` 回撤虽浅一些，但权益底座已远低于 A，后续恢复和右尾都回不来。
- Stage250 vs true chart：Stage250 代理判断回撤改善方向没错，真引擎回撤改善甚至从 `6.6801pp` 扩到 `7.7785pp`；但收益保留从代理 `97.21%` 崩到真引擎 `12.60%`，说明代理遗漏了 active position/整数手/复利路径语义。
- budget activity chart：降仓触发集中在 `2022` 和 `2025-2026` 这类深回撤或恢复阶段，正好切掉后续爬坡能力；早期触发也会改变本金路径，导致后面同一信号手数完全不同。
- year heatmap：C 并非单一年份坏掉；`2021` 收益从 A `1132.34%` 降到 C `429.77%`，`2023` 从 `131.54%` 降到 `66.22%`，`2025` 从 `54.12%` 降到 `0.65%`。年度回撤也不是一致改善，`2018/2021/2024/2025` 都存在更差或收益损失过大的问题。
- promotion gate chart：C 只有风控外观通过，战略目标失败；最大的问题是收益保留远低于 `80%` 且 Sharpe 被实质削弱。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_report_stage251_dd30_account_floor_true_engine_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_summary_stage251_dd30_account_floor_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_comparison_stage251_dd30_account_floor_true_engine_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_curve_stage251_dd30_account_floor_true_engine_v1.csv`
- trades：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_trades_stage251_dd30_account_floor_true_engine_v1.csv`
- gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage251_dd30_account_floor_true_engine/qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_promotion_gate_stage251_dd30_account_floor_true_engine_v1.csv`
- visuals：
  - `qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_path_chart_stage251_dd30_account_floor_true_engine_v1.png`
  - `qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_stage250_vs_true_chart_stage251_dd30_account_floor_true_engine_v1.png`
  - `qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_budget_activity_chart_stage251_dd30_account_floor_true_engine_v1.png`
  - `qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_year_heatmap_stage251_dd30_account_floor_true_engine_v1.png`
  - `qmt_roll_stage251_c9_minrisk_dd30_account_floor_true_engine_promotion_gate_chart_stage251_dd30_account_floor_true_engine_v1.png`

## 结论

- 本阶段结论：Stage250 的 `dd30_half_risk` 日级路径代理被真引擎否定。它能降低最大回撤和 broker10 尖峰，但以主动覆盖恢复段和右尾复利底座为代价，收益保留只有 `12.6009%`，远低于目标 `80%+`。
- 是否进入下一步：该 dd30 active account-floor 路线不进入下一步，不进入正式候选，不进入 A/B，不改 live/shadow 配置。
- 下一步：停止账户回撤阈值主动降仓救参；后续只能换到真正外生、入场前可见、覆盖完整且不切断 C9 右尾的风险信息，或研究部署层资金分层/出金锁盈这类不改变生产账户持仓路径的外层治理。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：本次没有新增过拟合；但继续救这条路线会过拟合。
- 原因：本阶段固定 Stage250 唯一最强线索 `dd30_half_risk`，没有扫 `25/30/35`、hysteresis、ladder、年份、产品、方向、月份或事件豁免。失败原因来自真引擎路径语义，而不是阈值没调准。若后续继续改阈值、加滞后、按年份或产品过滤，就是典型历史补丁。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：该路线无继续价值；大目标仍有价值。
- 原因：Stage250 只是日级权益路径代理，必须真引擎验真；Stage251 证明 active account floor 会覆盖右尾复利和恢复段，不能穿越周期。大目标仍有价值，但下一步不能再是账户 DD 阈值救援，而应转向外生风险状态或不改变正式持仓路径的部署层风险治理。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage251 路线终止摘要。
- 是否更新 `research/registry.md`：否，本线不新增/合并/废弃研究线。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段是真实组合引擎 A/C 反证且终止一条账户层路线，应进入总账和长期记忆。
