# Stage086 Stage449/raw 生成端 provenance 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 11:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读源码与资产 provenance 审计；不是真实组合引擎，不新增交易规则。
- 是否重要突破：否。它是数据源路线关闭与边界压实。
- 是否触发A/B：否。没有产生可接入正式版或 A/B 的策略版本。

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html`
  - TqSdk tick/行情对象字段文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html`
  - TqSdk 回测模式文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
- 我的判断：
  - 若要把盘口/微观结构接入规则，最低证据不是“有一分钟 open”，而是同源 tick/quote/depth 或可复现的 tick-to-bar 生成链。
  - TqSdk 文档显示 tick 对象应有 `last_price`、`bid_price1`、`ask_price1`、`volume`、`open_interest` 等字段，`DataDownloader dur_sec=0` 也支持 tick；因此 Stage449/raw 如果真实保存了 quote/depth，应能在 schema 或生成代码里看到这些字段。
  - vn.py `BarGenerator` 是从 tick 生成 1 分钟 bar 的标准语义；如果 Stage449 能被同源 tick 重建，至少应该能找到 tick serial 或类似 transform provenance。当前没有。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage086_stage449_raw_generation_provenance_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无交易参数；新增 provenance gates：`G1-G7`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage010 官方 C9/15w 日曲线；扫描 Stage446/448/449/070/079 相关本地源码与资产。
- 账户规模：`150,000`。
- 成本口径：沿用官方曲线成本与滑点汇总。
- 样本过滤：不按盈亏、年份、品种、方向筛选；全量扫描 Stage449 full bars，抽样/聚合扫描 Stage449 shards 与 Tq tick 样本 schema。
- 策略/归因口径：只读 provenance。只有同时满足同源、真实 quote/depth 或 tick 字段、非零 volume、非退化 OHLC、可复现 transform，才允许进入下一步微观候选。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6339`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：沿用 Stage010 官方口径 `53.2560%`
- 其他关键指标：
  - source_file_count：`11`
  - source_get_kline_serial_count：`5`
  - source_get_tick_serial_count：`3`，但 tick serial 来自 Stage079/077 审计脚本，不是 Stage446/448 生成端。
  - Stage446/448 生成端：`generator_get_kline=4`、`generator_get_tick=0`
  - asset_record_count：`92`
  - stage449_full_rows：`1,453,601`
  - stage449_full_zero_volume_pct：`100.0000%`
  - stage449_full_degenerate_ohlc_pct：`100.0000%`
  - stage449_quote_depth_asset_count：`0`
  - tq_tick_sample_file_count：`83`
  - tq_tick_bid_ask_file_count：`83`
  - field_gate_pass_count：`3/7`
  - rule_usable_same_source_microstructure_count：`0`
  - strategy_rule_created：`0`
  - true_engine_run：`0`
  - order_api_called：`0`
  - ctp_connected：`0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_report_stage086_stage449_raw_generation_provenance_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_summary_stage086_stage449_raw_generation_provenance_audit_v1.csv`
- source_audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_source_audit_stage086_stage449_raw_generation_provenance_audit_v1.csv`
- asset_schema_audit：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_asset_schema_audit_stage086_stage449_raw_generation_provenance_audit_v1.csv`
- field_gate_scorecard：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_field_gate_scorecard_stage086_stage449_raw_generation_provenance_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_decision_stage086_stage449_raw_generation_provenance_audit_v1.json`
- official path/provenance gate chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_official_path_provenance_gate_chart_stage086_stage449_raw_generation_provenance_audit_v1.png`
- schema field heatmap：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_schema_field_heatmap_stage086_stage449_raw_generation_provenance_audit_v1.png`
- bar quality chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_bar_quality_chart_stage086_stage449_raw_generation_provenance_audit_v1.png`
- source code provenance chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage086_stage449_raw_generation_provenance_audit/qmt_roll_stage086_c9_minrisk_stage449_raw_generation_provenance_audit_source_code_provenance_chart_stage086_stage449_raw_generation_provenance_audit_v1.png`

## 视觉结论

- official path/provenance gate chart：官方 C9/15w 权益、回撤、broker10 路径不变；图上明确标注 Stage449 quote/depth assets `0`、usable same-source microstructure `0`，说明主回撤和 broker10 尖峰仍没有可用微观源解释。
- schema field heatmap：Tq tick 样本有 `last_price/bid/ask/depth1/tick_datetime`，但所有 Stage449/446 bar 只有 OHLC/volume/OI 三类 bar 字段，且 `is_rule_usable_same_source_microstructure=0`。
- bar quality chart：Stage449 full、Stage446 seed、Stage449 shards 的 zero volume 与 degenerate OHLC 均为 `100%`；这不是成交量分钟 K，也不是盘口。
- source code provenance chart：可观察生成端 Stage446/448 以 `get_kline_serial(duration_seconds=60)` 为核心，非 `get_tick_serial`；后续 tick 代码来自 Stage079/080 的异源 transform/TCA 审计。

## 结论

- 本阶段结论：`stage086_stage449_raw_generation_no_hidden_quote_depth_no_rule`
- 是否进入下一步：进入外部/授权数据工程，不进入 true engine、不进入 A/B、不生成策略候选。
- 下一步：
  - 不再把 Stage449/raw zero-volume proxy 当成微观结构源。
  - 若继续 R4，只能找到真实 Stage449/raw 生成端 quote/depth 源文件，或取得授权 vendor/raw exchange tick/quote/depth。
  - 若不补授权微观源，则转向官方/授权会员持仓、仓单、库存、基差的点时化覆盖修复。

## 过拟合反思

- 运行前判断：否。只验证数据 provenance，不使用盈亏优化规则。
- 运行后判断：否。结论是关闭路线，不生成交易条件。
- 原因：本阶段没有按历史亏损、年份、品种、方向或 maxDD episode 调参；它用 schema、源码和 bar 质量硬证据判断 Stage449/raw 是否可用。绕过该结论继续在 zero-volume proxy 上挖字段才是过拟合。

## 继续价值反思

- 运行前判断：有。Stage085 最高 readiness 是 Stage449/raw，必须确认是否真有被遗漏的 quote/depth 字段。
- 运行后判断：有，但策略研究价值已转为数据工程价值。
- 原因：Stage086 把 R4 的本地可挖空间基本关闭；继续有价值的动作是拿真实授权数据，而不是继续在现有 Stage449 文件上构造规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage086 结论和下一步边界。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、不是重要突破，也不是跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为本线边界记录，不是正式候选或重要合入摘要。
