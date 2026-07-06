# Stage091 JD 保证金数据源资格矩阵

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05 18:24 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据合同/来源资格闸门
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：DCE 日交易参数页、DCE 对外门户 API 服务新闻、AKShare futures_settle 文档、GTJA calendar、CnOpenData 每日期货结算参数数据库。
- 我的判断：当前没有任何已验收的 `jd_contract_daily_margin_history`。能进入 true ledger 的路线只剩 DCE 注册门户 API/官方原始表，或授权 vendor 的逐日结算参数导出；GTJA、TqSdk 当前 quote/settlement、RQData 当前 `get_commission_margin` 都不能直接作为 2020-2026 JD 逐日保证金历史。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage091_jd_margin_source_contract_matrix.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--timeout`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 到 2026-06-30 的 JD true-ledger 数据需求；本阶段不回测。
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：仅做数据源资格和本地能力审计。
- 策略/归因口径：不改策略、不跑 true engine、不连接 CTP、不调用订单 API。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：`accepted_route_count=0`，`can_be_accepted_after_import_count=2`，`preferred_next_route=dce_registered_portal_api`，`ready_for_true_ledger_replay=False`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage091_jd_margin_source_contract_matrix/rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_report_stage091_jd_margin_source_contract_matrix_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage091_jd_margin_source_contract_matrix/rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_route_matrix_stage091_jd_margin_source_contract_matrix_v1.csv`
- orders：不适用
- daily：不适用
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage091_jd_margin_source_contract_matrix/rebuilt_c9_v2_stage091_jd_margin_source_contract_matrix_local_capability_stage091_jd_margin_source_contract_matrix_v1.csv`

## 结论

- 本阶段结论：`stage091_no_accepted_jd_margin_source_route_matrix_ready`。
- 是否进入下一步：是。
- 下一步：优先获取 DCE 注册门户 API 文档/凭证或授权 vendor 逐日结算参数样本；拿到后先做 hash/PIT/覆盖验收，再考虑 Stage208 true ledger。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只做数据源资格矩阵，不看收益、不调策略参数。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：JD 保证金历史仍是 true ledger 硬阻塞，但已明确下一步不应继续在 GTJA 或 DCE 未授权公共端点上消耗。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等拿到 DCE/vendor 数据或确认路线废弃再更新。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。

## 独立 agent 审查

- 审查 agent：`019f31ca-ef45-7ca3-bf91-1ccd55c5ad02`
- 审查时间：2026-07-05 18:23 CST 左右
- 置信度：`0.84`
- 严重风险：未发现。脚本未命中 `send_order`、`cancel_order`、CTP 网关、邮件、`launchd`、subprocess 或 true-engine/backtest 入口；主逻辑是读取 Stage088-090 产物、本地包能力检查、4 个 DCE 公开 HTTP 探针，并生成本线输出。
- 中等风险：DCE 注册门户 API 方向合理，但字段级能力尚未拿到文档/样本验证；已按建议把 `has_exchange_margin_ratio` 和 `has_contract_daily_grain` 改为 `expected_must_verify`，把 coverage 改为 `potential_full_coverage_must_verify`。DCE 公共页面探针也已收窄为“当前本机未取得可验收机器数据”，不证明所有公开 HTML 路径不可能。
- 低风险：审查复算支持 `accepted_route_count=0`、`can_be_accepted_after_import_count=2`、`preferred_next_route=dce_registered_portal_api`、`route_count=8`、`local_package_count=3`、`dce_probe_count=4`、`dce_probe_success_json_count=0`、`ready_for_true_ledger_replay=False`。
- 建议：结论保留。继续向 DCE 注册 API/官方原始表或授权 vendor 逐日结算参数数据推进；不要把 GTJA、TqSdk 当前 settlement/quote、RQData 当前函数、AKShare 当前 DCE 缺口直接接入 JD 2020-2026 true ledger。拿到样本后先验收字段、PIT 发布时间/生效时间、连续日历覆盖、JD 合约覆盖、raw file hash，再允许讨论 Stage208 true ledger。
- 审查后过拟合反思：否。本阶段不是收益优化，不构成过拟合。
- 审查后继续价值反思：有。JD 精确逐日保证金仍是 true ledger 的硬阻塞。
