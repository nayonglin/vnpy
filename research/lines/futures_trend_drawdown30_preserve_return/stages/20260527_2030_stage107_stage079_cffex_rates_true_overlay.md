# Stage107 Stage079中金所国债真实一手Overlay

- 时间：2026-05-27 20:30 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：不同资产风险源真实整数手 scout；固定 Stage103 `broker10_guard`，测试中金所国债期货是否能作为现金槽位附近的低相关收益源。
- 是否重要突破版本：否。国债 overlay 提升了全周期收益和 6 个月体验分，但 `start_2022` 冷启动重新击穿 30% 回撤，且相对 Stage103 的成本/回撤增量不稳。
- 是否触发 A/B/C：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`Stage103+国债60日动量真实一手`；C2=`Stage103+国债120日动量真实一手`。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage407_stage079_cffex_rates_true_overlay.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage407_stage079_cffex_rates_true_overlay_report_stage407_stage079_cffex_rates_true_overlay_v2.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage407_stage079_cffex_rates_true_overlay_chart_stage407_stage079_cffex_rates_true_overlay_v2.png`

## 开始前反思

- 是否在过拟合：否。Stage107 不是按坏窗口补条件，而是验证一个不同资产风险源：中金所 TS/TF/T/TL 国债期货，且只测试 Stage081 已出现但未落地的 `60/120日` 时间序列动量形状。
- 是否仍有价值继续做：是。Stage104/105/106 显示同商品趋势/动量承载容易在 `start_2022` 类窗口同向承压，因此有必要尝试更不同的利率风险源。

## 外部调研和判断

- 调研来源：
  - 中金所 2年国债期货合约：`https://www.cffex.com.cn/en_new/2ts.html`
  - 中金所 5年国债期货合约：`https://www.cffex.com.cn/en_new/5tf.html`
  - 中金所 10年国债期货合约：`https://www.cffex.com.cn/en_new/10t.html`
  - 中金所 30年国债期货合约：`https://www.cffex.com.cn/en_new/30yearCGBFutures.html`
  - 中金所 2年国债期货 tick 调整公告摘要：`https://www.cffex.com.cn/en_new/`
