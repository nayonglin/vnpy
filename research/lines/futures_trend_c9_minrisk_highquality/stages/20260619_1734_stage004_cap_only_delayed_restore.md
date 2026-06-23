# Stage004 C9/15w broker10 cap-only delayed restore 反证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 17:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前官方正式 C9/15w 的冻结 A vs C 真实组合引擎；只在正式版已有 broker10 cap 降手事件内尝试分钟级延迟恢复
- 是否重要突破：否。属于重要负结果，明确停止 cap-only delayed restore 形状。
- 是否触发A/B：是，A vs C。C 是可能影响正式版执行/风险治理的部署层候选，因此按 `skills/version-ab-experiment/SKILL.md` 记录。

## 外部调研与判断

- 参考资料：
  - SSRN `Trend Following Strategies: A Practical Guide`：https://papers.ssrn.com/sol3/Delivery.cfm/5140633.pdf?abstractid=5140633&mirid=1
  - SSRN `Position sizing methods for a trend following CTA`：https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
  - SSRN `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4438260_code412374.pdf?abstractid=4438260&mirid=1
  - `pysystemtrade` / Rob Carver 系统化期货框架：https://github.com/pst-group/pysystemtrade
- 我的判断：
  - 外部资料支持趋势系统的仓位、波动、杠杆和保证金纪律，也支持把风险释放规则放进完整路径和成本压力里验证。
  - 外部资料不支持复制一个分钟级别的具体 `R` 倍数、比例或确认窗口；这类参数必须来自本地策略结构和冻结验证，而不是看结果后扫参。
  - Stage004 因而只采用一个低自由度原则：触发条件不新增，只沿用正式版 Stage830 broker10 cap 已经判定“账户压力过高”的事件；在这些事件里把风险释放顺序后移，而不是全量机械半仓。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage004_cap_only_delayed_restore.py`
- 修改脚本：
  - 同脚本内修复输出统计兼容性：当 `entry_risk` 不含 Stage830 字段时，从 `trade_events` 的 `broker10_margin_cap_reduce` 事件恢复候选表，并标记实际拆分；不改变策略路径。
- 删除脚本：无。
- 新增参数：
  - `enable_stage004_cap_only_delayed_restore=True`
  - `trigger = stage830_broker10_margin_cap_applied == 1`
  - 复用 Stage002 冻结参数：`stage002_initial_fraction=0.50`、`stage002_progress_r=0.50`
  - 恢复层止损：原入场价
- 修改参数：无正式参数修改；不改 C9 `0.5R` stop/retry，不改品种池、AI池、资金口径、执行链路。
- 删除参数：无。

## 回测/验证参数

- A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- C：`C_stage004_cap_only_delayed_restore`
- 区间：`2018-01-01 -> 2026-06-15`
- 账户：`150,000`
- 数据：日线组合真实回放 + 触发事件入场日分钟 K atlas
- 成本：主口径 `1x`，并输出候选 `2x/3x` 成本压力
- 触发样本：
  - broker10 cap 候选事件：`30`
  - 实际进入 Stage004 拆分事件：`10`
  - restore events：`4`
  - restore 后同日止损：`3`
- 不连接 CTP，不读取真实账户，不调用订单 API。

## 结果

| 指标 | A 官方 C9/15w | C Stage004 |
| --- | ---: | ---: |
| 期末权益 | `39,176,437.60` | `23,490,523.20` |
| 总收益 | `26017.6251%` | `15560.3488%` |
| 收益保留 | - | `59.8070%` |
| 最大回撤 | `-45.0827%` | `-52.7338%` |
| 回撤改善 | - | `-7.6512pp` |
| Sharpe | `1.6331` | `1.4828` |
| 总滑点 | `2,730,130` | `1,760,560` |
| 总交易次数 | `787` | `724` |
| 胜率 | `53.2560%` | `52.8201%` |
| broker10 峰值 | `111.7365%` | `117.9016%` |
| days_over_100pct | `5` | `3` |

- 路径峰谷：
  - A peak `2022-03-09`：`9,506,358.50`，trough `2022-06-29`：`5,220,639.60`，DD `-45.0827%`
  - C peak `2022-03-09`：`4,761,449.50`，trough `2022-06-29`：`2,250,555.50`，DD `-52.7338%`
- C 的 2x 成本压力：
  - 期末权益 `21,729,963.20`
  - 总收益 `14386.6421%`
  - 最大回撤 `-56.3601%`
  - Sharpe `1.4009`
  - broker10 峰值 `130.4534%`
  - days_over_100pct `14`
