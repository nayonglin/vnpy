# Stage069 初始开仓双锚点价格基准审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 07:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据覆盖/成交价锚点语义审计，不是交易规则
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方文档：`TqBacktest` 在订阅 tick 时 quote 按 tick 推进；未订阅 tick 而只订阅 K 线时，quote 会由 K 线近似生成，盘口字段也会退化。
  - vn.py GitHub README：`data_recorder` 用于记录 Tick 或 K 线数据，供回测或实盘初始化使用，说明 tick 与 bar 是不同粒度的数据资产。
  - Quantpedia continuous futures methodology：连续合约的 roll/adjust 方法没有单一最优选择，策略回测与执行/经济解释的价格口径应分开。
  - QuantStart continuous futures：期货多合约拼接存在 contango/backwardation 和 roll return 问题，连续合约适合研究，但真实执行必须回到具体合约。
- 我的判断：
  - Stage068 发现的 ready tick 与 official open price 不 exact，不能直接解释为成交异常，更不能写成过滤或滑点规则。
  - 对 C9 初始开仓来说，至少存在两个不同锚点：`event_scan_anchor` 是官方 C9/C2 事件语义扫描起点，`price_proxy_anchor` 是解释 official open price 的 raw proxy 成交价锚点。
  - 后续盘口/TCA 必须先用 `price_proxy_anchor` 对齐成交价，再用 `event_scan_anchor` 单独审计日内事件语义；两者混用会制造假 mismatch。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage069_initial_entry_dual_anchor_price_basis_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE069_ENABLE_TQSDK`：默认 `0`；本阶段仅曾用 `1` 做前 5 笔 `price_proxy_anchor` smoke 下载。
  - `STAGE069_DOWNLOAD_ROLES`：默认 `price_proxy_anchor`，避免把 event scan 与 price proxy 混作同一下载目标。
  - `STAGE069_MAX_EVENTS`：默认 `0` 全量计划；smoke 下载时使用 `5`。
  - `STAGE069_DOWNLOAD_WINDOW_MINUTES=3`
  - `STAGE069_MAX_SECONDS_PER_EVENT=60`
  - `STAGE069_TICK_DATA_LENGTH=12000`
  - `STAGE069_NEAR_R_TOL=0.05`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage068 生成的 `219` 笔 Stage045 `full_event_sync_exact=1` 初始开仓，覆盖 `2020-01-09` 至 `2026-03-16`。
- 账户规模：当前官方 C9/15w，`150,000`。
- 成本口径：沿用官方 C9/15w 既有成本，不新增滑点/手续费假设。
- 样本过滤：
  - 只读 Stage068 plan 与 features。
  - 每笔 initial entry 拆成两行 anchor plan：`event_scan_anchor` 与 `price_proxy_anchor`。
  - 复用 Stage068 已下载的 `5` 个 event scan tick 文件。
  - 对前 `5` 个可配对事件补下载 `price_proxy_anchor` tick；最终全量输出恢复为 no-download 口径。
- 策略/归因口径：
  - 不改变官方交易。
  - 不新增开仓、减仓、恢复风险或退出规则。
  - 不跑 true engine。
  - 不连接 CTP，不调用订单 API。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage069_dual_anchor_price_basis_partial_unresolved_no_rule`
  - base trade count：`219`
  - anchor plan rows：`438`
  - event scan anchor ready：`5`
  - price proxy anchor ready：`5`
  - paired ready：`5`
  - event scan price exact：`1/5`
  - price proxy price exact：`5/5`
  - proxy improves abs delta：`4/5`
  - all initial entries realized PnL：`32,390,657.50`
  - both pending：`214` 笔，PnL `32,395,977.50`
  - price proxy anchor exact：`5` 笔，PnL `-5,320.00`
  - event scan anchor median abs delta：`0.4348R`
  - price proxy anchor median abs delta：`0.0000R`

## 视觉观察

