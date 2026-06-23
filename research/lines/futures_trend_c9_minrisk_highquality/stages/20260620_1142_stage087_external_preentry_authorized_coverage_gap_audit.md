# Stage087 外生点时化授权覆盖缺口审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 11:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据工程闸门；不写真引擎、不新增交易规则、不触发 A/B、不连接 CTP、不调用订单 API
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SHFE 官方 Daily Data / Daily Warrant：https://www.shfe.com.cn/eng/reports/StatisticalData/DailyData/?query_params=dailystock
  - CZCE 官方持仓排名：https://www.czce.com.cn/cn/jysj/ccpm/H077003004index_1.htm
  - CZCE 官方仓单日报：https://www.czce.com.cn/cn/jysj/cdrb/H077003010index_1.htm
  - DCE 官方日成交持仓排名：https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/rcjccpm/index.html
  - DCE 官方仓单日报：https://www.dce.com.cn/dalianshangpin/xqsj/tjsj26/rtj/cdrb/index.html
  - GFEX 官方日成交持仓排名：https://www.gfex.com.cn/gfex/rcjccpm/hqsj_tjsj.shtml
  - GFEX 官方仓单日报：https://www.gfex.com.cn/gfex/cdrb/hqsj_tjsj.shtml
  - AKShare 期货数据文档：https://akshare.akfamily.xyz/data/futures/futures.html
- 我的判断：
  - 交易所官方确实存在会员持仓/持仓排名、仓单日报、日统计等日频公开数据入口；AKShare 也提供了部分交易所仓单等接口说明。
  - 但“网上有官方入口”不等于本地 cache 已经可交易化。本阶段要审的是本地 cache 是否同时满足点时化、全历史覆盖、产品覆盖、官方/授权 provenance、右尾保护和前序路线未关闭。
  - 结论是当前本地会员持仓、基差、仓单 cache 都不能作为规则源；最多作为数据工程线索，不能继续在现有 cache 上扫阈值。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage087_external_preentry_authorized_coverage_gap_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MAX_SIGNAL_AGE_DAYS=7`，固定点时化宽限窗口，只允许入场日前可见数据向后绑定
  - 三类固定 source：`member_rank`、`basis`、`warehouse`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w Stage010 路径 `2018-01-02` 至 `2026-06-15`
- 账户规模：`150,000`
- 成本口径：沿用官方 Stage010 C9/15w，滑点总额 `2,730,130`
- 样本过滤：官方 closed lots `399` 笔；不按年份、品种、方向、盈亏筛选
- 策略/归因口径：
  - 本阶段只做外生数据覆盖审计，不生成候选资金曲线
  - 对每笔官方 lot 用 `entry_date - 1 calendar day` 作为入场前查询日期
  - 会员持仓、基差、仓单若同产品最近数据在 `7` 日内且不晚于查询日期，则记为点时化 ready
  - 仍要求官方/授权 provenance、全历史覆盖、右尾缺口安全、前序路线未关闭全部通过才允许成为规则源

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`53.2560%`
- 其他关键指标：
  - `source_count=3`
  - `rule_candidate_allowed_source_count=0`
  - `any_external_ready_lot_pct=78.1955%`
  - `any_external_missing_positive_pnl=736,555`
  - `any_external_missing_big_winner_count=1`
  - `member_rank` ready lot `82/399=20.5514%`；缺口正收益 `37,783,075`；缺口 big winners `21`
  - `basis` ready lot `295/399=73.9348%`；缺口正收益 `3,579,845`；缺口 big winners `3`
  - `warehouse` ready lot `135/399=33.8346%`；缺口正收益 `33,839,935`；缺口 big winners `11`
  - 三类 source 均只通过 `local_cache_present / point_in_time_key / preentry_bindable`，在 `full_history_product_coverage / official_or_authorized_provenance_validated / prior_not_closed / right_tail_missing_safe / rule_candidate_allowed` 上失败

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_report_stage087_external_preentry_authorized_coverage_gap_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_summary_stage087_external_preentry_authorized_coverage_gap_audit_v1.csv`
- orders：无
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_lot_coverage_stage087_external_preentry_authorized_coverage_gap_audit_v1.csv`
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_source_scorecard_stage087_external_preentry_authorized_coverage_gap_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_product_year_coverage_stage087_external_preentry_authorized_coverage_gap_audit_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_official_path_external_coverage_chart_stage087_external_preentry_authorized_coverage_gap_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_product_year_coverage_heatmap_stage087_external_preentry_authorized_coverage_gap_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_missing_right_tail_conflict_chart_stage087_external_preentry_authorized_coverage_gap_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage087_external_preentry_authorized_coverage_gap_audit/qmt_roll_stage087_c9_minrisk_external_preentry_authorized_coverage_gap_audit_next_action_scorecard_stage087_external_preentry_authorized_coverage_gap_audit_v1.png`

## 结论

- 本阶段结论：`stage087_external_cache_not_authorized_fullcoverage_no_rule`
- 是否进入下一步：进入数据工程下一步，不进入策略规则或 A/B
- 下一步：
  - 若继续外生源路线，只能先取得或重建官方/授权 raw 历史数据，保留原始响应、查询参数、日期戳和 hash；会员持仓至少补齐 `2018-2022` 及 DCE/GFEX/CZCE/SHFE 口径，仓单/库存/基差要覆盖 C9 全产品与全历史。
  - 在完成 provenance 和覆盖前，不允许把当前 cache 的 ready/missing、会员 TopN、basis/warehouse 变化、产品或年份写成过滤、降仓、恢复风险或正式候选。
  - 若暂时拿不到授权外生数据，策略研究应回到 Stage045 `timestamp_ready=1` replay 子集，提出完全不同构、非旧 no-follow/min-risk/breakeven/reentry-candle 的第一性分钟候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段固定覆盖闸门，不使用最终盈亏去拟合规则，也没有扫窗口、阈值、产品、年份或方向；输出是拒绝当前数据源进入规则，而不是从缺口中提炼交易条件。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只限数据工程。
- 原因：内部分钟、Tq tick、Stage449/raw、账户层路线已多次关闭，真正有希望降低回撤且不砍右尾的方向仍是新的点时化外生信息；但现有本地 cache 不够，继续在它上面调规则没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage087 当前状态和边界。
- 是否更新 `research/registry.md`：否；本线仍是并行研究线，未形成正式候选或重要合入。
- 是否追加根目录 `memory.md/back_log.md`：否；不是重要突破、路线废弃、正式候选或跨线合并。
