# Stage046 Entry-Day Confirmed Breakeven True Engine

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 02:44 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结 A vs C 真实组合引擎 / 当前官方 C9/15w 上的分钟级保本候选验证
- 是否重要突破：否，属于候选反证与路线废弃
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 做最小有效 `A vs C`；未进入多起点或正式候选

## 外部调研与判断

- 参考资料：
  - Backtrader Stop-Loss Trading：`https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/`
  - Backtrader StopTrail：`https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/`
  - NautilusTrader Backtesting：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - NautilusTrader Orders：`https://nautilustrader.io/docs/latest/concepts/orders/`
  - vn.py `BarGenerator` GitHub 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
- 我的判断：
  - stop、trailing stop、breakeven 本身是普世风险管理形状，但必须写成明确事件顺序和撮合语义，不能从日内 OHLC 推断同根先后。
  - Stage046 因此冻结为“官方 C9 先执行、官方 C2 `+1R` confirm 先发生后，下一根以后回踩入场价才保本退出”；同根 confirm+breakeven 保持官方路径。
  - 这个候选的第一性理由是：方向已经证明后，把剩余入场日风险移到不亏；不是按历史亏损样本筛选，也不是调整 R 倍数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage046_entry_day_confirmed_breakeven_true_engine.py`
- 修改脚本：无正式策略脚本；仅本线新增研究工具
- 删除脚本：无
- 新增参数：
  - `enable_stage046_entry_day_confirmed_breakeven=True`
  - 固定规则：官方 C2 `+1R` confirm 先于 C2 `-1R` stop 后，下一根分钟K开始若同日回踩原始入场价，则按入场价保本退出 active same-direction layers
- 修改参数：无正式参数修改；不改 C9 `0.5R`、不改重试次数、不改 C2 `1R`
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方成本，另输出 `1x/2x/3x` 成本压力
- 样本过滤：无收益过滤；缺分钟K、风险无效、C9 stop/retry 先触发、C2 stop 先触发、同根 confirm+breakeven、无 confirm 或无回踩均保持官方路径
- 策略/归因口径：
  - A：当前官方正式 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
  - C：A + `entry_day_confirmed_breakeven`
  - 不改正式配置、不连接 CTP、不调用订单 API

## 结果

- A 期末权益：`39,176,437.60`
- A 总收益：`26017.6251%`
- A 最大回撤：`-45.0827%`
- A Sharpe：`1.6331`
- A 总滑点：`2,730,130`
- A 总交易次数：`787`
- A 胜率：`53.2560%`
- A broker10 峰值：`111.7365%`
- C 期末权益：`30,476,991.80`
- C 总收益：`20217.9945%`
- C 收益保留：`77.7088%`
- C 最大回撤：`-62.8055%`
- C Sharpe：`1.5351`
- C 总滑点：`2,582,120`
- C 总交易次数：`789`
- C 胜率：`52.6557%`
- C broker10 峰值：`134.2634%`
- C days_over_100pct：`6`
- 其他关键指标：
  - breakeven events：`34`
  - breakeven exit volume：`7,335`
  - stop_retry_event_count：`125`
  - 3x 成本压力：期末权益 `25,312,751.80`，总收益 `16775.1679%`，最大回撤 `-79.6247%`，Sharpe `1.2994`
  - triggered events 官方路径匹配：`34` 个事件匹配 `28` 行 official closed-lot PnL；官方原路径净 PnL `+3,803,769.40`，正贡献 `+5,867,420.00`，负贡献 `-2,063,650.60`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_report_stage046_entry_day_confirmed_breakeven_true_engine_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_summary_stage046_entry_day_confirmed_breakeven_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_comparison_stage046_entry_day_confirmed_breakeven_true_engine_v1.csv`
- events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_breakeven_events_stage046_entry_day_confirmed_breakeven_true_engine_v1.csv`
- official event match：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_official_event_match_stage046_entry_day_confirmed_breakeven_true_engine_v1.csv`
- daily/curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_curve_stage046_entry_day_confirmed_breakeven_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_path_chart_stage046_entry_day_confirmed_breakeven_true_engine_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage046_entry_day_confirmed_breakeven_true_engine/qmt_roll_stage046_c9_minrisk_entry_day_confirmed_breakeven_true_engine_atlas_page001_stage046_entry_day_confirmed_breakeven_true_engine_v1.png` 至 `page004`

## 结论

- 本阶段结论：
  - Stage046 失败，决策：`stage046_failed_return_retention_no_param_rescue`。
  - 收益保留只有 `77.7088%`，未达 `80%` 硬要求；更严重的是最大回撤从 `-45.0827%` 恶化到 `-62.8055%`，broker10 峰值从 `111.7365%` 恶化到 `134.2634%`。
  - 触发事件在官方原路径中不是坏信号集合，匹配 closed-lot 净 PnL 为 `+3,803,769.40`；少数右尾赢家被保本退出后，权益分母下降，后续同样回撤时百分比和 broker10 均更差。
  - 视觉上，资金曲线显示 C 从 `2021-2023` 明显低于 A；回撤 trough 从 A 的 `2022-06-29` 延后到 C 的 `2023-03-08` 且更深；atlas 中多笔大手数样本在早段确认后只是日内回踩，后续仍可能是官方右尾。
- 是否进入下一步：不进入多起点、不进入正式候选、不触发 promotion。
- 下一步：
  - 停止 `entry_day_confirmed_breakeven` 形状，不做 confirm R、保本价、同根处理、产品/方向/年份/月度救参。
  - 当前证据再次说明“入场日保护利润/保本退出”容易切掉 C9 右尾复利底座；后续若继续目标，应换到真正外生、入场前可见、覆盖完整的风险源，或只做 forward-watch，不再围绕入场日回踩保本调参。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续救参会变成过拟合。
- 原因：
  - 规则预声明，且只引用官方既有 C2 `+1R` confirm 和原始入场价，不按品种、方向、年份、月份、最终盈亏或 Stage043/044/045 residual 反推。
  - 失败后如果改 `1R`、允许同根、推迟/提前保本或只保留某些产品方向，就是典型历史结果驱动的参数救援。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：该形状无继续价值；整条目标仍有价值。
- 原因：
  - 这个形状验证了一个重要负结论：即使不减初始仓位，只在确认后保本，仍会因砍右尾而恶化权益分母和 broker10。
  - 继续价值不在这条规则，而在换信息源：找入场前可见、真正外生、覆盖完整的风险状态；否则继续从历史分钟路径里找“确认后保本/回踩退出”会越来越像过拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage046 失败结论和停止规则。
- 是否更新 `research/registry.md`：否，本阶段是线内路线反证，不改变总索引。
- 是否追加根目录 `memory.md/back_log.md`：是，属于真实回测和路线废弃摘要。
