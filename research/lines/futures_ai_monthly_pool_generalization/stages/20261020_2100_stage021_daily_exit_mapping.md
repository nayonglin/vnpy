# Stage021 完整日级退出/配置继承与执行时钟映射

- line_id：futures_ai_monthly_pool_generalization；时间：2026-10-20 21:00 CST；非重要收益突破。
- 变更仅为只读证据输出：`outputs/stage021_daily_exit_mapping/README.md`、`contract.json`、`bindings.json`、复现检查脚本。未改策略、正式配置、数据库、LINE或registry。
- 20文件SHA、43函数AST绑定，36相同/7变化；配置用AST字面量/继承链静态追踪，不调用文件生成build。

确认正常持仓先当日close更新动态stop→prev2day→layer stop→组合退出→RSI partial→MA20。stop只以close触发且close是事件参考价；实际Stage847引擎继承ConfirmedDailyNextRealOpenEngine，日级委托在下一session open撮合，绝不能称当日stop价成交。RSI partial触发continue，会跳过当日MA退出。alignment/reverse/adds均关闭，阶梯锁盈、ATR14中点、prev2day、RSI95/5和MA20开。

继承C3 pressure040组合heat与force95→80保证金降杠杆确实有效，不能按基类默认False误报关闭；隔离单品种固定风险源删除它们是实质目标delta。roll是delay5、target history、shape+MACD同向、先平再判重开、按allowed缩量，不能用简单连续价格拼接代替。当前/冻结普通日级方法大多同AST，但on_bars结算、trade同步及Stage827执行已有变动，二者整源不等价。

本次训练profile只关闭halfR/retry，C2保留；正式halfR/C2不变。未来标签的pending action、next session open、roll两腿、分数RSI/整数手差异仍须显式合同和覆盖证据，不能把局部gross MTM当60日净标签。

新增/修改/删除策略参数和回测结果均无；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。真实金融回放/fit/下载/订单/生产修改均0。

开始/结束新增按真实收益选参过拟合：否，无真实收益试算或阈值扫描；历史选择偏差仍在。继续价值：是，避免把当日close参考退出误标为可成交，并揭示须剥离的账户退出依赖；未证明模型/收益提升。完整参数、函数行/SHA及后续delta见输出README/contract/bindings。
