# Stage067 两个后续C2事件：统一分钟输入复核

2026-10-20 23:08。不是重要突破版本；只修研究数据覆盖，不修改策略、055、旧058或旧117分钟manifest。

对Stage064提出的OI202301/2022-08-29和SH202605/2026-03-16，一次读取全部6个小CSV（4,742,440 bytes）及一个SH605 SQLite native projection。六个CSV当前rawSHA均与原056和064冻结清单相同。使用055完整reference_grid及056原逐来源资格函数，不补timestamp、不拼provider，不根据C2或收益筛选。

全部7个components：2通过、1缺格、4在参考会话内无行。两个通过输入各345分钟，均来自tqsdk_stage462_completed_preclose_full_dates_shard；分别覆盖2022-08-26 21:00→2022-08-29 14:59、2026-03-13 21:00→2026-03-16 14:59，保留休市间隔。exact epoch年月与vendor orderbook、native实键、上市退市日期绑定，当前clean日OHLC和首分钟open一致。SH Stage506只有225分钟，缺前夜120分钟，拒绝；SQLite该日无行。身份并非依靠CZCE短码猜年代。

qualified_inputs_manifest.json只含两条新输入，可供独立复核后root与旧117并集。每条保留source_id、rawSHA、provider component、完整grid hash、055 SHA、cleanOHLC与firstopen。manifest SHA为0dcbdb62a302a1e389d437f7fba26213f23cf7c25c44e46dbbc99e017ff1e1eb；旧117 SHA仍为20e79f62c937537cd91b9458cb153bc78d11be1d79f2cdc016a36a47b6a1ce46。物理session、broker、PIT和usable_for_trading均未认证；这是conditional reference输入，不是实际anchors或C2结果。

3项本线TDD红→绿；核对source/file哈希、未知候选保留、同内容source不丢失。完整line单测结果另记verification.json。未算C2结果、未回放全60日、未fit、未改标签、未下载。收益、权益、回撤、Sharpe、交易次数、胜率、滑点：N/A。本次新增模型参数0、修改0、删除0。

调研沿用协议内VeighNa维护者GitHub和Backtrader官方执行语义：输入bar合格不推出实际成交先后。判断新增收益选参过拟合否，因为统一检查所有候选且不读结果；继续价值是，因为确实补到两个后续阻塞输入，但完整窗和模型质量必须另审，不承诺改善。

代码：tools/stage067_followup_minute_input_audit.py；独立输出：outputs/stage067_followup_minute_input_audit/；暂不改LINE/registry。
