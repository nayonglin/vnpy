# Stage006 全开仓30日方向一致风险1.2倍预声明门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 冻结时间：`2026-08-22 20:20 CST`
- 阶段性质：在 Stage005 未晋级的换月连续历史候选上，增加一个低自由度、对称的方向动量风险增强假设；本文件在看到 Stage006 回测结果前提交冻结
- 是否重要突破：否；当前只是待证伪假设

## 外部调研与判断

- Moskowitz、Ooi、Pedersen 的期货时间序列动量研究表明，资产自身过去收益方向对未来收益存在跨资产的正向可预测性：`https://www.aqr.com/Insights/Research/Journal-Article/Time-Series-Momentum`。
- AQR 的长期趋势跟踪研究把过去收益为正做多、为负做空作为基本趋势形态，并检验跨市场、跨周期稳定性：`https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing`。
- 判断：30交易日净方向用于已有开仓信号的风险增强有结构理由，但文献不能证明本策略的固定30日和1.2倍有效；必须由独立 A/C/D 真引擎和后续多周期反证。

## 冻结规则

- A：当前正式 C9/15万原样。
- C：A + `backwards_ratio_continuous + shrink_to_allowed` 换月形态续仓。
- D：C + 所有风险预算开仓上下文的30日方向一致增强。
- 30日定义：信号日已完成收盘价除以向前第30个交易日收盘价再减1，需要连续 `31` 个有效收盘价。
- 多头仅当30日收益 `>0`、空头仅当30日收益 `<0` 时，把现有风险金额乘 `1.2`；等于0、历史不足、非有限值或非法配置时倍率保持 `1.0`，不阻断原交易。
- 适用上下文：`flat_entry`、`reverse_entry`、`rollover_reopen`、`regular_add`、`donchian_add`、`post_quality_add` 以及通过共用风险预算入口产生的其他开仓上下文。
- 1.2倍发生在已有风险金额和组合过热缩放之后、风险手数取整之前；保证金、单笔资金上限、组合容量、风险簇、相关性及 broker 风控继续在后续限制最终手数。
- 默认参数关闭，不修改正式配置、正式物料、master、production、CTP 或订单链。

## 最小全周期门

- 数据区间固定 `2018-01-01` 至 `2026-05-29`，资金 `150,000`，费率、滑点、AI、broker约束与 Stage005 相同。
- D 必须存在真实 `directional_30d_risk_boost_aligned=1` 事件，且所有记录满足：对齐行 `target_risk_amount=base×1.2`，未对齐行 `target_risk_amount=base×1.0`。
- D 总收益不得低于 C。
- D 相对 C 最大回撤恶化不得超过 `2pp`。
- D Sharpe 不得低于 C `0.02`。
- D 总滑点不得超过 C 的 `110%`。
- D 必须账户生存，broker100 不得比 C 恶化。
- 全部门通过才运行 Stage007 固定多周期报告；任一失败即停止本规则，不围绕30日或1.2倍扫参救援。

## 运行前反思

- 过拟合判断：否。方向规则对称、参数只有一个整数窗口和一个用户冻结倍率，且结果前预声明；但若失败后扫描20/40/60日或1.1/1.3倍则会迅速过拟合。
- 继续价值判断：有。它直接检验“趋势方向一致时是否值得承担略高风险”的第一性假设，最小全周期门能低成本决定是否值得进入多周期。
