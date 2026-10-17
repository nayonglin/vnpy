# Stage018 精确completed数据独立复核

研究线 futures_trend_triple_screen。仅审本次新增12945分钟/39会话；没有复连、重试、测试重跑、账户回放或旧数据全量审计。

父进程exit=0、117.012390秒，无硬杀且输入不变；worker/progress阶段均all_target_minutes_completed，worker预算114.597067秒，idle_waits=2、update_calls=4、ready_serial_count=8。35项冻结来源的当前SHA全部匹配，父receipt绑定的6项产物SHA全部匹配。017 manifest仍逐字节相同；原012 collector、017与SDK/auth等冻结输入未改。父子记录零订单/撤单/CTP/金融/原数据写入，原始SDK输出及凭证没有保存。

独立用固定日期和七类品种的交易时段重建本批39个网格：日盘225，普通夜盘FG/MA/SA总345、au总555、cu总465；清明后4月6日目标仅日盘。原始12945行全部唯一、正价且OHLC范围合法、成交量/OI非负，精确等于冻结目标网格；12945条保存的后继证明一一对应，后继至少晚60秒。没有接受各serial的最后形成行。保存文件只有CST bar/successor时间，没有另存provider纳秒serial快照；UTC转CST依赖未改、已审的Stage012 collector，不能把保存后继证明扩大为独立第三方行情真值。

独立Decimal聚合5个会话：强制AP210.CZCE/2022-04-06的225分钟，另AP205/3月28日、MA205/4月6日、au2206/4月1日、cu2204/3月28日。每个会话的OHLCV、首openOI、末closeOI全部与原CSV及冻结参考七字段精确相等。AP210为8888/8942/8696/8884、V218838、openOI118247、closeOI129669；其14:59的保存后继为4月7日09:00。本次不重复全部39会话的独立日聚合；其余会话的生产quality通过及输入SHA均已核。

资格结论：qualified_precise_sessions=39、qualified_minute_rows=12945、required_AP210_accepted=true，限receipt所列精确会话用于研究数据资格。可作为后续显式接入018的Stage016输入依据；本review不构建或覆盖任何base/cache，也不授权金融重放或生产。本次tq_dl布尔仍false但公开serial数据已返回，故不能用该布尔单独断言此接口不可用；不推断017超时的具体触发位置。

累计金融attempt仍4、完成1，C0无alpha结论。过拟合：否，本次修正SDK等待语义且未改变目标或策略参数。继续价值：是，取得受旧source859问题影响的AP210完整替代依据；后续仍需Stage016精确替换/追加及独立资格，不能把本次成功当作全路径数据就绪。
