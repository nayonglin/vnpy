# Stage024 固定初始R与实际成交记账组件结果

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:05 CST记录；实际probe20:59:32；day。
- 重要突破：否，经济机制与输入边界进展，无模型/收益突破。
- 新增`tools/stage024_fixed_r_accounting.py`、runner及8测试。仅消费外部实际fill，不生成fill或完整source。
- 新增研究字段：open/close/close_today各per_lot及turnover rate、extra_slippage_price、历史有效性声明；模型/alpha参数新增修改删除均无。回测结果新增修改删除无。

9条预声明合成tape/15fill，3 economic_unknown、5 conditional、1显式zero且declared_validated测试分支。首笔signed currency-R固定；整数部分退出、平今/平昨、roll两腿和不同合约乘数分别入账；无连续约价格跳差盈利；mark非强平；缺费用/slippage/mark不填0。禁止超量、错合约、未平先roll、重复entry、不合法tick价格和反向初始R。

真实经济资格不由调用方一个validated布尔值认证；同品种roll身份、trading_day会话、实际fill和历史经济资料必须由上游证明。当前只支持单层一次完整entry，不是通用broker多partial fills或多层账户账本，也不处理决策状态/信号。

先测模块缺失失败，再实现，8项测试通过。独立Stage025对全部snapshot/tape/SHA手写Decimal复算386检查0失败，另15非法事件拒绝且状态不变，未解决P0/P1/P2=0/0/0。当前证据见`outputs/stage024_fixed_r_accounting/`与Stage025。

调研/判断：官方vn.py actual tape/MTM分离思路与本地Stage847延迟撮合时钟要求使用实际fill独立记账，不能把provisional realized加两次。本轮Stage021/022已核源码及官方GitHub；不从通用撮合文档推导本地历史资格。

权益、收益率、最大回撤、Sharpe、总滑点、交易次数、胜率N/A；真实源金融回放、fit、净60日标签、下载、订单和生产修改均0。开始/结束新增真实收益选参过拟合否；继续价值是，经济部分为完整标签源所必需，但尚不能训练。
