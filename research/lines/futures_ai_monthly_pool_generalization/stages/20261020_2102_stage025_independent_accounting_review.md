# Stage025 独立 fixed-R actual-fill 账本复核

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:02 CST；day。
- 独立 reviewer；研究源 halfR/retry=False、C2保留；正式代码和配置未改。

9条合成tapes/15笔fills，手写Decimal oracle与产物snapshot/tape逐项一致；386独立断言0失败，8原单测通过；15非法事件拒绝且深拷贝状态不变。SHA核实runner、组件、fixtures、results与summary；无剩余P0/P1/P2。非重要收益突破，新增复核产物只位于 outputs/stage025_independent_accounting_review/。

覆盖平今/隔夜部分退出、short方向、乘数变化显式roll、初始currencyR固定、合约价差不生利润、mark不收假想退出费、unknown不填零和显式zero、比例费用及每笔tape复算。额外确认缺平今费不替换为隔夜费用、旧roll平后未新开可mark、mark不产生fill或费用。

仅可接纳为actual-fill accounting primitive。调用方还须认证同产品roll、时序/session、真实fill和历史经济；historical_validated=True只是声明，1合成validated不是真资格。extra_slippage是显式额外成本，不重复扣已在actual fill中的同一滑点。组件不产生策略/执行/60日标签。

本次模型/alpha参数新增修改删除0，金融回测结果新增修改删除0；权益、收益率、回撤、Sharpe、总滑点、交易次数、胜率N/A。真实金融回放、fit、净60日标签、下载、订单及生产修改0。开始/结束新增收益选参过拟合：否，只有合成算术与不变量；继续价值：是，但完整日级决策/next-open tape生成、C2未知路径、历史经济仍需后续补齐。没有证明模型预测力或收益改善。
