# Stage001 外部来源与历史反证简记

- 研究线：`futures_trend_triple_screen`。
- 日期：2026-10-17；范围：本次结构设计和分钟缺口备用通路的只读调研，不是新回测或生产资格证据。
- 判断：三重滤网的结构有一次低自由度验证价值，经典名称、开源实现和既有论文都不预先证明本策略alpha；本次未按收益扫描窗口或阈值。

## 设计来源

1. [Elder官方MetaStock手册](https://6e6fa188-f273-4932-86c0-66af721f16a8.usrfiles.com/ugd/6e6fa1_60651ebd50ca4ea0bd0421f83dce9e74.pdf)：第31页用最近两根周MACD柱的关系定义斜率，日线使用2日Force Index；第10页说明Force Index为价格变化乘成交量的EMA。官方手册也明确工具并非完整交易系统。本轮只检验第一层增量，不冒称完整三重系统。
2. [LEAN ForceIndex源码](https://github.com/QuantConnect/Lean/blob/master/Indicators/ForceIndex.cs)、[LEAN MACD源码](https://github.com/QuantConnect/Lean/blob/master/Indicators/MovingAverageConvergenceDivergence.cs)：核对指标数学定义和暖机。源码可用作实现参照，不能当盈利证据；本线具体EMA初始化以冻结协议为准。
3. [Backtrader多周期文档](https://www.backtrader.com/docu/data-multitimeframe/data-multitimeframe/)及[交易日历文档](https://www.backtrader.com/docu/tradingcalendar/tradingcalendar/)：高低周期必须正确对齐、保留高周期暖机，节假日周结束须依实际交易日历判断。
4. [TradingView高周期数据说明](https://www.tradingview.com/pine-script-docs/concepts/other-timeframes-and-data/)：未确认周线的最终值回填到历史周内会泄漏。本线固定仅使用上一已完成ISO周，不把周五最终状态回填周一。

## 仓库既有反证

- `futures_swing_no_lower_shadow` Stage008：周线顺势＋连续两日加速，总收益−0.8590%、最大回撤−1.9902%，只有15个完整回合；不能把减少交易后的低回撤当alpha。
- 同线Stage009：周线顺势＋回调后第一根点火，收益+0.4770%、Sharpe0.0481；2倍滑点已平仓PnL−11,205，停止追加条件救参。该来源并非本次正式C9同源，不能直接推定C0失败。
- `futures_trend_winner_trade_forensics` Stage014：慢趋势一致性可靠性门通过0，最强14笔小样本不足；不重开120/200日窗口扫描。
- `futures_trend_rebuilt_c9_15w_optimization` Stage018/019：高波动低效率减仓门砍掉大量正贡献，收益保留失败；停止同形状阈值、手数、窗口救参。
- `futures_trend_rollover_shape_same_volume` Stage269：全市场ER跨周期覆盖不足，中组收益依赖少数重叠窗口；不把ER中组转成三重滤网规则。

这些是仓库历史记录中的反证与先验，本次未重新跑其旧账户或重新认证旧机器数据。

## 分钟历史数据备用通路：未实测

- [天勤官方快速入门](https://doc.shinnytech.com/tqsdk/latest/quickstart.html)提供`TqBacktest + get_kline_serial`历史回放用法，并注明实际权限以账户为准。
- [官方版本记录](https://doc.shinnytech.com/tqsdk/latest/version.html)记载2021-08重新开放免费每日3次回测，2022-01再次确认；[官方auth源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/auth.py)在回测模式提供基础行情权限，而[DataDownloader官方文档](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html)明确历史下载为专业版功能。`tq_dl=false`不能单独证明正规回放不可用，但回放权限也不等于无限历史下载授权。
- 本次未登录账户、未执行网络probe、未下载分钟数据、未修改SDK或绕过权限，故**不声称天勤2020年rb2010历史通路已打通**。
- 公开GitHub候选未确认满足目标真实合约、日期及完整1min OHLCV：`future_highFreq`声明服务器未接入；公开CC0五分钟数据不能重建一分钟路径；Zenodo分钟close数据缺OHLCV且只含当时活跃合约，不能作为本次撮合补丁。
- 根代理随后在本机找到Stage491旧已验收来源，报告目标交易日完整345根分钟线、与日线匹配且SHA已列入旧A输入manifest。因此本次无需启用上述网络备用通路；实际本地修补与来源资格以runner及独立review receipt为准，本文件不替代其核验。

结束判断：本次来源调研没有新增按收益选参的过拟合；结构验证仍有价值。分钟来源已在本机解决后，继续扩大外部搜索没有当前必要。
