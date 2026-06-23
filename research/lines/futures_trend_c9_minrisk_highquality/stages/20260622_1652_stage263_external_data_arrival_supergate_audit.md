# Stage263 外部数据到货统一 supergate 审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-22 16:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读外部数据到货总闸门审计；不创建策略规则、不运行 true engine、不触发 A/B、不改官方配置、不连接 CTP/SimNow、不调用 order API
- 是否重要突破：否，非收益突破；是流程补齐资产，把授权 orderflow/depth 与 broker/production 执行回放两条路线合成同一张到货验收账本
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Databento MBO 文档：`https://databento.com/docs/schemas-and-data-formats/mbo`
  - Databento MBP-10 文档：`https://databento.com/docs/schemas-and-data-formats/mbp-10`
  - Databento common fields：`https://databento.com/docs/standards-and-conventions/common-fields-enums-types`
  - FIX 4.4 ExecutionReport：`https://www.onixs.biz/fix-dictionary/4.4/msgtype_8_8.html`
- 我的判断：MBO/MBP-10 的本质是订单簿事件级数据，FIX ExecutionReport 的本质是订单状态与成交回报链；分钟 OHLCV/OI、smoke、read-only、adapter、pending order 和普通回测成交表都不能替代这两类证据。Stage263 因此只固定“真数据到货后先跑哪个验收链”，不从历史盈亏反推任何交易阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage263_external_data_arrival_supergate_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读固定账本口径 `external_data_route_count=2`、`authorized_orderflow_required_window_count=485`、`authorized_w0_request_count=41`、`execution_replay_expected_entry_count=219`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage251 官方 A 臂曲线，`2018-01-02` 至 `2026-06-15`
- 账户规模：复用官方 C9/15w 口径
- 成本口径：复用 Stage251 官方 A 臂，未新增成本假设
- 样本过滤：只读前序 Stage112/113/114/117/120/135/141/260/261 执行回放导入包输出；不新增样本筛选
- 策略/归因口径：外部数据到货 supergate；不构造信号、不回测候选、不跑 true engine

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - 决策：`stage263_external_data_arrival_supergate_ready_wait_real_data_no_rule`
  - 外部路线数：`2`
  - 路线合同 ready：`2/2`
  - 真实外部数据 supplied：`0/2`
  - 已验收路线：`0/2`
  - 策略规则 allowed：`0/2`
  - true engine allowed：`0/2`
  - 授权 MBO/MBP10 orderflow：必需窗口 `485`，已覆盖 `0`，还差 `485`；W0 request `41`，hard accept `0`，还差 `41`
  - broker/production 执行回放：entry 同源覆盖 `0/219`，还差 `219`；required schema field `58`；fixture selftest `6/6`
  - Stage260 accepted same-source replay file：`0`
  - supergate：`3/9`，通过项仅为无副作用、两条合同包 ready、fixture/synthetic 防误用 ready；真实数据、验收、覆盖、schema/field、tail/bottom-loss、策略/true engine 全部失败

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage263_external_data_arrival_supergate_audit/qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_report_stage263_external_data_arrival_supergate_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage263_external_data_arrival_supergate_audit/qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_summary_stage263_external_data_arrival_supergate_audit_v1.csv`
- orders：不适用，本阶段不生成订单
- daily：官方路径图 `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_official_path_supergate_status_stage263_external_data_arrival_supergate_audit_v1.png`
- quality：
  - `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_route_supergate_stage263_external_data_arrival_supergate_audit_v1.csv`
  - `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_artifact_readiness_stage263_external_data_arrival_supergate_audit_v1.csv`
  - `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_arrival_decision_tree_stage263_external_data_arrival_supergate_audit_v1.csv`
  - `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_missing_evidence_ledger_stage263_external_data_arrival_supergate_audit_v1.csv`
  - `qmt_roll_stage263_c9_minrisk_external_data_arrival_supergate_audit_supergate_status_stage263_external_data_arrival_supergate_audit_v1.csv`
  - 视觉图 5 张：official path、route heatmap、artifact readiness matrix、arrival decision tree、missing evidence chart

## 结论

- 本阶段结论：已经补完“到货后怎么验收”的统一 supergate；本地不再缺流程包，真正缺的是两类外部实证数据本身。授权 orderflow/depth 路线还差 W0 `41/41` request、必需窗口 `485/485`；执行回放路线还差同源 entry 覆盖 `219/219`、字段合同 `18/18`、真实 replay package `1/1`。
- 是否进入下一步：进入，但下一步不是继续本地分钟覆盖，而是等待或导入真实 broker/production replay 包，或授权 MBO/MBP10 W0 包。
- 下一步：
  1. 若 broker/production replay 到货，先跑 Stage261 import packet，再跑 Stage260 field/source audit 与 tail atlas，最后 Stage141。
  2. 若授权 MBO/MBP10 W0 到货，先跑 Stage135/117/120/112/113，再进入 Stage141。
  3. 若只出现 smoke/read-only/adapter/pending order/minute OHLCV/backtest ledger，统一拒收为交易证据，只能记录负证据或管线 smoke。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有选择品种、年份、方向、盈亏窗口或阈值，不用收益表现训练规则，只按外部数据语义和前序固定合同整理验收链。它降低了“拿局部文件救参”的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但价值边界已经收窄。
- 原因：当前已把“还差多少覆盖”从含混问题拆成两个硬缺口：orderflow `485` 窗口/`41` W0 request 与 execution replay `219` entry。继续本地 OHLCV/OI 覆盖没有价值；继续价值只在真实外部数据到货、数据合同验收或拒绝伪数据替代。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage263 两条摘要
- 是否更新 `research/registry.md`：否，非跨线正式候选或路线废弃
- 是否追加根目录 `memory.md/back_log.md`：否，非重要收益突破或正式候选
