# Stage301：固定风险 log 目标复议，原单位不等价且已有直接实验，NO-GO

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 01:58 CST。
- 性质：只读科学可行性与历史去重；非重要突破、非正式A/B、非实现或actual授权。
- 本阶段0 SQL、0标签/大表/NPZ/行情读取、0训练、0现金、0下载、0源码实施；未读296模型/gamma或297任何新成绩。不改LINE、registry、旧source、正式或生产。
- 开始判断：同史反复更换目标存在过拟合风险；核实单位、数学对象及历史是否已做，值得继续。不能把研究范围预设成仅允许新外生数据，也不能因不存在唯一最优参数而否决一个可固定的政策实验。

## 结论

**本提案NO-GO，不追加6fit/4cash。** 原式 `log1p(0.0025*net_R_stress)/0.0025` 确实表达凹效用偏好，但原first-exit净R与当前资金风险分母不完全一致，不能硬称继承了账户0.25%风险的增长目标。更实质的去重发现是：098已经指出这个错配，099—103已用含成本预算校正后的共同量，实际完成固定线性L与log曲率G的4fit/8cash反证，并关闭该固定log代理。不是今天才找到一个未验证的目标方向。

此结论不宣称全部效用目标、所有新规则或所有后续数据上的log学习均无效。它拒绝的是在未提出独立决策对象或新机制的情况下，把相同f、相同log曲率换成六折或新动作母体再做一次。本次没有新参数、预算或下一包实施设计。

## 有界一手调研

本次共2个搜索query、2个原文页面open尝试，至此停止：

