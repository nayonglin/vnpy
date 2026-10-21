# Stage023 独立品种实际成交账本合同

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 20:57 CST；结果前协议。
- 范围：继续Stage020完整标签源的经济记账组件，消费外部已识别的实际fill，不生成fill或交易信号。普通日退出次session open与入场日C2分钟fill由各自执行合同提供，不能用decision临时价代替。
- 本研究source halfR/retry=False、C2保留；正式配置不改，无正式A/C、模型拟合、真实源金融回放或生产变更。

## 固定经济合同

1. 单产品、同一方向的独立episode；显式open/close tape支持整数手部分退出，以及旧约清空后新约显式重开。换月新价/新乘数不重设分母；不自动搬移持仓或猜新约数量。禁止多个合约并存、未平先roll或重复普通entry。
2. 首次actual entry与signal stop形成signed初始R，必须正确侧且正；risk_currency=R_price×首次历史乘数×初始整数手数，整个episode不变，不用abs/minrisk抬高。换约收益使用各自entry与乘数，不把连续合约价格跳差算损益。
3. 每笔fill带规范trading_day与contract；不由自然日期推断夜盘交易日。close_today按该lot entry trading_day是否相同区分，FIFO扣减；超量close拒绝，正有限价格/数量/乘数/tick验证。此组件不认证canonical session、真实tick路径或历史经济PIT。
4. 费用显式输入open/close/close_today的per-lot与turnover rate，可共同非零；缺失任何实际所需费率则fee/net未知，不默认0。显式0是允许真实零费，不与缺失混淆。按fill价×multiplier×qty算turnover，不把双边费再乘2；每个fill独立计费。
5. 另列每笔slippage_price×multiplier×qty（非负），代表fill价之外的显式成本假设；已经内含在fill价中的滑点不可重复提供。缺失则净值未知。无默认成本寻优。
6. 已实现gross、未实现MTM、commission、extra_slippage、net和各自R分开；期末mark不是平仓，不产生exit fee，不使unrealized变realized。open手数、部分close、roll tape均保留，不按当前仓位合并历史。
7. metadata含历史有效性标志。即使数字可算，只要资料非历史PIT验证，结果标conditional_economics；不包装成成熟60日训练标签。metadata价格/数量非法抛错，合法但成本缺失保留经济未知。

## 验证与独审

先写小测试见红再实现Decimal记账。预声明：多空、整数部分平仓、平今/平昨、固定初始R、换约不同乘数、不计价差、未知费用与显式0、期末mark非强平、非法/超量/反向/未平换月拒绝；固定合成tape只作经济机制验证，不是策略绩效。实现后独立agent以手写Decimal复算所有tape并查逻辑、数据与边界；实际结果另Stage024。

调研：本轮重新检查[VeighNa官方回测源码](https://raw.githubusercontent.com/vnpy/vnpy_portfoliostrategy/main/vnpy_portfoliostrategy/backtesting.py)的成交/逐日损益分离，并以本仓库实际Stage847→Stage827→Stage502调用链确定执行时点；[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)只作通用成交语义参照。判断：不能以临时decision价记已实现净收益，更不能让缺费用变免费交易。

开始过拟合：无新增按真实收益选参，检查固定经济恒等式；继续价值：是，成本与roll会改变跨品种标签次序。权益、收益率、最大回撤、Sharpe、滑点总额、真实交易数、胜率均N/A；无真实市场回放/fit/标签/下载/订单。
