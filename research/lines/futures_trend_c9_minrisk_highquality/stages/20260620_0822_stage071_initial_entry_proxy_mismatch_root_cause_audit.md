# Stage071 初始开仓 price_proxy mismatch 根因审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 08:22 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：价格源/盘口锚点根因审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档：回测订阅 tick 时 quote 使用 tick 更新；未订阅 tick 而只订阅 K 线时，盘口字段由 K 线合成，语义不同。
  - vn.py GitHub README：`data_recorder` 将 Tick 与 K 线作为不同数据资产记录，tick 可服务更细粒度回放和策略初始化。
  - HftBacktest 文档：高频/盘口回放需要显式处理 feed、order latency、order book 与成交队列，不能只用 bar close 推断成交质量。
  - QuantStart / Quantpedia / Databento 连续合约资料：连续合约适合信号研究，但执行价格需要回到具体合约、具体滚动/复权口径和具体时间。
- 我的判断：
  - Stage070 的 `14/60` proxy mismatch 不能直接当成微观结构信号，因为其中既有 tick size 附近误差，也有 official open 明显落在目标分钟盘口区间外的样本。
  - 盘口 TCA 的第一性要求是先解释价格源和锚点；在价格源未闭环前抽取 spread/depth/imbalance，会把数据口径差异误判成信号质量。
  - 本阶段只做根因分类和视觉复核，不写策略、不跑 true engine。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage071_initial_entry_proxy_mismatch_root_cause_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage070 前 `60/219` 笔 initial-entry `price_proxy_anchor` 样本，覆盖 `2020-01-09` 至 `2021-01-06`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 仅审计 Stage070 的 `14` 个 `price_proxy_anchor` mismatch。
  - 不按盈亏、产品、方向、年份、交易所或时段筛选。
  - 不下载新 tick，只读取 Stage070 已有 tick 文件、anchor feature 与 trade comparison。
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
  - decision：`stage071_proxy_mismatch_root_cause_unresolved_no_rule`
  - Stage070 proxy ready：`60/60`
  - Stage070 proxy exact：`46/60`
  - proxy mismatch：`14`
  - near mismatch `<=0.05R`：`7`
  - far mismatch `>0.05R`：`7`
  - unresolved mismatch：`7`
  - `outside_target_book_range`：`7` 笔，净 PnL `+30,619.00`，median delta `0.0597R`，max delta `0.5714R`
  - `near_005r_outside_spread`：`6` 笔，净 PnL `+13,960.00`，median delta `0.0202R`，max delta `0.0385R`
  - `inside_spread_not_exact`：`1` 笔，净 PnL `-15,960.00`，delta `0.0175R`

## 视觉观察

- path/class chart 显示：Stage071 的 exact/mismatch 点仍只落在 `2020-2021` 早期低权益区间，远不能代表 C9 全周期权益台阶或主回撤尾部。
- mismatch class 贡献曲线显示：`outside_target_book_range` 最终反而净正，`near_005r_outside_spread` 也净正；这证明 mismatch root class 不是坏信号集合。
- delta/root chart 显示：真正需要解释的是 `outside_target_book_range` 的 7 笔，其中 `hc2010 2020-05-12 21:00` delta 达 `0.5714R`，`jm2005 2020-02-11 09:00` delta 达 `0.3684R`；这些不是普通 spread 内误差。
- mismatch atlas 显示：多笔 official open 虚线在当分钟 bid/ask/last 路径之外，例如 `jm2005.DCE`、`hc2010.SHFE`、`ru2101.SHFE`；同时也存在 `SM101.CZCE` 这类 inside-spread-not-exact 近似误差。两类不能混为一个交易标签。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_report_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_summary_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_decision_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.json`
- mismatch audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_mismatch_audit_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.csv`
- class summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_class_summary_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.csv`
- path/class chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_official_path_mismatch_class_chart_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.png`
- delta/root chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_proxy_mismatch_delta_chart_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage071_initial_entry_proxy_mismatch_root_cause_audit/qmt_roll_stage071_c9_minrisk_initial_entry_proxy_mismatch_root_cause_audit_proxy_mismatch_tick_atlas_stage071_initial_entry_proxy_mismatch_root_cause_audit_v1.png`

## 结论

- 本阶段结论：`stage071_proxy_mismatch_root_cause_unresolved_no_rule`
- 是否进入下一步：是，但下一步仍是账本/价格源审计，不是 TCA 特征抽取或策略规则。
- 下一步：
  - 暂停 `60->219` 直接批量补数和 spread/depth/imbalance 特征抽取。
  - 审计 `_resolve_trade_price` 的 raw proxy 来源、Stage040/041/043/045 事件字段、Stage861 分钟源、TqBacktest tick、交易所 tick size、主力/连续合约映射和 bar/tick 时间截取。
  - 将 `outside_target_book_range` 拆成价格源不可解释、连续/主力映射疑点、tick/bar 截取差异或可接受近似误差。
  - 根因未闭环前，禁止把 exact/mismatch、root class、scan/proxy delta、spread、depth、imbalance、mid/last move、产品、年份或方向写成开仓过滤、最小风险、恢复仓或退出规则。

## 过拟合反思

- 运行前判断：否。本阶段固定审计 Stage070 的全部 `14` 个 mismatch，不按结果挑样本，也不新增参数。
- 运行后判断：否，但若把 root class 直接交易化就是过拟合。
- 原因：
  - mismatch 组和 `outside_target_book_range` 组均为净正 PnL，不能作为坏信号。
  - 样本只覆盖早期 `2020-2021`，视觉上不代表全周期风险尾部。
  - 本阶段只做数据口径分类，没有改变策略行为。

## 继续价值反思

- 运行前判断：有价值。Stage070 证明 price proxy anchor 大体有效，但 `14/60` mismatch 会污染后续盘口规则。
- 运行后判断：有价值，但价值在修账本，不在马上提规则。
- 原因：
  - Stage071 把小误差和盘口外价格源差异拆开，避免把数据问题误当 alpha。
  - `7` 个 outside-book 样本说明 initial-entry tick/TCA 路线仍有基础设施阻塞。
  - 只有先闭环成交价来源，后续分钟级“最小风险搏最大收益”才有可靠执行证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage071 状态和下一步价格源审计边界。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据资产与价格基准推进。
