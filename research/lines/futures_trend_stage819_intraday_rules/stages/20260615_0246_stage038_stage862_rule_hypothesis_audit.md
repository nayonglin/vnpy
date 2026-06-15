# Stage038 Stage862 完整分钟K规则假设审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 02:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读规则假设审计 + 全覆盖分钟K视觉复核
- 是否重要突破：否。它收窄了规则方向，但不是收益突破或正式候选。
- 是否触发A/B：否。没有新策略接入、没有真实引擎变更、没有候选推广。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub README 对 CTA、组合策略与回测组件的定位，继续支持研究/执行隔离：<https://github.com/vnpy/vnpy/blob/master/README_ENG.md>
  - backtesting.py API 文档强调 OHLCV、commission/spread 和 bar 级执行语义，提醒同一 bar 内 stop/target 顺序有粒度问题：<https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html>
  - 公开 ORB/日内止损示例只支持开盘区间、逐 bar 止损、收盘处理等形状，不支持复制参数。
- 我的判断：公开资料只能提供工程纪律，不能提供可复制的 `OR15`、`0.5R`、`60m` 或重试次数参数。Stage862 必须做假设审计和反证，不能因为某个 lot-level proxy 好看就直接进引擎。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage862_stage861_rule_hypothesis_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `model_tag=stage862_stage861_rule_hypothesis_audit_v1`
  - visual review 每页 `4` 笔，最多 `24` 笔
  - 审计固定形状：`P1/P2/P3/P4/P5` lot-level proxy，`S1/S2/S3/S4` 结构破坏规则复测，`H1-H6` 规则假设分类
  - 只读允许位：`new_rule_allowed=0`、`engine_allowed=0`、`ab_allowed=0`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage861 全覆盖 Stage825 closed lots，入场年份覆盖 `2018` 到 `2026`。
- 账户规模：不适用，本阶段不重跑组合权益曲线。
- 成本口径：不适用，本阶段是 lot-level proxy 与分钟K结构审计；真实成本/资金复用已由 Stage847/C9 引擎作为上下文。
- 样本过滤：Stage861 `341` 笔 entry-day closed lots 全量；Stage861 full minute bars `1,479,592` 根；Stage849 pressure key dates `19` 个作为提醒证据。
- 策略/归因口径：
  - 基准 lot PnL：Stage861 `realized_pnl` 合计 `28,171,880`
  - `P2`：`0.5R` 实时止损，只有重新收复原入场价后才允许一次重试；仍是只读 proxy，不是引擎。
  - `S1-S4`：复用 Stage842 的结构破坏定义，但在 Stage861 完整分钟K上重算。
  - Stage847/C9 真实引擎作为上下文：C9 相对 C4 权益 `+6,871,220`，但最大回撤恶化 `-2.4518pp`。

## 结果

