# Stage021 Stage845 C8释放资金复用压力簇归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 21:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；读取 Stage844 输出，不重新回测，不修改正式版、不修改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。该阶段反证“按复用压力簇直接做冷却/闸门”的干净性。
- 是否触发A/B：否。本阶段没有产生可接入正式版或候选版的新策略版本。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 止损后的复用必须和仓位规模、组合压力、保证金路径一起评估，不能只看单笔止损是否正确。
  - 但风险管理闸门必须有广义机制支撑，不能因为少数 `broker10` 高压样本或最坏 K 线图就写成品种/年份/方向补丁。
  - Stage845 因此只检验“释放资金后新增仓是否集中进入压力簇”这个 broad mechanism；若证据混杂，就转向入场质量，不做复用冷却。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage845_stage844_reuse_cluster_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`。
- 账户规模：沿用 Stage819 候选 `300,000` 口径；本阶段不重新计算组合成交。
- 成本口径：沿用 Stage844 已生成的 C4/C8 日度曲线、reuse attribution、event window。
- 样本过滤：仅分析 Stage844 中 S3 事件后 `1/3/5/10/20` 日内的 C8-vs-C4 复用行；不按年份、品种、方向筛选。
- 策略/归因口径：
  - 事件聚类：每个 S3 事件窗口内的新增 C8 暴露，统计增量风险、增量 PnL、top product-direction share、top direction share、same-direction risk share。
  - 压力四分位：只读拆分 `broker_delta_top_quartile`、`drawdown_delta_worst_quartile`、`incremental_risk_top_quartile`。
  - 入口压力桶：按入场日 C8 broker10 与 drawdown 桶统计新增仓 PnL。
  - K线视觉：选取高风险/高 broker delta 的 post-S3 新增仓，生成入场日分钟K atlas，标记 entry 与 initial stop。

## 结果

- 期末权益：本阶段不重新回测；沿用 Stage843 C8 `33,052,106.4`、Stage830 C4 `30,523,910.8`。
- 总收益：本阶段不重新回测；沿用 C8 `10917.3688%`、C4 `10074.6369%`。
- 最大回撤：本阶段不重新回测；沿用 C8 `-51.4922%`、C4 `-50.7900%`。
- Sharpe：本阶段不重新回测；沿用 C8 `1.3872`、C4 `1.4519`。
- 总滑点：本阶段不重新回测；沿用 C8 `2,312,880`、C4 `2,079,430`。
- 总交易次数：本阶段不重新回测；沿用 C8 `686`、C4 `677`。
- 胜率：本阶段不重新回测；沿用 C8 `52.5699%`、C4 `53.6294%`。
- 其他关键指标：
  - 决策标签：`stage845_reuse_cluster_evidence_mixed_no_rule`。
  - 20日窗口：`43` 个事件，`33` 个有增量复用，增量行 `89`，增量风险 `+2,445,213.4`，增量 PnL `+3,361,304.0`。
  - 20日增量风险 vs broker10 delta 的 Spearman 相关仅 `0.0809`，线性相关 `0.0167`；top direction share vs broker10 delta 相关 `0.0650`，证据很弱。
  - `broker_delta_top_quartile`：`11` 个事件，增量风险 `+831,784.4`，增量 PnL `+872,618.6`，正 PnL 事件 `7`，负 PnL 事件 `2`。
  - `drawdown_delta_worst_quartile`：`11` 个事件，增量风险 `+1,223,597.8`，增量 PnL `+2,065,243.6`，正 PnL 事件 `7`，负 PnL 事件 `0`。
  - 入场日 C8 `broker_60_80` 桶：`20` 行，风险 `+469,458.6`，PnL `+92,741.6`。
  - 入场日 C8 `broker_80_100` 桶：`8` 行，风险 `+513,437.2`，PnL `+1,092,500.0`。
  - 入场日 C8 `broker_ge100` 桶：`2` 行，风险 `+72,460.0`，PnL `+211,190.0`。
  - 反而 `broker_lt30` 桶为负：`28` 行，风险 `+672,624.2`，PnL `-301,292.6`。这说明简单“高 broker 禁止复用”不是干净规则。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_report_stage845_stage844_reuse_cluster_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_event_cluster_summary_stage845_stage844_reuse_cluster_forensics_v1.csv`
- orders：无，本阶段未生成订单。
- daily：无新增日度回测；使用 Stage844 daily delta。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_decision_stage845_stage844_reuse_cluster_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_event_cluster_stage845_stage844_reuse_cluster_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_row_pressure_bucket_stage845_stage844_reuse_cluster_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_row_pressure_summary_stage845_stage844_reuse_cluster_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_pressure_quartile_stage845_stage844_reuse_cluster_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_cluster_chart_stage845_stage844_reuse_cluster_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_reuse_entry_atlas_page001_stage845_stage844_reuse_cluster_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_reuse_entry_atlas_page002_stage845_stage844_reuse_cluster_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage845_stage844_reuse_cluster_forensics_reuse_entry_atlas_page003_stage845_stage844_reuse_cluster_forensics_v1.png`

## 结论

- 本阶段结论：
  - 复用压力簇证据混杂，不足以形成 live-feasible 的冷却/闸门规则。
  - 高 broker 或 broker delta 高的事件里，新增复用仍为正收益；直接禁止高压状态下复用会误伤收益，不符合穿越周期的规则设计。
  - 20日相关性弱，说明 C8 的 broker10/回撤恶化不能简单归因于“新增风险越多越危险”或“同方向集中越危险”。
  - Stage845 不进入真实引擎、不进入官方候选、不触发 A/B。
- 是否进入下一步：进入下一步，但方向切换。
- 下一步：
  - 停止复用冷却/压力桶补丁。
  - 转向入场质量只读法证：在候选 Stage819/C4 的全周期交易中，寻找能实时判定、低自由度、不过度延迟右尾的入场质量信号。
  - 不再沿 S3、cooldown、broker bucket、年份/品种/方向做救参。

## 过拟合反思

- 运行前判断：否。Stage845 使用 Stage844 冻结输出，固定 `1/3/5/10/20` 日窗口，检验 broad cluster，而不是优化阈值。
- 运行后判断：否。结论是否定规则，不把最坏事件、最坏品种、最坏年份直接变成补丁。
- 原因：结果显示高压桶仍有正收益，若强行写“高 broker 禁复用”才是过拟合。

## 继续价值反思

- 运行前判断：有价值。Stage020 指向路径压力，必须确认是否有简单复用纪律可以继续。
- 运行后判断：有价值，但只作为排除路线。复用压力簇不是干净方向，继续在这里做阈值会进入过拟合。
- 原因：它帮助我们避免把“多赚但风险高”误解为简单 broker bucket 闸门问题；下一步应回到更贴近用户目标的分钟级入场质量。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage021 状态和后续方向。
- 是否更新 `research/registry.md`：否，本阶段没有新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或路线迁移。
