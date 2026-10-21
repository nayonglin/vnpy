# Stage623：已有K标签与完整准入扩展的最小接口核查

- line_id=`futures_full_market_long_signal_ai`；2026-10-21 09:12 CST；day；非重要突破，独立于正式C9。
- 已读registry；本轮恰3份小源/manifest：233纯measurement源、233实际manifest、156纯选择源。没有导入策略，没有打开actions/common/native/childscore/标签载荷或任何真实Y值，0fit/0cash/0SQL/0下载/0实施。
- 结论：**有现成的完整K标签供应文件可复用，不必重造K Y。独立一手路径的风险/成本定义相容；它不是157账户现金Y。简单去掉正分门再选月不能保证保留原admitted动作，须做分支扩展。**

## 已定位的文件及绑定

基目录`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/`。

| 文件 | bytes | SHA256 | 本轮验证层级 |
| --- | ---: | --- | --- |
| `tools/stage233_K_payoff_measurement.py` | 25,686 | `cc4bac7a67ca41254ea88a2afb22d665ada6a796ace82d23e204989b1971dfee` | 实读小源并核当前SHA |
| `outputs/stage233_K_payoff_measurement/actual_run1/manifest.json` | 12,639 | `f028bdb67d5db85c4202fb92a9fe328ed020e30d7c3ee2707db2fa9ea3a1686e` | 实读，status=completed，核当前SHA；无Y载荷 |
| `tools/stage156_voluntary_choices.py` | 17,062 | `4c56ad2f0e812a10aca9a153e3328c8a8aa6e8df1a1b588f3aecf898713f7200` | 实读小源并核当前SHA，亦与233绑定一致 |
| `outputs/stage233_K_payoff_measurement/actual_run1/labels_K.csv.gz` | 205,038,809 | `b499a7a559ee7f8ada7f67631e665302bb3ffd3c92d6ca8121ce44d82fdcc1ec` | SHA继承已完成manifest，仅stat确认存在/bytes相同，不读/重hash |
| `outputs/stage233_K_payoff_measurement/actual_run1/mothers_K.csv.gz` | 22,137,868 | `f943ceb2af2913eaccd8a89a64f64556766248a9a6b704a1dfb175132960f9e8` | 同上；不必为简单标签join先读母大表 |

这定位的是237—240目标实验谱系已有的上游233全域供应接口，不是238的某fold训练缓存。本轮未打开237协议或238/239manifest，不宣称重新核完那条消费链、234独审或全部K标签数值；父线此前验收与本轮接口核查分开。没有为补绑定扩大3文件预算。

## 完整性及目标相容性

233 `actual`对原129 actions只开一个stream，`measure_rows`逐sequence核原母身份/anchor，**每一输入action都向labels_sink写一行**；没有按分数、选中、训练折、filled或闭合筛输出。完成时对原227计数分区和冻结expected_action_rows/mother_rows作一致性断言。结合本线已接受129的1,552,456 child/399252母身份，这不是只含原正分信号或某个成熟train子集的文件，包含原u_action_eligible全部child及其非准入/未知状态。此为源路径＋completed/继承计数的证据，不冒称本轮重数了205MB文件。

接口按`action_id`（可辅sequence/mother等身份）连接完整原分数，不能只用epoch/date串接或把157的正分signals当E。主要消费列已在manifest的`label_columns`明确给出：

- `u_action_eligible, primary_domain, calendar_allowed, calendar_state, D_date, K_index/K_date/K_state, timing_state/branch`；
- `K_stress_known, K_stress_net_R, K_stress_known_date/known_phase`，另有对应base；
- `policy_reward_known, policy_reward, policy_known_date/phase`，区分已知不参与的0；
- 原`label_state/participation_state/unknown_*`与原`net_R_stress`仍保存。**不能误取未加K前缀的旧net_R_stress当K Y。**