1. [J. L. Kelly Jr., 1956, A New Interpretation of Information Rate，Princeton转载原文](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf)，成功读取10页原文。其增长量基于实际财富的连续乘积；论证需明确下注与复投机制。一般情形明确采用独立符号/噪声，结论末尾也限制比较策略范围。它没有证明本线逐事件加权标签等于重叠期货组合增长或控制峰值最大回撤。
2. L. Breiman, *Optimal Gambling Systems for Favorable Games*，搜索核到Fourth Berkeley Symposium原论文身份；[原文PDF链接](https://citeseerx.ist.psu.edu/document?doi=83aff2f65e86a55ce6f1bf457a8b74274e6ec8c7&repid=rep1&type=pdf)本次open超时，未取得全文。不得将其当成已核证明，也不追加页面补额度。

调研判断：log偏好有原始理论动机；具体增长解释必须从本地实际资金映射推导。这里不需要新优化器或Kelly手数实现。098已有作者论文/代码调研，本次不重复拉取GitHub或以社区代码替代原始理论。

## 1．原净R分母与资金risk_per_lot：不一致

直接静读最小源码，而非推测列名：

- [129标签定义](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:246)：`R0_points=.25*N`；251—258行分别存储 `cash_risk_unit=.25*N*M` 和由现金核产生的含成本 `stress_u_risk_estimate_per_lot`。332—342行的净CNY已扣双侧费用，滑点已在成交价内，`net_R_stress=net_pnl_stress_per_lot/(.25*N*M)`。净利润含费，不代表分母也含费。
- [070单位风险与预留](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage070_policy_kernel.py:42)：`risk_per_lot=.25*N*M+roundtrip_fee+buy_slippage+sell_slippage`；55—71行按 `SINGLE_RISK*equity/risk_per_lot` 算连续手数，再共同缩放、整数化。
- [131当前核继承](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:12)：绑定并继承070；152—161行在D开盘重算单位风险、只减手数，持仓保存该含成本风险。另有容量、资金、family占用等约束。
- [既定风险政策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage042_cross_session_experiment.py:30)：`SINGLE_RISK=.0025`，不是本次拟合或搜索所得。

令 `d=.25*N*M`、`C=stress净CNY/lot`、`y=C/d`、`c_u=u时点双侧成本预算`。即使暂时去掉联合约束与整数手，实际连续计划回报也是

```text
q = f*E_u/(d+c_u)
q*C/E_u = f*a_u*y，a_u=d/(d+c_u)
```

而原式 `log(1+f*y)` 对应 `q=f*E_u/d`。两者只有成本为零等特殊情况下才相等，不满足本任务要求的完全一致。D重算、联合缩放与整数化又使实际有效份额依路径变化；不能把未来实际q或equity塞回训练标签来伪造对齐。

**f=.0025可以合法地从政策继承，完全不必先证明它唯一最优。** 错配在经济量及资金映射，不在“没有最优f”。若仅将原式宣布为人为效用，它可在数学上成立，但失去“当前资金份额直接对应财富因子”的解释；修正后正是已做过的098—103对象。

## 2．定义域、成熟与删失：不能预判失败，也不能宣称识别了未来增长

原式要求 `y>-400R`；`y=-400R`为负无穷，低于该点不是实数log。含成本校正量z则要求 `1+.0025*z>0`。当前没有读取全Y，故**不声称六折实际出现或不存在越界行**。129的有限净R检查不等于这项严格正财富检查；极窄止损和long-only也不保证跨gap损失的R下界。

若这是一个尚未做过且另获授权的有限代理实验，固定f后可事先规定：任一原成熟训练行非正财富因子/非有限效用即整候选fail-stop，不能删行、clip、加epsilon、换f或只保留可定义子集。这是可固定的可证伪规则，定义域未知本身不是反对一切实验的充分理由。本阶段不为它扫描Y，更不新增这一实验。

[130原成熟域](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:60)要求自身 `closed_complete_bar_model`、`u<cutoff`、`label_known_date<cutoff`、原净R有限；held按原family哈希排除。144—148行保持原family区间唯一性→equal-u权重及训练尺度。因此该目标只能表示原加权成熟域内的效用条件均值，不能自动识别全部机会、自然发生概率或资金占用分布的效用。

长持有右尾可能在cutoff尚未成熟，价格/经济unknown也可能非随机。log变换没有补回它们，未成熟/open/unknown不能填0；前向也不能按未来是否闭合、log是否有限来筛身份。即便有限训练样本全在域内，也不能推出未来财富因子几乎处处为正或负log尾可积。删失与尾部未知阻断的是无条件增长/生存结论；它们不构成“任何条件效用代理在逻辑上都不可研究”的定理。

## 3．真实偏好内容、组合限制及历史去重

本式不是单纯换单位：`U'_f(y)=1/(1+fy)`、`U''_f(y)=-f/(1+fy)^2<0`，一般 `E[U_f(Y)|X] != U_f(E[Y|X])`。虽然每条已知Y的正负号/顺序不变，学习其条件均值可以产生不同决策。小幅区间近似 `U_f(y)=y-f*y²/2+…`，既加重左尾也压缩趋势大右尾，不保证只去掉坏尾。这里的数学推导不新增观测信息，也不依赖297成绩。

但单事件log不能称组合增长：`log(1+sum_j r_j)`一般不等于 `sum_j log(1+r_j)`。重叠事件的共同风险、时间占用、margin、整数手、撤销及后续机会均未由单事件效用刻画；并发唯一性权重不提供联合分布，也不是Kelly概率。即便现金收益改善，仍需单独判断最大回撤与尾部，不能由标签凹性签发窄损安全或加注资格。

有限历史区别如下：

| 既有包 | 实际改变对象 | 与本提案关系 |
| --- | --- | --- |
| 旧高分/加注、meta-label路线 | 旧字段质量判断或按score改变参与/投注 | log目标在原则上不是同一机制；不应仅凭那些旧失败否决所有效用学习。021/014已有范围说明，本次不重查那些大产物或宣称完成穷尽旧史审计 |
| DOMAIN52，217—221 | D<K训练loss支撑及总权重质量；原Y不变 | 非同一干预。其失败不证明凹效用无效，也不能作为重复log的新增根据 |
| K_TARGET52，236—240 | 同S/权重/52/scaler，只将原first-exit改为严格K政策payoff | 改退出收益对象，非凹效用；其失败不否定一切目标对齐。但用旧first-exit效用仍不能冒称K组合价值 |
| **098—103固定log代理** | **同成本预算量z，L学z、G学log1p(.0025*z)/.0025，其余模型/成熟/权重/执行固定** | **这才是直接重叠命题，已实际完成并关闭，不能忽略** |

直接去重证据：[098单位与数学审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1841_stage098_risk_objective_feasibility.md)、[103结案11—25行](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261018_1905_stage103_log_utility_decision.md:11)。103记录f固定为既定政策、L/G均为COMMON52及alpha1 Ridge，两个main cutoff共4fit、8cash、102独审接受；四组G收益均低于L、四CI跨0，84行明确关闭固定log曲率、不扫f或效用族。这是历史小记录复核，不是本阶段重算成绩。

旧包没有现在129完整动作结构与family held，因此它不构成对新六折数据集的一般不可能性证明。但仅“换成当前母体/多加held”是运输复测，尚未带来一个没有被这次直接曲率实验触及的金融命题；原式错误也不能靠不同数据集消除。当前没有实质理由在同史上重新消耗6fit/4cash。以后若有独立规则、目标或政策机制，仍可单独开题；不要求其必须来自外生新数据。

## 变更、反思与交付边界

- 唯一新增本文；源码、模型、数据、参数、回测结果新增/修改/删除均0。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A；没有新增金融结果，不触发本阶段实际回测独审。
- 结束过拟合判断：**历史重复择题风险是；本阶段没有按296/297成绩选方向或调f。** 发现同一目标已有直接实验后，再用同史换母体/折数续跑会增加选择自由度。
- 结束继续价值：**继续本固定log包否；完成单位核对和历史去重是。** 不是把用户目标限制为只能找新数据，也不把log偏好本身判成伪科学。用户完整高质量做多、更高净收益且更低回撤目标仍未由本审查完成。
- 本结论无actual授权、无新预算、无实现TODO；不更新LINE/registry，由root合入本次去重发现。
