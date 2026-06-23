# Stage260 同源执行回放 source inventory 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 时间：`2026-06-22 16:33`
- 工作模式：`day`
- 阶段性质：只读 source inventory / 字段合同审计；不创建交易规则，不运行 true engine，不触发 A/B，不改正式配置，不连接 CTP/SimNow，不调用订单 API。
- 是否重要突破版本：否。它是覆盖缺口闭环，不是策略候选。
- decision：`stage260_execution_replay_local_inventory_missing_same_source_no_rule`

## 外部调研与判断

- vn.py `OrderData/TradeData` 以 `vt_orderid`、`vt_tradeid`、`vt_symbol`、`direction`、`offset`、`price`、`volume`、`datetime` 等字段串联订单/成交事件：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py
- vn.py CTA engine 的订单事件处理依赖 `EVENT_ORDER`、`EVENT_TRADE` 与 `vt_orderid` 路径：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- TT FIX Drop Copy `ExecutionReport` 使用 OrderID/ExecID/ExecType/OrdStatus/LastPx/LastShares/TransactTime 等字段描述执行回报：https://library.tradingtechnologies.com/tt-fix/drop-copy/Msg_ExecutionReport_8.html
- CME trade detail 字段同样强调成交编号、合约、买卖、价格、数量、时间等执行链字段：https://www.cmegroup.com/tools-information/webhelp/gps/Content/TrdDetFldDesc.html
- 我的判断：同源执行回放不是“有订单文件”就够，必须能把 `C9 signal -> submit reference -> exact returned vt_orderid -> order lifecycle -> trade/fill -> account/gateway -> raw hash/license` 串起来，并覆盖右尾与底部亏损视觉样本。当前本地文件不满足，不能进入分钟微观结构规则、true engine 或 A/B。

## 本次版本改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage260_execution_replay_source_inventory_audit.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/`
- 新增审计：
  - 本地执行/订单/成交/CTP/SimNow/只读/smoke/adapter 文件扫描
  - 同源执行回放字段合同 `18` 项
  - promotion gate `7` 项
  - Stage259 下一步队列再判定
  - 官方 A 臂资金曲线 + 执行回放覆盖状态视觉图
- 新增参数：
  - `FULL_ENTRY_DECISION_COUNT=219`
  - `CORE_FIELD_GROUPS=10`
  - `STRICT_FIELD_GROUPS=16`
  - `MAX_CSV_ROWS_TO_COUNT_BYTES=80MB`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无，未跑回测。
- 修改回测结果：无。
- 删除回测结果：无。

## 关键结果

- 官方 A 臂不变：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6331`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
- 本地执行相关文件扫描：
  - scanned files：`10,342`
  - order/trade-like files：`562`
  - 收紧后的非 smoke/read-only/adapter source candidates：`346`
  - accepted same-source replay files：`0`
- Stage111：
  - Stage932 session：`8`
  - valid research sample：`0/8`
- Stage112：
  - rule-ready MBO/MBP10 data file：`0`
- Stage255 继承覆盖结论：
  - full orderflow/execution replay ready：`0/219`
  - missing：`219/219`
  - same-source execution replay missing：`219`
- 字段合同：
  - field contract：`18`
  - pass：`0/18`
  - source license/permission source candidate hit：`0`
  - full entry decision coverage：`0`
  - right-tail/bottom-loss visual coverage：`0`
- promotion gate：
  - pass：`1/7`
  - 唯一通过项：无正式配置/订单副作用。

## 视觉输出

- official path execution replay status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit_official_path_execution_replay_status_stage260_execution_replay_source_inventory_audit_v1.png`
- field contract heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit_field_contract_heatmap_stage260_execution_replay_source_inventory_audit_v1.png`
- asset inventory chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit_asset_inventory_chart_stage260_execution_replay_source_inventory_audit_v1.png`
- candidate file gate heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit_candidate_file_gate_heatmap_stage260_execution_replay_source_inventory_audit_v1.png`
- next action queue chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage260_execution_replay_source_inventory_audit/qmt_roll_stage260_c9_minrisk_execution_replay_source_inventory_audit_next_action_queue_chart_stage260_execution_replay_source_inventory_audit_v1.png`
- 图像检查：5 张 PNG 尺寸正常、非空，像素标准差约 `31.9219` 到 `106.7810`。

## 对“为什么一直在覆盖”的回答

- 分钟 K / formal feature 覆盖已经是 `219/219`，还差 `0`。
- 当前一直补的不是分钟覆盖，而是更高层的“规则级 source contract 覆盖”：
  - 授权订单流 / 执行回放覆盖：`0/219`，还差 `219/219`。
  - 同源执行回放字段合同：`0/18`，还差 `18/18`。
  - Stage932 smoke 有格式样本，但 valid research sample `0/8`。
  - Stage112 授权 MBO/MBP10 rule-ready 文件 `0`。
- 因此继续覆盖的本质不是在重复正式版，而是在排除“看起来有数据、实则不能交易化”的假覆盖。

## 结论

当前本地没有可用于规则研究的同源 broker/production 执行回放；只有 smoke、read-only、adapter contract、pending order、历史回测 ledger 或非 C9 entry 覆盖文件。它们能说明格式和流程，但不能证明执行质量因果，也不能支持“高质量信号时用最小风险搏最大收益”的分钟级交易规则。

本阶段不允许进入 true engine、A/B 或正式候选。下一步仍只能：

1. 采购/采集授权 orderflow、depth、MBO/MBP10；
2. 导入 broker/production 同源执行回放；
3. 获取带完整 source contract 的库存/基差/期限结构或会员类别/席位数据；
4. 若没有外部状态，只能做不改变正式持仓路径的账户外层治理。

## 开始与结束反思

- 开始前是否过拟合：否。Stage260 只审计数据源和字段合同，不扫阈值、不按品种/年份/方向补丁。
- 结束后是否过拟合：否。结论是阻断规则化，未从样本差异里提取交易规则。
- 开始前是否还有价值继续：是。Stage259 的第二优先队列就是 `import_broker_or_production_execution_replay`，需要确认本地是否已有可用回放。
- 结束后是否还有价值继续：有，但只对外部/同源数据导入或不改变持仓路径的治理有价值；继续本地 OHLCV/OI、smoke/read-only/adapter 文件上救参没有价值。

## 后续 TODO

- 若能拿到 broker/production 回放，先跑同等 gate：raw hash、schema hash、source license、signal-reference-vt_orderid-trade join、219 entry 覆盖、右尾/底部亏损视觉覆盖。
- 若没有新数据，不再扫本地分钟阈值；只允许做数据采购 manifest、forward capture 验收或账户外层治理。
- 不修改正式配置，不触发 A/B，不接入正式链路，直到 source contract 全部通过。
