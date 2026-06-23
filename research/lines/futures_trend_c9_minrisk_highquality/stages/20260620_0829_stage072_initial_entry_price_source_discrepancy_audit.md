# Stage072 初始开仓 raw proxy 与 Tq tick 价格源差异审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 08:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：价格源同源性审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档：回测订阅 tick 时 quote 使用 tick 更新；未订阅 tick 而只订阅 K 线时，盘口字段由 K 线合成，tick 与 K 线源语义不同。
  - vn.py GitHub README：`data_recorder` 将 Tick 与 K 线作为不同数据资产记录，历史数据管理支持 CSV 导入导出；执行审计不能混用未证明同源的数据。
  - HftBacktest 文档：市场回放要处理 feed、order latency、order book 与成交队列；tick/top-book 与分钟 open 不是同一层语义。
  - QuantStart / Quantpedia / Databento 连续合约资料：连续合约/主力合约适合信号研究，但执行价必须落回具体合约、具体滚动口径和具体时间源。
- 我的判断：
  - Stage071 的 outside-book mismatch 不是策略信号，优先级应从“盘口特征”降为“数据源同源性”。
  - 如果 official/raw open 与 Tq tick top-book 不同源，spread/depth/imbalance 的统计意义会被污染。
  - 本阶段只读 Stage040/045/070/071 产物，先判断 official open 是否被 `_resolve_trade_price` raw proxy 解释，再看与 Tq tick 的差异。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage072_initial_entry_price_source_discrepancy_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage071 的 `14` 个 price proxy mismatch，覆盖 `2020-02-11` 至 `2020-12-17`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定审计 Stage071 的全部 `14` 个 mismatch。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
  - 不下载新 tick，不跑 TqBacktest。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓、减仓、恢复风险或退出规则。
  - 不跑 true engine。
  - 不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage072_raw_proxy_exact_tq_tick_source_discrepancy_unresolved_no_rule`
  - Stage071 mismatch：`14`
  - raw proxy exact official：`14/14`
  - engine selected exact official：`14/14`
  - raw window starts at anchor minute：`14/14`
  - Tq target-minute exact：`0/14`
  - outside target book range：`7`
  - near `0.05R` outside spread：`6`
  - inside spread not exact：`1`
  - engine proxy kind：`stage149_seed_proxy=7`，`raw_proxy=7`
  - `outside_target_book_range/raw_proxy`：`4` 笔，净 PnL `-10,611.00`
  - `outside_target_book_range/stage149_seed_proxy`：`3` 笔，净 PnL `+41,230.00`

## 视觉观察

- path/source chart 显示：Stage072 所有差异点仍只位于 `2020-2021` 早期低权益段，不覆盖 C9 后续主要权益台阶和主回撤；因此不能从这些点反推全周期交易规则。
- source-discrepancy 累计 PnL 显示：`raw_open_exact_tq_tick_book_outside_unresolved` 最终为净正，`raw_open_exact_tq_tick_near_miss` 也为净正；数据源差异不是坏信号。
- raw vs Tq delta chart 显示：`raw exact`、`engine exact`、`raw anchor match` 全部为 `14/14`，但 `Tq exact=0/14`，且 `outside book=7/14`；这把矛盾明确收敛到 raw minute open 与 Tq tick top-book 的源差异。
- atlas 显示：`jm2005.DCE`、`hc2010.SHFE`、`ru2101.SHFE` 等样本中 official/raw open 虚线与 Tq tick bid/ask/last 路径分离；`FG009.CZCE`、`CF105.CZCE` 等近似误差较小但仍不 exact。两类都不能转成开仓/恢复/退出规则。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_report_stage072_initial_entry_price_source_discrepancy_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_summary_stage072_initial_entry_price_source_discrepancy_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_decision_stage072_initial_entry_price_source_discrepancy_audit_v1.json`
- source discrepancy audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_source_discrepancy_audit_stage072_initial_entry_price_source_discrepancy_audit_v1.csv`
- source diagnosis summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_source_diagnosis_summary_stage072_initial_entry_price_source_discrepancy_audit_v1.csv`
- path/source chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_official_path_source_discrepancy_chart_stage072_initial_entry_price_source_discrepancy_audit_v1.png`
- raw vs Tq delta chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_raw_vs_tq_delta_chart_stage072_initial_entry_price_source_discrepancy_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage072_initial_entry_price_source_discrepancy_audit/qmt_roll_stage072_c9_minrisk_initial_entry_price_source_discrepancy_audit_raw_vs_tq_tick_atlas_stage072_initial_entry_price_source_discrepancy_audit_v1.png`

## 结论

- 本阶段结论：`stage072_raw_proxy_exact_tq_tick_source_discrepancy_unresolved_no_rule`
- 是否进入下一步：是，但下一步仍是数据源同源性审计，不是规则或 TCA 特征。
- 下一步：
  - 暂停 `60->219` 直接批量补数和 spread/depth/imbalance 特征抽取。
  - 审计 raw minute 源 `s452._load_raw_bars`、Stage149 proxy detail、Stage861 full minute、TqBacktest tick 的同源性、字段含义、时间戳 convention 和主力/连续合约映射。
  - 优先解释为什么 raw minute first-open 能精确命中 official open，但 Tq tick 目标分钟 top-book 不包含该价。
  - 同源性未闭环前，禁止把 exact/mismatch、source discrepancy、root class、spread、depth、imbalance、mid/last move、产品、年份或方向写成交易规则。

## 过拟合反思

- 运行前判断：否。本阶段只读全部 `14` 个 Stage071 mismatch，不新增参数，不按收益挑样本。
- 运行后判断：否，但如果把 raw/Tq 源差异交易化就是过拟合。
- 原因：
  - outside-book 与 near-miss 组都为净正，不能作为坏信号。
  - 视觉上样本集中在早期低权益段，不代表全周期回撤源。
  - 本阶段只审计数据源，不改变交易行为。

## 继续价值反思

- 运行前判断：有价值。Stage071 尚未解释 `7` 个 outside-book mismatch。
- 运行后判断：有价值，但路线继续收窄到数据工程。
- 原因：
  - Stage072 证明 official open 不是不可解释：raw proxy/engine selected 全部 exact。
  - 同时也证明当前 Tq tick top-book 不能直接作为 official open 的执行价源。
  - 先解决同源性，才能避免后续 TCA/盘口规则建立在错配数据上。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage072 状态和下一步数据源同源性边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线价格源审计推进。
