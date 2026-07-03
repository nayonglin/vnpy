# Stage036 - 过热抑制 + 恢复右尾保护真实引擎候选

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T17:51:09 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`否`

## 外部调研与判断

- 参考资料：Man Group trend-following market mix、Man AHL trend following drawdown/convexity 资料、Hurst/Ooi/Pedersen 长期趋势跟随证据、GitHub 上通用 systematic trading/risk-control 代码索引。
- 我的判断：趋势跟随的核心是右尾凸性，Stage036 不能重复 Stage024 hard gate；更合理的是过热时小风险试探，恢复右尾显式豁免。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage036_overheat_recovery_pilot_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage036_overheat_recovery_gate.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`OVERHEAT_RETURN_63D_PCT=20.0`、`RECOVERY_DRAWDOWN_PROTECT_PCT=0.3`、`RECOVERY_RETURN_63D_PROTECT_PCT=-20.0`、`CONSENSUS_MIN=1`、`CONSENSUS_MAX=3`、`PILOT_MIN_VOLUME=1`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 起每半年冷启动，统一结束 `2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前重建 C9/15w 与 Stage013 真实引擎口径。
- 样本过滤：不按品种/方向/日期/source 过滤。
- 策略/归因口径：Stage013 母本 + Stage036 过热 cap 到 1 手；不连接 CTP、不调用订单 API。

## 结果

- 期末权益：见 summary 输出。
- 总收益：最小/中位/最大 `9.2077% / 232.1954% / 9643.0235%`
- 最大回撤：最差 `-44.3589%`
- Sharpe：最小/中位 `0.7325 / 1.2026`
- 总滑点：见 summary 输出。
- 总交易次数：见 summary 输出。
- 胜率：见 summary 输出。
- 其他关键指标：严格任意 `>1` 年负窗口 `515884`，严格最差 `-44.3589%`，80% 收益保留 `16/17`，Stage036 事件 `10`，减少手数 `1160`。

## 失败归因补充

- Stage036 相比 Stage013 没有改善目标，反而把严格任意 `>1` 年负窗口从 Stage013 的 `330947` 扩大到 `515884`，严格最差从 `-43.7940%` 恶化到 `-44.3589%`，80% 收益保留从 `17/17` 变为 `16/17`。
- 失败的收益保留起点是 `2021-01`，Stage006 基准收益 `1496.8265%`，Stage036 收益 `923.4413%`，收益保留比例约 `61.6933%`。
- Stage036 实际只触发 `10` 个事件，全部是 `SA.CZCE` 在 `2022-08-31` 信号、`2022-09-01` 开仓的 long flat_entry，合计减少手数 `1160`。
- 逐笔看，Stage013 原 SA301.CZCE long 在 `2022-09-01` 以 `2360` 开，`2022-09-02` 以 `2310` 平，短期确实亏损；Stage036 cap 在 `2022-09` 短期减少了亏损。
- 但曲线对比显示，短期改善随后被账户路径扰动反噬：以 `2021-01` 起点为例，`2022-09-30` Stage036 相对 Stage013 约 `+41920`，到 `2022-12-30` 已变为约 `-23070`，到 `2023-06-30` 约 `-66050`，终点 `2026-06-30` 约 `-792300`。
- 结论：问题不是“SA 这一笔亏不亏”，而是过热 cap 改变了 loss_streak、权益和后续风险释放路径；该形状属于脆弱的账户路径干预，停止继续扫 `20%/30%/consensus/1手` 周边阈值。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage036_overheat_recovery_pilot_engine/rebuilt_c9_stage036_overheat_recovery_pilot_engine_report_stage036_overheat_recovery_pilot_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage036_overheat_recovery_pilot_engine/rebuilt_c9_stage036_overheat_recovery_pilot_engine_summary_stage036_overheat_recovery_pilot_engine_v1.csv`
- orders：不适用。
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage036_overheat_recovery_pilot_engine/rebuilt_c9_stage036_overheat_recovery_pilot_engine_curves_stage036_overheat_recovery_pilot_engine_v1.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage036_overheat_recovery_pilot_engine/rebuilt_c9_stage036_overheat_recovery_pilot_engine_overheat_events_stage036_overheat_recovery_pilot_engine_v1.csv`

## 结论

- 本阶段结论：`stage036_goal_not_met_not_promoted`。
- 是否进入下一步：按决策与指标决定；若未达标，不允许扫相邻阈值救参。
- 下一步：若有改善但未达标，优先做失败归因；若收益保留失败，则停止该形状。

## 过拟合反思

- 运行前判断：否。规则来自 Stage035 的机制拆分，并做成低自由度单点；没有按品种、方向、月份、source 定制。
- 运行后判断：否。本阶段没有根据结果改阈值；若继续扫 20%/30%/consensus/手数周边就是过拟合。
- 原因：本阶段没有根据结果调整阈值；后续如果改 `20%/30%/1-3/1手` 周边就是过拟合。

## 继续价值反思

- 运行前判断：有。Stage035 已拆出过热回吐和恢复右尾，值得做一次真实引擎验真。
- 运行后判断：有限。若未达标，应先做失败归因，而不是直接救参；若收益保留失败则停止该形状。
- 原因：见核心指标和目标审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`。
