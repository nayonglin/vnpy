# Stage013 实际新增日线有限独立复审

结论：通过，P0=0、P1=0。**只接受`qualified_daily.csv`内4500个精确合约/目标日作为研究日线参考**，不是4502目标全部成功，也不把94份raw的其他历史日自动资格化。2条无后继拒绝与16条无真实日线carry排除保持。

独立对4500条全量核查：身份唯一、属于冻结4502目标集合、七数值有限且OHLC合法/量仓非负、tq与vt合约对应、原ns经UTC转上海后匹配trade_date及保存时间；后继必须同时id更大、ns更晚，且逐条与target_qualification记录一致。OHLCV及openOI对固定preflight DB参考逐条比较，六字段最大绝对差全部为0。没有重新查询DB或改变OI映射。closeOI只由provider字段提供，DB closeOI始终N/A，不能声称DB也验证了它。

4502条qualification与冻结target一一对应，True集合恰等4500条qualified集合。仅以下两条False，原因均为`no_forward_successor`，不改门、不重试：

| 合约 | 目标日 | 处理 |
| --- | --- | --- |
| fu2605.SHFE | 2026-04-30 | 快照最后有效日无更晚合法后继，保留拒绝 |
| fu2609.SHFE | 2026-08-31 | 快照最后有效日无更晚合法后继，保留拒绝 |

独立只解析4份raw快照：旧到期AP005、活跃AP701、上述两个拒绝合约。接受样本对应原id/ns和七字段逐值相同，保存的后继在同一快照中真实存在；两个拒绝样本确实找不到更大id且更晚时间的有效行。94份raw的声明SHA与已钉住parent/symbol receipt逐项绑定，但没有全部重读/重算其历史，不能称为94个完整快照独立全量再资格。

冻结target/excluded/preflight/qualified/qualification/parent/worker等小产物SHA匹配，15个原输入当前SHA均未变；没有新增网络、TqSdk实例或账户运行。原parent仍exit1、`worker_terminal`、all_inputs_unchanged=true；worker仍`completed_with_target_rejections`。94/94快照已采集，耗时251.747866秒，峰值RSS488,620,032字节，BT/order/cancel/CTP/金融均0。新的独立子集资格不改写原部分拒绝结论。

本次只允许Stage015按这4500条已接受目标引用日线参考；拒绝目标、16条carry和3个旧分钟冲突仍单列。Stage015还需另行增量验收分钟session，不能用raw或“94合约已采集”自动填资格。原CSV、DB、base、策略及既有OI口径均未改，C0_attempt3、fallback和生产未授权。金融attempt累计4、完整1，C0 alpha不可评价。

过拟合判断：否，目标预先固定，未按收益挑数据或救参数。继续价值：是，4500条已证实日线参考可以推进原缺CSV分钟的独立资格；不因2条末日拒绝而改规则。调研沿用Stage013官方API/原导入器合同，本复核只新增本地实际数据证据，没有联网事实查询。
