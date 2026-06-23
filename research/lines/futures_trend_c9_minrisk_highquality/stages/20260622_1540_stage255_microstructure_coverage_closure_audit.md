# Stage255 微观结构覆盖闭环审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:40 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读覆盖审计；回答“本地还差多少要补”和“真实订单流是否已经能重启”
- 是否重要突破：否，但这是路线边界确认
- 是否触发A/B：否；没有形成正式候选

## 外部调研与判断

- 参考资料：
  - Alpha Architect, Order Flow Correlation May Imply Momentum Factor Crowding: https://alphaarchitect.com/order-flow-correlation-may-imply-momentum-factor-crowding/
  - arXiv, Order Book Filtration and Directional Signal Extraction: https://arxiv.org/html/2507.22712v1
  - GitHub, `shaileshkakkar/OrderImbalance`: https://github.com/shaileshkakkar/OrderImbalance
  - Dean Markwick, Order Flow Imbalance blog: https://dm13450.github.io/2022/02/02/Order-Flow-Imbalance.html
  - HftBacktest docs, Order Book Imbalance: https://hftbacktest.readthedocs.io/en/latest/tutorials/Market%20Making%20with%20Alpha%20-%20Order%20Book%20Imbalance.html
- 我的判断：真正的 OFI/OBI/队列压力需要动态盘口深度、订单事件、撤单、主动成交流或同源执行回放。分钟 OHLCV/OI 即使已经点时化补齐，也不能替代 MBO/MBP10 或执行回放；继续把分钟特征包装成“订单流”会变成信息层级错配和过拟合。

## 开始前反思

- 是否在过拟合：否。本阶段不是调阈值、扫参数或挑品种，而是把 Stage103/110/111/112/117/136/140/141 与 Stage179/180/181/238/239 的覆盖口径统一审计，目标是防止把低信息层误用成高信息层。
- 是否还有价值继续：有。Stage252-254 已经说明分钟价量/OI 组合不能交易化，下一步必须确认到底是“数据还没补完”还是“已补完但信息层不够”。这个审计能直接回答后续是否继续本地补覆盖。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage255_microstructure_coverage_closure_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `FULL_ENTRY_DECISION_COUNT=219`
  - `W0_EXPECTED_REQUEST_COUNT=41`
  - `W0_EXPECTED_WINDOW_COUNT=70`
  - MBO/MBP10/执行回放必需字段探针：`ts_event/action/side/order_id/sequence/bid_price1/ask_price1/bid_size1/ask_size1/order_ts/fill_ts/fill_price/source_license` 等
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- 样本过滤：
  - Stage179/180/181：点时化 cutoff minute feature source
  - Stage238/239：formal feature 与 read-only signal label join
  - Stage111/112/117/136/140/141：执行回放、真实 W0、候选 promotion gate 的接入状态
- 策略/归因口径：
  - 只读覆盖闭环审计
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- 分钟级点时覆盖：`219/219`，还差 `0`
- 分钟 feature cell：`2190/2190`
- formal feature row：`219/219`
- Stage239 label join：`219/219`
- Stage239 candidate feature：`7`
- Stage239 watch-only：`2`
- 真实 W0 request：`0/41`，还差 `41`
- 真实 W0 window：`0/70`，还差 `70`
- Stage112 rule-ready MBO/MBP10 文件：`0`
- Stage112 accepted MBO 文件：`0`
- Stage112 accepted MBP10 文件：`0`
- 219 个 entry 决策的真实订单流覆盖：`0/219`，还差 `219`
- 同源执行回放覆盖：`0/219`，还差 `219`
- orderflow schema ready：`0`
- route true_engine_allowed：`0/5`
- promotion gate：`4/9`
- 决策：`stage255_minute_coverage_complete_real_orderflow_missing_no_rule`

## 视觉分析

- official path coverage status：官方资金/回撤路径未变；图中分钟覆盖是 `219/219`，真实 orderflow 覆盖仍是 `0/219`，说明缺口不是收益曲线回测，而是数据层。
- coverage ledger chart：Stage179/180/181/238/239 全绿，W0 request/window、full entry orderflow、执行回放全红；本地分钟补充已经闭环，外部真实微观结构数据没有到位。
- schema probe chart：Stage180 cutoff source 只能命中 `vt_symbol/exchange` 这类标识字段，缺 `ts_event/action/side/order_id/sequence/bid/ask/size/fill_ts` 等核心字段；不能计算 OFI、OBI、队列压力或同源滑点。
- gate status matrix：通过分钟覆盖、formal 表、单特征未提升和无运行时副作用；失败项集中在真实 W0、MBO/MBP10 schema、219 真实订单流覆盖、执行回放和候选 promotion。
- route status chart：分钟 feature route 状态是 `completed_but_exhausted`，小组合分钟规则是 `closed_no_rule`；可继续的不是本地覆盖脚本，而是外部授权 MBO/MBP10 或同源执行回放导入。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_report_stage255_microstructure_coverage_closure_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_summary_stage255_microstructure_coverage_closure_audit_v1.csv`
- coverage ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_coverage_ledger_stage255_microstructure_coverage_closure_audit_v1.csv`
- route status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_route_status_stage255_microstructure_coverage_closure_audit_v1.csv`
- gate status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_gate_status_stage255_microstructure_coverage_closure_audit_v1.csv`
- schema probe：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage255_microstructure_coverage_closure_audit/qmt_roll_stage255_c9_minrisk_microstructure_coverage_closure_audit_filtered_source_schema_probe_stage255_microstructure_coverage_closure_audit_v1.csv`
- visuals：`official_path_coverage_status`、`coverage_ledger_chart`、`gate_status_matrix`、`schema_probe_chart`、`route_status_chart`

## 结束后反思

- 是否在过拟合：否。结论来自数据层 hard gate，不来自收益标签挑选或参数救参；并且明确关闭“继续用分钟特征补真实订单流”的错误方向。
- 是否还有价值继续：有，但方向要换。继续本地补分钟覆盖已经没有价值，因为分钟覆盖还差 `0`；真正有价值的是导入授权 MBO/MBP10、同源执行回放，或另开外生持仓/会员结构点时修复路线。若这些外部数据没有到位，本线不能靠继续扫分钟特征证明目标完成。

## 后续 TODO

- 不再围绕 Stage238 的 7 个分钟 candidate feature 扫阈值、分位、年份、交易所、方向或产品补丁。
- 若拿到授权 MBO/MBP10，先复跑 Stage112/117/136，再进入 Stage255 schema/gate 复核，通过后才允许设计 orderflow preflight。
- 若拿到 broker/production 执行回放，先复跑 Stage111 intake acceptance，通过字段、同源、点时和覆盖 gate 后再做执行质量归因。
- 若短期拿不到微观结构数据，下一步只能研究不改变正式持仓路径的部署层治理，或独立的外生持仓/会员结构点时覆盖修复。
