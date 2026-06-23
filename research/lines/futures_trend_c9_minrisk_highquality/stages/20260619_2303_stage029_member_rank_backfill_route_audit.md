# Stage029 会员持仓覆盖缺口与接口可行性视觉审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 23:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：覆盖缺口 / 数据源路线审计；不新增交易规则、不改正式配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - AKShare 期货文档：`https://akshare.akfamily.xyz/data/futures/futures.html`
  - AKShare GitHub issue #7002：`https://github.com/akfamily/akshare/issues/7002`
  - AKShare changelog：`https://akshare.akfamily.xyz/changelog.html`
  - AKShare GitHub README：`https://github.com/akfamily/akshare`
- 我的判断：会员持仓排名仍是比粗供需分更接近“谁在承接风险”的外生源，但当前问题不是 alpha 规则，而是历史覆盖与接口稳定性。AKShare 文档显示 DCE 理论历史很深、GFEX 只能自 `2023-11-10` 起；GitHub issue 与本地 smoke 均复现 DCE `BadZipFile`，说明不能把“函数存在”当成“历史回测 selector 可用”。补齐前继续扫 TopN、rolling、level/flow 权重或阈值，是在 17% 覆盖样本上过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage029_member_rank_backfill_route_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增只读 smoke timeout `16s`、固定探针日 `20240603`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w closed lots `2018-01-15` 至 `2026-06-02`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w 输出，总滑点 `2,730,130`
- 样本过滤：无过滤，官方 `399` 笔 closed lots 全量参与覆盖审计
- 策略/归因口径：只读绑定 Stage028 会员持仓覆盖状态，叠加 Stage548/599/620 既有外部源探针，并做 5 个 AKShare endpoint smoke；smoke 仅证明当前点查状态，不等于历史回填。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot `36.0902%`
- 其他关键指标：
  - official closed lots：`399`
  - member ready：`69`，覆盖率 `17.2932%`
  - member missing：`330`，missing net PnL `22,263,004.00`
  - `2020-2022` missing：`212` 笔，missing net PnL `9,241,635.60`
  - missing exchanges：`4`
  - missing products：`19`
  - history-ready exchange：`0`
  - endpoint smoke：DCE `futures_dce_position_rank` 报 `BadZipFile`，DCE `get_dce_rank_table` 超时；CZCE/SHFE/GFEX 点查成功但不证明历史 selector ready

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage029_member_rank_backfill_route_audit/qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_report_stage029_member_rank_backfill_route_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage029_member_rank_backfill_route_audit/qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_summary_stage029_member_rank_backfill_route_audit_v1.csv`
- orders：无
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage029_member_rank_backfill_route_audit/qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_path_coverage_gap_chart_stage029_member_rank_backfill_route_audit_v1.png`
- quality：
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_gap_by_year_stage029_member_rank_backfill_route_audit_v1.csv`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_gap_by_product_stage029_member_rank_backfill_route_audit_v1.csv`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_gap_by_exchange_year_stage029_member_rank_backfill_route_audit_v1.csv`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_route_audit_stage029_member_rank_backfill_route_audit_v1.csv`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_endpoint_smoke_probe_stage029_member_rank_backfill_route_audit_v1.csv`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_gap_contribution_chart_stage029_member_rank_backfill_route_audit_v1.png`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_exchange_year_gap_heatmap_stage029_member_rank_backfill_route_audit_v1.png`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_product_gap_priority_chart_stage029_member_rank_backfill_route_audit_v1.png`
  - `qmt_roll_stage029_c9_minrisk_member_rank_backfill_route_audit_route_readiness_heatmap_stage029_member_rank_backfill_route_audit_v1.png`

## 结论

- 本阶段结论：`stage029_member_rank_backfill_not_history_ready_endpoint_repair_required`
- 是否进入下一步：不进入交易规则、true engine 或 A/B。会员持仓路线只能进入数据工程修复/forward watch。
- 下一步：若继续会员持仓，先修 DCE/CZCE/SHFE/GFEX 历史 selector 和点时化回填，尤其 DCE `BadZipFile/timeout` 与 Stage620 `history_selector_allowed=0`；若暂不做数据工程，策略研究应换到其他覆盖完整、入场前可见、真正外生的风险源。

## 过拟合反思

- 运行前判断：否。Stage029 不写交易规则，不根据亏损交易筛品种/年份/方向，只审计覆盖缺口和接口可行性。
- 运行后判断：否。本阶段把会员持仓路线降级为数据工程问题，明确禁止继续在 17% 覆盖样本上调参。
- 原因：视觉路径显示 2020-2022 主回撤底座缺会员数据，ready/missing 贡献曲线显示 missing 承担大量正净贡献；任何把 missing 当坏信号或把少数 ready bucket 当规则的做法都会过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage028 已证明覆盖太低，必须判断补数是否值得。
- 运行后判断：有价值，但价值从 alpha 研究切到数据工程/forward watch。会员持仓作为外生源仍可能有用，但当前资料不足以支撑 C9/15w 的历史规则验证。
- 原因：CZCE/SHFE/GFEX 点查成功说明路线不是完全死路；但 DCE 关键产品 `jm/lh` 仍有 parser 风险，且所有交易所 history selector 尚未 ready。

## 合入建议

- 是否更新本线 `LINE.md`：是，已追加 Stage029 摘要与下一步约束。
- 是否更新 `research/registry.md`：否；非正式候选、非重要突破、非跨线合入。
- 是否追加根目录 `memory.md/back_log.md`：否；这是本线内部数据源路线审计，不是正式候选或重要突破。
