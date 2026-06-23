# Stage088 官方外生 raw 源 smoke 与 provenance 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 11:57 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：官方/公开外生数据源 raw smoke、hash/provenance 审计；不是策略回测
- 是否重要突破：否。只是确认部分官方 raw 路线可落盘，不构成交易规则
- 是否触发A/B：否。无候选、无 true engine、无正式接入价值判断

## 外部调研与判断

- 参考资料：
  - AKShare futures 文档：`https://github.com/akfamily/akshare/blob/main/docs/data/futures/futures.md`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - AKShare DCE wrapper 问题：`https://github.com/akfamily/akshare/issues/7002`
  - SHFE Daily Ranking：`https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=pm`
  - SHFE Daily Warrant：`https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=dailystock`
  - DCE 官网入口：`https://www.dce.com.cn/dceg/`
- 我的判断：
  - 会员持仓、仓单/库存是经济含义明确的入场前外生源，理论上比继续从 closed-lot 盈亏桶反推规则更接近目标。
  - 但 AKShare 近期对 DCE、CZCE、SHFE 相关接口有修复和更名记录，GitHub issue 也显示 DCE wrapper 存在 `BadZipFile/JSONDecodeError` 风险；所以必须先做 raw response 落盘、hash、parse smoke，不能直接把 wrapper 输出或本地 cache 当成可交易证据。
  - 本阶段只回答“能不能开始设计受控回填 manifest”，不回答“有没有 alpha”，更不能进入正式规则或 A/B。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage088_official_external_raw_source_smoke_audit.py`
- 修改脚本：同上，补了 wrapper-only source 的空 direct 汇总容错
- 删除脚本：无
- 新增参数：
  - `SAMPLE_DATES=["20210301","20240603","20260612"]`
  - `REQUEST_TIMEOUT=10`
  - `WRAPPER_TIMEOUT=25`
  - direct raw source：SHFE 仓单、SHFE 会员排名 new/legacy、CZCE holding/warehouse、DCE member batch、DCE warehouse、GFEX warehouse
  - AKShare wrapper source：DCE/CZCE/SHFE/GFEX 会员与仓单 wrapper
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w Stage010 权益曲线 `2018-01` 至 `2026-06`；raw smoke 使用 `20210301/20240603/20260612` 三个样本日
- 账户规模：`150,000`
- 成本口径：复用官方 Stage010 只读结果；本阶段不重算交易成本
- 样本过滤：无策略样本过滤；仅按 source/date 做 endpoint smoke
- 策略/归因口径：
  - 官方路径只读，不改正式配置
  - direct probe 必须保存 raw 文件和 sha256
  - wrapper probe 只做可用性正/反控，不作为 provenance 充分证据

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage088_official_raw_smoke_partial_but_not_backfill_ready_no_rule`
  - direct probes：`24`
  - direct parsed：`14`
  - direct hashed：`21`
  - wrapper probes：`8`
  - wrapper ok：`6`
  - wrapper rows：`3,498`
  - source_count：`8`
  - smoke_backfill_ready_source_count：`3/8`
  - smoke backfill-ready：`czce_member_rank`、`czce_warehouse`、`gfex_warehouse`
  - partial but not ready：`shfe_member_rank`、`shfe_warehouse`
  - blocked：`dce_member_rank`、`dce_warehouse`、`gfex_member_rank`
  - DCE direct：三日均 `HTTP 412`，raw 可 hash 但不可 parse
  - DCE wrapper：`futures_dce_position_rank` 复现 `BadZipFile`，`futures_warehouse_receipt_dce` 复现 `JSONDecodeError`
  - SHFE warehouse：`20210301/20240603` 可 parse，`20260612` 为 `404`
  - GFEX member：wrapper 有 rows，但本阶段没有 direct raw URL/hash 证据

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage088_official_external_raw_source_smoke_audit/qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_report_stage088_official_external_raw_source_smoke_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage088_official_external_raw_source_smoke_audit/qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_summary_stage088_official_external_raw_source_smoke_audit_v1.csv`
- orders：无
- daily：无新交易日线，仅复用 Stage010 official curve
- quality：
  - `qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_source_summary_stage088_official_external_raw_source_smoke_audit_v1.csv`
  - `qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_direct_raw_probe_stage088_official_external_raw_source_smoke_audit_v1.csv`
  - `qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_akshare_wrapper_probe_stage088_official_external_raw_source_smoke_audit_v1.csv`
  - raw responses：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage088_official_external_raw_source_smoke_audit/raw/`
  - official path raw smoke chart：`qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_official_path_raw_smoke_chart_stage088_official_external_raw_source_smoke_audit_v1.png`
  - endpoint matrix chart：`qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_endpoint_matrix_chart_stage088_official_external_raw_source_smoke_audit_v1.png`
  - raw response bytes chart：`qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_raw_response_bytes_chart_stage088_official_external_raw_source_smoke_audit_v1.png`
  - next action chart：`qmt_roll_stage088_c9_minrisk_official_external_raw_source_smoke_audit_next_action_chart_stage088_official_external_raw_source_smoke_audit_v1.png`

