# Stage044 C2 Directional Stop Semantics Audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 02:14 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：replay 语义审计 / 不生成交易规则
- 是否重要突破：否，属于分钟 replay 基础设施校准，不是收益突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order 文档：`https://www.backtrader.com/docu/order/`
  - Backtrader order creation/execution 文档：`https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - SHFE trading hours：`https://www.shfe.com.cn/eng/reports/CalendarHolidays/TradingHours/`
- 我的判断：
  - 成熟回测系统都把成交、bar 时间戳、stop/confirm 触发和同 bar 优先级当成执行语义，不应把语义缺口当作 alpha。
  - 本仓库官方 Stage827 C2 代码已经给出权威语义：C2 stop 不是直接使用 `planned_stop_price`，而是用 `entry_price - direction_sign * 1R * risk_price` 重建；confirm 是 `entry_price + direction_sign * 1R * risk_price`。
  - Stage043 剩余 `4` 笔 residual 的本质是 replay 误把 `planned_stop_price` 当 C2 stop，属于账本字段角色混淆，不是首根 bar 可交易信号。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage044_c2_directional_stop_semantics_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增 replay 语义审计变体：
  - `stage043_planned_stop_as_c2_stop_start0_stop_first`
  - `stage827_directional_c2_stop_start0_stop_first`
  - `stage827_directional_c2_stop_start1_stop_first`
  - `stage827_directional_c2_stop_start0_confirm_first`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage043 / Stage042 / 官方 C9/15w 输出
- 账户规模：`150000`
- 成本口径：沿用官方曲线，`total_slippage=2,730,130`
- 样本过滤：Stage043 timestamp-ready initial orders，共 `219` 笔
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 审计口径：成交价与 official-open scan 沿用 Stage043；只替换 C2 stop 价格语义为 Stage827 官方公式。
  - 不改变开仓、平仓、手数、资金路径；same-exit 曲线只用于证明语义审计没有改变策略收益。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - Stage043 planned-stop baseline event match：`215/219 = 98.1735%`
  - Stage827 directional C2 formula event match：`219/219 = 100.0000%`
  - Stage043 residual orders：`4`
  - Stage043 residual resolved by directional C2：`4/4 = 100.0000%`
  - official semantics variant：`stage827_directional_c2_stop_start0_stop_first`
  - planned stop side 分布：
    - `planned_below_or_equal_entry_for_long`：`176` 笔，residual `0`
    - `planned_above_or_equal_entry_for_short`：`34` 笔，residual `0`
    - `planned_above_entry_for_long`：`6` 笔，residual `3`
    - `planned_below_entry_for_short`：`3` 笔，residual `1`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_report_stage044_c2_directional_stop_semantics_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_summary_stage044_c2_directional_stop_semantics_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_variant_replay_ledger_stage044_c2_directional_stop_semantics_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_semantic_path_chart_stage044_c2_directional_stop_semantics_audit_v1.png`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_variant_match_chart_stage044_c2_directional_stop_semantics_audit_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage044_c2_directional_stop_semantics_audit/qmt_roll_stage044_c9_minrisk_c2_directional_stop_semantics_audit_residual_atlas_stage044_c2_directional_stop_semantics_audit_v1.png`

## 结论

- 本阶段结论：
  - Stage043 剩余 `4` 笔 `no_intraday_event -> c2_stop` 已被 Stage827 官方 C2 directional stop 语义完全解释。
  - 真实 C2 stop 公式为 `entry_price - direction_sign * 1R * risk_price`，不是直接使用 `planned_stop_price`；这解释了 `planned_stop_price` 在 long 中高于 entry、short 中低于 entry 的少数样本为什么会被 Stage043 误判为首根 C2 stop。
  - 使用官方语义后，timestamp-ready 子集 event family match 达到 `100%`，资金曲线和回撤曲线与官方完全重合。
- 是否进入下一步：进入下一阶段 replay 精度审计；不进入候选策略、不触发 A/B。
- 下一步：
  - 只审计事件时间精度和字段同步：C9 first stop/reentry/retry failed、C2 hit/confirm 的具体 timestamp 与官方 event rows 的一致性。
  - 在时间精度和价格字段语义通过前，继续暂停新增分钟进出场候选。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有调参、没有筛品种/方向/年份、没有按收益结果选择样本。
  - 审计依据来自官方 Stage827 代码的执行语义，不是从 `4` 笔 residual 的盈亏表现反推规则。
  - 视觉图只是验证资金路径未改变、residual 被字段语义解释，不构成交易信号。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - event family match 从 `98.1735%` 推进到 `100%`，说明 replay 基础设施已经能复现官方 C9/C2 事件 family。
  - 这为后续分钟级规则提供了更可靠的账本地基；如果没有这个地基，任何“首根触线/分钟形态”都可能只是字段语义误差。
  - 继续价值在于做事件时间精度审计，而不是立刻做新交易规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage044 结论与下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内 replay 语义修复，不是重要合入摘要。
