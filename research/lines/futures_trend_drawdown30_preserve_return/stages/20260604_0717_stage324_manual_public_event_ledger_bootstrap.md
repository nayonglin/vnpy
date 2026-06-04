# Stage324 手工/公开事件源账本 Bootstrap

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据资格推进；不新增收益回测、不改策略规则、不生成 paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否。它补齐了 `j/i/ag/CY/SR` 的 source/event catalog 起点，但没有形成可部署 selector。
- 是否触发A/B：否。没有形成可接入正式版本的新策略或新风险预算。

## 外部调研与判断

- 参考资料：
  - DCE API SDK / credentials required：https://pypi.org/project/dceapi/
  - DCE API Rust docs / news、delivery、member、market services：https://docs.rs/dceapi-rs/latest/dceapi_rs/
  - ICE DCE licensed data catalog：https://developer.ice.com/fixed-income-data-services/catalog/dalian-commodity-exchange-dce
  - SHFE Daily Data / ranking、warrant reports：https://www.shfe.cn/eng/reports/StatisticalData/DailyData/
  - USDA NASS National Crop Progress：https://data.nass.usda.gov/Publications/National_Crop_Progress/index.php
  - USDA WASDE release page：https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/commodity-markets/wasde-report
  - USDA ERS Cotton and Wool Outlook：https://ers.usda.gov/publications/pub-details?pubid=114047
  - CZCE English overview：https://english.czce.com.cn/en/AboutUs/Overview/Overview/H081001001003index_1.htm
  - CZCE static reference data example：https://english.czce.com.cn/en/DFSStaticFiles/Future/2024/20240418/EnglishFutureDataReferenceData.htm
- 我的判断：
  - 扩池选品方向继续成立，但产品选择必须先过 source/TCA/live 可执行闸门。
  - `j/i` 最关键的 DCE 事件、交割、会员、仓单源仍偏授权 API 或商业 feed；当前没有 `DCE_API_KEY/DCE_SECRET`，不能把它当 selector。
  - `ag.SHFE`、`CY.CZCE`、`SR.CZCE` 已有公开 source catalog，可以做 forward monitor 起点，但公开 source catalog 不是 alpha 事件。
  - 所有行强制 `usable_for_history_selector=0`，避免把事后整理的事件源倒灌进历史回测。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage624_manual_public_event_ledger_bootstrap.py`
- 修改正式策略脚本：无。
- 删除脚本：无。
- 新增参数/闸门：
  - `MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20`
  - `usable_for_forward_monitor`
  - `usable_for_history_selector = 0`
  - `event_auto_monitor_validated = 0`
  - `event_signal_ready = 0`
  - `paper_or_whitelist_allowed = 0`
  - `point_in_time_rule`：只认 `received_at_local`，`published_at` 不赋予历史 selector 资格。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 数据区间：不适用；本阶段只做 source/event catalog bootstrap。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只覆盖 Stage316/321 监控产品：`j.DCE`、`i.DCE`、`ag.SHFE`、`CY.CZCE`、`SR.CZCE`。
  - 只写阶段级输出，不追加 master forward ledger。
  - 所有行 `usable_for_history_selector=0`、`event_signal_ready=0`。
- 策略/归因口径：
  - `j/i`：DCE authorized API / ICE vendor catalog，仍锁。
  - `ag`：SHFE Daily Data 公开日数据目录，可做手工 forward monitor。
  - `CY`：USDA NASS/ERS + CZCE 静态参考，属于棉花链间接映射。
  - `SR`：USDA WASDE + CZCE 白糖静态参考，属于白糖宏观供需映射。

## 结果

- 决策：`manual_public_event_ledger_bootstrapped_selector_locked`
- ledger rows：`10`
- 覆盖产品：`5/5`
- forward monitor rows：`6`
- history selector rows：`0`
- event auto monitor validated rows：`0`
- event signal ready rows：`0`
- DCE authorized credentials present：`0`
- selector unlocked now：`0`
- paper/whitelist allowed：`0`
- hard gates：`7/10`
- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增收益曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增收益曲线。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易。
  - Stage526 参考：`1,342,190`
- 总交易次数：无新增交易。
  - Stage526 参考：`905`
- 胜率：无新增交易。
  - Stage526 非零日胜率参考：`53.6330%`

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_chart_stage624_manual_public_event_ledger_bootstrap_v1.png`
- 左上 heatmap：`j/i` 在 `exchange_notice_delivery_margin` 和 `licensed_market_data` 上均为 `LOCK`，说明黑色链条仍被授权源/商业源锁住；`ag` 只有 `exchange_warehouse_member` 为 `MON`；`CY/SR` 有 `MON/REF`，但没有任何 alpha signal。
- 右上 taxonomy：共覆盖 `6` 类 source/event family，没有变成单一 USDA 或单一交易所来源。
- 左下 completeness：`source_url/raw_hash/product_map` 都是 `100%`，但 `history_selector/event_auto_monitor/event_signal_ready` 都是 `0%`，边界清楚。
- 右下 gates：通过项主要是 source catalog 完整、hash 完整、selector/paper 锁定；失败项是 `DCE credentials`、`event auto monitor`、`20 PIT dates`。这正是当前路线的真实阻塞。

