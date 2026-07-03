# Stage031 公开 raw manifest 批次计划审计

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02T08:03:49
- 阶段性质：只读数据工程计划；不下载全量、不回测、不改策略、不连接 CTP、不调用下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考交易所公开仓单/排名页面、AKShare 期货数据文档，以及旧线 Stage088-090 的 raw smoke/manifest 探针。
- 我的判断：CZCE 会员/仓单和 GFEX 仓单可以先推进 raw 归档工程，但这只是数据地基；不能替代 orderflow/depth、生产执行回放或期权链历史。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage031_public_raw_manifest_plan_audit.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage031_public_raw_manifest_plan.py`
- 新增参数：`batch_size=100`，只用于下载计划分批；无交易参数。
- 修改参数：无
- 删除参数：无

## 结果

- planned_raw_request_count：`1504`
- batch_count：`16`
- source_count：`3`
- immediate_strategy_candidate_count：`0`
- 决策：`stage031_public_raw_manifest_batch_plan_ready_no_strategy_candidate`
- 下一方向：`execute_public_raw_download_batches_then_hash_parse_readiness_audit`

## 输出文件

- batch_plan：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage031_public_raw_manifest_plan_audit/rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_batch_plan_stage031_public_raw_manifest_plan_audit_v1.csv`
- batch_summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage031_public_raw_manifest_plan_audit/rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_batch_summary_stage031_public_raw_manifest_plan_audit_v1.csv`
- source_gate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage031_public_raw_manifest_plan_audit/rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_source_gate_stage031_public_raw_manifest_plan_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage031_public_raw_manifest_plan_audit/rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_decision_stage031_public_raw_manifest_plan_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage031_public_raw_manifest_plan_audit/rebuilt_c9_v2_stage031_public_raw_manifest_plan_audit_report_stage031_public_raw_manifest_plan_audit_v1.md`

## 过拟合反思

- 运行前判断：否。Stage031 只把已探针通过的公开 raw source 转成下载批次计划，不新增收益阈值或交易规则。
- 运行后判断：否。输出仍是数据交付清单；禁止把 source/date ready、缺失、产品命中或单一 raw source 写成交易条件。

## 继续价值反思

- 运行前判断：有。Stage030 已确认数据先行，本阶段把 CZCE/GFEX 公开 raw 路线从描述推进到可执行批次。
- 运行后判断：有，但下一步必须下载、hash、解析并做 post-download readiness；在此之前仍无策略候选。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是。
- 追加根目录 `memory.md/back_log.md`：否，本阶段不是策略候选或重要突破。
