# Stage115 采购波次反挑样本计划

## 基本信息

- 时间：2026-06-20 17:31
- 工作模式：day
- 研究线：`futures_trend_c9_minrisk_highquality`
- 阶段性质：只读采购波次计划；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API、不下载外部数据。
- 决策：`stage115_procurement_waves_built_no_data_no_rule`
- 重要突破版本：否。它把 Stage114 的采购包拆成可执行波次，并增加反挑样本闸门；仍不是策略证据。

## 开始前反思

- 是否在过拟合：否。本阶段没有根据收益结果选择交易规则，只把已经固定的 `485` 个 required windows 映射到采购波次，并规定早期波次不能用于策略研究。
- 是否还有价值继续：是。Stage114 的采购包太大，直接全量推进成本高；Stage115 把数据到货拆成可落地步骤，同时防止 W0/W1 小样本被误用成 alpha 结论。

## 外部调研与判断

- Databento Historical / Batch 文档显示，历史数据请求和批量下载可以通过 symbols、schema、start/end、split duration/size 等字段组织。判断：Stage115 的波次应保留 request/batch 的可执行边界，但 delivery order 只能代表数据工程顺序。
- Databento 官方 GitHub 客户端与 DBN 资料强调统一 schema、symbology 和二进制数据结构。判断：W0 的价值首先是验证 schema、timestamp、symbol mapping 和 provenance，而不是评价策略收益。
- Apache Arrow Dataset / Parquet 文档支持多文件、分区数据集。判断：落盘仍应按 product/day/schema 等稳定维度组织，不能按候选交易或 right-tail/bottom-loss 标签切碎数据。
- NIST SP1270 对 sampling / selection bias 的讨论说明，非代表性样本无法外推到总体。判断：W0/W1 即使覆盖了高视觉优先、右尾和亏损窗口，也必须禁止策略结论；全量 W2 和 Stage112/113 hard gate 通过前，不做规则预检。

调研结论：采购波次可以分层交付，但研究权限不能分层放开。W0 只能做 pipeline smoke，W1 只能做 coverage/visual QA，W2 全量到齐并通过验收后，才有资格进入后续只读微观结构预检。

参考链接：

- https://databento.com/docs/api-reference-historical
- https://databento.com/docs/api-reference-historical/batch/batch-download
- https://github.com/databento/databento-python
- https://github.com/databento/dbn
- https://arrow.apache.org/docs/python/dataset.html
- https://arrow.apache.org/docs/python/parquet.html
- https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.1270.pdf

## 本阶段改动

