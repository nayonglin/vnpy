# Stage009 opening-range adverse-break exit 真实引擎

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 18:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结 A/C 真实组合引擎 + 资金曲线/分钟 K atlas 视觉复盘
- 是否重要突破：否
- 是否触发A/B：否，C 未达到收益保留和 Sharpe 要求，不接正式版

## 外部调研与判断

- 参考资料：
  - Intraday Time Series Momentum: International Evidence：`https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf`
  - Intraday Time-series Momentum: Evidence from China：`https://ideas.repec.org/p/pra/mprapa/97134.html`
  - Open Range Breakout SSRN working paper：`https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2488539_code1009018.pdf?abstractid=2488539&mirid=1`
  - Assessing the profitability of intraday opening range breakout：`https://ideas.repec.org/p/hhs/umnees/0845.html`
  - pysystemtrade / systematic futures trading reference：`https://github.com/pst-group/pysystemtrade`
- 我的判断：
  - 外部资料支持“首半小时/开盘区间”有信息含量，但不能推出它能作为趋势持仓的硬退出规则。
  - ORB 更适合识别日内方向启动；把“开盘区间先反向突破”用于退出中长趋势仓，可能把正常回踩误判成趋势失败。
  - Stage009 的结果与这个担忧一致：回撤更浅，但收益保留大幅不足，视觉上是系统性砍右尾。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage009_opening_range_adverse_exit_true_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `enable_stage009_opening_range_adverse_exit=True`
  - `stage009_opening_range_bars=30`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-06-15`
- 账户规模：`150,000`
- 成本口径：正常成本，并输出 `1x/2x/3x` 成本压力
- 样本过滤：不按品种、方向、年份、月份过滤；缺失 entry-day 分钟K和同根上下突破歧义均保持官方路径
- 策略/归因口径：
  - A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - C：官方 C9 正常开仓；若 C9 自身 `0.5R` stop/retry 先触发，则优先执行官方 C9；否则用入场后可见前 `30` 根分钟K形成 opening range，若后续先反向突破且未先顺向突破，则按触发分钟收盘价退出同方向 active layers。

## 结果

- A 期末权益：`39,176,437.60`
- A 总收益：`26017.6251%`
- A 最大回撤：`-45.0827%`
- A Sharpe：`1.6331`
- A 总滑点：`2,730,130`
- A 总交易次数：`787`
- A 胜率：`53.2560%`
- C 期末权益：`15,841,431.50`
- C 总收益：`10460.9543%`
- C 最大回撤：`-38.1841%`
- C Sharpe：`1.5122`
- C 总滑点：`1,535,180`
- C 总交易次数：`812`
- C 胜率：`51.9744%`
- 收益保留：`40.2072%`
- 最大回撤改善：`+6.8986pp`
- broker10 峰值：A `111.7365%`，C `103.2489%`
- broker10 `days_over_100pct`：A `5`，C `2`
- C 触发 opening-range exit：`85` 次，退出手数 `8457`
- C 3x 成本压力：期末权益 `12,771,071.50`，总收益 `8414.0477%`，最大回撤 `-50.2882%`，Sharpe `1.2663`，broker10 峰值 `169.7599%`
- 触发样本与官方 closed-lot 形态匹配：`88` 条匹配，官方实现 PnL 净额 `+1,113,780`，其中正贡献 `+8,289,210`、负贡献 `-7,175,430`。这说明触发集合不是稳定坏信号集合，而是好坏混杂且含右尾。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_report_stage009_opening_range_adverse_exit_true_engine_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_summary_stage009_opening_range_adverse_exit_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_comparison_stage009_opening_range_adverse_exit_true_engine_v1.csv`
- daily/curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_curve_stage009_opening_range_adverse_exit_true_engine_v1.csv`
- trades：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_trades_stage009_opening_range_adverse_exit_true_engine_v1.csv`
- quality/events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_opening_range_exit_events_stage009_opening_range_adverse_exit_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_path_chart_stage009_opening_range_adverse_exit_true_engine_v1.png`
- minute atlas：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_atlas_page001_stage009_opening_range_adverse_exit_true_engine_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_atlas_page002_stage009_opening_range_adverse_exit_true_engine_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_atlas_page003_stage009_opening_range_adverse_exit_true_engine_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage009_opening_range_adverse_exit_true_engine/qmt_roll_stage009_c9_minrisk_opening_range_adverse_exit_true_engine_atlas_page004_stage009_opening_range_adverse_exit_true_engine_v1.png`

## 视觉分析

- 资金曲线：C 紫线从 `2020` 后长期低于 A 蓝线，`2022-2023` 的回撤确实更浅，但高水位和后续复利明显被压低；这不是“用更小风险拿同一右尾”，而是“砍右尾换平滑”。
- 回撤曲线：C 最大回撤改善约 `6.90pp`，但改善来自提前退出大量趋势波动，而不是识别出稳定低质量信号。
- broker10 曲线：C 峰值从 `111.7365%` 降至 `103.2489%`，但 3x 成本下 broker10 仍会冲到 `169.7599%`，说明收益分母被削弱后压力仍会在成本压力下回补。
- atlas page001/page002：`AP501`、`lh2505`、`MA305`、`si2310` 等样本显示，opening range 反向突破常只是开盘回踩，后面仍能沿官方方向走出大段趋势；规则视觉上过早否定趋势。
- 逐笔归因：触发集合在官方 closed-lot 参考中净 PnL 仍为正，且含 `lh2505 +2,390,400`、`fu2205 +854,910`、`fu2509 +820,000/+550,000`、`SM505 +410,000` 等右尾或中右尾，不能作为硬退出集合。

## 结论

- 本阶段结论：`stage009_failed_return_retention_no_param_rescue`
- 是否进入下一步：不沿此形状继续
- 下一步：
  - 停止 `opening_range_adverse_break_exit`，不扫 `15/30/60`、不改全退/半退、不按品种/方向/年份/月度补丁。
  - 后续若继续分钟执行层，应减少“入场后硬退出/降仓”思路，优先寻找入场前或入场当刻已经可见的结构质量，或者先修复 `missing_entry_day_minutes` 的权威分钟覆盖。
  - 若目标是降低资金曲线回撤但不伤右尾，账户层外部资金分层/出金锁盈/独立 sleeve 比单笔首日硬退出更符合当前证据。

## 过拟合反思

- 运行前判断：否。规则来自首半小时动量和 ORB 的普世结构，不使用最终盈亏、弱窗口、品种、方向、年份或月份。
- 运行后判断：否，但如果现在为了救结果去改 opening range 长度、退出比例或额外条件，就是过拟合。
- 原因：单一冻结规则被真实引擎反证；反证后停止，而不是围绕失败结果调参。

## 继续价值反思

- 运行前判断：有。Stage008 说明 no-follow 收盘标签太粗，opening range first-break 顺序是更严格的结构质量检验，值得真实引擎验证一次。
- 运行后判断：该形状无继续价值。
- 原因：它虽降低最大回撤和 broker10，但收益保留只有 `40.2072%`，且视觉和逐笔归因均显示它系统性砍掉右尾复利。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage009 失败和禁止参数救援。
- 是否更新 `research/registry.md`：否，本线仍是并行研究线，未出现正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选、路线废弃总账或跨线合并事件。
