# Stage001 主力换月形态确认原手数重开 A/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-20 23:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：基于正式 C9/15万的独立研究分支实现与首轮完整区间 A/C
- 是否重要突破：否；工程合同闭环，但没有真实短历史成功续接样本，不能晋级正式版
- 是否触发A/B：是；A 为当前正式 C9/15万原样，C 只增加本次换月规则

## 外部调研与判断

- 参考资料：pysystemtrade 数据文档 `https://github.com/pst-group/pysystemtrade/blob/develop/docs/data.md`，其换月数据合同要求在换月日同时具备当前合约和下一合约价格。
- 我的判断：新主力续接指标必须只用新合约自身截至换月日可见的历史，不能把旧、新合约原始价格拼接后计算；固定 120 个自然日数据预热是数据可用性缓冲，不是 alpha 参数。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rollover_shape_same_volume/tools/stage001_rollover_shape_same_volume_ac.py`
- 修改脚本：`qmt_roll_portfolio_strategy.py`、Stage847 回放诊断帧、Stage947 市场数据刷新命令。
- 删除脚本：无。
- 新增参数：`enable_rollover_shape_same_volume_reopen=False`，默认关闭。
- 修改参数：无；A 与 C 均使用当前正式 `account_capital/c3_capital=150000`、正式 AI eligibility、C9 分钟 K 注入、broker10 cap 和 0.5R stop/retry-once。
- 删除参数：无。
- 新增规则：旧多仓仅在新主力 `MA5>MA10>MA20>MA40` 且 MACD 柱 `>0` 时同向续接；旧空仓条件镜像；手数为旧仓实际剩余手数 `exact-or-skip`。
- 修改规则：换月候选不再要求完整 `ArrayManager.inited`，但实际有限收盘价必须至少覆盖 MA40；普通开仓的正式 AM41 合同不变。
- 数据链：Stage947 对映射涉及合约改为从目标日前固定 120 个自然日开始拉取 K 线；结束日仍为当日/刷新截止日，不读取未来数据。
- 风险容量：换月容量计算前只释放本轮风险快照中确实计入的旧合约保证金/集群风险；旧 Bar 若仅来自引擎回退则释放 `0`，不会误减其他持仓风险。

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-05-29`。
- 账户规模：`150,000`。
- 成本口径：两臂沿用当前正式 C9/15万 rates、slippage、contract size、pricetick 与 broker10 口径。
- 样本过滤：正式产品池、正式 AI eligibility；Stage901 正式回放入口负责完整分钟 K 注入。
- 策略/归因口径：
  - A：`stage001_A_official_live_c9_15w`。
  - C：`stage001_C_official_live_c9_15w_rollover_shape_same_volume`。
  - 唯一策略变量：`enable_rollover_shape_same_volume_reopen=False/True`。
- 有效性校准：A 的 `2018-01` 路径与既有 Stage153 同期轨迹一致；不能复用缺少正式分钟 K 注入的旧 Stage847 直接回放口径。

## 结果

### A 正式基线

- 期末权益：`13,071,214.10`
- 总收益：`8,614.1427%`
- 最大回撤：`-56.2069%`
- Sharpe：`1.3622`
- 总滑点：`1,525,590`
- 总交易次数：`808`
- 胜率：`52.5841%`（非零日收益胜率）

### C 换月候选

- 期末权益：`13,518,540.80`
- 总收益：`8,912.3605%`
- 最大回撤：`-57.2674%`
- Sharpe：`1.3625`
- 总滑点：`1,576,750`
- 总交易次数：`809`
- 胜率：`52.7170%`（非零日收益胜率）

### 差异与换月事件

- 期末权益：`+447,326.70`。
- 总收益：`+298.2178pp`。
- 最大回撤：恶化 `-1.0604pp`（绝对回撤更深）。
- Sharpe：`+0.0003`，基本持平。
- 总滑点：`+51,160`。
- 总交易次数：`+1`。
- C 共记录 `23` 次换月：`13` 次形成原手数完整重开目标且全部匹配实际开仓成交，`10` 次不开仓，未成交目标 `0`，静默缩手 `0`。
- `5` 次目标合约尚未完整初始化，但数据库中实际都只有 `1` 根可见 K 线，因此全部以 `insufficient_indicator_history` 跳过。
- 新增回测结果：以上 A/C、事件诊断和逐日曲线。
- 修改回测结果：废弃两次缺少 Stage901 正式分钟 K 注入/资本口径不正确的预跑，不作为结论或输出引用。
- 复审修复后重跑时间：`2026-08-20 23:13 CST`；完整 A/C 和事件统计未变化。
- 删除回测结果：无历史正式结果被删除；Stage001 产物最终只保留正式 Stage901 A/C 覆盖后的文件。

## 输出文件

- report：本 stage 文件。
- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_ac_summary.csv`
- comparison：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_ac_comparison.csv`
- daily：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_ac_curve.csv`
- orders：无；订单 API、撤单 API 均未调用。
- trade events：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_trade_events.csv`
- trades：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_trades.csv`
- quality：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_rollover_shape_diagnostics.csv`
- decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage001/stage001_decision.json`

## 结论

- 本阶段结论：`stage001_implementation_kept_research_only_not_promoted`。
- 正面证据：完整区间 A/C 的收益提高，`13` 次目标重开全部匹配到实际开仓成交，且成交手数严格等于旧仓实际手数。
- 反面证据：最大回撤恶化 `1.0604pp`，总滑点增加 `51,160`，Sharpe 仅提高 `0.0003`，不能把收益抬升直接解释为更稳健。
- 关键限制：历史短合约数据仍只有 1 根，改善来自已初始化换月事件的 exact-or-skip 路径变化，不是“40 根短历史成功续接”的直接 OOS 证明；事件只有 `23` 次，样本很小。
- 是否进入下一步：保留研究分支和固定规则，不合入正式配置、不激活实盘。
- 下一步：等待 120 日预热产生真实 `40` 根以上但未 `inited` 的换月事件，做 forward shadow；不扫描 MA/MACD/手数比例救参。

## 过拟合反思

- 运行前判断：否。规则来自同产品换月连续性的结构约束，方向、MA、MACD 和手数合同在结果前冻结。
- 运行后判断：低到中等风险，不能把当前收益抬升视为稳定 alpha，尤其最大回撤和成本同时恶化。
- 原因：只有 `23` 次换月，且目标短历史续接样本为 `0`；若据当前结果继续改 MA、MACD、日期或品种就是过拟合。

## 继续价值反思

- 运行前判断：是。原逻辑会因目标合约历史不足只平不重开，且重开会重新计算手数，存在执行语义缺口。
- 运行后判断：是，但价值仅限 research/forward shadow，不足以晋级正式版。
- 原因：工程合同、数据预热、审计和 exact-or-skip 已闭环；真正短历史续接仍需新增点时样本验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为 Stage001 完成、研究保留不晋级。
- 是否更新 `research/registry.md`：暂不；研究分支未合入 master，待后续合入者统一登记。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，因为这是基于当前正式版本的 A/C 与明确不晋级结论；不追加 `memory.md`。
