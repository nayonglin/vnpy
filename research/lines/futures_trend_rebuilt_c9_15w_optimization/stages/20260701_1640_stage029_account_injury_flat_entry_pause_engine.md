# Stage029 账户受伤状态暂停新 flat_entry 真实引擎候选

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：2026-07-01 16:40 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 冻结真实引擎验证；A 为当前重建 C9/15w，C 为 Stage029
- 是否重要突破：否
- 是否触发A/B：是，触发 A vs C 真实引擎验证，但不晋级正式

## 外部调研与判断

- 参考资料：Concretum position sizing、Diva CTA position sizing、pysystemtrade、CFA/managed futures trend-following 资料。
- 我的判断：账户风险预算有第一性价值，但机械 drawdown gate 容易破坏趋势右尾；本阶段只验证一个冻结的新开仓暂停规则，不扫参数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage029_account_injury_flat_entry_pause_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`enable_stage029_account_injury_pause_gate=True`、`stage029_injury_drawdown_trigger_pct=0.2`、`stage029_injury_loss_streak_trigger=3`
- 修改参数：无，官方线上 C9/15w 配置未改
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9/15w 真实引擎成本、滑点和合约乘数
- 样本过滤：每半年冷启动起点 `17` 个；目标审计覆盖 `2020-01-01` 到 `2025-06-30` 任意起点、周期大于一年
- 策略口径：仅当 opened `flat_entry` 入场前 `portfolio_drawdown_pct >= 20%` 或 `loss_streak >= 3` 时跳过该新开仓；不影响已有仓位、换月、加仓、反手、AI 池和开仓日实时止损重试

## 结果

- 期末权益最小/中位/最大：`128,660.00` / `162,795.00` / `760,201.00`
- 总收益最小/中位/最大：`-14.2267%` / `8.5300%` / `406.8007%`
- 最大回撤最差/中位：`-27.4723%` / `-12.1174%`
- Sharpe 最小/中位/最大：`-1.3722` / `0.3434` / `1.2456`
- 总滑点：`59,790.00`
- 总交易次数：`613`
- 胜率中位：`57.6923%`
- 暂停事件：`2869`；累计减少手数：`21042`
- 密集任意结束日 `>1` 年负窗口：`230729` / `7215647`，最差 `-24.7340%`
- 到 `2026-06-30` 负窗口：`433` / `13267`，最差 `-24.7340%`
- 全周期 `80%` 收益保留：`1/17`
- AI 月度审计 FAIL：`0`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage029_account_injury_flat_entry_pause_engine/rebuilt_c9_stage029_account_injury_flat_entry_pause_engine_report_stage029_account_injury_flat_entry_pause_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage029_account_injury_flat_entry_pause_engine/rebuilt_c9_stage029_account_injury_flat_entry_pause_engine_summary_stage029_account_injury_flat_entry_pause_engine_v1.csv`
- daily/curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage029_account_injury_flat_entry_pause_engine/rebuilt_c9_stage029_account_injury_flat_entry_pause_engine_curves_stage029_account_injury_flat_entry_pause_engine_v1.csv`
- injury pause events：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage029_account_injury_flat_entry_pause_engine/rebuilt_c9_stage029_account_injury_flat_entry_pause_engine_injury_pause_events_stage029_account_injury_flat_entry_pause_engine_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage029_account_injury_flat_entry_pause_engine/rebuilt_c9_stage029_account_injury_flat_entry_pause_engine_decision_stage029_account_injury_flat_entry_pause_engine_v1.json`

## 结论

- 本阶段结论：`stage029_goal_not_met_not_promoted`
- 是否进入下一步：不自动晋级；按结果决定是否需要失败归因或换方向。
- 下一步：若目标未达标，先做 Stage029 vs Stage006/013 的失败归因，不扫 `20%/25%/30%`、`loss_streak 2/3/4`、品种、方向或日期。

## 过拟合反思

- 运行前判断：有风险但可控；触发条件来自 Stage028，但冻结且只用入场前账户状态。
- 运行后判断：否。本阶段没有根据结果微调阈值；若继续救该形状的小阈值或局部窗口，就是过拟合。
- 原因：若失败后继续微调阈值或按坏窗口筛品种，就是过拟合。

## 继续价值反思

- 运行前判断：有价值；它检验 Stage028 账户受伤状态是否能真实减少左尾。
- 运行后判断：有限。若目标未达标，应先做失败归因；不要直接继续扫账户回撤或 loss_streak 阈值。
- 原因：真实引擎结果能决定账户受伤暂停是否值得进一步归因。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要 A/C 记录；`memory.md` 仅在结论改变长期策略时再追加
