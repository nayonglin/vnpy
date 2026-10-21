# Stage028 两个已绑定历史分钟见证的日级决策连接协议

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:05 CST；结果前。
- 只消费Stage014已通过逐来源条件检查的JM/AU两个参考观察，不重新选择provider、不扩大覆盖、不改两事件之外的未知状态。当前C2见证是参考policy而非真实交易/来源真值。
- 本probe只做执行时钟/接口诊断，不产生金融绩效、实际交易量或60日标签；外部整数qty=2只为固定诊断输入，不宣称正式手数或选定新源最终position policy。

从绑定clean SQLite只读获取两合约各执行日截至41共同源日完整OHLC及signal日H/L；不拼合约、补缺bar或用未来AM。绑定各source_id并保持库stat不变。同步实际reference entry和signal-date初始stop/extrema；正常next-session首持仓日age=1是已有源码时钟，非假定实际fill当天age0。异常延迟/缺交易日不在本probe认证。

JM已按当前C2 adverse-ties政策stop，进入flat分支，不再对已平持仓调用普通日退出。AU已confirm解除C2，才将reference层交冻结AST单base日级adapter，观察动态stop→prev2day→base→RSI→MA的实际decision。RSI6与prevMA20从AM41本日及过去数据算，不用未来开盘修改decision。

若读取下一共同源日同epoch daily.open，仅命名next_open_proxy，canonical_anchor_verified=False，绝不喂实际fill账本/记净收益，不把它当待成交订单已完成；没有next proxy时保留缺失。已有分钟见证只覆盖entry session，不转授次日资格。输入/输出绑定并独立复算，测试避免未来窗口、缺日偷补与首/次日混淆。

开始新增真实收益选参过拟合否，两个目标按此前固定source资格选择，无收益筛选；继续价值是，将局部合成组件回到真实来源检查状态连接与时钟，仍不外推全市场。
