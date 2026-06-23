# Stage054 C9 stop/retry reentry reclaim quality audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 04:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读上界审计；不是 true engine，不是交易规则，不改正式配置。
- 是否重要突破：否；这是关闭一条 stop/retry 小变体路线。
- 是否触发A/B：否；结果不是候选，不需要读取 `skills/version-ab-experiment/SKILL.md`。

## 外部调研与判断

- 参考资料：
  - Trend Following, Stop Losses and Frequency of Trading: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126476
  - Alpha Architect 趋势跟踪 whipsaw 与右尾讨论：https://alphaarchitect.com/trend-following-the-epitome-of-no-pain-no-gain/
  - Man Group 趋势跟踪速度权衡：https://www.man.com/insights/need-for-speed-trend-following
  - Backtrader GitHub 回测/stop order 工程参考：https://github.com/mementum/backtrader
- 我的判断：趋势跟踪的核心是右尾分布，stop/retry 的微观补丁如果没有外生信息或真实可执行成交证据，容易把“慢、深、反复”的噪声误判为坏信号，结果砍掉后续大趋势。Stage054 因此只做冻结上界：如果连乐观跳过都不能降低回撤，就不进入 true engine。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage054_c9_reentry_reclaim_quality_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `low_quality_reentry_bars=120`
  - `low_quality_extra_adverse_r=0.5`
  - `fast_reclaim_bars=30`
  - 目标条件：`stop_to_reentry_bars >= 120 OR extra_adverse_after_stop_r >= 0.5`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage010 官方 C9/15w 全周期账本与 Stage861 minute bar 覆盖。
- 账户规模：`150,000`
- 成本口径：沿用官方 Stage010 曲线成本；本阶段不重算撮合和滑点。
- 样本过滤：仅审计 C9 first stop 后发生 synthetic reentry open 的事件；Stage861 当日分钟不可定位的事件单独标记 `not_reentered_or_unready` 或 `minute_index_out_of_range`。
- 策略/归因口径：官方 C9/15w 为 A；C 为“跳过 slow/deep reentry lot PnL”的 closed-lot cashflow 上界，不改变后续仓位、保证金和交易序列，因此只能作为反证上界，不能当正式回测。

## 结果

- 官方 A：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
  - broker10 峰值：`111.7365%`
- slow/deep 目标桶：
  - 目标事件：`6`
  - 产品数：`6`
  - 年份数：`4`
  - reentry lot PnL：`+1,361,035.60`
  - initial stop PnL：`-330,928.40`
  - reentry 正收益：`+1,625,720.00`
  - reentry 负收益绝对值：`264,684.40`
  - median stop-to-reentry bars：`246.0000`
  - median extra adverse R：`0.3479`
- 乐观跳过上界：
  - 期末权益：`37,815,402.00`
  - 总收益：`25110.2680%`
  - 最大回撤：`-52.9918%`
  - Sharpe：`1.5700`
  - 最大回撤改善：`-7.9091pp`，即明显恶化。
  - 收益保留：`96.5125%`
  - broker10 same-margin diagnostic 峰值：`116.8169%`
- 关键样本：
  - 目标桶大赢家：`lh2301.DCE` reentry PnL `+867,200`，`sp2205.SHFE` reentry PnL `+756,960`。
  - 目标桶亏损：`rb2305.SHFE` `-128,520`，`fu2405.SHFE` `-125,000`，`SA105.CZCE` `-11,164.40`。
  - 最差 reentry 并不主要落在目标桶：`jm2209.DCE` `-310,980` 属于 `not_reentered_or_unready`，`OI505.CZCE` `-172,500` 属于 `fast_clean_reclaim`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_report_stage054_c9_reentry_reclaim_quality_audit_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_decision_stage054_c9_reentry_reclaim_quality_audit_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_features_stage054_c9_reentry_reclaim_quality_audit_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_bucket_summary_stage054_c9_reentry_reclaim_quality_audit_v1.csv`
- daily/curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_curve_stage054_c9_reentry_reclaim_quality_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_upper_bound_path_chart_stage054_c9_reentry_reclaim_quality_audit_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_reentry_quality_scatter_stage054_c9_reentry_reclaim_quality_audit_v1.png`
- bucket chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_bucket_pnl_chart_stage054_c9_reentry_reclaim_quality_audit_v1.png`
- quality atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage054_c9_reentry_reclaim_quality_audit/qmt_roll_stage054_c9_minrisk_reentry_reclaim_quality_audit_atlas_manifest_stage054_c9_reentry_reclaim_quality_audit_v1.csv`

## 视觉分析

- 资金曲线：跳过 slow/deep reentry 的红线在 2022 主回撤段更深，最大回撤从官方 `-45.0827%` 恶化到 `-52.9918%`；后续权益也低于官方。
- broker10 图：同保证金诊断下红线峰值升到 `116.8169%`，说明该规则不是降低风险，而是削弱权益分母后放大压力。
- scatter：slow/deep 目标区混有大正收益和小/中亏损，`lh2301`、`sp2205` 直接反证“慢或深回补就是低质量”。
- bucket chart：`slow_or_deep_reclaim` 是最高正 PnL 分桶，reentry lot PnL `+1,361,035.60`；`fast_clean_reclaim` 反而为负，但样本只有 `6` 个且 retry failed 多，若转去挖 fast bucket 会变成事后救参。
- atlas：第 1 页亏损样本形态不统一；第 2 页 `sp2205/lh2301` 显示 slow/deep 后仍可走出大右尾。分钟路径没有形成可穿越周期的统一坏质量经验。

## 结论

- 本阶段结论：`stage054_slow_deep_reentry_quality_no_engine`。
- 是否进入下一步：不进入 true engine，不进入 A/B，不作为正式候选。
- 下一步：关闭 stop/retry reentry slow/deep skip 路线；不得继续扫 `120` bars、`0.5R`、fast/normal bucket、产品、方向、年份或月份。若继续 stop/retry，只能先补 tick/真实成交量或引入真正外生、重入当刻可见的信息源；否则应回到会员持仓/仓单/库存/基差等点时化数据工程。

## 过拟合反思

- 运行前判断：过拟合风险中等；因为“慢/深回补可能低质量”有第一性解释，但仍来自 stop/retry 历史事件形态，容易滑向亏损样本切片。
- 运行后判断：没有形成过拟合正式规则，风险可控；因为结果为反证并明确关闭路线。
- 原因：目标桶本身是净正贡献，且视觉上存在大右尾反例。继续调 bars/R 阈值或转挖 fast bucket 才会变成过拟合。

## 继续价值反思

- 运行前判断：有继续价值；它验证了 C9 stop/retry 里一个常见直觉，即“慢/深回补是否应跳过”。
- 运行后判断：这条具体路线没有继续价值，但阶段本身有价值。
- 原因：上界已证明跳过目标桶会恶化回撤并削弱右尾；价值在于把 stop/retry 小变体继续调参的空间收掉。

## 合入建议

- 是否更新本线 `LINE.md`：是，只追加 Stage054 结论和下一步边界。
- 是否更新 `research/registry.md`：否；不是重要突破、正式候选、跨线合并或路线废弃的全局事件。
- 是否追加根目录 `memory.md/back_log.md`：否；仅本线阶段反证。
