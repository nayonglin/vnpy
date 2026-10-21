# Stage052：一次期限信息三臂训练与真实研究现金比较

- line_id `futures_full_market_long_signal_ai`；root冻结2026-10-18 14:31 CST。沿当前`codex/ai-training-data-expansion`，不新分支/工作树、提交、推送或生产。
- 上轮049/050/051完成实际数据与独审，是实质进展。现在直接实验，不重新构建标签、特征或验证全原生库。全市场高质量long、更高收益低回撤、随后极窄止损/加注目标未完成。
- 范围明确：已有049规范化输入+042研究现金核的单一新增信息比较，不改正式策略；纯信息归因，当前非正式A/B晋升。使用实施计划与并行agent流程，在本研究线保存计划/证据；用户已授权自主设计、继续和多agent，不新增确认步骤。

## 调研与选择

实查[sklearn官方HGB文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)、[维护方GitHub源码](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/sklearn/ensemble/_hist_gradient_boosting/gradient_boosting.py)，本机`.py311` sklearn1.6.1确认接口支持sample_weight/关闭early_stopping，无fit探路。自动early stopping可能在大样本随机留出验证；本合同显式关闭。实查[原作者PBO论文](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)：多次研究同段历史的选择风险不能靠换名消除，2020以后不是研究者真正未见样本。

判断：相同小树能表达q与品种自身状态的非线性交互，较强制一个固定线性效应更适合本问题；容量固定且ALIGNED与同值SHUFFLED主比较控制新增槽的复杂度。不是先跑Ridge失败再加树，也不复活旧RFF/历史预测。只检验这一种学习器与新增观察；失败停止本q+学习器+经济政策组合，不声称否定一切AI，不换树深/标签/窗/seed救结果。

## 输入、共同列与同容量三臂

唯一母体049全部399252行，2010—2026-10-16。主y为已完整闭合参与事件`net_R_stress`，固定2N(u)×M分母，所有取消/未知/删失的trade目标仍null。只在训练选择真实成熟行；预测/现金不能先按未来filled、closed、标签值、q可得或55突破筛选。

共同26列，顺序在机器协议固定：

1. 已接受009中S11：r1_atr,r5_atr,r20_atr,body_atr,range_atr,close_location,gap_atr,compression5_20,log_volume_ratio20,breakout20_atr,atr_pct。仅按event_id读取这些X，**不读旧Y、预测、mask或market-lag四列**；旧21bar未就绪时各列缺失，20ready行仍可预测，不按旧feature_ready删行。
2. 049的13列：normalizer,peer_count,tenor_span_years,return_mean,return_std,return_min,return_max,front_next_basis_u,front_next_basis_prev,front_next_tenor_span_years,q_missing,front_next_missing,normalizer_missing。
3. 两个u已知控制：stress_u_cost_R=(stress_u_fee_roundtrip_per_lot+stress_u_slippage_roundtrip_per_lot)/cash_risk_unit；low20_distance_R=(u_close-low20_u)/(2*N_u)。不使用实际D/exit费用、未来取消/成熟或实际持有时间作为X。

对共同26列各附同顺序missing indicator，共52列；第53列为q槽。COMMON槽恒0，ALIGNED=q_aligned，SHUFFLED=q_shuffled。q缺失统一以共同缺失中性处理，不把缺失收益填0。普通/F是不同curve经济表达，family分组仍共享；不额外引入产品ID/year/month或旧C9条件。

每scope/cutoff，仅成熟训练行和训练权重决定共同26列有限值加权mean/population std；缺失先用训练mean、零方差scale1；missing列保留0/1不另按臂缩放。q均值/方差由同训练行ALIGNED与SHUFFLED各半权重联合有限值估计，三臂共享。缺失q填该共同mean后标准化0；COMMON用原尺度0经同一scaler，成为可由树常数吸收的固定槽。无全样本缩放、winsorize、clip、目标变换或截尾。

## 27次fit及严格成熟/重叠

三个calendar cutoff：2020-01-01、2023-01-01、2026-01-01；分别预测u属于2020—22、2023—25、2026部分年的所有母体行。模型在该cutoff前已完成source收盘资料拟合，只有`u_date<cutoff且label_known_date<cutoff且closed_complete`进入训练。不使用测试期后来才成熟的标签或随机train/test；纯前向成熟隔离不额外造任意embargo。

三个scope：main使用全部训练family；holdout_0/1用`int(SHA256(family_id),16)%2`沿原固定分组，将对应组的所有历史训练标签排除，仅预测该组机会。普通/F不可分组穿透；held query使用自己已观察历史/curve合法，但不是zero-shot无历史。共同scaler/q scaler/学习器均不见held标签。main全母体每臂161014个2020+u预测；两held合并亦为同母体每臂161014。2010—19不输出伪OOS score；2020首账户首open没有前一年未存在模型的信号，保持空仓；2023冷启动可使用上一2022u合法旧模型score准备首open，模型更新不改之前已决定的订单。

每训练集合内按family建立entry—exit含首尾的日并发c；每事件U=持有区间mean(1/c)。先按u归一令该日Σw=1，再整体均值归一。只用该cutoff已成熟训练集合，不以测试/未来事件算并发，不按盈利或目标幅度加权。输出训练ID、权重、scaler与区间身份供独审；不声称w总和是独立经验数。

