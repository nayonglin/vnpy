# Stage055 reentry OHLCV source repair audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 04:45 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据源修复审计；不是 true engine，不是交易规则，不改正式配置。
- 是否重要突破：否；这是数据资产发现，不是策略候选突破。
- 是否触发A/B：否；`candidate_like=false`，不需要读取 `skills/version-ab-experiment/SKILL.md`。

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html
  - TqSdk GitHub：https://github.com/shinnytech/tqsdk-python
  - vn.py `BarGenerator` tick-to-minute 逻辑：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
  - vn.py issue #2883，历史上分钟 bar 的 close/volume/open_interest 可能因生成逻辑错误为 0：https://github.com/vnpy/vnpy/issues/2883
- 我的判断：外部资料确认，正常可交易分钟 bar 应该有 high/low/volume/open_interest 语义；如果本地分钟源 exact bar 只有单价且 volume 为 0，只能作为路径价格参考，不能支撑重入当刻 K 线质量规则。本阶段发现 Stage491/459/462 full-session backfill 能修复一部分 exact OHLCV，这是数据工程入口，不是 alpha。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage055_reentry_ohlcv_source_repair_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MAX_ATLAS_EVENTS=12`
  - `ATLAS_WINDOW_MINUTES=60`
  - 审计源：Stage491、Stage459、Stage462、Stage448、Stage452、Stage498、Stage504、Stage506 本地 TqSdk minute shard。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage054 的官方 C9/15w stop/retry reentry events，覆盖 `2018-2026`。
- 账户规模：`150,000`
- 成本口径：沿用 Stage054 官方曲线，不新增交易、不重算滑点。
- 样本过滤：只审计 `retry_reentered=1` 的 `54` 个 C9 reentry 事件。
- 策略/归因口径：逐事件、逐源检查 reentry exact bar 是否存在，以及 `high-low>0` 且 `volume>0` 的 OHLCV ready 状态；只读记录 `range_r`、`body_r`、`volume_ratio_20`，不生成交易信号。

## 结果

- 官方 A：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
  - broker10 峰值：`111.7365%`
- reentry 数据修复：
  - reentry 事件：`54`
  - best-source OHLCV ready：`34/54=62.9630%`
  - best-source OHLCV ready reentry PnL：`+1,727,602.00`
  - remaining no-ready：`20`
  - remaining no-ready reentry PnL：`+969,695.00`
  - Stage491 单源 OHLCV ready：`23/54`
  - Stage491 单源 ready reentry PnL：`+1,142,966.00`
  - Stage054 slow/deep 目标 OHLCV ready：`6/6`
  - Stage054 slow/deep ready reentry PnL：`+1,361,035.60`
- 源质量：
  - Stage448 file exists `38/54`、exact bar `29/54`，但 OHLCV ready `0/54`；问题是 exact bar 多数零 range/零 volume。
  - Stage491 file exists `27/54`、exact bar `23/54`、OHLCV ready `23/54`，是当前最强修复源。
  - Stage459/462 分别 OHLCV ready `7/54`、`8/54`，可作为 Stage491 补充。
- 年度覆盖：
  - `2018/2019` ready 为 `0`。
  - `2020` ready `6/8`，`2021` ready `8/10`。
  - `2022/2023/2024/2026` ready 为 `100%`。
  - `2025` ready `1/2`，未 ready 的 `FG601.CZCE` reentry PnL `+950,000`，不能把缺覆盖当坏信号。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_report_stage055_reentry_ohlcv_source_repair_audit_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_decision_stage055_reentry_ohlcv_source_repair_audit_v1.json`
- source quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_source_quality_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- event repair：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_event_repair_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- source summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_source_summary_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- year summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_year_summary_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- bucket summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_bucket_summary_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- gap plan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_remaining_gap_plan_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_readiness_contribution_curve_stage055_reentry_ohlcv_source_repair_audit_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_readiness_path_chart_stage055_reentry_ohlcv_source_repair_audit_v1.png`
- source chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_source_readiness_chart_stage055_reentry_ohlcv_source_repair_audit_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_reentry_ohlcv_scatter_stage055_reentry_ohlcv_source_repair_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage055_reentry_ohlcv_source_repair_audit/qmt_roll_stage055_c9_minrisk_reentry_ohlcv_source_repair_audit_atlas_manifest_stage055_reentry_ohlcv_source_repair_audit_v1.csv`

## 视觉分析

- path chart：官方权益曲线保持原路径；ready 与 no-ready 两组 reentry PnL 都为正，说明数据是否 ready 不能当交易筛选信号。
- source chart：Stage448 exact bar 多但 OHLCV ready 为 `0`；Stage491 是主要修复源，Stage459/462 是补充源。
- scatter：OHLCV-ready 样本的 `range_r` 与 `volume_ratio_20` 中正负 PnL 混杂，红框 slow/deep 目标也不形成单调分界。当前只能说数据可用，不能说量能或 range 可交易化。
- atlas：左侧 Stage448 能画出 close path 但 volume 退化，右侧 Stage491/459 有 high-low 区间和成交量柱；`SA105/MA109/sp2205/lh2301` 等目标事件清楚显示源质量差异。

## 结论

- 本阶段结论：`stage055_stage491_repairs_reentry_ohlcv_partial_data_asset_no_trade_rule`。
- 是否进入下一步：进入数据工程/只读交叉，不进入 true engine 或 A/B。
- 下一步：
  - 先补 Stage491/同口径 full-session backfill 的剩余 `20` 个 no-ready reentry 缺口，尤其 `2018/2019`、`FG601.CZCE`、`OI201.CZCE`。
  - 补齐前不得把 `range_r`、`body_r`、`close_position`、`volume_ratio_20`、OHLCV-ready 状态、source 名称直接写成开仓/跳过/降仓规则。
  - 补齐后才允许做一次预声明只读交叉：重入当刻真实 OHLCV 是否能与真正外生状态或 Stage045 replay 语义结合，并且必须先证明不砍右尾。

## 过拟合反思

- 运行前判断：过拟合风险低到中等。做数据源修复本身不过拟合，但一旦看到 ready 样本 PnL 就容易把 coverage 变成筛选信号。
- 运行后判断：本阶段不过拟合；已经明确不把 source-ready 或量能/range 交易化。
- 原因：ready/no-ready 都有正贡献，scatter 无单调结构；本阶段只证明数据质量边界被 Stage491 部分修复。

## 继续价值反思

- 运行前判断：有价值。Stage032/033 后 stop/retry 的核心阻塞是 exact OHLCV 缺失，本阶段直接检验是否有未纳入的新本地源。
- 运行后判断：有价值，但继续方向必须是数据工程，不是参数实验。
- 原因：Stage491 把 `34/54` reentry 的 best-source OHLCV 修好，并覆盖全部 Stage054 slow/deep 目标；但剩余 `20` 个 no-ready 仍有 `+969,695` 右尾贡献，覆盖不足还不能支撑策略规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage055 摘要与数据工程边界。
- 是否更新 `research/registry.md`：否；不是正式候选、路线合并或全局重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段为本线数据资产发现，尚未形成策略候选。
