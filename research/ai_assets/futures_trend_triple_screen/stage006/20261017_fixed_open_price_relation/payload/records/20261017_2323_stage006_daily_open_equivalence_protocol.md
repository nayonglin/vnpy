# Stage006 已接受A0开盘anchor与真实日线open的限定等价审计

- line_id：futures_trend_triple_screen；冻结时间2026-10-17 23:23 CST。
- 性质：只读数据证据；金融回放0、下载0、alpha变更0。尚未批准改变执行合同或增加fallback。

## 调研与问题

[Backtrader官方说明](https://backtrader.com/blog/posts/2017-05-01-cheat-on-open/cheat-on-open/)及[GitHub broker源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)区分前日收盘发单、次bar open成交和当日已知价格后的下单。我们保持原C9信号/发单时序，只核查已接受A0的canonical首分钟开盘价是否逐事件等于原引擎精确合约真实日线open。

普通委托目前全部要求首分钟anchor，盘中0.5R/C2路径又要求开仓日完整分钟。两种数据要求应分清；日线open在数值上相同，也不能替代盘中先后顺序或伪造分钟OHLCVOI。

## 固定范围与计算

1. 范围严格为A0_attempt2的全部535条execution_anchor_requests，以精确vt_symbol×trading_date查询原A同SHA SQLite、interval=d的唯一真实日线bar。无真实bar和重复bar明确列出，不能用carry或另一合约补齐。
2. 对anchor.price与真实日线open逐事件比较：保存绝对差和精确/浮点容差一致；按offset、direction（有值时）汇总，并列缺bar/非法价/差异明细。只读价格、日期、订单关联字段，不读取账户权益/收益/事后盈亏。
3. 检查anchor实际物理时刻等原session helper，夜盘归属沿原交易日；不因日线日期相同就把自然日09:00当开盘。
4. 输入文件与源码/协议指纹保存；DB以只读方式访问、拒非空WAL，不修改数据。一次审计，不跑A0/C0，不改变Stage001/002/004已冻结工具。
5. 有意义测试覆盖：精确合约与日期、真实bar缺失/重复拒绝、价格不相同不能判等价、夜盘日期不按自然日误归。输出完整事件检查小表、汇总JSON和异常明细，N/A金融指标。

## 可得结论与边界

即使535条全部一致，也只证明该已接受路径的开盘价格一致；不能直接证明所有新候选、无真实bar、分钟内限价/止损、跳空数量计算或真实成交可实现性。任何将来执行数据表达的改变都要另行预声明共同数据合同、时间可见性和独立复核，不能偷偷把它作为C0第三次缺口回退。

过拟合判断：否，本次全量固定事件只读价格关系，不读收益、不选参。继续价值：是，可以判断哪些分钟要求来自盘中路径、哪些来自同一开盘价的数据表达；若不一致则保留不一致，不为减少缺口强称等价。
