# Stage181 cutoff-filtered minute feature materializer

- 时间：2026-06-21 04:46 CST
- 研究线：`futures_trend_c9_minrisk_highquality`
- 工作模式：`day`
- 决策：`stage181_cutoff_filtered_minute_feature_audit_ready_no_formal_feature_table_no_rule`
- 是否重要突破版本：否。它是 Stage180 安全源之后的点时化特征审计地基，不是策略收益突破，也不允许接入正式规则。

## 外部调研与判断

- pandas 官方 `rolling` / `std` / `pct_change` 文档确认滚动窗口和标准差应显式约定窗口边界与 `ddof`，本阶段用闭合 1m bar、`std(ddof=1)`，避免实现含糊。
- vn.py `BarGenerator` 源码体现 bar 聚合应以已完成 OHLCV bar 为基础；本阶段只读取 Stage180 已按 `bar_end_ts <= decision_ts` 裁剪后的源。
- IBM 对 data leakage 的说明强调训练/特征生成不能使用目标时点之后的信息；本阶段不读取 Stage178 direct normalized 文件，只读 Stage180 filtered source。
- 判断结论：Stage181 不复制外部策略，只采用通用时序特征实现原则。当前最关键不是加规则，而是把入场前 30m/60m 特征的时点边界和 lineage 做实。

## 本次改动

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage181_cutoff_filtered_minute_feature_materializer.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage181_cutoff_filtered_minute_feature_materializer/`
- 新增输出：
  - summary：`qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer_summary_stage181_cutoff_filtered_minute_feature_materializer_v1.csv`
  - feature value audit：`qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer_feature_value_audit_stage181_cutoff_filtered_minute_feature_materializer_v1.csv`
  - feature readiness audit：`qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer_feature_readiness_audit_stage181_cutoff_filtered_minute_feature_materializer_v1.csv`
  - formula audit：`qmt_roll_stage181_c9_minrisk_cutoff_filtered_minute_feature_materializer_formula_implementation_audit_stage181_cutoff_filtered_minute_feature_materializer_v1.csv`
  - lineage audit、gate status、report、decision JSON
  - 5 张图：官方资金路径、feature readiness matrix、feature value heatmap、lineage cutoff matrix、gate status matrix

## 参数变化

- 新增参数：无策略参数。
- 新增实现约定：
  - 只允许读取 Stage180 cutoff-filtered source。
  - 特征 cutoff：`bar_end_ts <= decision_ts`。
  - `realized_volatility_30m` 使用 `std(log(close).diff(), ddof=1)`。
  - `turnover_vwap_gap_30m` 使用成交额推导的合约乘数代理，避免把 `turnover / volume` 误当价格。
  - `volume_participation_30m` 暂用最近 30 根闭合 bar 的非零成交分钟占比，同时保留 `volume_sum_30m` 诊断字段。
- 修改参数：无。
- 删除参数：无。

## 回测与审计结果

- 本阶段不运行 true engine，不新增交易规则，不触发 A/B，不连接 CTP，不调用 order API。
- Stage180 安全源：`4/4` ready。
- Feature contract：`10` 个特征。
- Feature audit rows：`4`。
- Feature readiness rows：`40`。
- Feature ready cells：`40/40`，ready ratio `1.0000`。
- Cutoff guard：`4/4`。
- Lineage pass：`4/4`。
- Formal feature table rows：`0`。
- Strategy feature usable：`0`。
- Strategy rule created：`0`。
- True engine run：`0`。
- A/B triggered：`0`。

## 官方路径指标

- 期末权益：`39,176,437.60`
- 总收益：`26,017.63%`
- 最大回撤：`-45.08%`
- Sharpe：`1.633`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.09%`
- Broker10 最大保证金/权益：`111.74%`

## 视觉检查

- 官方资金路径图显示本阶段未改变收益/回撤路径，只在底部记录 audit rows、ready cells、formal rows 和 rules。
- Feature readiness matrix 全绿，4 个 Stage180 安全源的 10 个 Stage156 特征均可在 cutoff 前计算。
- Feature value heatmap 非空且有横截面差异；`volume_participation_30m` 在 4 个样本上全为 `1.0`，说明这一字段在当前高流动样本中区分度弱，后续需要在更大 Stage177 批次上继续确认，不能提前拿它做规则。
- Lineage cutoff matrix 与 gate matrix 全绿；formal feature table 与 strategy rule 均保持阻断。

## 反思

- 是否过拟合：否。本阶段没有使用最终 PnL 标签、没有调阈值、没有品种/年份补丁，也没有根据结果筛选样本；只做点时化数据和通用特征的审计物化。
- 是否还有价值继续做：是。4 个高优先级、跨交易所样本已证明 Stage180 安全源能产出完整入场前特征；下一步价值在于把 Stage177 补数继续扩到更多 entry decision，确认这些特征在尾部、亏损、低分辨率和普通样本中都稳定，而不是被 4 个样本偶然通过。

## 后续规划

- Stage182 优先继续按 Stage177 manifest 分批交付更多 predecision lookback 数据，并复跑 Stage179/180/181。
- 同步定义“audit package -> formal feature table”的闸门，但在样本覆盖扩大前不允许接策略规则。
- 对 `volume_participation_30m` 做保守观察：若大样本仍长期等于 1，应降级为数据质量诊断，不作为有效 alpha/risk 特征。
