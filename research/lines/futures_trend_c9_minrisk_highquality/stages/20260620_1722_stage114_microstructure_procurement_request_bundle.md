# Stage114 微观结构数据采购请求包

## 基本信息

- 时间：2026-06-20 17:22
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读采购/导入请求包；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage114_procurement_request_bundle_built_no_data_no_rule`
- 重要突破版本：否。它把 Stage113 的 `485` 个必需窗口转成可采购、可落盘、可验收的请求清单，但仍不是策略证据。

## 开始前反思

- 是否在过拟合：否。本阶段没有按收益结果调规则或筛样本，只把已固定的 required windows 合并成数据请求。
- 是否还有价值继续：是。Stage113 已经知道必须覆盖哪些窗口，Stage114 让“缺数据”变成供应商/授权数据可执行清单，后续可以直接按 request bundle 获取数据并回填 Stage112/113。

## 外部调研与判断

- Databento Historical API 文档显示，历史数据通常通过 dataset、symbols、schema、start/end 等参数取数，批量下载可以按 split duration/size 拆文件。判断：Stage114 应保留 `schema + symbol + start/end` 的供应商中性字段。
- Databento batch download 文档显示，批量任务会生成可下载文件并组织到 job 目录。判断：本线需要 manifest 明确 request_id、raw_file、data_file、raw hash、schema hash 和 query params，不能把下载目录当 provenance。
- Apache Arrow/Parquet 文档显示可以写 partitioned dataset，但 partition 太细会增加文件数量和管理成本。判断：不要按 candidate/window 分区；应按 vendor/schema/exchange/product/trading_day 分区，并通过 coverage proof 关联 window ids。
- CME MDP 资料显示，市场数据有 channel/market group 和 event-based SBE 格式。判断：对国内期货 vendor 也要保留 exchange/product/day 的批次边界和授权来源，避免跨源混合。

调研结论：采购包应按合约和交易日合并窗口，同时保留产品/年份/交易所批次；落盘应分 raw、normalized parquet、coverage proof 三层，避免把派生数据和原始授权证据混在一起。

参考链接：

- https://databento.com/docs/api-reference-historical
- https://databento.com/docs/api-reference-historical/timeseries/timeseries-get-range-async
- https://databento.com/docs/api-reference-historical/batch/batch-download
- https://arrow.apache.org/docs/python/parquet.html
- https://arrow.apache.org/docs/python/dataset.html
- https://www.cmegroup.com/market-data/distributor/market-data-platform.html

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage114_microstructure_procurement_request_bundle.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage114_microstructure_procurement_request_bundle/`
- 新增核心输出：
  - `request_intervals`：把 Stage113 required windows 按 `vt_symbol + trading_day` 合并成请求区间。
  - `procurement_batches`：按 `year + exchange + product + schema` 聚合成采购批次。
  - `request_priority_queue`：按视觉优先、right-tail、bottom-loss、maxDD 和 orderflow_required 排序。
  - `product_year_matrix`：产品/年份覆盖热图数据。
  - `storage_layout_plan`：raw/data/proof 三层落盘计划。
  - `procurement_manifest_template`：供应商数据到货后的 manifest 模板。

## 参数与结果变更

- 新增参数：
  - `REQUEST_MERGE_GAP_MINUTES=10`
  - `MIN_REQUEST_SECONDS=60`
  - MBO 优先策略：`mbo_l3_preferred_mbp10_minimum`
  - MBP-10 最低策略：`mbp10_minimum_mbo_accepted`、`mbp10_or_mbo`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做采购优先级视觉图。
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
| required_window_count | 485 |
| request_interval_count | 276 |
| procurement_batch_count | 126 |
| product_year_cell_count | 90 |
| unique_vt_symbol_count | 146 |
| unique_product_count | 19 |
| unique_exchange_count | 4 |
| unique_trading_day_count | 203 |
| total_request_seconds | 3,117,720 |
| total_request_hours | 866.0333 |
| mbo_preferred_request_count | 112 |
| mbp10_minimum_request_count | 164 |
| visual_priority_request_count | 74 |
| right_tail_request_count | 18 |
| bottom_loss_request_count | 22 |
| maxdd_context_request_count | 36 |
| procurement_gate_pass_count | 4 / 6 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

Gate 解释：

- 通过的是 planning gate：request intervals 已生成、`485` 个窗口全部映射、batch 和 manifest template 已生成。
- 未通过的是 data gate：授权 raw/data/proof 文件仍为 `0`，Stage112/113 接受仍为 `0`。

## 视觉产物

- official path request priority：`qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_official_path_request_priority_stage114_microstructure_procurement_request_bundle_v1.png`
- request interval chart：`qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_request_interval_chart_stage114_microstructure_procurement_request_bundle_v1.png`
- product-year heatmap：`qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_product_year_heatmap_stage114_microstructure_procurement_request_bundle_v1.png`
- batch complexity chart：`qmt_roll_stage114_c9_minrisk_microstructure_procurement_request_bundle_batch_complexity_chart_stage114_microstructure_procurement_request_bundle_v1.png`

视觉观察：

- official path request priority 图显示采购点覆盖权益台阶、2022 主回撤、broker10 尖峰和近端高位震荡，说明不能只采某个年份或右尾样本。
- request interval chart 显示请求量在 `2020/2021` 最大，且 session guard 使早期请求小时数较高。
- product-year heatmap 显示需求分散在 `19` 个产品和 `4` 个交易所，`MA/jm/SM/fu/rb/sp/ru/CF` 等是主要采购对象；这反证了“按单品种补数据就够”的想法。
- batch complexity chart 显示优先批次包括 `fu.SHFE 2022`、`lh.DCE 2024`、`MA.CZCE 2023`、`fu.SHFE 2023`、`rb.SHFE 2023` 等。它们是采购优先级，不是交易规则。

## 结论

Stage114 已把 Stage113 的 `485` 个窗口转为 `276` 个请求区间和 `126` 个采购批次，且全部窗口已映射。当前仍没有授权数据到货，因此不能进入 true engine、A/B、正式候选或任何微观结构规则预检。

本阶段的有效进展是：下一步不再泛泛说“需要授权盘口数据”，而是可以按 `request_intervals` / `procurement_batches` 明确向供应商或数据工程流程请求，并按 `storage_layout_plan` 与 `procurement_manifest_template` 落盘。

## 后续规划和 TODO

1. 按 `request_priority_queue` 先处理视觉优先、right-tail、bottom-loss、maxDD 批次，仍不得把 priority 当交易信号。
2. 数据到货后按 raw/data/proof 三层落盘，并填 `procurement_manifest_template` 所需字段。
3. 先复跑 Stage112，再复跑 Stage113；只有两者 hard data gate 全过，才允许进入只读微观结构规则 preflight。
4. 如果供应商只能提供 L1 或没有 sequence/capture continuity proof，只能作为 TCA/forward-watch，不进入规则研究。

## 结束反思

- 是否在过拟合：否。采购清单没有改变策略，也没有从收益标签反推规则；priority 只服务数据获取顺序。
- 是否还有价值继续：有，但下一步价值取决于是否能拿到授权数据或明确供应商字段合同。若没有数据，继续做内部 OHLC 规则会偏离当前边界并增加过拟合风险。