- 资金曲线价格基准图显示：已解释为 `price_proxy_anchor_exact` 的样本只覆盖 `2020` 年初 5 笔，之后主要权益台阶仍属于 `both_pending`；因此当前结论只能修正锚点语义，不能证明任何盘口信号。
- scan/proxy delta 散点图显示：4 个夜盘 raw proxy 样本的 `event_scan_anchor` 价格偏差约 `0.2381R` 至 `1.1818R`，但 `price_proxy_anchor` 全部回到 `0R`；这直接支持“价格 mismatch 是锚点定义差异”的解释。
- 双锚点 tick atlas 显示：左侧 `event_scan_anchor` 往往是 official date 日盘 `09:00`，官方开仓价线常远离当时 bid/ask/last；右侧 `price_proxy_anchor` 多是 candidate date 夜盘 `21:00`，官方开仓价线穿过 tick bid/ask/last。`au2006` 的 scan/proxy 同为 `2020-02-06 09:00`，两侧一致，构成对照样本。
- anchor status 图显示：两个 anchor role 都只有 `5/219` ready，覆盖率仍极低；剩余 `214` 笔还不能下结论。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_report_stage069_initial_entry_dual_anchor_price_basis_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_summary_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- dual anchor plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_dual_anchor_plan_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- download status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_download_status_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- anchor features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_anchor_price_features_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- trade comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_trade_anchor_comparison_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- coverage summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_coverage_summary_stage069_initial_entry_dual_anchor_price_basis_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_official_path_price_basis_chart_stage069_initial_entry_dual_anchor_price_basis_audit_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_scan_vs_proxy_delta_scatter_stage069_initial_entry_dual_anchor_price_basis_audit_v1.png`
- status chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_anchor_status_chart_stage069_initial_entry_dual_anchor_price_basis_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage069_initial_entry_dual_anchor_price_basis_audit/qmt_roll_stage069_c9_minrisk_initial_entry_dual_anchor_price_basis_audit_dual_anchor_tick_atlas_stage069_initial_entry_dual_anchor_price_basis_audit_v1.png`

## 结论

- 本阶段结论：`stage069_dual_anchor_price_basis_partial_unresolved_no_rule`
- 是否进入下一步：是，但仍只能作为数据覆盖/TCA 纪律继续。
- 下一步：
  - 优先批量补齐剩余 `214` 笔 `price_proxy_anchor` tick，先验证 official open price 是否能在 raw proxy 成交价锚点内稳定 exact。
  - `event_scan_anchor` 后续只用于 C9/C2 event semantics 审计，不用于解释成交价。
  - 若 full proxy coverage 仍 exact，再开始提取 spread、depth、official volume / depth、mid/last move 等 TCA 特征；若不 exact，先查连续合约/复权/主力切换价格基准。
  - 在覆盖和价格基准未闭环前，禁止 true engine、A/B、正式候选或任何开仓过滤/最小风险/恢复仓/退出规则。

## 过拟合反思

- 运行前判断：否。本阶段不是从亏损样本反推规则，而是修正 Stage068 暴露的价格基准问题。
- 运行后判断：否，但如果把 `5/5 price_proxy exact` 外推成全周期盘口信号，就会过拟合。
- 原因：
  - 当前 paired ready 只有 `5/219`，且 PnL 合计仅 `-5,320`，不代表全周期。
  - 结论是数据语义边界，不是收益模式。
  - 本阶段没有筛年份、品种、方向、月份或阈值，也没有使用未来盈亏设计规则。

## 继续价值反思

- 运行前判断：有价值。Stage068 的价格 mismatch 如果不拆清，会让后续所有 tick/TCA 研究建立在错误锚点上。
- 运行后判断：有价值，但价值仍在数据资产和执行纪律，不在当前生成策略。
- 原因：
  - 双锚点拆分解释了 Stage068 的主要 mismatch，降低后续误判风险。
  - 初始开仓 `219` 笔覆盖主要权益台阶，若能补全 proxy tick，可以审计高质量信号的真实入场成本与流动性。
  - 当前覆盖不足，必须继续补数，而不是提前写规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage069 状态和 Stage068 后续边界修正。
- 是否更新 `research/registry.md`：否，非合入/正式候选/重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破，仅本线数据语义推进。