- 新增工具：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage115_procurement_wave_antiselection_plan.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage115_procurement_wave_antiselection_plan/`
- 新增核心输出：
  - `wave_batch_assignments`：把 Stage114 的 `126` 个采购批次分配到 W0/W1/W2。
  - `wave_request_intervals`：把 `276` 个 request intervals 带上波次标签。
  - `wave_summary`：汇总每波 batch/request/window/小时数和允许用途。
  - `cumulative_plan`：展示到每个波次为止的计划覆盖率与当前验收覆盖率。
  - `anti_selection_gate`：把早期波次禁止策略研究写成硬闸门。
  - `supplier_checklist`：保留授权、schema、timestamp、continuity、raw provenance、coverage 等验收要求。

## 参数与结果变更

- 新增参数：
  - `W0_pipeline_smoke`：最小确定性跨 schema/exchange/period/product 样本，只验证链路。
  - `W1_tail_visual_coverage`：覆盖视觉优先、right-tail、bottom-loss、maxDD context 批次，只做覆盖和视觉 QA。
  - `W2_full_population`：剩余完整总体，用于避免后续预检基于挑选子集。
  - `accepted_window_coverage_pct_now=0.0`
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无真实回测；只复用当前路径资金曲线做波次覆盖视觉检查。
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
| total_batch_count | 126 |
| total_request_count | 276 |
| total_window_count | 485 |
| wave_count | 3 |
| W0 batch / request / window | 12 / 41 / 70 |
| W1 batch / request / window | 36 / 78 / 131 |
| W2 batch / request / window | 78 / 157 / 284 |
| planned_full_window_coverage_pct | 100.0% |
| accepted_window_coverage_pct_now | 0.0% |
| total_request_hours | 866.0333 |
| anti_selection_gate_pass_count | 5 / 7 |
| true_engine_allowed | 0 |
| strategy_feature_usable | 0 |

波次摘要：

| 波次 | 用途 | 禁止用途 | batch | request | window | 小时 |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| W0_pipeline_smoke | pipeline/schema/provenance validation only | 不做 signal research、rule preflight、PnL attribution、产品/年份结论 | 12 | 41 | 70 | 132.6167 |
| W1_tail_visual_coverage | coverage and visual QA only | W2 与 Stage112/113 通过前，不做策略比较 | 36 | 78 | 131 | 199.3167 |
| W2_full_population | 完整补齐剩余总体 | 不自动晋升；只允许后续只读预检 | 78 | 157 | 284 | 534.1000 |

Gate 解释：

- 已通过：`485/485` required windows 已全部分配到波次；W0/W1 策略使用权限均为 `0`；priority/wave label 只代表采购顺序；full population 仍是预检前置。
- 未通过：授权 raw/data/proof 文件仍为 `0`；Stage112/113 hard data gate 仍未通过。

## 视觉产物

- official path wave plan：`qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_official_path_wave_plan_stage115_procurement_wave_antiselection_plan_v1.png`
- wave bar chart：`qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_wave_bar_chart_stage115_procurement_wave_antiselection_plan_v1.png`
- cumulative coverage chart：`qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_cumulative_coverage_chart_stage115_procurement_wave_antiselection_plan_v1.png`
- product-year wave heatmap：`qmt_roll_stage115_c9_minrisk_procurement_wave_antiselection_plan_product_year_wave_heatmap_stage115_procurement_wave_antiselection_plan_v1.png`

视觉观察：

- official path wave plan 显示 W0/W1/W2 采购点覆盖权益台阶、2022 主回撤、broker10 尖峰和近端震荡；这说明波次是覆盖顺序，不是交易信号。
- wave bar chart 显示 W0 只是小规模 smoke，W2 才是主要总体；不能用 W0/W1 的局部表现提前决定规则。
- cumulative coverage chart 明确区分 planned coverage 和 accepted coverage；当前 accepted coverage 仍为 `0%`。
- product-year heatmap 显示 W0/W1/W2 分散在多产品、多年份、多交易所上；没有单一产品或年份足以代表总体。

## 结论

Stage115 已把 Stage114 的 `126` 个采购批次、`276` 个请求区间、`485` 个 required windows 拆成 W0/W1/W2 三个波次，并建立反挑样本硬闸门。当前 `authorized_data_delivered=0`，`stage112_stage113_acceptance_passed=0`，因此仍不能进入 true engine、A/B、正式候选或微观结构规则预检。

本阶段的有效进展是：后续可以先交付 W0 来验证数据链路，但 W0/W1 永远不能当策略样本。只有 W2 全量到齐、Stage112/113 验收通过后，才允许从数据层进入后续只读规则预检。

## 后续规划和 TODO

1. 先按 W0 交付最小跨样本数据，只验证 license、schema、timestamp、sequence continuity、raw/data/proof layout。
2. W0 通过后交付 W1，检查 visual priority、right-tail、bottom-loss、maxDD context 的覆盖与图形质量，仍不做策略比较。
3. W2 补齐剩余总体后，复跑 Stage112 和 Stage113；只有 hard gate 全通过，才允许下一阶段只读微观结构预检。
4. 如果供应商只能给 L1、缺少 sequence/capture proof 或不能保留 raw provenance，只能作为 TCA/forward-watch，不进入规则研究。

## 结束反思

- 是否在过拟合：否。Stage115 没有改变任何交易规则，也没有用早期小样本做收益判断；反而把 W0/W1 从制度上锁死为非策略样本。
- 是否还有价值继续：有。继续价值来自数据链路落地和验收；若没有授权微观结构数据，继续在现有 OHLC/历史标签里挖规则会重新抬高过拟合风险。