- 期末权益：不适用。本阶段不跑组合权益曲线。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`stage862_stop_retry_budget_lock_watch_structural_filters_rejected_no_engine`
  - input Stage861 entry lots：`341`
  - input Stage861 full minute bars：`1,479,592`
  - Stage861 entry-day coverage rate：`100%`
  - base lot PnL：`28,171,880`
  - `P2_stop05_retry_on_entry_reclaim` proxy delta：`+6,558,265.1`
  - `P2` big winner delta：`-983,330`
  - `no_same_day_recovery`：`59` 笔，PnL `-13,030,405`
  - `no_stop05_hit`：`171` 笔，PnL `+39,238,295`
  - `S3_two_stop_side_closes_before_reclaim` full coverage delta：`-566,700`
  - `S3` big winner delta：`-5,276,980`
  - visual review pages：`5`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_report_stage862_stage861_rule_hypothesis_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_summary_stage862_stage861_rule_hypothesis_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_decision_stage862_stage861_rule_hypothesis_audit_v1.json`
- hypothesis summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_hypothesis_summary_stage862_stage861_rule_hypothesis_audit_v1.csv`
- proxy summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_proxy_summary_stage862_stage861_rule_hypothesis_audit_v1.csv`
- proxy yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_proxy_yearly_stage862_stage861_rule_hypothesis_audit_v1.csv`
- structure rule stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_structure_rule_stats_stage862_stage861_rule_hypothesis_audit_v1.csv`
- structure yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_structure_yearly_stage862_stage861_rule_hypothesis_audit_v1.csv`
- cohort stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_cohort_stats_stage862_stage861_rule_hypothesis_audit_v1.csv`
- visual manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_visual_review_manifest_stage862_stage861_rule_hypothesis_audit_v1.csv`
- visual PNG：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage862_stage861_rule_hypothesis_audit_visual_review_page001_stage862_stage861_rule_hypothesis_audit_v1.png` 到 `page005`
- orders：不适用
- daily：不适用
- quality：用 hypothesis/proxy/structure/visual manifest 完整性检查替代。

## 结论

- 本阶段结论：
  - `H1_stop05_retry_reclaim_budget_locked` 只保留为 building block：`0.5R` 实时止损 + 收复入场价后重试，是唯一仍有 lot-level 正证据且接近实时可执行的形状；但 Stage847/C9 已证明它不能作为 standalone engine，因为相对 C4 最大回撤恶化。
  - `H2_or15_entry_filter` 否决：虽然 proxy delta `+7,943,180`，但它与 Stage834 OR15 close/hold 语义反证冲突，且仍损伤赢家。
  - `H3_60m_1r_fast_confirmation` 否决：proxy delta `-6,501,835`，big winner delta `-16,285,700`，视觉页显示多个右尾并非快速确认后才启动。
  - `H4_structural_break_after_stop` 否决：Stage842 subset 上的结构破坏线索在 Stage861 完整覆盖下转负，`S3` full coverage delta `-566,700`，big winner delta `-5,276,980`。
  - `H5_no_same_day_recovery_after_stop` 只作诊断：`59` 笔合计 `-13,030,405`，但“当天没有收复”是收盘后才完全知道的信息，不能直接当实时规则。
  - `H6_do_not_delay_clean_winners` 是设计约束：`no_stop05_hit` 的 `171` 笔贡献 `+39,238,295`，未来任何规则都必须证明不误伤这类右尾。
- 是否进入下一步：是，但方向明显收窄。
- 下一步：
  - 不再做 OR、60m 确认、S1-S4 结构破坏、品种/年份/方向、小数 R 倍数或重试次数扫描。
  - 若继续，只允许设计一个冻结真实引擎：`H1 + 风险预算锁定 + 二次失败纪律`。核心不是改变 `0.5R` 或重试次数，而是防止 C9 在止损释放资金后放大同一路径和同方向风险。

## 过拟合反思

- 运行前判断：否。Stage862 使用 Stage861 全覆盖 `341` 笔和固定历史形状，不按年份、品种、方向或个别图谱筛选规则。
- 运行后判断：否。审计本身主要做反证和方向收窄，没有生成新可执行参数；但如果下一步为了修复 C9 回撤去扫 `0.4R/0.6R`、`OR10/OR20`、重试 `1/2/3` 次、单品种或单年份过滤，就会过拟合。
- 原因：本阶段证明很多直觉形状在全覆盖下不稳定，尤其 S3 从 subset 正证据变为 full coverage 负证据，这是反过拟合收益。

## 继续价值反思

- 运行前判断：有价值。Stage861 只是图谱完成，仍需要把数据证据和视觉证据转成可反证的规则假设。
- 运行后判断：仍有价值，但路线收窄。继续价值只在 `H1` 的真实引擎改造上：保留实时止损/收复重试的交易直觉，同时通过预算锁定和二次失败纪律解决 Stage847/C9 的资金路径风险。
- 原因：大多数入场确认和结构退出已经被明确反证；继续做这些分支只会变成参数救参。真正值得继续的是资金路径约束下的实时 stop/retry 机制。

## 校验

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage862_stage861_rule_hypothesis_audit.py`
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage862_stage861_rule_hypothesis_audit.py`
- 输出完整性检查：
  - summary `1` 行
  - hypothesis summary `6` 行
  - proxy summary `5` 行
  - structure rule stats `4` 行
  - visual review manifest `19` 行
  - visual review PNG `5` 张
  - decision：`stage862_stop_retry_budget_lock_watch_structural_filters_rejected_no_engine`
  - `allow_new_rule=false`、`allow_engine=false`、`allow_ab=false`
- 视觉抽查：
  - page001：右尾样本非空，显示多笔大赢家并非都在开盘后快速线性确认，支持不做快速确认过滤。
  - page002：左尾样本非空，显示入场后触发 `0.5R` 后未能收复并沿止损侧延展，支持 stop/retry skeleton，但不支持事后 EOD no-recovery 直接实盘化。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage038 最新状态和下一步。
- 是否更新 `research/registry.md`：否。本阶段不改变总索引的正式/候选关系。
- 是否追加根目录 `memory.md/back_log.md`：否。没有新正式候选、没有策略突破、没有跨线合并或路线废弃。
