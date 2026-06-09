# Stage025 理论收益率大赢家K线图册

- 时间：2026-06-09 13:46 CST
- line_id：`futures_trend_winner_trade_forensics`
- 工作模式：`day`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage752_theoretical_winner_kline_atlas.py`
- 决策：`readonly_visual_forensics_no_promotion`

## 外部/GitHub调研结论

- 外部资料支持用 K 线图册做人工复盘和形态观察，但没有找到可直接复制到本策略的“普适大赢家K线规则”。
- GitHub/资料层面，`mplfinance` 等库适合做K线可视化；本次为了不新增依赖，使用 `matplotlib` 手工绘制 OHLC 蜡烛图。
- 趋势跟随资料普遍强调大赢家来自持续趋势、波动扩张和让利润奔跑；但把视觉共同点直接写成规则，过拟合风险很高。

## 本次变更

- 新增只读绘图脚本，不修改正式策略、不连接 CTP、不调用下单、不改任何参数。
- 数据源：Stage719 正式版 closed lots。
- 大赢家定义：不是按实际 PnL、手数、合约乘数排序，而是按理论方向收益率排序：
  - 多头：`(exit_price - entry_price) / entry_price`
  - 空头：`(entry_price - exit_price) / entry_price`
- 选取口径：全周期正理论收益交易的 top20%，阈值 `7.62348%`。
- 每笔图包含：入场前 `40` 根K线、持仓段、平仓后 `40` 根K线；蓝线/蓝三角为入场，紫线/紫三角为平仓，浅黄区域为持仓期。

## 输出结果

- 选中大赢家：`29` 笔。
- 图册页数：`8` 页，每页最多 `4` 笔。
- 成功绘制K线：`23` 笔。
- 缺少合约CSV无法绘制：`6` 笔，图中已标注 `missing bars`，不使用伪造或替代K线。
- 最高理论收益：
  - `jm2509.DCE long 2025-07-09 -> 2025-07-25`：`42.0836%`
  - `SM201.CZCE long 2021-09-01 -> 2021-09-23`：`33.3488%`
  - `FG009.CZCE long 2020-07-03 -> 2020-08-12`：`29.2277%`，但该合约CSV缺失

## 输出文件

- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_manifest_stage752_theoretical_winner_kline_atlas_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_summary_stage752_theoretical_winner_kline_atlas_v1.csv`
- chart page01：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page01_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page02：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page02_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page03：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page03_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page04：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page04_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page05：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page05_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page06：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page06_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page07：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page07_stage752_theoretical_winner_kline_atlas_v1.png`
- chart page08：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage752_theoretical_winner_kline_atlas_page08_stage752_theoretical_winner_kline_atlas_v1.png`

## 初步观察

- 多数可绘制的大赢家不是“入场前一直无影线”的单一形态，而更像是突破/均线扭转后快速加速。
- `jm2509`、`SM201`、`FG109` 这类右尾样本都有一个共同点：入场后很快出现方向性扩张，且 MA5/MA10/MA20 很快形成顺向排列。
- 一些大赢家在入场前存在整理、回撤或杂乱K线，说明“入场前短影线”若作为硬条件，容易漏掉真正右尾。
- 这次图册更支持把 K 线特征用于人工复盘和候选特征发现，而不是直接作为放大风险资金的规则。

## 过拟合与继续价值反思

- 本次是否过拟合：否。这里只做全周期视觉归因，且按预先定义的理论方向收益率排序，没有改变策略，也没有用图形结论直接交易化。
- 若下一步把某个肉眼形态直接写成规则：是高过拟合风险，必须先转成可量化、事前可见、跨年份/跨品种验证的特征。
- 是否有价值继续：有。价值在于从图册中提出少数候选结构，例如“入场后5根内方向性扩张”“均线快速顺排”“突破后回踩不破入场区”，再做只读统计验证。

## TODO

- 从图册中提取候选形态，不扫小数阈值，优先做 3 个结构化特征：
  1. 入场后 `5` 根内的方向性扩张；
  2. 入场前 `20` 根压缩后，入场后波动扩张；
  3. 入场后 MA5/MA10/MA20 快速顺排且未深度回撤。
- 每个特征必须用 Stage719 closed lots 做跨年份、跨品种、方向覆盖检查；不直接接正式版。