- 调研判断：国债期货确实是比商品横截面动量更不同的风险源，且交易所最低保证金低，理论上适合做现金槽位附近的低相关承载。但它不能只看净值层，必须落到真实一手、保证金和冷启动窗口。
- 规格修正：v1 初稿把 TF 最低保证金保守写成 `1.2%`，并把 TS tick 固定为 `0.005`；v2 已修正为 TF `1%`，TS 自 `2023-11-07` 起按 `0.002` tick 估算滑点。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage407_stage079_cffex_rates_true_overlay.py`
- 新增参数：
  - `stage103_plus_cffex_rates_tsmom60_min1_guard`：TS/TF/T/TL 按60日时间序列动量，单品种最多1手，受 `1.10` 倍保证金闸门约束。
  - `stage103_plus_cffex_rates_tsmom120_min1_guard`：TS/TF/T/TL 按120日时间序列动量，单品种最多1手，受 `1.10` 倍保证金闸门约束。
  - 合约面值：TS `200万`，TF/T/TL `100万`；最低保证金：TS `0.5%`，TF `1%`，T `2%`，TL `3.5%`。
- 修改参数：无正式策略默认修改；仅修正本次审计脚本的合约规格。
- 删除参数：无。

## 回测结果

Stage079：期末权益 `31,040,650`，总收益 `4947.2602%`，最大回撤 `-29.7007%`，Sharpe `1.3188`，Ulcer `15.0874`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。

Stage103 `broker10_guard`：期末权益 `31,730,915`，总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，总滑点 `1,569,265`，总交易次数约 `1217`，3个月分 `121.2041`，6个月分 `134.4513`。

`stage103_plus_cffex_rates_tsmom60_min1_guard`：期末权益 `31,907,575`，总收益 `5088.2236%`，最大回撤 `-29.1336%`，Sharpe `1.3615`，Ulcer `14.2061`，总滑点 `1,609,705`，总交易次数约 `1875`。3个月分 `119.6467`，6个月分 `145.0947`，用户目标8项改善 `5/8` 与 `6/8`。国债 overlay 全周期PnL约 `176,660`，滑点 `40,440`，换手 `658` 手，活跃率约 `82.83%`。

`stage103_plus_cffex_rates_tsmom120_min1_guard`：期末权益 `32,094,795`，总收益 `5118.6659%`，最大回撤 `-28.9719%`，Sharpe `1.3813`，Ulcer `14.0003`，总滑点 `1,594,305`，总交易次数约 `1637`。3个月分 `131.4049`，6个月分 `159.4910`，用户目标8项改善 `6/8` 与 `6/8`。国债 overlay 全周期PnL约 `363,880`，滑点 `25,040`，换手 `420` 手，活跃率约 `79.05%`。

多起点失败点：

- `tsmom60`：`start_2022` 总收益 `676.1854%`，最大回撤 `-30.5953%`，DD30 不通过；10%保证金上浮下有 `1` 天拒单。
- `tsmom120`：`start_2022` 总收益 `691.9935%`，最大回撤 `-32.7044%`，DD30 不通过；10%保证金上浮下有 `1` 天拒单。
- `ytd_2026`：两条国债 overlay 均弱于 Stage103，`tsmom60` 为 `-16.0748%/-26.1497%`，`tsmom120` 为 `-15.4634%/-25.1899%`，而 Stage103 与 Stage079 均为 `-12.0179%/-23.8062%`。

成本压力：

- `tsmom60` 在 `1x/2x/3x/5x` 下最大回撤为 `-29.1336%/-30.6880%/-32.3378%/-39.1469%`，相对 Stage079 不差，但 `1x/2x/3x` 不如 Stage103。
- `tsmom120` 在 `1x/2x/3x/5x` 下最大回撤为 `-28.9719%/-30.4656%/-32.0457%/-39.1469%`，`1x` 略好于 Stage103，但 `2x/3x` 不如 Stage103。

## 结论

- 决策：`no_new_promotion`。
- 我的判断：不按硬目标放宽也不建议晋级。国债 overlay 的全周期收益和 6个月体验分漂亮，但 `start_2022` 是本线最关键的冷启动反证窗口之一；一个候选如果在这个窗口把 Stage103 从 `-28.5161%` 拉到 `-30.5953%/-32.7044%`，它本质上没有解决“任何时候启动”的持有体验问题。
- 可以保留的知识：国债期货是方向正确的低相关风险源，但“简单一手TSMOM overlay”不够。若未来继续利率方向，必须换成更低相关、更稳健的结构，例如曲线相对价值、期限利差状态或真实资金隔离 paper，而不是继续扫 `60/120日` 或单合约。
- 当前最优仍是 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。它是执行相对候选，不是绝对部署候选；Stage079 仍是当前正式 baseline。

## 后续规划和 TODO

1. 不继续救国债 `60/120日` 动量窗口、单个合约、保证金小数、tick假设或过滤日期。
2. 停止围绕同商品横截面反转、同商品横截面动量和简单国债TSMOM做正式晋级救援。
3. 下一步若继续研究，只能做两类：Stage103 工程化/paper/影子盘执行验证；或者开启真正不同结构的外生/跨资产研究，且必须先定义低自由度经济逻辑。

## 结束后反思

- 是否在过拟合：不是。失败后没有继续改窗口、品种、日期或小数；v2 只修正了公开合约规格口径。
- 是否还有价值继续做：当前这个国债TSMOM子路线继续价值低；总目标仍有价值，但研究重点应从“继续找更高表内分数”转向“保护 Stage103 候选的执行真实性”或寻找更本质的跨资产状态暴露。
