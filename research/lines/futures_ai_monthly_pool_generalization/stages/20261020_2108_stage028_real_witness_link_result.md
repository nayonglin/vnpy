# Stage028 两个历史参考见证的日级连接结果

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:08 CST记录，实际单次21:06:34 CST；day。
- 是否重要突破：不是模型/收益突破，是从合成组件回到真实来源的连接验证。
- 用户训练源halfR/retry=False、C2保留；正式配置未改。新增`tools/stage028_real_witness_link.py`及3窗口测试；模型/alpha参数新增修改删除无。qty2只为诊断输入，不是最终训练手数政策。金融回测结果新增修改删除无。

## 实际数据与结果

此前已固定的JM/AU条件分钟见证不改源选择；clean DB只读84精确epoch/date键、每事件执行日截至41共同源日完整OHLC。保留source_id、输入/输出/源证据SHA与库stat前后不变检查，不证明全库历史PIT或来源真值。

- JM202201@2021-09-30，2021-10-08入场日按当前C2政策stop参考fill3224.5，连接进入reference flat，不调用普通日级退出。
- AU202112@2021-07-30，2021-08-02入场日已confirm；用冻结AST日级adapter实际返回long_base_stop，收盘参考377.84，只提出next_valid_session_open_required请求，没有fill_price。下一源日2021-08-03 daily.open377.44仅proxy，canonical_anchor_verified=False，不喂实际fill账本或记净收益。
- 正常源时钟首持仓日age=1，因state.entry_date保留signal日；异常延迟/断档未在此认证。RSI6/prevMA20仅用截至本日AM41，输入层extrema沿signal OHLC，未用次日proxy改decision。

## 校验和边界

先写窗口测试见模块缺失失败，再最小实现3项通过，检查执行日截至窗口、不用未来、缺共同源日不偷补、signal与execution须相邻。root全线82项测试通过；实际2事件由独立Stage029再审，不以root结论替代独审。

没有实际交易量认证、完整strategy/source、历史经济PIT、未来session anchor或60日净标签。实际18个C2双触未知仍未解决。本probe不是2笔真实交易或金融回测；fit/下载/订单/生产修改0。权益、收益率、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

本轮源码与官方资料调研判断：C2与普通close决策属于不同阶段；单看stop临时价会错认实际退出，必须保持pending request与actual fill分开。相关官方GitHub/执行资料及本地MRO证据见Stage021/022/023。

开始/结束新增收益选参过拟合否，无参数扫描或收益择样；继续价值是，真实来源接口已检出并防止时钟混记，但不能以两个条件点外推泛化或模型更好。证据`outputs/stage028_real_witness_link/`，独审另Stage029。