唯一学习器HGBRegressor：squared_error、learning_rate0.05、max_iter100、max_leaf_nodes7、max_depth3、min_samples_leaf100、l2_regularization1、max_bins127、max_features1、categorical_features=None、early_stopping=False、warm_start=False、random_state20261018；其他参数绑定本机1.6.1默认，不按成绩改。固定OMP/BLAS各1，sample_weight上述w。每cutoff×scope×arm一次，总27 actual fit，不CV、早停试选或多seed。实际预测和模型保存，不在独审重新fit。

动作唯一为history_ready20且finite score>0请求long，其余不请求；q缺失仍由共同信息打分。只改开/不开，不按分数放大风险、topN、加仓、窄止损或修改退出。旧009是共同控制数据，不是另一次旧实验或已证alpha。

## 12个研究现金账户

完全复用已独审042纯核，禁止调用其55信号生成。053预测按event_id合并049 u字段成为signals，所有原行和当时reference保留给退出请求；只有potential由动作决定。禁止把label_state/filled/实际entry/exit/netY用于是否执行、数量或持仓管理。主scope三臂各独立维护状态。一个新的native只读SQL供所有账户，不重新生成049或014旧数据。

仅2起点（2020-01-01、2023-01-01）至2026-10-16×base/stress×三臂=12独立冷启动账本。100万元，单family初风险0.25%、总2%、margin预留25%、buffer1.10，u收盘联合缩放先实数预算再floor，D只减不增且不借后释放资金，roundlot/epoch乘数/tick与静态vendor margin假设沿041/042。base每边max2CNY/1bp、滑点max1tick/1bp；stress6CNY/3bp/3tick及较高margin，数量可能变化，不能说只有手续费不同。旧epoch因果20low/2N、换月/期限、缺价stale/延迟退出、close mark/未知敞口与破产停开不变。

保存全部fills/daily/budgets/position_days/closed/open/summary，不把独立标签PnL加成权益。相同风险预算比较；每个账户真现金有限，标签之间重叠、family占用与整数手拒绝均保留。2020—25逐年结果由2020连续账户日收益切片，不冒称新冷启动或相加为新账户；2026为部分年。未知/末开放/stale及替代零值情景照报，不以未结仓删现金曲线。

## 最少、实际相关的判断

主问题ALIGNED相对SHUFFLED的信息增量，COMMON为必要共同参照。以同source日账户log增长差为主；若任一破产不删负值修log，直接生存失败。一次固定252 source-day circular moving-block bootstrap、2000次、seed20261018；所有对比共用索引，保存索引hash/seed/分布。252大于已闭合最长104日，不证明完全独立或覆盖所有宏观尾部；6个完整年限制置信度，不能把2000次重采样称2000个新市场。

只设三个有实际含义的继续条件，逐项报支持/不支持/未知，不生成20门：

1. 主2020 base的ALIGNED−SHUFFLED以及ALIGNED−COMMON配对log增长差95%CI下端均>0；ALIGNED净收益更高且最大回撤不比两个参照更深。两个对比共同要求，不能单挑赢一臂。
2. ALIGNED自身stress净增长正/无破产；2023冷启动base与stress对两个参照增量同向、回撤不恶化。未知估值足以翻转关键结论时为不确定，不把静态规格升格broker资格。
3. 两个family held的预声明机会诊断增量ALIGNED−SHUFFLED均正；只在各臂共同的已识别（closed或known_nonparticipation）域按u日等权统计mask×净R，known非参与贡献0，并明确这是条件诊断而非全机会价值/现金收益。全母体score和选中unknown/open/cancel数量同时保留，不能用已识别子集决定执行；selected未知足以改变方向则不宣称普适。尾部另报实际现金family×年集中度/主要赢家与年度贡献，不删最大赢家造稳健。

代理诊断只解释，最终真实现金增长/DD及成本/开放风险决定是否值得继续；即使通过也仅支持该信息候选，未证明用户完整目标或获准窄损/加注。失败不做正式多周期矩阵；若值得晋级再按version-ab与multicycle技能、活动正式基准另验证。

## 实施分工与运行顺序

- 053 agent：tools/stage053_maturity_information_fit.py及最少合成tests，读取本协议/049/009固定数据，27fit/模型/全预测/权重/scalers/manifest/terminal；实际只root启动一次。不得SQL或现金。
- 054 agent：tools/stage054_maturity_cash_compare.py及最少合成tests，依赖053完整manifest与相同052SHA；一次native加载/12现金账本/统计，实际只root启动一次，不再fit。
- 055独立agent：先有限协议/两模块源码预审；每次实际训练/回测后一次独立审查完整权重与成熟/保存模型预测重放、所有现金恒等式/预算与summary/CI、有限因果native案例。不重训/策略重放、SQL或旧suite。重大实现错误修正并如实计启动；不为dtype/展示小问题重跑。
- root：冻结机器bindings→必要synthetic RED/GREEN与源码review→053一次→完整终态→054一次→055独审→056结论/局部登记/更新LINE及registry仅本行。源/输出均新目录，拒绝覆盖，不更改049/042/正式配置。无需重复用户确认。

当前本052无新增fit/账户或绩效，权益/收益/DD/Sharpe/滑点/次数/胜率N/A；累计288fit/18现金不变。开始过拟合判断：不按新成绩选参数，但重复历史择题和尾部不确定性仍有。继续价值：是，前置数据齐备，直接用有限真实经济比较证伪新信息。结束以实际结果据实决定，不因准备或绿灯宣告alpha/窄损/加注/goal完成。
