# Stage014 Stage838 C4集中簇持仓生存线压力起点验证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 19:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结 C6 stress-start 真实引擎验证；只读研究，不改正式版，不连接 CTP，不调用下单。
- 是否重要突破：否。它反证了一个看似合理的持仓后集中簇生存线。
- 是否触发A/B：否。C6 未达到可接正式版、可与 Stage372/第78正式基准结合或做正式 A/B 的标准。

## 外部调研与判断

- 参考资料：
  - CME Position and Risk Management：强调 futures 风险需要用仓位规模、止损和风险承受度控制。
  - CME Product Margins / margining materials：保证金会随产品和波动变化，不能把固定名义仓位等同于固定风险。
  - Euronext Clearing Risk Management：保证金是覆盖持仓潜在清算成本的核心工具。
  - FINRA / clearing intraday margin materials：intraday margin monitoring 与账户权益变化、持仓变化相关。
  - GitHub/开源参考：多停留在 margin call、最大保证金或简单杠杆控制，未找到可直接复制的产品方向簇集中规则。
- 我的判断：外部资料支持“账户/持仓层风控必须关注保证金、集中度和日内/日终监控”，但并不支持按某个历史压力日反推出产品、年份或方向专属补丁。因此本阶段只验证 broad rule shape：broker10 压力 + top3 产品方向簇集中 + 单方向集中，而不是继续扫分钟止损或具体产品。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage838_stage830_c4_cluster_survival.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `enable_stage838_cluster_survival=True`
  - `cluster_trigger_ratio=1.0`
  - `cluster_target_ratio=0.95`
  - `cluster_broker_multiplier=1.65`
  - `top3_share_min=0.75`
  - `direction_share_min=0.75`
  - `priority=top3_product_direction_then_dominant_direction`
- 修改参数：无正式参数修改。内部诊断曾用 `cluster_broker_multiplier=1.10`，因 runtime `_estimate_margin_usage` 低估 exact 输出保证金、未触发事件，最终冻结为与 Stage830/Stage833 一致的 runtime 校准倍数 `1.65`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：压力起点分别从 `2018-01-01`、`2019-01-01`、`2020-01-01`、`2021-01-01` 跑到 `2026-05-29`。
- 账户规模：沿用 Stage819 候选 30w 口径。
- 成本口径：沿用 Stage819/C4 原组合成本；不做成本倍数压力扩展。
- 样本过滤：只跑 Stage832 已识别的 C4 broker100/DD50 压力起点，未扩展到全年度起点。
- 策略/归因口径：
  - A：Stage827 `stage827_stage819_baseline`
  - C4：Stage830 `stage830_stage819_c2_broker10_100_cap`
  - C6：C4 + 持仓后 concentration-aware survival
  - C6 触发语义：runtime-calibrated broker10 `>100%`，且 top3 产品方向簇占比 `>=75%`，且 dominant direction 占比 `>=75%`，则优先减 dominant top3 product-direction 的最大保证金持仓，直到 runtime ratio 约 `95%`。

## 结果

- 期末权益：
  - `2018-01`：A `26,322,730`；C4 `30,523,910.8`；C6 `30,817,212.2`
  - `2019-01`：A `22,792,425`；C4 `35,491,021.8`；C6 `33,961,608.2`
  - `2020-01`：A `18,787,535`；C4 `25,947,231.6`；C6 `26,350,528.8`
  - `2021-01`：A `5,779,775`；C4 `13,705,900.0`；C6 `13,267,841.0`
- 总收益：
  - `2018-01`：A `8674.2433%`；C4 `10074.6369%`；C6 `10172.4041%`
  - `2019-01`：A `7497.4750%`；C4 `11730.3406%`；C6 `11220.5361%`
  - `2020-01`：A `6162.5117%`；C4 `8549.0772%`；C6 `8683.5096%`
  - `2021-01`：A `1826.5917%`；C4 `4468.6333%`；C6 `4322.6137%`
- 最大回撤：
  - `2018-01`：A `-54.7546%`；C4 `-50.7900%`；C6 `-50.3261%`
  - `2019-01`：A `-43.4335%`；C4 `-50.7898%`；C6 `-59.7206%`
  - `2020-01`：A `-44.6223%`；C4 `-50.8993%`；C6 `-50.5898%`
  - `2021-01`：A `-42.8163%`；C4 `-49.4595%`；C6 `-49.1419%`
- Sharpe：
  - `2018-01`：A `1.4363`；C4 `1.4519`；C6 `1.4278`
  - `2019-01`：A `1.5297`；C4 `1.5931`；C6 `1.5283`
  - `2020-01`：A `1.5941`；C4 `1.6220`；C6 `1.5974`
  - `2021-01`：A `1.3961`；C4 `1.6024`；C6 `1.5752`
