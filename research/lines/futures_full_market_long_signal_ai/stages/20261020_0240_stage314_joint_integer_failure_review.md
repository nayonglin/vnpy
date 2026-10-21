# Stage314：同批整数预算的独立失败现场审计

- 研究线：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 02:40（上海）。本阶段不是重要收益突破。
- 本轮仅审311已冻结预算与312/313实际失败现场；不属于OI信号、正式C9或ABC。未修改参数、源码、solver、精度、tie或协议，未重试。静态收据core0；实际执行出现1项阻断。
- [独立收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage314_joint_integer_independent_review/receipt.json)：19719 bytes，SHA256 `c078daded9daf999c7126088c0ee77334cded0f19bdf5b21853186261e887084`。

结论：313首本现金在2021-07-06的lex_3收到HiGHS status2“不可行”，但该整数问题存在精确可行解，且320组合穷举证明它是唯一主目标最优解。阻断属于本冻结数值oracle/接口链的执行失败，不能归因为预算约束数学不可行，也不能归因为alpha失败。尚未定位presolve、容差或接口的具体原因；本审查没有调用求解器。

## 实际终态与范围

root唯一session65606于2026-10-20 02:35–02:36执行，terminal真实exit1，耗时2.681463秒。上限4本，实际started1、completed0；另外3本未启动。0fit、0旧控制重放、0SQL、0自动重试。完整新现金仍为0，root口径累计完成453fit/246cash，另记本次1个未完成尝试。

独立一遍读取234420B失败audit，共366批，365完成/1失败；模式为empty178、single-family79、scale-one36、joint-integer73（其中72完成）。完整旧157 signals4365行只读一次；audit内399条accepted记录的原始字段、score、u/D/K/anchor身份均与原token直接解析精确一致。未读取旧大mother、native价格、labels或模型，未重资格化旧价格。

## 算术与前序证据

全部73个整数问题按“原float各自转Decimal(str)，L在Decimal域乘”的冻结顺序独立重建A/B ceil、C half-even、cap floor、UB及小于2^50范围，完全一致。399条单位风险、保证金、费用和滑点独算最大差为0；原未量化目标/common scale及触发条件亦一致。UB0仍计入accepted family，只有原scale严格小于1且至少2family才触发。

46个full-upper解析解、19个UB0解析lex步骤有相应依据；107个已接受MILP步骤的整数距离、资源约束、primary/prefix等式、目标/dual绝对间隙小于0.5单位、fun/gap与节点时间累计证据均通过。前72个实际应用批次的n=Lk、单family/总风险、总保证金、容量、冻结费用以及Decimal和float未量化预算均未超限。59批数量改变，72批预算冻结值改变。对前序MILP的最优性核的是保存的dual证书算术，不冒充另一求解器或穷举证明。

## 最后一批的精确矛盾

变量顺序为EB/J/JM/PG/HC/RB，UB=`[4,0,1,1,3,3]`。320组合中37可行，唯一primary最大值280584162，唯一最优且lex最大为`[0,0,0,0,3,0]`。固定primary和前三个lex前缀后仍恰有1可行点，k3=0，故lex_3没有可行性歧义。

- 风险grid用量1367439852 ≤ 12349148051；保证金35587200003 ≤ 44646109249。
- 未量化风险1367.43985087886982元、保证金35587.200000000003元；单family上限2360.2850925元，仍满足原预算。
- primary、lex_0、lex_2都保存同一个可行点，lex_1为UB0解析步骤；随后lex_3返回status2。失败调用尚余9.990727583秒，之前累计nodes1，不支持时间/节点耗尽解释。
- 最后批次actual_rows空、没有solution，失败在应用预算之前。按311立即停止、保留现场且无fallback/retry，符合失败纪律。

108份MILP options均未保存node_limit。冻结312确实构造`100000−累计mip_node_count`，并将同一个options对象传入SciPy；库调用时对象被修改是可能解释，但本审查不据此断言具体原因，也不能把缺字段当作未传入的证据。实际Python3.11.5/numpy2.2.3/scipy1.17.1已由root授权绑定。此项保留为审计元数据不完整，不为它重跑或修源。

## 财务与置信度边界

无完整daily/fills/closed/open/positions/reservations账本，不能独立重建own-state完整递归或D执行；这里只核保存的E/F0/margin与原预算行一致，并继承静态确认的private callback及D不回收。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率、年度和pairedCI全部不可提供；没有四本收益比较，主stress目标门未评估。不能把局部365批当完整回测，不能继承旧控制指标充作新指标。

本次不是过拟合搜索：固定收益前政策，未因失败更改solver/grid/tie或尝试救参。继续完成失败审查有价值，已经证明“数学可行但oracle报告不可行”；本冻结包按原fail-stop关闭，不再执行。预算机制的经济价值仍未被本次尝试检验，不能由执行失败否定alpha，也没有获得PIT、可执行真值或正式资格。原全市场高质量long→小止损→加注目标仍未实现。
