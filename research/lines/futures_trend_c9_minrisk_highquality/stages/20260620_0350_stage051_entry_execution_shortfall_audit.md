# Stage051 entry execution shortfall audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 03:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage045 timestamp-ready replay 底座上的入场执行短缺只读审计；不是真实组合引擎，不是 A/B 候选，不是实盘规则。
- 是否重要突破：否。它反证一个新执行价质量路线，不产生候选。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Perold implementation shortfall 思想：交易决策价和实际成交价之间的差异是真实执行成本和机会成本来源。
  - Almgren-Chriss `Optimal Execution of Portfolio Transactions`：执行问题应在交易成本和价格风险之间权衡，而不是按最终盈亏反推过滤。
  - Rob Carver / systematic execution：执行规则应简单、可复现，常见思路包括被动限价和等待市场回来，但必须先验证执行信号本身是否稳定。
- 我的判断：`official_open_price` 相对 `planned_entry_price` 已经不利移动超过半个 planned stop distance，是一个普世且点时可见的执行价质量问题，值得做一次冻结审计；但它必须证明不是趋势右尾的组成部分，才可能进入下一步 true engine。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage051_entry_execution_shortfall_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `TARGET_GAP_R = 0.5`
  - `TARGET_COHORT = adverse_entry_gap_ge_0_5r`
  - `entry_gap_r = direction_sign * (official_open_price - planned_entry_price) / planned_stop_distance`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage045 timestamp-ready 子集覆盖的官方 C9/15w 初始开仓，主要为 `2020-2026`。
- 账户规模：官方正式 `150,000`。
- 成本口径：沿用官方 C9/15w；官方总滑点 `2,730,130`。
- 样本过滤：只审计 Stage045 已同步的 `timestamp_ready=1` 且 Stage861 official-date replay ready 的 `219` 笔；`fallback/no-proxy` 初始订单不硬补，不用最终盈亏补 timestamp。
- 策略/归因口径：只读审计。乐观上限为 closed-lot cashflow 级别跳过 `adverse_entry_gap_ge_0_5r` cohort，不代表真实可执行引擎。

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方 closed-lot 胜率：`36.0902%`
- 其他关键指标：
  - timestamp-ready orders：`219`
  - target cohort：`adverse_entry_gap_ge_0_5r`
  - target orders：`36`
  - target products：`14`
  - target years：`7`
  - target net PnL：`+5,017,339.60`
  - target positive PnL：`+8,030,065.00`
  - target negative PnL：`-3,012,725.40`
  - target median entry gap：`1.2396R`
  - target max entry gap：`5.8333R`
  - 乐观跳过 target 后期末权益：`34,159,098.00`
  - 乐观跳过 target 后总收益：`22672.7320%`
  - 乐观跳过 target 后最大回撤：`-49.1332%`，日期 `2023-03-08`
  - 乐观跳过 target 后 Sharpe：`1.4981`
  - 收益保留：`87.1437%`
  - 最大回撤改善：`-4.0505pp`，即回撤恶化
  - 决策：`stage051_entry_shortfall_target_is_right_tail_no_engine`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_report_stage051_entry_execution_shortfall_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_summary_stage051_entry_execution_shortfall_audit_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_decision_stage051_entry_execution_shortfall_audit_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_features_stage051_entry_execution_shortfall_audit_v1.csv`
- target orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_target_orders_stage051_entry_execution_shortfall_audit_v1.csv`
- upper-bound curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage051_entry_execution_shortfall_audit/qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_upper_bound_curve_stage051_entry_execution_shortfall_audit_v1.csv`
- quality / visuals：
  - `qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_upper_bound_path_chart_stage051_entry_execution_shortfall_audit_v1.png`
  - `qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_bucket_contribution_chart_stage051_entry_execution_shortfall_audit_v1.png`
  - `qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_gap_scatter_stage051_entry_execution_shortfall_audit_v1.png`
  - `qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_bucket_year_heatmap_stage051_entry_execution_shortfall_audit_v1.png`
  - `qmt_roll_stage051_c9_minrisk_entry_execution_shortfall_audit_minute_atlas_stage051_entry_execution_shortfall_audit_v1.png`

## 视觉观察

- upper-bound path chart 显示红线长期低于官方蓝线，尤其 `2025` 后跳过 target 会砍掉明显右尾；回撤从官方 `-45.0827%` 恶化到 `-49.1332%`，不是降回撤路线。
- bucket contribution chart 显示 `adverse_entry_gap_ge_0_5r` 红线累计为正，且 `adverse_entry_gap_0_25_0_5r` 橙线也显著正贡献，说明“成交比计划价贵”在趋势跟随里常常是动量延续的入场状态，而非坏信号。
- minute atlas 显示多笔 target 样本在官方 open 后继续沿趋势方向走，例如 `si2509.GFEX`、`AP505.CZCE`、`jm2405.DCE`、`fu2209.SHFE`；也存在 `cu2307.SHFE`、`OI205.CZCE` 等亏损反例，但正负混杂，不能抽象成普世过滤。

## 结论

- 本阶段结论：入场执行短缺是 TCA 风险源，但 `adverse_entry_gap >= 0.5R` 在 C9/15w 上不是坏信号集合；它覆盖 `36` 笔、`14` 产品、`7` 年，净盈利 `+501.7万`，乐观跳过反而恶化最大回撤。
- 是否进入下一步：不进入 true engine，不触发 A/B，不改正式配置。
- 下一步：关闭“直接不追 adverse entry gap >= 0.5R”交易化路线，不扫 `0.25/0.5/1.0R`、gap 方向、产品、年份或方向。该信息只保留为执行 TCA / 成交质量监控，除非未来有盘口/流动性点时数据证明另一个独立机制。

## 过拟合反思

- 运行前判断：否。本阶段使用外部执行短缺原则和固定 `0.5R` 风险预算口径，不按历史亏损窗口选择。
- 运行后判断：审计本身不是过拟合；若继续切 gap 阈值、只排除 `cu/OI/lh` 等亏损产品、只看 `2023` 或改成方向筛选，就会过拟合。
- 原因：target cohort 净正且跨年跨产品，失败不是阈值差一点，而是执行价不利移动与趋势延续天然相关。

## 继续价值反思

- 运行前判断：有价值。执行短缺是普世的执行问题，适合在 Stage045 replay 底座上做一次冻结审计。
- 运行后判断：这条直接交易化路线没有继续价值；本研究总目标仍有价值。
- 原因：Stage051 明确告诉我们“开得贵”并不等于低质量信号。继续推进应回到 Stage050 的另一条路：点时化外生数据覆盖，或需要有全新第一性信息源，不能在 gap 桶上救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage051 反证结论和后续边界。
- 是否更新 `research/registry.md`：否，非正式候选、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，非重要突破、非正式候选、非路线废弃总账事件。
