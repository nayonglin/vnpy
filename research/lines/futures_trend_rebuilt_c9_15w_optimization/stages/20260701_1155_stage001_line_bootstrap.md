# Stage001 重建版 C9/15w 优化线立线

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 11:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究线立线
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu，`The Probability of Backtest Overfitting`：用于约束多候选、多参数 winner-picking 风险。
  - Hurst、Ooi、Pedersen，`A Century of Evidence on Trend-Following Investing`：用于提醒趋势跟随的长期价值来自跨市场、跨周期右尾，不应为局部平滑轻易砍趋势暴露。
- 我的判断：本阶段只是立线，不做策略实验；后续每条优化路线必须先做方向相关调研，再决定采纳、否决或融合，不能直接从回测曲线倒推规则。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 新增研究线：`research/lines/futures_trend_rebuilt_c9_15w_optimization/LINE.md`

## 基准绑定

- 当前基准：功能性重建后的当前线上 C9/15w 版本 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- 基准阶段：Stage167。
- 基准记录：`research/lines/futures_trend_stage819_intraday_rules/stages/20260701_0217_stage167_c9_live_multiperiod_ai_audit.md`。
- AI 池 sha256：`8f54218d5c1922ebd4e0a2a16ef6d80c4f4392d1aa6c8cddd3f6127ffca574e3`。
- AI 审计：`PASS 858`、`PRE_AI_HISTORY 60`、`FAIL 0`。
- 基准结果：正收益 `17/17`；期末权益最低/中位/最高 `152,851.60 / 455,463.70 / 14,900,482.00`；总收益最低/中位/最高 `1.9011% / 203.6425% / 9,833.6547%`；最差最大回撤 `-56.2069%`；回撤中位 `-47.2779%`；Sharpe 最低/中位/最高 `0.2860 / 1.1937 / 1.4786`；peak broker10 margin/equity `96.6295%`。

## 结果

- 期末权益：无新增回测。
- 总收益：无新增回测。
- 最大回撤：无新增回测。
- Sharpe：无新增回测。
- 总滑点：无新增回测。
- 总交易次数：无新增回测。
- 胜率：无新增回测。
- 其他关键指标：已建立独立研究线和基准边界。

## 输出文件

- LINE：`research/lines/futures_trend_rebuilt_c9_15w_optimization/LINE.md`
- stage：`research/lines/futures_trend_rebuilt_c9_15w_optimization/stages/20260701_1155_stage001_line_bootstrap.md`

## 结论

- 本阶段结论：已为“当前重建版 C9/15w”建立独立优化线，后续优化与历史 C9 日内规则线、旧 C9 minrisk/highquality 线隔离。
- 是否进入下一步：是。
- 下一步：先做 Stage002 只读归因，聚焦 DD50 起点、最大回撤路径和 broker10 高水位，不直接写交易规则。

## 过拟合反思

- 运行前判断：否。本阶段不做回测、不做参数选择，只建立研究边界。
- 运行后判断：否。没有根据结果挑规则或调参数。
- 原因：基准固定为 Stage167，后续候选必须预声明并多周期验证。

## 继续价值反思

- 运行前判断：是。用户准备对当前重建版做优化，必须先隔离研究线，避免污染正式执行链路和旧产物对照。
- 运行后判断：是。独立线已经明确基准、禁止事项和下一步归因方向。
- 原因：当前重建版 AI 漏用已排除，优化价值集中在回撤尾部和保证金压力治理。

## 合入建议

- 是否更新本线 `LINE.md`：已创建。
- 是否更新 `research/registry.md`：建议补登记本线，便于后续 agent 从 registry 找到 line_id。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段只是立线，不是重要突破或正式候选变更。
