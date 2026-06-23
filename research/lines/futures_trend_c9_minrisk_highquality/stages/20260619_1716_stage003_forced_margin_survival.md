# Stage003 C9/15w 强制保证金生存层反证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 17:16 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前官方正式 C9/15w 的冻结 A vs C 真实组合引擎；账户层保证金生存线验证
- 是否重要突破：否。属于重要负结果，明确停止全局 forced margin 形状。
- 是否触发A/B：是，A vs C。C 是可能影响正式版风险治理的部署/账户层候选，因此按 `skills/version-ab-experiment/SKILL.md` 记录。

## 外部调研与判断

- 参考资料：
  - SSRN `Trend Following, Stop Losses, and the Frequency of Trading`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126476
  - SSRN `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1
  - SSRN `Trend Following, Risk Parity and Momentum in Commodity Futures`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
  - `pysystemtrade` / Rob Carver 系统化期货框架：https://github.com/pst-group/pysystemtrade
- 我的判断：
  - 外部资料支持趋势系统必须有仓位、杠杆、保证金和成本压力治理，也支持用简单、稳定、可复验的规则做多周期验证。
  - 外部资料不支持在看到失败后继续扫 `95/80` 周边小数，也不支持把保证金压力日按品种、年份或方向写成补丁。
  - 本阶段只采用一个冻结粗档：`broker10 95% -> 80%` 最大保证金减仓。它若不能在 C9/15w 真实路径上改善回撤并保留右尾，就直接反证。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage003_forced_margin_survival.py`
- 修改脚本：无正式策略脚本修改；只新增本线隔离研究脚本。
- 删除脚本：无。
- 新增参数：
  - `enable_forced_margin_deleverage=True`
  - `forced_margin_deleverage_trigger_ratio=0.95`
  - `forced_margin_deleverage_target_ratio=0.80`
  - `forced_margin_deleverage_broker_multiplier=1.65`
  - `forced_margin_deleverage_priority="largest_margin"`
  - `forced_margin_deleverage_max_reductions_per_day=100`
- 修改参数：无正式参数修改；不改 C9 `0.5R` stop/retry，不改品种池、AI池、资金口径、执行链路。
- 删除参数：无。

## 回测/验证参数

- A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- C：`C_stage003_forced95_to80_largest_margin`
- 区间：`2018-01-01 -> 2026-06-15`
- 账户：`150,000`
- 数据：日线组合回测 + forced event 当日分钟 K atlas
- 成本：主口径 `1x`，并输出候选 `2x/3x` 成本压力
- 输出：A/C 全路径资金曲线、回撤曲线、broker10 曲线、forced events 表、压力日分钟 K atlas、决策 JSON
- 不连接 CTP，不读取真实账户，不调用订单 API。

## 结果

| 指标 | A 官方 C9/15w | C Stage003 |
| --- | ---: | ---: |
| 期末权益 | `39,176,437.60` | `23,126,332.60` |
| 总收益 | `26017.6251%` | `15317.5551%` |
| 收益保留 | - | `58.8738%` |
| 最大回撤 | `-45.0827%` | `-54.1289%` |
| 回撤改善 | - | `-9.0463pp` |
| Sharpe | `1.6331` | `1.4817` |
| 总滑点 | `2,730,130` | `1,737,640` |
| 总交易次数 | `787` | `720` |
| 胜率 | `53.2560%` | `52.6410%` |
| broker10 峰值 | `111.7365%` | `122.6604%` |
| days_over_100pct | `5` | `6` |

- C forced event：`13` 次
- C forced closed volume：`342` 手
- C forced 最大触发前 ratio：`133.1634%`
- C forced 最大触发后 ratio：`92.9658%`
- 路径峰谷：
  - A peak `2022-03-09`：`9,506,358.50`，trough `2022-06-29`：`5,220,639.60`，DD `-45.0827%`
  - C peak `2022-03-09`：`4,542,887.30`，trough `2022-06-29`：`2,083,870.30`，DD `-54.1289%`
- C 的 3x 成本压力：
  - 期末权益 `19,651,052.60`
  - 总收益 `13000.7017%`
  - 最大回撤 `-62.1094%`
  - Sharpe `1.3137`
  - broker10 峰值 `154.6067%`
  - days_over_100pct `20`

