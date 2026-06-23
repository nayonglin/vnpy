# Stage116 W0 pipeline intake packet

## 基本信息

- 时间：2026-06-20 17:40
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读 W0 交付/验收包；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage116_wave0_packet_built_no_data_no_rule`
- 重要突破版本：否。它把 Stage115 的 W0 变成可交付 intake packet 和 manifest 模板，但仍不是策略证据。

## 开始前反思

- 是否在过拟合：否。本阶段只拆 W0 数据交付与验收字段，且继续把 `strategy_use_allowed_now` 和 `rule_preflight_allowed_now` 锁为 `0`。
- 是否还有价值继续：是。Stage115 已经规定 W0 只能做 pipeline smoke，Stage116 让 W0 可以直接交给供应商或数据工程流程，减少人工挑选和错用样本的空间。

## 外部调研与判断

- Databento Historical / Batch 文档和官方 Python/GitHub 资料显示，历史数据交付需要保留 schema、symbol、start/end、encoding/provenance 等可复验字段。判断：W0 manifest 必须逐 request 填 raw_file、raw_sha256、normalized file、proof file、schema hash 和 timestamp 字段。
- Apache Arrow Dataset / Parquet 文档支持多文件、分区数据集。判断：W0 仍按 wave/request/batch/product/day/schema 组织，不按 candidate 或收益标签切分。
- NIST SP1270 对 sampling / selection bias 的讨论说明，非代表性样本不能外推总体。判断：W0 即使覆盖 `70` 个窗口，也只能验证数据链路，不能做 signal research、PnL attribution 或产品/年份结论。

调研结论：W0 的价值是验收“能不能安全地拿到、存下、证明、读取”微观结构数据，而不是判断策略好坏。早期样本越小，越应该把权限写死。

参考链接：

- https://databento.com/docs/api-reference-historical
- https://databento.com/docs/api-reference-historical/batch/batch-download
- https://github.com/databento/databento-python
- https://github.com/databento/dbn
- https://arrow.apache.org/docs/python/dataset.html
- https://arrow.apache.org/docs/python/parquet.html
- https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1270.pdf

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage116_wave0_pipeline_intake_packet.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage116_wave0_pipeline_intake_packet/`
- 新增核心输出：
  - `w0_request_packet`：W0 的 `41` 个 request 明细。
  - `w0_batch_packet`：W0 的 `12` 个采购批次。
  - `w0_delivery_manifest_template`：逐 request 的 raw/data/proof 填报模板。
  - `w0_acceptance_tests`：W0 入库前硬闸门。
  - `w0_coverage_probe`：W0 的 exchange/product/year/schema 覆盖结构。

## 参数与结果变更

- 新增参数：
  - `WAVE_ID=W0_pipeline_smoke`
  - `strategy_use_allowed_now=0`
  - `rule_preflight_allowed_now=0`
  - `accepted_window_coverage_pct_now=0.0`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做 W0 intake 视觉检查。
- 修改回测结果：无。
- 删除回测结果：无。

当前路径指标保持不变：

| 指标 | 数值 |
| --- | ---: |
| 期末权益 | 39,176,437.60 |
| 总收益 | 26017.6251% |
| 最大回撤 | -45.0827% |
| Sharpe | 1.6331 |
| 总滑点 | 2,730,130 |
| 总交易次数 | 787 |
| 胜率 | 36.0902% |
| broker10 峰值 | 111.7365% |

## 关键结果

| 项目 | 结果 |
| --- | ---: |
| w0_batch_count | 12 |
| w0_request_count | 41 |
| w0_window_count | 70 |
| w0_unique_vt_symbol_count | 22 |
| w0_unique_product_count | 12 |
| w0_unique_exchange_count | 4 |
| w0_unique_year_count | 6 |
| w0_total_request_hours | 132.6167 |
| w0_visual_priority_count | 39 |
| w0_right_tail_window_count | 14 |
| w0_bottom_loss_window_count | 15 |
| w0_maxdd_context_window_count | 12 |
| w0_mbo_preferred_request_count | 11 |
| w0_mbp10_minimum_request_count | 30 |
| acceptance_gate_pass_count | 5 / 11 |
| accepted_raw_file_count_now | 0 |
| accepted_data_file_count_now | 0 |
| accepted_proof_file_count_now | 0 |
| stage112_intake_allowed_now | 0 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

Gate 解释：

- 已通过：W0 request packet 非空、batch packet 非空、request_id 唯一、策略权限锁为 `0`、禁止 candidate-level partition。
- 未通过：raw/data/proof 文件均未声明，raw sha256 未声明，sequence gap `0` 未证明，Stage112 intake 仍不允许。

## 视觉产物

- official path W0 intake map：`qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_official_path_w0_intake_map_stage116_wave0_pipeline_intake_packet_v1.png`
- W0 request duration chart：`qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_request_duration_chart_stage116_wave0_pipeline_intake_packet_v1.png`
- W0 schema/exchange matrix：`qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_schema_exchange_matrix_stage116_wave0_pipeline_intake_packet_v1.png`
- W0 product-year heatmap：`qmt_roll_stage116_c9_minrisk_wave0_pipeline_intake_packet_w0_product_year_heatmap_stage116_wave0_pipeline_intake_packet_v1.png`

视觉观察：

- official path W0 intake map 显示 W0 覆盖不同权益阶段、2022 主回撤附近和近端样本，但标题明确为 pipeline sample only；这些点不能被解释为交易信号。
- request duration chart 显示主要请求集中在约 `6.17` 小时的完整日盘窗口，说明 W0 主要是交付 sizing 问题，不是参数问题。
- schema/exchange matrix 显示 W0 同时覆盖 MBO preferred 与 MBP-10 minimum，且覆盖 CZCE/DCE/GFEX/SHFE；这服务 schema smoke。
- product-year heatmap 显示 W0 分散在 `2020-2025`、`12` 个产品上，但规模仍太小，不能代表总体。

## 结论

Stage116 已把 W0 拆成可直接交付和验收的 intake packet：`12` 批、`41` 请求、`70` 窗口、`132.6167` 请求小时。当前 `accepted_raw_file_count_now=0`、`accepted_data_file_count_now=0`、`accepted_proof_file_count_now=0`，因此 Stage112 intake、true engine、A/B、正式候选和微观结构规则预检全部继续阻塞。

本阶段的有效进展是：后续拿到 W0 数据后，不需要再人工解释该怎么落盘；只要填 manifest 并跑 acceptance tests，就能判断是否可以进入 Stage112 intake。

## 后续规划和 TODO

1. 让供应商或数据工程流程按 `w0_request_packet` 和 `w0_delivery_manifest_template` 交付 W0。
2. W0 到货后，必须填 raw/data/proof、raw sha256、schema hash、timestamp timezone、sequence gap 和 continuity proof。
3. 只有 W0 acceptance tests 的 data_hard 项全部通过，才允许跑 Stage112 intake；仍不得做策略研究。
4. W0 通过后再进入 W1 coverage/visual QA，W2 全量到齐前仍不做微观结构规则预检。

## 结束反思

- 是否在过拟合：否。W0 没有用于收益判断，所有早期样本都被标记为 pipeline-only，并且 Stage112 intake 仍被数据硬闸阻塞。
- 是否还有价值继续：有，但下一步价值取决于能否拿到 W0 授权数据。没有数据时继续发明 OHLC 或历史标签规则，会偏离“普世、穿越周期、不过拟合”的目标。
