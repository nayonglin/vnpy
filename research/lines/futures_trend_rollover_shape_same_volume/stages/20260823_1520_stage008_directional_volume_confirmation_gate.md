# Stage008 30日方向与成交量扩张联合加风险多周期闸门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：日间研究模式
- 记录时间：2026-08-23 15:20 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：用户确认后的结果前不可变研究闸门
- 是否重要突破：否，结果未知
- 是否触发A/B：是，固定 A/C/D/F 四臂比较

## 外部调研与判断

- 参考资料：
  - CME《What is Volume?》：成交量是合约级交易活跃度，换月期间交易量会从到期合约迁移到后续合约；因此量能可以作为参与度信息，但换月附近也可能出现机械性迁移。<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>
  - Lee 与 Swaminathan《Price Momentum and Trading Volume》：历史成交量与价格动量存在经验关系，但该结论不能直接证明本商品期货策略获得独立 alpha。<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=92589>
- 我的判断：本规则比单纯 30 日方向加杠杆更有研究价值，因为成交量扩张可能降低 D 版约 98% 的近乎普遍触发；但它仍复用价格趋势，并有换月量迁移混淆，属于中等过拟合风险的单次证伪，不允许结果后扫窗口、倍率或阈值。

## 本次变更

- 新增脚本：`tools/stage008_directional_volume_confirmed_multicycle_acdf.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 新增测试：`tests/test_rollover_shape_stage008_runner.py`，并扩展 `tests/test_rollover_shape_same_volume.py`
- 删除脚本：无
- 新增参数：
  - `directional_30d_risk_boost_require_volume_expansion=True`（仅 F）
  - `directional_30d_volume_recent_days=10`
  - `directional_30d_volume_prior_days=10`
- 修改参数：无；30 日、10/10 日与 `1.2` 倍均在结果前固定
- 删除参数：无

## 固定策略合同

- A：当前正式 C9/15万原样基线，不启用换月续仓，不启用方向加风险。
- C：A + 换月连续历史形态续仓，不启用方向加风险。
- D：C + 30 日价格方向同向时所有开仓上下文风险金额乘 `1.2`，用于复验 Stage007 身份。
- F：C + 同时满足以下两个条件时所有开仓上下文风险金额乘 `1.2`：
  1. 信号日收盘价相对 30 个交易日前收盘价的方向与开仓方向一致；
  2. `T-9..T`（包含信号日）的 10 个交易日成交量总和严格大于 `T-19..T-10` 的前 10 个交易日成交量总和。
- F 其余情形风险倍率为 `1.0`；成交量不足、非有限、负数或总和无效时 fail-closed 为“不加风险”，不取消原始交易。
- F 不启用反向 `0.8`；不开参数扫描；覆盖 flat、reverse、rollover reopen、regular add、donchian add、post-quality add。
- 换月使用当时可见的连续主力来源历史；成交量不做价格复权，并单独检查换月重开触发集中度。

## 回测参数

- 数据区间：`2018-01-01` 至 `2026-05-29`
- 账户规模：正式 C9/15万口径
- 成本口径：与 Stage007/正式基线一致
- 固定窗口：全周期 1 个；1/2/3 年独立窗口均包含每个可用的 1 月与 6 月起点；末端 near-complete 只展示、不进入晋级聚合
- 独立真引擎运行：`43 × 4 = 172`
- 比较：`A_vs_C`、`A_vs_D`、`C_vs_D`、`A_vs_F`、`C_vs_F`、`D_vs_F`
- 聚合：每个比较分别统计 1/2/3 年 × combined/January/June，共 `54` 行
- 身份闸门：A/C/D 的同窗关键指标必须与 Stage007 一致；不一致则整代结果作废重跑，不解释为策略差异

## 预声明决策闸门

- F 规则合同必须逐行成立：只有“方向同向且成交量扩张”才为 `1.2`，其他为 `1.0`；风险金额精确匹配。
- F 必须既有实际加风险诊断，也必须比 D 有选择性：`0 < boost_applied_count < price_aligned_count`。
- 晋级比较只认 F 相对 A 与 C；相对失败的 D 改善不能单独构成晋级。
- 全周期 A_vs_F 与 C_vs_F 均须同时通过：收益不低于左臂、回撤恶化不超过 `1pp`、Sharpe 不劣于 `0.01`、滑点不超过 `105%`、账户生存、broker100 严重度不恶化。
- 1/2/3 年各 combined/January/June 的 A_vs_F 与 C_vs_F 均须同时通过：收益胜率至少 `50%`、收益差中位数非负、回撤 `2pp` 非劣率至少 `80%`、DD50 失败数不增加、Sharpe `0.05` 非劣率至少 `80%`、聚合滑点不超过 `105%`、全部生存、broker100 失败数不增加。
- 任一闸门失败，结论为 `volume_confirmed_boost_not_promotable`；不因局部漂亮窗口改门槛。

## 固定输出

- CSV：窗口 summary、六组 comparison、周期 aggregate、全部曲线、全周期 F entry-risk、trades、trade-events、量能合同汇总
- JSON：Stage008 decision 与逐项门槛
- 图片：全周期、1年、2年、3年、周期聚合，共 5 张固定格式图片
- 安全边界：不修改正式配置、正式物料、master、production、CTP、定时任务或订单接口

## 运行前反思

- 是否过拟合：是，中等风险。原因是该规则是在 D 失败后追加的确认条件；用单一固定规格、完整多周期与结果前冻结限制自由度，但不能消除后验灵感风险。
- 是否有价值继续：是。成交量扩张可能把 D 的近普遍加杠杆变成更稀疏的参与度确认，值得一次固定证伪；若仍无法相对 A/C 改善收益风险成本，则停止该形状，不扫 5/10/20 日、倍率或大于等于阈值。

## 运行后待填写

- 期末权益：待回测
- 总收益：待回测
- 最大回撤：待回测
- Sharpe：待回测
- 总滑点：待回测
- 总交易次数：待回测
- 胜率：待回测
- 过拟合反思：待回测
- 继续价值反思：待回测