## 视觉分析

- 资金曲线显示 C 从 `2020` 起长期低于 A，`2022-03-09` 的高水位只有 A 的约一半；这意味着 forced margin 不是只切坏仓，而是在早期直接削弱了右尾复利底座。
- 回撤曲线显示 C 在 `2022-06-29` 的回撤更深，说明“减仓降低保证金”没有转换为账户权益路径的稳定性。
- broker10 曲线显示 C 虽然若干触发日能把 runtime ratio 打回 `80%` 附近，但全路径 exact broker10 峰值仍从 A 的 `111.7365%` 恶化到 `122.6604%`，3x 成本下升到 `154.6067%`。
- 分钟 K atlas 显示，典型 forced 事件发生在 `ru/rb/CF/jm/MA` 等趋势长仓上；例如 `2020-07-09 ru2009` 从 `6` 手直接减到 `0`，`2022-01-13 rb2205` 从 `236` 手减到 `111` 手，`2022-03-29 CF205` 从 `109` 手减到 `43` 手。这些动作是保证金压力下的粗砍仓，不是高质量信号的低风险入场/退出纪律。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_report_stage003_forced_margin_survival_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_decision_stage003_forced_margin_survival_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_summary_stage003_forced_margin_survival_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_comparison_stage003_forced_margin_survival_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_curve_stage003_forced_margin_survival_v1.csv`
- cost stress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_cost_stress_stage003_forced_margin_survival_v1.csv`
- forced events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_forced_events_stage003_forced_margin_survival_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage003_forced_margin_survival/qmt_roll_stage003_c9_minrisk_forced_margin_survival_path_chart_stage003_forced_margin_survival_v1.png`
- minute atlas：
  - `qmt_roll_stage003_c9_minrisk_forced_margin_survival_atlas_page001_stage003_forced_margin_survival_v1.png`
  - `qmt_roll_stage003_c9_minrisk_forced_margin_survival_atlas_page002_stage003_forced_margin_survival_v1.png`
  - `qmt_roll_stage003_c9_minrisk_forced_margin_survival_atlas_page003_stage003_forced_margin_survival_v1.png`
  - `qmt_roll_stage003_c9_minrisk_forced_margin_survival_atlas_page004_stage003_forced_margin_survival_v1.png`

## 结论

- 决策：`stage003_forced_margin_survival_not_promoted_no_threshold_rescue`
- 不进入多起点扩展验证，不接正式候选，不做阈值救援。
- 原因：
  - 收益保留只有 `58.8738%`，显著低于 `80%` 硬门槛。
  - 最大回撤恶化 `9.0463pp`，不是降低回撤。
  - broker10 峰值和 days_over_100pct 均恶化。
  - 成本压力下 C 的最大回撤和 broker10 尾部进一步恶化。
- 不允许的后续：
  - 不扫 `trigger=0.90/0.95/1.00` 或 `target=0.75/0.80/0.85`
  - 不换 `largest_margin/largest_loss` 来救同一形状
  - 不按 `ru/rb/CF/jm/MA`、年份、方向、交易所或月份补丁化

## 过拟合反思

- 运行前判断：否，但边界很窄。
- 运行后判断：否，仅限本次冻结验证；若继续救参会立即转为过拟合。
- 原因：
  - 本次只测一个旧体系已有证据的粗档账户生存层，没有看结果后调小数。
  - 结果是全路径失败，不是某个局部参数没调好。
  - forced 事件命中的多是趋势右尾仓，说明问题在形状本身，而不是单一品种或窗口。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：这个具体形状没有继续价值；整条研究线仍有价值。
- 原因：
  - C9/15w 的 DD40/DD50 与 broker10 尾部仍真实存在。
  - Stage003 说明“持仓后看到保证金压力就全局砍最大保证金仓”不是正确答案，它砍掉右尾复利底座。
  - 下一步必须换第一性原则：寻找不系统性砍赢家的低风险参与方式，或先做高质量信号/右尾保留的只读视觉归因；不能继续保证金阈值小数救援。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：否；并行新线仍由合入者统一更新 registry。
- 追加根目录 `back_log.md`：是；本次属于 A vs C 回测，按 A/B 技能要求记录。
