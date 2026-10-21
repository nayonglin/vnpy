# Stage315：整数预算实验执行中止，不作收益优劣结论

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 02:41 CST；分支`codex/ai-training-data-expansion`；非重要突破，非正式A/B/C。
- 决策：关闭311–314这一个冻结数值实现包；预算机制的经济价值**未评估**，不以技术失败否定alpha。完整用户目标仍active。
- [机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage315_joint_integer_budget_decision/decision.json)；[独立审计](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_0240_stage314_joint_integer_failure_review.md)；[唯一实际终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage313_joint_integer_cash/actual_run1/actual_terminal.json)。

## 本轮做了什么

311在实际前冻结303/310提出的同批整数分配政策。复用原纯COMMON52同K的4365信号及原score，0重训、0信号重算；仅在原共同scale<1且至少两个accepted family时，以净R×窄R元值代理同时分配整数手数，原风险/保证金/容量/F0不改。312新算子+3组tiny、313新adapter+2项tiny，314独立静审后root授权一次actual。原核不是先到先得bug。

新增参数是该分配政策、δ=1e-6元保守格网及固定solver/字典序规则；原策略风险/止损/特征参数0修改、0删除。新u整数冻结额不同于旧实数缓冲，会改变D减量，因此本包不等于纯score因果效果。实现、源、协议、runtime及所有binding已在311/313/314闭包，不重复旧训练或四控制。

预定100万初资，2020连续/2023独立空仓×base/stress，至2026-10-16；两stress权益严格更高、DD严格更浅才支持探索，base描述，固定252块/2000次配对CI。该门未进入可评估状态。

## 实际终态与精确矛盾

actual于02:35–02:36执行，2.681463秒、exit1。四本上限，启动1本（2020base），完整完成0本，另外3本未启动；新fit0、SQL0、旧控制重放0、retry0。累计完整仍453fit/246cash，另记本次1个不完整尝试，不虚增为四本回测。

失败audit共366批，365完成/1失败；73次整数触发含72次完成。最后u为2021-07-06，变量EB/J/JM/PG/HC/RB，UB=[4,0,1,1,3,3]。主解及前两lex步骤已留下k=[0,0,0,0,3,0]，后续lex3却返回status2不可行。314以纯Python整数穷举320组合，37可行，该k是唯一主目标最优且lex最大，固定前3前缀仍恰有一个可行点。风险grid 1,367,439,852≤12,349,148,051，保证金35,587,200,003≤44,646,109,249；并非数学无解。尚余9.99秒、累计nodes1，不是算时或节点耗尽。具体底层presolve/容差/接口原因未定位。

按311预定fail-stop，停止并保留现场，不换solver、精度、tie或gap补跑。本报告未以部分日期权益充作全周期结果。

## 独立复核、数据与置信度

314收据SHA `c078daded9daf999c7126088c0ee77334cded0f19bdf5b21853186261e887084`：review completed、执行core blocker1、source arithmetic blocker0、review check failure0。399条已accepted信号原字段与157完整4365 tokens对齐；全部73整数问题的Decimal系数/UB和保守预算重建一致，单位费滑独算最大误差0；46个full-upper解析证据、19个零UB步骤、107份已接受MILP证书算术通过，前72个应用批次的未量化/float预算均未超限。前序最优性仅核保存dual证书，不冒充全表另一个求解器证明。最后320枚举只是失败现场数学复核，不是新的金融回测。

108份solver options缺node_limit字段；冻结源码确有共享剩余节点参数，缺日志不能证明没传入，具体突变原因未核。原值保留，不为元数据修补重跑。运行环境Python3.11.5、Numpy2.2.3、SciPy1.17.1由root授权绑定。

失败函数未返回完整daily/fills/closed/open/positions账本，不能独立重建own-state全路径及D执行，也未重新读取旧大mother/价格/标签做资格认证。这里只验证保存的u状态与预算/信号算术；不夸称端到端已通过。

| 要求指标 | 本轮新版本结果 |
| --- | --- |
| 期末权益、总收益、最大回撤、Sharpe | N/A，未完成整本账 |
| 总滑点、费用、交易次数、闭合净胜率 | N/A，未产生完整金融账本 |
| 年度、family归因、配对CI | N/A，不借旧控制数据填新结果 |
| 双stress晋级门 | 未评估，并非失败/通过的经济证据 |

## 调研判断与下一步

[SciPy官方milp](https://docs.scipy.org/doc/scipy-1.17.0/reference/generated/scipy.optimize.milp.html)是double数值接口；作者[SmartPredictThenOptimize](https://github.com/paulgrigas/SmartPredictThenOptimize/blob/master/README.md?plain=1)支持预测与决策层分开验证。这些资料只支持机制设计和数值边界，没有证明中国期货alpha。当前实际矛盾进一步说明不能把solver状态当无条件精确真值。

接受[316独立价值审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261020_0237_stage316_historical_search_value_no_go.md)：它未读本轮任何结果，已按原始论文与维护者GitHub判断，当前没有足够具体新信息支持再加一个弱同史包。453+246不是独立试验数，不能机械算过拟合概率；反复用过的2020/2023及held窗口也不能因换fold重新成为未见测试。[作者回测研究协议](https://people.duke.edu/~charvey/Research/Published_Papers/P138_A_backtesting_protocol.pdf)支持重视整个研究选择过程，这里不计算PBO或宣布一切AI无效。

下一步317只盘点并冻结现有最少纯52模型/scaler、因果特征/156157规则、日历/经济与资金核的真实闭包；不把157历史信号缓存当未来生成器。随后只观察冻结之后才完成的交易日；冻结前已发生但晚取的数据仍是历史。当前不宣称未来自动化、完整PIT或生产ready，不新建策略臂或调度。

## 开始与结束反思

- 开始：一次固定预算机制有价值，但同史持续择题风险为是，未假定提高利用率必然提高收益。
- 结束：本次无金融结果救参，不能据技术失败判断优劣；本冻结数值包继续修补/重跑价值不足，关闭。完整研究目标继续有价值，下一证据应来自事前冻结后的未来，而非继续在相同历史中挑新低维函数。
- 当前正式策略/风险、生产资格、增加投注均无新授权或晋级；目标未完成。日常记录留本线，未追加根总账或推送Git。

## 2026-10-20 02:48 CST：下一步准备验收

317已确认portable和scaler小状态齐全，模型实际为26原值+26 missing flags，可不重训恢复。318最小观察设计获root接受，见[实施范围](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage315_joint_integer_budget_decision/forward_preparation_acceptance.json)；下一步只实现原因果-u薄生成器/接收时钟/连续paper状态，并做最多3组必要tiny，0新fit或历史cash。317/318均0实现/fitcashSQL，不是未来生成器已完成。真正T0须等代码、输入时点与初始状态一起冻结另签；311、315及318写稿时间均不启动forward时钟。
