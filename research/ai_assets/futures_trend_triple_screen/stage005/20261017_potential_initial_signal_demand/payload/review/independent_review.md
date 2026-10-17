# Stage005 限定独立复审

结论：在固定原策略纯信号接口、原实际参数及既有数据的范围内，语义审查和小样本复算通过；P0=0、P1=0。接受为**潜在即时初始信号及首日 session 需求表**，不能作为完整账户需求证明，不能授权 C0_attempt3、价格 fallback 或生产使用。

本次未运行金融引擎、未重新枚举1786个指标批次、未重算周表/A0账户、未重新验收旧分钟数据、未下载。新金融 attempt=0，原累计4次 attempt 中仍只有 A0_attempt2 完整完成，C0 alpha 不可评价。

## 方法与身份

`__new__`仅创建原策略方法容器，套用A0记录的 actual settings，无`strategy_engine`或`states`。每日真实批次先更新全部metadata合约的AM，再按当日mapping检查目标真实bar与AM暖机；非主力历史继续积累，目标缺bar不从carry生成flat信号。2019-06-01 preload经原函数核对一致。原vendor的warmup/trading分段没有重置AM、没有重复处理分界bar，2020前不进入本阶段事件集。

动态核对实际C9继承链及Stage001研究wrapper：`_generate_signal`、`_build_history_df`和递归`self`调用的其余10个helper，均与base同一函数对象；继承链6个项目源码SHA同时匹配A0实际运行provenance。因此直接base调用在此纯接口范围内等价，没有漏掉子类信号override。它不意味着可省略账户初始化、环境门、AI池、手数、持仓与排序规则。

## 独立小样本结果

只读329条精确合约真实日线，按最后41个观测重新喂原ArrayManager；另查历史观测数，未用连续全历史EMA替换AM41。

| 哨点 | 结果 |
| --- | --- |
| rb2005 2020-01-08 | long_case3，150个历史观测；周反向阻止C0 |
| AP005 2020-01-09 | short_case2，151个历史观测；周同向许可 |
| ru2005 2020-01-10 | long_case2；周unknown保留，下一全局日01-13，物理首分钟01-10 21:00 |
| hc2010 2020-09-01 | long_case1a；09-02新主为hc2101，需求仍属于hc2010 |
| CF201 2021-09-23 | short_case2；周unknown保留 |
| sp2701 2026-10-14 | short_case2/open_interest_surge；无下一批次，terminal_pending不生成session |
| rb2005 2020-01-07 / AP005 2020-01-08 | 两个已暖机真实窗口均无信号，事件表没有对应行 |
| lc2401 2023-07-21 | 仅1条真实bar，AM未暖机，没有初始事件 |

6个正信号的signal/risk_mode/窗口首尾价格/历史count/下一metadata全局批次日期全部匹配；抽取6条已冻结周状态核对ready/direction，无周特征重算。5个精确session缓存join的expected/available/missing/anchor/complete及物理首末时间与原helper相同。只继承Stage004有限语义及8会话独立审查，不把继承变成全量独立重验。

现有输出表的有限算术核对：900 raw事件、701 C0许可（其中143 unknown均保留）；1个terminal_pending。899 raw session中483缺口、156831缺分钟；700 C0 session中378缺口、124772缺分钟。原A0只读date/product/contract/signal四身份列，886/886都是事件集的子集。17个跨mapping变更边界保留信号原合约。以上均不是实际开仓/成交或收益指标。

## 必须保留的范围限制

已知C0失败的rb2010 2020-05-18和2020-08-12，均**不在Stage005即时初始需求集合**。原`run_failure`保留缺anchor错误与日期，但没有offset/order来源；两个`engine.log`均为0字节，minute_requests为空。因此不能断言这两次缺口一定是平仓、换月或某类OPEN，只能证明初始需求表不足以覆盖已经出现的实际新路径。

本表不包含延迟初始需求、现有仓位退出/加仓、换月重开或其他遗留订单闭包；独立B的新信号也不能由C9集合替代。即使补齐700个C0首日session，也不能由此批准账户再跑。local candidate paths仍只是路径库存，尚未读取/验收payload，不能计作已补齐。

历史策略选择风险仍然存在；本次过拟合判断为否，因为只核固定源码、身份、因果时点和数据需求，没有按收益挑参数或事件。继续做数据需求闭包有价值，可减少逐缺口金融重跑；继续做收益参数寻优目前没有新的可接受证据。

调研与判断：沿用Stage005预声明中的Backtrader官方次bar说明和GitHub broker源码背景，本次关键证据来自本地已接受C9、原ArrayManager、vendor时序、Stage502 carry边界和只读SQLite哨点；未新增需要外部验证的市场事实。置信度限定于已见历史、静态接口与9个真实窗口，不能泛化成OOS alpha结论。
