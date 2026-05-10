# 2026-05-10 18:47 Stage225 Stage78-1 AI选品开关A/B消融

## 版本改动

- 是否重要突破：是。首次对`78-1`正式基准做AI选品开/关的单因素消融，直接验证AI品种池是否创造真实增益。
- 新增脚本：`examples/portfolio_backtesting/run_qmt_roll_stage225_stage78_1_ai_ablation_suite.py`
- 新增参数：无。
- 修改参数：仅实验变量`enable_ai_product_pool_filter=True/False`。
- 删除参数：无。
- 正式基准未改动：`78-1`仍默认开启AI选品。

## 回测参数

- 版本：`78-1`
- 官方版本：`official_stage78_1_defensive_50w_no_sizing_cap`
- 初始资金：`500,000`
- sizing资金封顶：`0.0`
- 基础风险：`0.045`
- AI ON：`enable_ai_product_pool_filter=True`
- AI OFF：`enable_ai_product_pool_filter=False`
- 其他条件：同一产品宇宙、FU卫星、无sizing封顶、风险四档、短空门禁、同日收盘撮合。
- 分析区间：`2020-01-01`至`2026-04-30`
- Monte Carlo：`1000`次，`daily_block_bootstrap`与`trade_block_bootstrap`
- 滑点压力：`1x/2x/3x/5x`

## 新增回测结果

- 主回测 AI ON：
  - 期末权益：`25,542,885`
  - 总收益：`5008.5770%`
  - 最大回撤：`-40.0607%`
  - Sharpe：`1.1295`
  - 总滑点：`1,968,150`
  - 总交易次数：`880`
  - 胜率：`43.2432%`
- 主回测 AI OFF：
  - 期末权益：`7,588,545`
  - 总收益：`1417.7090%`
  - 最大回撤：`-46.6939%`
  - Sharpe：`0.7214`
  - 总滑点：`1,270,300`
  - 总交易次数：`1,358`
  - 胜率：`40.5839%`
- 全样本结论：
  - AI ON期末权益约为AI OFF的`3.37`倍。
  - AI ON收益高`3590.8680`个百分点，最大回撤改善约`6.63`个百分点，Sharpe提升约`0.41`。
  - AI ON交易次数减少`478`笔，说明AI主要价值不是提高频率，而是过滤低质量交易。

## 多周期结果

- `2020起点至今`：AI ON `5008.5770%`，AI OFF `1417.7090%`。
- `2021起点至今`：AI ON `2710.1240%`，AI OFF `848.3100%`。
- `2022起点至今`：AI ON `979.7190%`，AI OFF `123.6600%`。
- `2023起点至今`：AI ON `778.1290%`，AI OFF `126.5790%`。
- `2024起点至今`：AI ON `446.1780%`，AI OFF `159.3840%`。
- `2025起点至今`：AI ON `308.2790%`，AI OFF `145.4130%`。
- `2026起点至今`：AI ON `-9.8920%`，AI OFF `-39.9220%`。
- `2020-2021独立启动`：AI ON `583.0930%`，AI OFF `281.7380%`。
- `2022-2023独立启动`：AI ON `123.7880%`，AI OFF `7.6300%`。
- `2024-2025独立启动`：AI ON `418.5170%`，AI OFF `218.7380%`。
- `2026独立启动至最新`：AI ON `-9.8920%`，AI OFF `-39.9220%`。
- 结论：AI ON在所有11个窗口收益和Sharpe均优于AI OFF；仅`2024-2025`独立阶段最大回撤略差于AI OFF。

## 滑点压力

- AI ON `1x/2x/3x/5x`总收益：`5008.5770% / 4614.9470% / 4221.3170% / 3434.0570%`
- AI OFF `1x/2x/3x/5x`总收益：`1417.7090% / 1163.6490% / 909.5890% / 401.4690%`
- AI ON `5x`滑点下仍显著高于AI OFF `1x`，说明AI收益优势不是由低成本假设单独制造。
- 但AI ON `5x`最大回撤为`-66.4314%`，滑点压力下尾部波动仍重。

## Monte Carlo结果

- AI ON daily bootstrap：
  - 亏损概率：`2.0%`
  - 爆仓概率：`0.0%`
  - 回撤超过40%概率：`95.9%`
  - 中位收益：`1649.6720%`
- AI OFF daily bootstrap：
  - 亏损概率：`15.5%`
  - 爆仓概率：`0.0%`
  - 回撤超过40%概率：`99.5%`
  - 中位收益：`355.3278%`
- AI ON trade bootstrap：
  - 亏损概率：`0.2%`
  - 爆仓概率：`52.6%`
  - 回撤超过40%概率：`88.6%`
  - 中位收益：`5017.2125%`
- AI OFF trade bootstrap：
  - 亏损概率：`2.8%`
  - 爆仓概率：`53.9%`
  - 回撤超过40%概率：`92.7%`
  - 中位收益：`1613.5985%`
- 结论：AI ON降低亏损概率和极端回撤概率，但不能消除路径顺序风险；trade-block口径下仍有较高穿仓/破产概率，需要作为资金管理风险提示。

## 修改/删除结果

- 修改结果：无。
- 删除结果：无。

## 调研与判断

- 外部调研结论：稳健验证不能只看全样本收益，必须做单因素消融、多起点/多阶段、成本压力和路径重排；本次实验遵循该原则。
- 第一性判断：AI选品若有价值，应表现为减少低质量交易、提升多窗口收益和风险调整收益，而不是只在一个全样本窗口抬高收益。
- 本次证据链支持AI有真实价值：
  - 收益优势跨11个窗口一致。
  - 交易次数明显下降但收益上升。
  - 2022-2023弱窗口从几乎走平提升到可观正收益。
  - 2026冷启动亏损从`-39.9220%`收敛到`-9.8920%`。
  - Monte Carlo亏损概率显著下降。
- 限制：AI OFF不是独立优化过的无AI版本，因此本次只能证明“在78-1当前框架内，AI过滤器有价值”，不能证明这套AI池是全局最优。

## 反思

- 过拟合反思：否。本次没有新增交易规则或按结果调参，只关闭/开启单个过滤器做消融，属于反过拟合证据链。
- 继续价值反思：有。AI选品已被验证为78-1的重要组成，但尾部路径风险仍然存在，后续应研究资金暴露治理，而不是继续微调AI名单追收益。

## 后续规划

- 保持`78-1`正式基准默认AI开启。
- 新研究分支默认先与`78-1 AI ON`对照；独立原始idea探索可先不开AI，避免把正式基准alpha混入新idea。
- 针对`2026`低胜率和trade-block尾部风险做归因，不直接改AI池。
- 后续若更新月度AI池，应按同样A/B消融流程复验。

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_report_stage225_stage78_1_ai_ablation_suite_v1.md`
- HTML：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_report_stage225_stage78_1_ai_ablation_suite_v1.html`
- 主摘要：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_main_summary_stage225_stage78_1_ai_ablation_suite_v1.csv`
- 多周期：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_multiperiod_summary_stage225_stage78_1_ai_ablation_suite_v1.csv`
- 滑点压力：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_slippage_stress_stage225_stage78_1_ai_ablation_suite_v1.csv`
- Monte Carlo：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage225_stage78_1_ai_ablation_suite_monte_carlo_summary_stage225_stage78_1_ai_ablation_suite_v1.csv`