## 输出文件

- ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_event_ledger_stage624_manual_public_event_ledger_bootstrap_v1.csv`
- product summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_product_summary_stage624_manual_public_event_ledger_bootstrap_v1.csv`
- source summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_source_summary_stage624_manual_public_event_ledger_bootstrap_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_gates_stage624_manual_public_event_ledger_bootstrap_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_decision_stage624_manual_public_event_ledger_bootstrap_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_report_stage624_manual_public_event_ledger_bootstrap_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_chart_stage624_manual_public_event_ledger_bootstrap_v1.png`

## 结论

- 本阶段结论：
  - `j/i/ag/CY/SR` 已有阶段级 source/event catalog bootstrap，source URL、产品映射和 raw hash 齐全。
  - 但这不是交易信号；`history_selector_rows=0`、`event_signal_ready=0`、`selector_unlocked_now=0`。
  - `j/i` 仍是 P1，但卡在 DCE 授权源和 live TCA；`ag/CY/SR` 只适合继续 forward monitor。
- 是否进入下一步：进入，但只能进入 source 自动化和 PIT 累计，不进入收益回测 selector、paper、A/B 或交易白名单。
- 下一步：
  1. 对 `ag/CY/SR` 做自动 raw-text monitor 或半自动 daily snapshot，确保每次都有 `received_at/source_url/raw_hash/product_mapping/status`。
  2. 对 `j/i` 获取授权 DCE API 或正式数据服务；否则只保留 P1 worklist，不给风险预算。
  3. 累计至少 `20` 个 PIT received_at 日期后，再按 Stage561/261 固定协议做 `63/126` 日 IC/bucket/paper sleeve 审计。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 没有用历史收益挑品种，没有修改交易逻辑，没有新增白名单。
  - source catalog 行全部锁定 `usable_for_history_selector=0`。
  - 高价值的 `j/i` 没有因历史低相关直接晋级，而是继续卡在授权源、TCA 和 live context。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只能继续做数据资格。
- 原因：
  - 这一步把“选对品种”推进成可审计 source/event ledger 字段，而不是停留在主观判断。
  - 但预测力仍完全未证明，继续价值在于 PIT 样本累计和自动 monitor，不在于立刻跑收益。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage624_manual_public_event_ledger_bootstrap.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage624_manual_public_event_ledger_bootstrap.py`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage624_manual_public_event_ledger_bootstrap_decision_stage624_manual_public_event_ledger_bootstrap_v1.json`：通过。
- 图表已视觉检查：source catalog 与 selector locked 的边界清晰，无误读为 alpha。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage324。
- 是否追加根目录 `memory.md/back_log.md`：否。没有正式候选、重要突破、路线废弃或跨线合并。
