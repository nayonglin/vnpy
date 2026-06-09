# Stage026 理论亏损率失败交易K线图册

- 时间：2026-06-09 13:55 CST
- line_id：`futures_trend_winner_trade_forensics`
- 工作模式：`day`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage753_theoretical_loser_kline_atlas.py`
- 决策：`readonly_visual_loser_forensics_no_promotion`

## 外部/GitHub调研结论

- GitHub/资料层面，`mplfinance` 和相关注释教程支持在K线上标注入场/出场点；本次沿用自绘 matplotlib OHLC 图，不新增依赖。
- 失败交易复盘资料普遍强调区分“规则内失败”和“模式失效后继续持有/扩大风险”；但没有找到可直接复制到本策略的普适失败K线规则。
- 趋势跟随研究也提示亏损交易多、右尾少是策略风格的一部分；不能因为失败图看起来相似就直接删除某类信号。

## 本次变更

- 新增只读失败交易K线图册脚本，不修改正式策略、不连接 CTP、不调用下单。
- 数据源：Stage719 正式版 closed lots。
- 排序口径：理论方向收益率为负的全部交易，按理论亏损比例从高到低排序：
  - 多头亏损：`(entry_price - exit_price) / entry_price`
  - 空头亏损：`(exit_price - entry_price) / entry_price`
- 每笔图包含：入场前 `40` 根K线、持仓段、平仓后 `40` 根K线；蓝线/蓝三角为入场，紫线/紫三角为平仓，浅红区域为亏损持仓期。

## 输出结果

- 失败交易总数：`175` 笔。
- 图册页数：`44` 页，每页最多 `4` 笔。
- 最大理论亏损比例：`13.2865%`。
- 中位理论亏损比例：`1.6287%`。
- 缺少本地合约CSV无法绘制：`26` 笔，图中已标注 `missing bars`，不使用伪造或替代K线。
- 最严重失败：
  - `MA605.CZCE long 2026-04-08 -> 2026-04-09`：`13.2865%`，本地缺CSV
  - `fu2209.SHFE long 2022-05-06 -> 2022-05-11`：`10.2032%`
  - `fu2301.SHFE long 2022-08-29 -> 2022-09-01`：`7.0722%`
  - `jm2105.DCE long 2021-01-11 -> 2021-01-14`：`6.9859%`

## 输出文件

- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage753_theoretical_loser_kline_atlas_manifest_stage753_theoretical_loser_kline_atlas_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage753_theoretical_loser_kline_atlas_summary_stage753_theoretical_loser_kline_atlas_v1.csv`
- chart pages：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage753_theoretical_loser_kline_atlas_page01_stage753_theoretical_loser_kline_atlas_v1.png` 至 `page44`

## 初步观察

- 最严重失败里有两类：一类是短时间急反向跳变或连续反向K线，另一类是入场时已经接近局部冲高/反弹末端。
- 多数严重亏损不是因为持仓很久，而是在 `2~6` 根K线内快速失效；这更支持“入场后早期失效识别/快速减仓”作为候选复盘方向，而不是入场前固定K线形态删除。
- 有些亏损发生在 `risk=0.1` 高连败状态，说明连败机制不是只错杀机会，也在真实压低部分糟糕交易的损失规模。

## 过拟合与继续价值反思

- 本次是否过拟合：否。这里只按预先定义的理论亏损比例排序并绘图，不改变策略、不筛选规则。
- 若直接从最亏几十笔里倒推“禁止某个品种/月份/某根K线”：是高过拟合风险。
- 是否有价值继续：有。价值在于把失败分为“入场后立即失效”“趋势末端追入”“跳空/极端波动”“短侧反向挤压”等结构，再做跨年份/跨品种只读统计。

## TODO

- 结合 Stage025 大赢家图册，下一步可做赢家/失败对照特征：
  1. 入场后 `1/2/3/5` 根内是否快速跌破入场K低点/高点；
  2. 入场前 `20` 根是否已经远离 MA20/MA60、处于趋势末端加速；
  3. 入场后第一根反向实体/长影线是否预示快速失败。
- 所有特征只能先做只读统计，不接正式版，不扫小数阈值。