- 总滑点：
  - `2018-01`：A `2,149,150`；C4 `2,079,430`；C6 `2,108,280`
  - `2019-01`：A `1,793,410`；C4 `2,348,680`；C6 `2,343,600`
  - `2020-01`：A `1,489,460`；C4 `1,779,890`；C6 `1,861,250`
  - `2021-01`：A `493,780`；C4 `954,740`；C6 `936,450`
- 总交易次数：
  - `2018-01`：A `666`；C4 `677`；C6 `667`
  - `2019-01`：A `621`；C4 `625`；C6 `617`
  - `2020-01`：A `529`；C4 `534`；C6 `530`
  - `2021-01`：A `387`；C4 `395`；C6 `391`
- 胜率：
  - `2018-01`：A `53.1069%`；C4 `53.6294%`；C6 `53.7148%`
  - `2019-01`：A `54.2778%`；C4 `53.9027%`；C6 `54.3458%`
  - `2020-01`：A `54.7544%`；C4 `54.4397%`；C6 `54.5455%`
  - `2021-01`：A `53.5475%`；C4 `54.0984%`；C6 `53.9617%`
- 其他关键指标：
  - C6 对 A 收益胜出 `4/4`，但回撤胜出仅 `1/4`。
  - C6 对 C4 回撤胜出 `3/4`，但收益中位差为 `-24.1263pp`。
  - A broker100 失败 `0/4`；C4 broker100 失败 `4/4`；C6 broker100 失败仍为 `4/4`。
  - C6 DD50 失败 `3/4`，没有改善 C4。
  - C6 最大 broker10 为 `124.9520%`，高于 C4 压力峰值，说明生存线没有解决 exact 输出口径的保证金超限。
  - C6 cluster 事件 `7` 次，合计减仓 `173` 手；runtime over trigger `8` 次，max runtime ratio `1.1501`。
  - cluster 事件主要是 `2021-02-19 CF105.CZCE long` 与 `2022-03-29 CF205.CZCE long`，没有命中 Stage832 最关键的 `2022-07` 黑色/燃油 short broker100 压力簇。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_report_stage838_stage830_c4_cluster_survival_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_summary_stage838_stage830_c4_cluster_survival_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_comparison_stage838_stage830_c4_cluster_survival_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_aggregate_stage838_stage830_c4_cluster_survival_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_curves_stage838_stage830_c4_cluster_survival_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_trade_events_stage838_stage830_c4_cluster_survival_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_intraday_events_stage838_stage830_c4_cluster_survival_v1.csv`
- cluster_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_cluster_events_stage838_stage830_c4_cluster_survival_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_decision_stage838_stage830_c4_cluster_survival_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage838_stage830_c4_cluster_survival_chart_stage838_stage830_c4_cluster_survival_v1.png`

## 结论

- 本阶段结论：`stage838_c6_cluster_survival_not_enough`。集中簇持仓生存线的 broad shape 在法证上合理，但落进真实引擎后没有解决 broker100，且在 `2019-01` 显著恶化回撤到 `-59.7206%`。
- 是否进入下一步：C6 不进入年度全样本验证，不进入正式候选，不进入官方 A/B。
- 下一步：停止沿 C4 survival branch 扫 `trigger/target/broker_multiplier/top3_share/direction_share/product/year`。后续应回到原始分钟K目标，做 C2/C4 已触发日内止损事件的 K 线形态分层和未覆盖失败交易图谱，寻找低自由度、实时可执行的退出/重试规则；若继续账户层，只能引入真实 broker exact margin snapshot 或 next-day exact account layer，不能在回测内继续救阈值。

## 过拟合反思

- 运行前判断：中等。规则形状来自 Stage837 的全压力锚点和外部风控常识，不是单一品种补丁；但验证样本仍是已知压力起点。
- 运行后判断：如果继续扫小数阈值就是过拟合；停止该分支则不是。
- 原因：C6 没有命中关键 `2022-07` short 压力簇，反而提前在 long 集群上改变路径。继续微调触发线只是在已知路径上追结果，不是发现穿越周期的机制。

## 继续价值反思

- 运行前判断：有价值。它是 Stage837 法证形状进入真实引擎前必须做的一次反证。
- 运行后判断：C4 持仓后 survival 分支继续价值低；Stage819 分钟级规则主线仍有价值。
- 原因：C6 未能消除 broker100，也没有改善 DD50；但 C2/C4 的直接日内止损事件此前证明有正贡献，值得回到分钟K事件层做更细的实时退出/重试归因。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage014 结论并收束 C4 survival 分支。
- 是否更新 `research/registry.md`：否。该阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。该阶段为候选线内部反证，不是正式候选或重要合入摘要。
