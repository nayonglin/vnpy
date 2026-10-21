# Stage026 冻结日级退出纯adapter与合成probe

- line_id：futures_ai_monthly_pool_generalization；时间：2026-10-20 21:06 CST；局部组件，不是重要收益突破。
- 新增tools/stage026_daily_exit_adapter.py与test_stage026_daily_exit_adapter.py；只写本线产物，不改正式代码、配置、数据库、LINE或registry。
- 先13行为测试，模块缺失见红；实现后暴露两处源RSI诊断字段缺失，再补State.contract/product诊断属性；13测试最终通过。没有手改源AST，实际提取13方法，核冻结整SHA+manifest。

纯组件消费外部已知整数qty、源signal-date age、AM41 OHLC和RSI/前日MA20。严格dynamic→prev2day→layerstop→RSIcontinue→MA优先级；close触发而不是high/low碰障。只返回下一session待执行请求和proposed状态，不生成actual fill/ledger，qty不变；RSI done是待执行候选flag，外部未成交不能直接commit。roll不一致/pending直接unsupported，不静默忽略。原活跃组合heat/forced规则被明确排除为单品种研究delta。

21:05:07新建10合成fixture输出`outputs/stage026_daily_exit_adapter/run_20261020_210507_817251/`，8known decision/2roll unsupported/7queue request，input mutation0，绑定输入输出JSON/方法AST/代码与测试SHA。真实金融回放、成交、60日标签、fit、订单、下载、生产修改均0；权益、收益率、回撤、Sharpe、滑点、交易次数、胜率全部N/A。待独立Stage027复核后由root接纳。

重要前置：调用者须处理C2先后、已排委托、真实日历/分钟和年龄对齐；adapter不认证这些条件。full source entry_date来自信号日而非fill日，不在本组件猜age。没有用future open偷渡为fill。

新增/修改/删除正式参数或回测结果均无。开始/结束新增按真实收益选参过拟合：否，无真实收益扫描；继续价值：是，明确日级决定与可成交标签之间边界；无模型/收益改善证据。调研判断继承Stage021/022的本地源码与官方callback时钟资料，执行细节由冻结源码为准，不把日线参考close当可成交价。
