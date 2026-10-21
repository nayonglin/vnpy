# Stage030 日级规则、实际fill账本和历史连接接纳

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:10 CST；day。
- 本轮不是收益突破。新增单品种研究组件与真实来源连接，未创建正式A/C或训练臂。
- 用户授权仅训练源halfR/retry关闭；C2仍保留，正式配置未改。

## 接纳的事实与实现

1. Stage021/022分别静态提取配置/MRO及成交财务链：普通stop只按D.close判断，动态stop以完成D数据更新；请求到下一session实际open才成交。低高触碰或`execution_price_override`不能替代该时钟。源provisional realized和actual tape也不能重复记账。
2. 活跃组合heat/forced规则、共享资金/槽位、原streak等依赖在单品种新源中排除须声明为研究delta；不是整个正式C9源码等价迁移。冻结与当前完整财务/执行有差异，不能仅因信号或局部AST一致说整体一致。
3. Stage024实现固定初始signed currency-R、实际fill费用/部分平仓/roll经济组件。9合成tapes/15fill独审386检查通过，15非法事件拒绝且状态不变；8测试通过。只消费外部已识别fill，不认证其来源、同品种映射或历史经济PIT；显式0与缺费用区分，缺成本/mark则净值未知。
4. Stage026从冻结m0008提取13方法AST，严格dynamic→prev2day→base→RSI partial continue→MA，RSI整手语义保留。只提出nextsession请求与proposed状态，qty不改、未执行；roll显式unsupported。作者10合成fixture、13测试；独审68手写挑战、2715检查通过，无未解决P0/P1/P2。
5. Stage028实际21:06:34单次连接两既有历史条件分钟见证，只读84精确日线键、各执行日截至41bar。JM reference C2stop后flat，不进入普通日级决策；AU confirm后日终base stop排队，close参考377.84，下一源日open377.44仅proxy，未记fill、PNL或净标签。
6. Stage029独审逐键SQL、source_id、SHA、独立Wilder RSI6/MA20及AU具体触发分支，1086检查0失败，3窗口测试通过。qty2仅诊断，source age1依正常signal-date/nextsession条件；2点不外推全市场或真实执行资格。真实18个C2双触未知仍未解决。

root全线82项测试通过。新增/修改/删除模型与正式alpha参数无；新增研究经济字段、adapter与连接工具，未删除不利金融结果。权益、收益率、最大回撤、Sharpe、滑点总额、交易次数、胜率均N/A；本轮完整真实source金融回放/fit/净60日标签/订单/下载/生产修改0。

## 下一步具体门槛

将已验收组件连接为完整逐日driver，明确pending request与actual position不同状态，先结算上日pending actual fill，再处理入场日C2和本日已完成数据的退出。若普通开盘anchor或C2先后未知，则保留未知/分支；不以daily.open代理冒充真实fill，不把已排退出当已经空仓，不据未来覆盖删候选重排。

换月需要独立旧/新contract target、delay5与shape/history条件、old close/new open及各自新entry C2；不能以固定epoch持有自动替代。标签终点须预声明D60 MTM或D60决策/D61退出，两者成熟门槛与成本不同。初始qty/归一化政策尚未因本次qty2诊断选定；单手RSI no-op不能偷偷改成半手。

费用数字即使可算，静态资料仍保留conditional状态；不能为早日fit把费率缺失当0。完整driver、来源/经济可观察性和候选宇宙合同过关后，再生成成熟/未知标签状态并决定训练。现有组件已超出单纯合成测试，但还不是完整训练源。

## 调研与反思

本轮已重读[VeighNa官方GitHub回测实现](https://raw.githubusercontent.com/vnpy/vnpy_portfoliostrategy/main/vnpy_portfoliostrategy/backtesting.py)和[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)，结合本地实际MRO与冻结AST判断：信号参考、pending委托、actual fill及MTM必须分别处理，不能用通用撮合资料替本地实际会话认证。

开始/结束新增按真实收益选参过拟合：否；未扫描真实收益、调整阈值或按表现选两个事件。既有分钟覆盖选择和历史资料偏差仍存在。开始/结束继续价值：是；本轮把日级规则和经济记账落到实现，并回到真实输入检验时钟，但尚无模型预测力或收益提升证据。

研究记录在本线；root仅改LINE和registry本线行，保留其他并行工作，不追加根历史总账、不暂存提交、不部署。
