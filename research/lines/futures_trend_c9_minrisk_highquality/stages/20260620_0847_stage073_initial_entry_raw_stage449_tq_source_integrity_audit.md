# Stage073 初始开仓 raw/Stage449/Tq 源完整性审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 08:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：价格源同源性审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方回测文档：`https://doc.shinnytech.com/tqsdk/1.2.0/usage/backtest.html`，TqBacktest 用历史行情推进策略，模拟撮合按对手价成交。
  - TqSdk 行情文档：`https://tqsdk-python.readthedocs.io/en/latest/usage/mddatas.html`，K 线 open 是 K 线起始时刻最新价，tick 序列包含独立的 last/bid1/ask1/volume/open_interest 字段。
  - TqSdk API 文档：`https://doc.shinnytech.com/tqsdk/1.5.0/reference/tqsdk.api.html`，`get_tick_serial()` 返回交易所发出时间的 tick 序列及 top-book 字段。
  - vn.py GitHub README：`https://github.com/vnpy/vnpy/blob/master/README_ENG.md`，`data_recorder` 把 Tick 与 K-line 作为不同市场数据资产记录。
- 我的判断：
  - Stage072 的矛盾不是“盘口特征能区分好坏信号”，而是 official/raw/Stage449 minute open 与 Tq tick top-book 不同源。
  - Tq tick 的 bid/ask/last 与 Stage449 zero-volume minute open 不能未经同源证明就混成 execution feature。
  - 本阶段必须先做源完整性审计；同源性未闭环前，继续抽 spread/depth/imbalance 是数据污染，不是 alpha。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage073_initial_entry_raw_stage449_tq_source_integrity_audit.py`
- 修改脚本：
  - 同脚本内修正一次实现口径：不再按 `trade_id` 直连 Stage149 proxy detail，因为该文件的 `trade_id` 对本批 official open 不是稳定键；改用 Stage072 已同步的 `engine_selected_price/source` 与 `seed_price` 字段。
  - 同脚本内补齐官方指标读取：优先从 Stage045/Stage072 summary 读取 Sharpe、滑点、交易次数、胜率和 broker10。
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage072 的 `14` 个 initial-entry price proxy mismatch，覆盖 `2020-02-11` 至 `2020-12-17`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 固定审计 Stage072 全部 `14` 个 mismatch。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
  - 不新增下载，不新增 tick，不跑 TqBacktest。
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
  - decision：`stage073_stage449_zero_volume_open_proxy_vs_tq_tick_source_mismatch_no_rule`
  - mismatch：`14`
  - engine selected exact official：`14/14`
  - seed exact official：`7/14`
  - raw anchor open exact official：`14/14`
  - Stage449 anchor open exact official：`14/14`
  - raw/Stage449 open exact：`14/14`
  - Tq target-minute exact official：`0/14`
  - raw zero-volume：`14/14`
  - raw degenerate OHLC：`14/14`
  - Stage449 zero-volume：`14/14`
  - Stage449 degenerate OHLC：`14/14`
  - outside target book range：`7`
  - near `0.05R` outside spread：`6`
  - inside spread not exact：`1`
  - broker10 峰值：`111.7365%`

## 视觉观察

- official path source-integrity chart 显示：全部 `14` 个源差异点仍集中在 `2020-2021` 初始低权益区间，不覆盖 C9 后续主要权益台阶和主要回撤区间；不能从这些点反推全周期交易规则。
- cumulative PnL by class 显示：`stage449_raw_zero_volume_open_exact_tq_book_outside` 净 PnL `+30,619`，`stage449_raw_zero_volume_open_exact_tq_no_exact` 合并后也不是稳定坏信号；source mismatch 不是亏损标签。
- source delta chart 显示：`engine exact/raw exact/Stage449 exact/raw zero-volume/raw degenerate` 均为 `14/14`，而 `Tq exact=0/14`；delta 点里 `7` 个超过 `0.05R`，最大约 `0.5714R`。
- raw/Stage449/Tq atlas 显示：`jm2005.DCE`、`hc2010.SHFE`、`hc2010.SHFE 2020-05-12 21:00`、`ru2101.SHFE` 等 official/raw/Stage449 open 虚线常明显落在 Tq bid/ask/last 路径之外；这说明问题是价格源口径，不是微观结构信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_report_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_summary_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_decision_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.json`
- source integrity audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_source_integrity_audit_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.csv`
- class summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_source_integrity_class_summary_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.csv`
- path/source integrity chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_official_path_source_integrity_chart_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.png`
- source delta chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_source_delta_chart_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.png`
- raw/Stage449/Tq atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage073_initial_entry_raw_stage449_tq_source_integrity_audit/qmt_roll_stage073_c9_minrisk_initial_entry_raw_stage449_tq_source_integrity_audit_raw_stage449_tq_atlas_stage073_initial_entry_raw_stage449_tq_source_integrity_audit_v1.png`

## 结论

- 本阶段结论：`stage073_stage449_zero_volume_open_proxy_vs_tq_tick_source_mismatch_no_rule`
- 是否进入下一步：是，但下一步仍是数据源选择/数据工程，不是交易规则。
- 下一步：
  - initial-entry 盘口路线继续暂停直接批量补 `60->219` 和 TCA 特征抽取。
  - 若继续 initial-entry 执行审计，必须先选单一权威执行数据源：
    - 方案 A：回到 official/raw/Stage449/Stage861 minute open 同源口径，只做 bar-level 执行审计，不使用 Tq tick top-book 的 spread/depth/imbalance。
    - 方案 B：取得与 official open 同源的 tick/order-book 或能解释 zero-volume open 的授权/vendor 源，再重做盘口审计。
  - 在二者未完成前，禁止把 exact/mismatch、source class、zero-volume、degenerate OHLC、spread、depth、imbalance、mid/last move、产品、年份或方向写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段是数据源法证，固定审计 Stage072 的全部 `14` 个 mismatch，没有新交易参数。
- 运行后判断：否，但如果把源差异交易化就是过拟合。
- 原因：
  - 样本不是按盈亏挑选，且 source class 不是亏损标签。
  - 视觉上样本集中在 2020-2021 早期，不能代表全周期主风险。
  - 输出只收敛数据源边界，不改变交易行为。

## 继续价值反思

- 运行前判断：有价值。Stage072 已证明 raw/engine exact 但 Tq tick 不 exact，必须判断是策略信号还是数据源不一致。
- 运行后判断：有价值，但继续价值在“选权威执行源”，不在“继续抽盘口规则”。
- 原因：
  - Stage073 证明 official open 与 raw/Stage449 zero-volume degenerate minute open 完全同源，而与当前 Tq tick top-book 不同源。
  - 这能防止后续把异源盘口差异误当作高质量/低质量信号。
  - 如果下一步能拿到同源 tick/order-book，盘口路线仍有研究价值；否则应退回 bar-level 执行审计或换外生源。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage073 状态和下一步源选择边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线价格源审计推进。