233不是重放路径：旧独立action在K前已闭合就复制原结果；原完整可确认prefix需要K开盘退出时，仅用该同epoch K.open算一次原042不利SELL。原BUY填价/入场fee/slip原样保留；新net=`M*(K_sell_fill−original_entry_fill)−entryfee−K_sellfee`；分母明确核`R0=.25N`、`cash_risk_unit=R0*M`，与原NARROW一手stress净R一致，辅助2N列不能混用。K已知日期/phase保持，成本不可表示或前缀未知仍unknown，不用未来退出修复。

相容对象是**同原anchor/20low/.25N/生命周期＋K的独立一手潜在路径**。157沿同K规则把实际生命周期设min(old,K)，但它还受占仓、资金风险/保证金缩减、整数数量、容量和估值影响，可能在独立路径之外部分退出。因此K单动作Y不是157 OWN已成交root的真实财富贡献，不应冒称重现157现金结果。

对未来完整E的最小读法：先用u合格且纯calendar allowed定义E，不能按K_stress_known筛E；K_known=1取K_stress_net_R；明确的known_nonparticipation可取policy_reward的0。nonprimary_noaction虽也存0，仍在E之外，不能塞回随机可交易池；unknown calendar/路径/右删失不得填0。已有Y若不支持精确比较，就保留不可识别，不重造/填补。

## 去正分门并不自动保持原动作

617已核130：先每个exact product母内按最高score选月，再按普通/F及product等固定顺序选family赢家。156读取完整child、先K gate，再以相同`rank_action=(-score,epoch,action_id)`和`family_winners`执行；后者**不是跨整个family取最高分**。

两个纯逻辑例（不读真实分数/收益）：普通最佳+.1、F最佳+.2，原赢家仍是普通，跨family最大分会改为F；普通最佳−.1、F最佳+.2，原正分后赢家为F，但简单删除正分门再普通优先会改为普通。因此“所有family都取原最大分、不要求正分”两种常见解释都不能保证原admitted逐值不变。

最小相容扩展是：

1. 完整复现原156正分＋K winners及身份/anchor/tie，作为admitted分支原样保留，不重新定义原控制。
2. **仅对原无任何正分winner的family-u**，从原u_action_eligible、同纯K gate和有限score的完整child里，移除score>0一次；仍先每exact product取原最大分月，再原ordinary/F优先，得到唯一fallback。fallback不看Y；其余无观察/无合法E/unknown保留原状态。
3. 不能用156的`new_eligible`或`original_positive_eligible`直接当全E：它们已混入score>0，负分行被置0/覆盖reason。应复用同`calendar_boundary`和独立D<K逻辑；after-calendar-pending沿D_date<target月首的原已知关系，不把未知K裁到样本末。完整分数按原u对应2020/2023 cutoff消费；157 signals仍只作旧控制，不能补全拒绝域。

此扩展只为下一阶段定义可比较机会，不是新alpha，也没有选“最优负分动作”。若root要求完全统一无分支的全family最大分规则，则必须承认它同时改变原admitted选月/普通F政策，不能称准入单轴实验。本轮不实现扩展或读取任何候选Y。

## 交接与反思

最有价值的下步已具体：**可以复用233 labels_K，先冻完整E与上述保留原动作的扩展合同，再限定一次顺序读取预算；无需新的K路径/标签工程。** 完整分数载荷路径/bytes/SHA在本轮3文件预算内未重新核定，交由root已有130/538绑定供给，不用157正分signals替代。

本轮是本机既有接口核查，复用617/621当天已核原作者SPO及GitHub关于预测目标/动作/现金应区分的方法边界，不扩网络或新理论。事实与限制均在上文分开；不声明新证据优于现有模型。

开始/结束按新收益选参：否；长期同史适应性过拟合风险：是。开始/结束这个最小接口核查有价值；继续全库重算、重新资格认证或重复读旧大表无价值。策略参数和财务N/A；原目标active，未提供实盘/加注资格。仅新增本记录与小handoff，不修改LINE/registry/root logs。
