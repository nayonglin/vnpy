# Stage110 执行回放/数据合同再审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 16:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据合同审计 / 数据阻塞确认；不写真引擎，不新增交易规则，不触发 A/B
- 是否重要突破：否，属于 Stage109 之后的路线边界固化
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - HftBacktest 官方文档：其回放模型基于完整 order book 与 trade tick feed，并显式处理 feed/order latency 与 queue position，说明高质量微观结构规则需要盘口/成交/延迟/队列级数据，而不是仅靠分钟 OHLC。
  - vn.py `TickData` schema：tick 对象包含 last trade、orderbook snapshot、日内统计等字段，说明执行回放至少要有 top-of-book/depth、last price、volume/OI 等同步字段。
  - QuantConnect tick 文档：trade tick 与 quote tick 是不同数据类型，quote tick 代表 bid/ask 报价，不能把 bar close/open 当作报价与可成交深度。
  - QuantConnect data periods 文档：tick 是点值，bar 是区间值；分钟 bar 不包含区间内真实事件顺序。
- 我的判断：
  - Stage109 已关闭内部 minute-OHLC 候选后，继续研究的本质问题不是再找一个分钟标签，而是本地是否已有“授权历史 quote/depth”或“券商/生产同源执行回放”可以让微观结构规则进入 point-in-time 审计。
  - 当前外部资料与 Stage103 数据合同一致：若没有同源执行、盘口深度、raw provenance 和右尾保护视觉 gate，仅凭本地 Tq 小样本、CTP read-only 空文件或 dry-run hook 不能升级为策略规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage110_execution_replay_data_contract_audit.py`
- 修改脚本：无其他策略脚本；仅在 Stage110 自身脚本中修正资金路径图的重复列冲突
- 删除脚本：无
- 新增参数：无交易参数；固定审计对象为 Stage103 数据合同、Stage108 route scorecard、Stage109 关闭边界与本地 execution/tick artifact
- 修改参数：无
- 删除参数：无
- 正式配置变更：无
- CTP 连接：无
- 订单 API 调用：无

## 审计参数

- 数据区间：沿用 Stage045 官方资金曲线、Stage103 数据合同、Stage108 风险地图、Stage109 summary。
- 账户规模：官方 C9/15w 既有路径，仅做只读映射。
- 成本口径：沿用官方路径，未新增成交。
- 本地资产审计范围：
  - `authorized_historical_quote_depth`
  - `broker_or_production_execution_replay`
  - CTP read-only tick/order/trade snapshot 文件
  - Stage068/079/080 本地 Tq tick 与 transform 证据
  - Stage586/587/615 execution TCA/hook contract 证据
  - Stage109 internal OHLC 关闭证据

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `asset_count=11`
  - `rule_usable_asset_count=0`
  - `tca_or_forward_watch_only_asset_count=9`
  - `route_count=6`
  - `route_true_engine_allowed_count=0`
  - `authorized_historical_quote_depth_ready_count=0`
  - `broker_execution_replay_row_count=0`
  - `readonly_tick_row_count=0`
  - `stage068_initial_entry_tick_ready_count=5`
  - `stage068_initial_entry_tick_ready_rate_pct=2.2831%`
  - `hard_gap_count=6`
  - `promotion_gate_pass_count=0/5`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage110_execution_replay_data_contract_audit/qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_report_stage110_execution_replay_data_contract_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage110_execution_replay_data_contract_audit/qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_summary_stage110_execution_replay_data_contract_audit_v1.csv`
- asset inventory：`qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_asset_inventory_stage110_execution_replay_data_contract_audit_v1.csv`
- route contract：`qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_route_contract_reaudit_stage110_execution_replay_data_contract_audit_v1.csv`
- gap manifest：`qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_gap_manifest_stage110_execution_replay_data_contract_audit_v1.csv`
- procurement manifest：`qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_procurement_manifest_stage110_execution_replay_data_contract_audit_v1.csv`
- promotion gate：`qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_promotion_gate_stage110_execution_replay_data_contract_audit_v1.csv`
- 视觉图：
  - `qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_official_path_data_blockers_stage110_execution_replay_data_contract_audit_v1.png`
  - `qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_route_contract_heatmap_stage110_execution_replay_data_contract_audit_v1.png`
  - `qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_asset_inventory_chart_stage110_execution_replay_data_contract_audit_v1.png`
  - `qmt_roll_stage110_c9_minrisk_execution_replay_data_contract_audit_gap_manifest_chart_stage110_execution_replay_data_contract_audit_v1.png`

## 视觉检查

- official path data blockers 图可读：阻断点覆盖权益阶梯、最大回撤段和 2025-2026 近端高位震荡段，不是单一窗口问题。
- route contract heatmap 可读：`authorized_historical_quote_depth` 与 `broker_or_production_execution_replay` 两条真正需要的路由全红，`ctp_realtime_forward_capture` 与本地 Tq 路由只满足少量 schema/局部 topbook 条件，`true_engine_allowed` 仍为 `0`。
- asset inventory 图可读：本地有代码合同、dry-run hook 和少量 tick 文件，但全部被标记为 TCA/forward-watch only 或 closed，不构成规则资产。

## 结论

- 本阶段结论：`stage110_execution_replay_data_contract_not_ready_no_rule`。
- 是否进入下一步：是，但不能继续造内部 minute-OHLC 候选。
- 下一步：
  - 优先取得授权 historical quote/depth/orderflow 或 broker/production execution replay，并按 Stage103 合同检查 historical coverage、same-source execution、subminute ordering、topbook/depth、raw hash/schema、right-tail protection 和 license。
  - 若暂时没有新数据，只能继续整理数据采购 manifest、执行回放字段合同、forward-watch capture 验收，不进入 true engine/A/B/正式候选。

## 过拟合反思

- 运行前判断：否。Stage110 是数据合同审计，不从亏损样本、年份、品种、方向或阈值反推规则。
- 运行后判断：否。结果没有把任何本地 partial asset 交易化，反而确认 `rule_usable_asset_count=0`、`promotion_gate_pass_count=0/5`。
- 原因：审计标准来自外部微观结构回放原则和 Stage103 预声明合同，结论由数据是否存在、是否同源、是否有 raw provenance 决定，而不是由收益好坏决定。

## 继续价值反思

- 运行前判断：是。Stage109 关闭内部 OHLC 后，必须确认本地是否已有可继续的执行回放/盘口数据，否则容易在无数据情况下循环发明候选。
- 运行后判断：是，但价值转为数据工程/执行回放建设。继续在内部 OHLC 上做策略候选价值低；继续把数据合同、采购字段和 forward capture 做扎实有价值。
- 原因：11 类资产中没有一个可用于规则；真正可推进低回撤目标的下一信息层只能是授权 quote/depth/orderflow 或同源执行回放。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage110 结论与后续边界。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破版本。