## 视觉观察

- official path raw smoke chart：官方 C9/15w 权益、回撤、broker10 路径保持不变；底部 source smoke 显示 backfill-ready 只有 `3/8`，说明本阶段没有形成降低回撤候选。
- endpoint matrix chart：DCE member/warehouse 全红，SHFE legacy 全红，SHFE warehouse 近端样本失败；CZCE holding/warehouse 与 GFEX warehouse 三日样本可 parse。
- raw response bytes chart：DCE 虽有 response bytes/hash，但内容是 412/错误页或不可解析 JSON；这类 hash 只能证明请求响应可落盘，不证明数据可用。
- next action chart：`czce_member_rank/czce_warehouse/gfex_warehouse` 可以设计小规模 backfill manifest，但仍需全历史、全 C9 产品、点时化、hash manifest 验收；其他 source 需要授权离线文件、vendor raw 或新 direct endpoint。

## 结论

- 本阶段结论：
  - 官方 raw smoke 部分成功，但远不到可回填全历史，更不到可规则化。
  - `czce_member_rank`、`czce_warehouse`、`gfex_warehouse` 具备进入下一步“受控小规模回填 manifest”的资格。
  - `dce_member_rank/dce_warehouse` 仍是关键阻断，不能继续在 DCE payload、日期或 AKShare wrapper 周边反复试参救路线。
  - `gfex_member_rank` 只有 wrapper 输出，没有 direct raw/hash provenance，不允许进入规则。
  - `shfe_member_rank/shfe_warehouse` 需要进一步处理 legacy/近端失败和全历史覆盖。
- 是否进入下一步：可以进入数据工程下一步；不能进入策略 true engine、A/B 或正式候选。
- 下一步：
  - Stage089 建议只做 `czce_member_rank/czce_warehouse/gfex_warehouse` 的小规模 backfill manifest 设计：固定日期网格、产品映射、raw path、query params、sha256、parse rows、schema hash、失败原因。
  - 同时列出 DCE/GFEX member 的授权/offline/vendor 获取需求；没有这些数据前，不再围绕历史 closed-lot 缺口做规则。

## 过拟合反思

- 运行前判断：否。本阶段不是按收益、年份、品种或亏损桶调规则，而是验证官方 raw 数据源能不能点时化落盘。
- 运行后判断：否，但需要继续防止“数据可得性过拟合”。不能因为 CZCE/GFEX 某三天能取到，就假设全历史、全产品、全交易所都可用。
- 原因：本阶段没有使用最终盈亏标签形成规则；风险在于把三天 smoke 外推为全历史 readiness，所以结论明确降级为数据工程。

## 继续价值反思

- 运行前判断：有价值。当前目标需要真正入场前可见、非最终盈亏标签的外生信号；补 provenance 是必要前置。
- 运行后判断：有价值，但路径要收窄。CZCE/GFEX 仓单与 CZCE 会员可做小规模回填清单；DCE 和 GFEX 会员必须先解决授权 raw，否则不能继续策略化。
- 原因：视觉和 CSV 均显示局部 raw route 存在，但 source readiness 分化严重。继续价值在“建立可复验数据资产”，不在“马上降低回撤”。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage088 摘要和后续边界。
- 是否更新 `research/registry.md`：否。不是重要突破、正式候选或跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否。没有策略候选或正式口径变化。
