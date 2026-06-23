# Stage083 账户层波动闸门代理审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 10:51 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读账户层代理审计；不写真引擎、不新增交易规则、不触发 A/B、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否；这是封止型边界审计。
- 是否触发A/B：否。C 代理没有通过回撤和 broker10，`candidate_ready_count=0`。

## 外部调研与判断

- 参考资料：
  - KTH/DiVA `Position sizing methods for a trend following CTA`：趋势跟随仓位方法中 target volatility 是常见风险治理工具，但仍需验证是否伤害右尾。
  - Alpha Architect `Conditional Volatility Targeting`：条件波动率目标的基本思想是在高波动状态下降低风险暴露，低波动状态不应事后过度拟合。
  - Research Affiliates `Harnessing Volatility Targeting in Multi-Asset Portfolios`：波动率目标是管理组合风险的工具，但不是 alpha，也不能保证改善所有策略路径。
- 我的判断：Stage082 已关闭既有标签隔离 maxDD 的捷径。账户层 no-leverage volatility gate 是低自由度、普世、非盈亏标签的合理边界测试，但它不是最终分钟进出场方案；若代理都不能改善回撤，就不能进入真引擎或 A/B。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage083_account_volatility_gate_proxy_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `SHORT_VOL_WINDOW=63`
  - `SHORT_VOL_MIN_PERIODS=42`
  - `LONG_VOL_WINDOW=252`
  - `LONG_VOL_MIN_PERIODS=126`
  - 风险权重公式：`min(1, trailing_252d_annualized_vol / trailing_63d_annualized_vol)`，所有波动率均 shift 一天，只用前一交易日之前的数据。
- 修改参数：无正式策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-02 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：沿用官方 C9/15w Stage010 official daily curve；代理按风险权重线性缩放 `net_pnl/slippage/broker10 margin`。
- 样本过滤：无产品、方向、年份、月份、亏损标签过滤；volatility gate 未 ready 时权重为 `1`。
- 策略/归因口径：
  - A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - C：`C_vol_gate_q63_y252_no_leverage`，只降不升、无杠杆、无 floor、无单品种条件。

## 结果

- 期末权益：
  - A：`39,176,437.60`
  - C：`37,908,242.60`
- 总收益：
  - A：`26017.6251%`
  - C：`25172.1617%`
- 收益保留：`96.7504%`
- 最大回撤：
  - A：`-45.0827%`
  - C：`-45.6387%`
- 回撤改善：`-0.5560pp`，实际恶化。
- Sharpe：
  - A：`1.6339`
  - C：`1.6359`
- 总滑点：
  - A：`2,730,130`
  - C 缩放滑点：`2,603,166.65`
- 总交易次数：`787`，代理不改变逐笔交易数。
- 胜率：沿用官方参考 `53.2560%`；代理不重算逐笔胜率。
- 其他关键指标：
  - 决策：`stage083_account_vol_gate_proxy_not_promoted`
  - C 平均风险权重：`0.9152`
  - C 最小风险权重：`0.6428`
  - C 权重低于 `80%` 天数：`403`
  - C 权重低于 `50%` 天数：`0`
  - A broker10 峰值：`111.7365%`，over100 天数 `5`
  - C broker10 峰值：`114.4268%`，over100 天数 `8`
  - C `candidate_ready=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_report_stage083_account_volatility_gate_proxy_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_summary_stage083_account_volatility_gate_proxy_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_curves_stage083_account_volatility_gate_proxy_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_metrics_stage083_account_volatility_gate_proxy_audit_v1.csv`
- visuals：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_path_drawdown_broker_chart_stage083_account_volatility_gate_proxy_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_volatility_weight_chart_stage083_account_volatility_gate_proxy_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage083_account_volatility_gate_proxy_audit/qmt_roll_stage083_c9_minrisk_account_volatility_gate_proxy_audit_year_return_heatmap_stage083_account_volatility_gate_proxy_audit_v1.png`

## 视觉分析

- 资金/回撤/broker10 图：C 线长期贴着 A 但略低；2022 主回撤比 A 更深，broker10 尖峰也更高。说明单纯风险缩放没有改变回撤结构，反而因权益分母变薄恶化保证金比率。
- 波动率/权重图：2022 主回撤前权重多数仍接近 `1`，真正高波动触发发生在主要损伤之后；后续降权阶段又错过部分恢复和右尾。该规则是滞后风控，不是高质量信号最小风险参与。
- 年度热图：C 在 `2022` 年度收益高于 A，但 `2020/2021/2025` 右尾被削弱，长期权益底座变薄；最终最大回撤和 broker10 均未过关。

## 结论

- 本阶段结论：不进入真引擎。`63/252` no-leverage volatility gate 保留了 `96.7504%` 收益，但最大回撤恶化 `0.5560pp`，broker10 峰值从 `111.7365%` 恶化到 `114.4268%`，over100 天数从 `5` 增至 `8`。
- 是否进入下一步：不沿该 volatility gate 形状继续。
- 下一步：不得扫 `21/63/126/252`、min periods、vol ratio、目标波动、权重 floor 或 2022 特殊触发来救该形状。若继续账户层，只能换不依赖滞后波动的固定资本结构；若继续分钟目标，必须回到 Stage045 timestamp-ready replay 子集，提出不同于 no-follow/hard-exit/min-risk/breakeven/reentry-candle 的第一性候选，且 fallback/no-proxy 保持官方路径。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但仅限当前固定 spec。
- 原因：本阶段只测一个预声明 quarter-vs-year no-leverage archetype，没有按产品、方向、年份、月份、弱窗口或最终盈亏标签分组。若继续改窗口、加 floor、针对 2022 做条件，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该 volatility gate 形状没有继续价值；总目标仍有价值。
- 原因：Stage083 回答了一个重要边界问题：官方 C9 的深回撤不是简单“日收益波动升高后缩风险”能解决的，滞后波动闸门会在损伤之后降风险并削弱后续右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage083 结论和停止边界。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选、路线废弃合入或跨线里程碑。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段无正式候选、不触发 A/B；只记录在线内 stage 和 LINE。