- C 的 3x 成本压力：
  - 期末权益 `19,969,403.20`
  - 总收益 `13212.9355%`
  - 最大回撤 `-60.3470%`
  - Sharpe `1.3200`
  - broker10 峰值 `145.9962%`
  - days_over_100pct `21`

## 视觉分析

- 资金曲线显示 C 从 `2020` 开始持续低于 A，`2022-03-09` 的高水位只有 A 的约一半；之后 C 的复利斜率没有追上。这不是“少风险换同等右尾”，而是提前削弱了主趋势复利底座。
- 回撤曲线显示 A 与 C 的最深回撤发生在同一段 `2022-03-09 -> 2022-06-29`，但 C 的回撤更深，说明 cap-only 延迟恢复没有把账户压力转化成更好的权益路径。
- broker10 曲线显示 C 的 days_over_100pct 从 `5` 降到 `3`，但峰值从 `111.7365%` 恶化到 `117.9016%`；3x 成本下进一步恶化到 `145.9962%`。这说明局部少几天穿线不等于尾部风险真正下降。
- 分钟 K atlas 显示，4 次 restore 中只有 `SM101` 恢复后未在入场日止损；`ru2101`、`MA205`、`rb2205` 均在触达 `+0.5R` 后又回到原入场价止损，其中 `MA205` 恢复 `151` 手、`rb2205` 恢复 `121` 手，恰好发生在 2021-2022 右尾/压力段，增加路径脆弱性。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_report_stage004_cap_only_delayed_restore_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_decision_stage004_cap_only_delayed_restore_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_summary_stage004_cap_only_delayed_restore_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_comparison_stage004_cap_only_delayed_restore_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_curve_stage004_cap_only_delayed_restore_v1.csv`
- cost stress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_cost_stress_stage004_cap_only_delayed_restore_v1.csv`
- cap delay events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_cap_delay_eligible_events_stage004_cap_only_delayed_restore_v1.csv`
- restore events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_restore_events_stage004_cap_only_delayed_restore_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_path_chart_stage004_cap_only_delayed_restore_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage004_cap_only_delayed_restore/qmt_roll_stage004_c9_minrisk_cap_only_delayed_restore_atlas_page001_stage004_cap_only_delayed_restore_v1.png`

## 结论

- 决策：`stage004_cap_only_delayed_restore_not_promoted_no_param_rescue`
- 不进入多起点扩展验证，不接正式候选，不做参数救援。
- 原因：
  - 收益保留只有 `59.8070%`，远低于 `80%` 硬门槛。
  - 最大回撤恶化 `7.6512pp`，不是降低回撤。
  - broker10 峰值恶化，成本压力下回撤和 broker10 尾部进一步恶化。
  - 视觉上 C 在 2020-2022 削弱了复利高水位，后续没有补回；分钟 atlas 也显示恢复层经常是“刚确认又回撤止损”。
- 不允许的后续：
  - 不扫 `initial_fraction`、`progress_r`、恢复止损、恢复窗口或只对某些品种/方向/年份启用。
  - 不把 broker10 cap 事件再按交易所、品种、年份、月份、手数阈值筛选救参。
  - 不把 Stage002 的 delayed restore 形状包装成“只要触发更窄就能用”。

## 过拟合反思

- 运行前判断：否，触发条件来自正式版已有 Stage830 broker10 cap，不新增账户压力阈值。
- 运行后判断：否，仅限本次冻结验证；若继续筛 cap 事件、扫比例/R 或按大手数事件补丁化，就会过拟合。
- 原因：
  - 本次没有按历史弱窗口或具体品种设计触发条件。
  - 失败是全路径、收益、回撤、broker10、成本压力和视觉路径共同失败，不是一个局部参数没调好。
  - 触发样本集中在账户压力时刻，本来就是策略最脆弱的右尾复利区；继续微调会变成对 2020-2022 路径做局部补丁。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：这个具体形状没有继续价值；整条研究线仍有价值。
- 原因：
  - C9/15w 的高回撤和 broker10 尾部仍是真问题。
  - Stage004 反证了“只把 Stage002 缩窄到已有 broker10 cap 事件”仍然会破坏右尾，说明风险释放顺序本身不对。
  - 下一步应先做只读视觉归因：把 30 个 broker10 cap 事件、10 个实际拆分事件、以及 C9 的大赢家/大亏入场分钟形态放在同一图谱里，找是否存在入场当时可见、普世且不砍右尾的质量结构；在看到结构前不再写交易规则。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：否；并行新线仍由合入者统一更新 registry。
- 追加根目录 `back_log.md`：是；本次属于 A vs C 回测，按 A/B 技能要求记录。
