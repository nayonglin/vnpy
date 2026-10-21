# Stage007：全市场做多DAY屏障的单次信息增量实验

line_id=`futures_full_market_long_signal_ai`；2026-10-18 11:29 CST。收益前冻结，尚未读取新标签/收益或拟合模型。使用brainstorming形成有界设计，用户持续授权自主研究；本阶段按原授权实施，不重复形式审批。上一目标轮为真实进展：全市场观察表已完成并独审接受，绝非已完成策略目标。

## 唯一问题与边界

在六所全市场而非正式AI月池/C9事件中，**严格滞后的其他品种市场状态，是否在同一简单学习器下提供自品种价量以外、可以在固定小幅逆向屏障政策中识别的增量**？不寻最优止损/止盈/持有期/阈值/模型，不以新名称复活旧score-only加风险。

这是连续价格、理想即时触达撮合下的归一化**代理效用筛查**，不是固定小风险仓位、真实成交收益或现金回测。0.25ATR不是已证明“极小”的最佳止损。即便通过，真实tick、费用、跳价、限价、成交量、保证金、组合生存和正式多周期仍须后续验证；本轮不加注、不连接CTP、不改正式策略或月池，目标更高收益且更低回撤仍完整保留。

## 母体与代理目标

- 固定004/005已接受的399252个(product,u)观察行全部保留，212852条有参考者可检查历史；不以未来标签是否可得筛输入/预测。无观察/暖机/零ATR/缺D/尾部各有状态，未知不填0，不补行情。
- 同一真实reference_epoch截至u须有连续21个source-calendar交易日的合法正量bar；任何缺日重暖。以这21bar计算20个TR，`TR=max(H−L,abs(H−prevC),abs(L−prevC))`，`ATR20=mean(TR最后20)`，须正且有限。不开旧AM120或openingOI门。
- D仅004原planned_execution_date，不取“下一有价行”，不按D量/未来主力重选。参考F为同一epoch的D.open；这只是理想执行参考，不保证市场可以买到。R价格距离=`0.25*ATR20(u)`，SL=`F−R`，PT=`F+4R`，DAY未触及屏障则以D.close作参考退出。无重试、roll或隔夜新持仓；本轮没有手数/本金。
- D缺失、非法价、非正SL时`label_identified=false`；D超源结束日为right_censored。已知D的标签在D收盘后才可知，`label_known_date=D`只表示模拟日期合同，不是假造精确午夜/历史发布PIT。源资格继承266，未恢复真实历史费用/交易资格。
- 只有SL触达：gross代理区间[−1,−1]；只有PT：[4,4]；都不触达：同一点`(D.close−F)/R`；双触达：[−1,4]，`path_ambiguous=true`，不是确定负类。边界等号算触达。这个区间只在理想屏障成交模型内部成立，不能冒称含真实stop gap的保守现金界。
- 基础研究成本预算固定0.2R/次，代理上下端各减0.2；训练目标仅`proxy_lower`，不是实际输赢label。压力预算1R沿原预测mask扣额外0.8R，无重训/再选阈值。二者不是历史真实佣金或滑点。保留gross上下端、基础上下端与状态，缺失均空。

## 固定输入特征

u的21bar记c0为u−20收盘，c20为u收盘，过去20bar不含u时指u−20..u−1。全部价格同epoch未复权，方向始终long。

M0自品种11维，精确次序：

1. `r1_atr=(C_u−C_{u−1})/ATR20`。
2. `r5_atr=(C_u−C_{u−5})/(sqrt(5)*ATR20)`。
3. `r20_atr=(C_u−C_{u−20})/(sqrt(20)*ATR20)`。
4. `body_atr=(C_u−O_u)/ATR20`。
5. `range_atr=(H_u−L_u)/ATR20`。
6. `close_location=(C_u−L_u)/(H_u−L_u)`；平价bar为0.5。
7. `gap_atr=(O_u−C_{u−1})/ATR20`。
8. `compression5_20=mean(TR最后5)/ATR20`。
9. `log_volume_ratio20=log(V_u/mean(V_{u−20}..V_{u−1}))`。
10. `breakout20_atr=(C_u−max(H_{u−20}..H_{u−1}))/ATR20`。
11. `atr_pct=ATR20/C_u`。

M1只追加4维，不加interaction：`market_lag_median_r1,market_lag_breadth,market_lag_iqr_r1,market_lag_missing`。严格取前一个source-calendar日u−1所有feature_ready观察中的r1_atr；此r1必须同epoch相邻日，不拼每日代表价格。先将F与普通家族归并，族内r1均值，再排除当前产品自己的family，对其余family等权算median、正值比例、q75−q25（线性分位数）。没有其他可用family时前三维0、missing=1，否则missing=0；不前填，不按D/标签筛其他品种，也不把数量增长作为模型特征。

`family_id=exchange+'.'+product去末尾_F`，仅控制已知F重复，不能宣称已消除其他历史产品改名或行业相关性。保留原98目录，各品种不黑名单。M0/M1用同一feature_ready cohort，M1缺上下文不额外删除行。所有自身特征须有限；OI不作本次输入。

## 年度扩窗与模型

- 2015..2026每自然年一个冻结模型，最早训练u=2010。该年首个source-calendar u为test_start；训练只允许u<test_start且`label_known_date<test_start`。预测该年全部feature_ready行，之后才在共同label可识别子集评价。尾部/缺D预测仍保存。
- 每日期训练权重为其可用训练行数的倒数，再整体归一至均值1；无标签日不造权重。StandardScaler只fit训练侧（带同权重），缺上下文已按固定规则表示；常数列按sklearn默认scale1。
- M0/M1均固定`Ridge(alpha=1,solver='cholesky',fit_intercept=True)`，不调参/随机种子/模型。额外无需拟合的截距参考为当年训练日期等权目标均值；动量参考mask为`r20_atr>0`；现金mask为0。
- 再做预声明两组产品留出：`int(sha256(family_id).hexdigest(),16)%2`，每年训练排除测试组全部family历史，M0/M1各fit；同F必须同组，两组都报告并合并，不挑好组。总计划12年×(主样本2＋留出2×2)=72次Ridge fit，非72策略搜索；测试fixture fit另记，不计实际实验次数。
- `.py311/bin/python`原生独立数值运行时（本次实测numpy2.2.3/pandas2.2.3/sklearn1.6.1/scipy1.17.1），不导入旧金融FROZEN/qmt/native栈，不安装依赖。threadpoolctl限制BLAS为1，所有实际fit/样本键/训练截止/系数/scaler持久化。

## 评价与单次筛查门

- 所有模型唯一mask=`predicted_proxy_lower>0`；不topN、不阈值扫描。主评价2020—2026-10-16，2015+全历史另列。分母是每u共同label可识别行数，先产品等权再日期等权；完整ready数、缺D/未知数、两模型在未知行的mask率同时报告。条件评价不称全市场总体收益。
- M1自身值为`mean_u mean_i(mask1*proxy_lower)`。对比M0要用**配对区间**：a=mask1−mask0，a≥0取a*lower、a<0取a*upper，common mask的a=0精确抵消；不能把两策略lower相减冒称增量真实下界。upper相反端。
- 参与率对照：在每u共同可评价行中p=mean(mask1)，相同参与率无品种选择的参考值为p*mean(proxy)。M1超额区间按a=mask1−p逐项同样算界。它区分市场择时与品种选别，不能只凭M1少亏宣称找出高质量品种。
- 每年报告自身lower、paired lower/upper、参与率超额界、mask覆盖/日期/family、双触达与未知率、误删右尾proxy机会成本、MSE及分数校准。所有R都是归一化proxy，不报告伪造权益/收益率/Sharpe/最大回撤。
- 对主样本2015+和2020+日期网格，用固定60日移动block bootstrap、2000次、seed20261018；各统计共用抽样index。没有可识别行的日期保留NaN并披露，取有限值均值。只描述这套固定历史预测的条件不确定性，不涵盖研究者多次看历史的选择偏差。无策略重训bootstrap。
- `quality_information_screen_pass`同时要求：2020+M1至少60个入选日期/8个family；M1自身lower均值>0；M1−M0配对lower及相对参与率lower的95%CI下端均>0；2015+对应三项lower均值>0；两个产品留出组2020+的M1自身lower与paired lower均值都>0；同mask成本1R压力下2020+自身lower均值>0；2020..2025至少4个完整年paired lower>0且2026部分年自身lower>0。每项逐项true/false；失败不得改屏障、interaction、成本或阈值救参。若仅择时证据，明确单列，不称品种质量通过。
- 此门只是值得继续执行验证，不满足原目标完成审计。正式收益/DD、独立多周期和窄损加注生存门未被替代；若失败，停止本次跨市场特征包+该代理政策，不将其外推为所有AI无效。

## 执行与复现

009作者：只新增数据builder/test/唯一stage与outputs，先3—4个有效RED/GREEN（未来前缀、calendar缺口/缺D、双触达interval、F族/lag信息边界），一次实际构建；不fit模型。010另一作者可并行实施trainer/test，3—4个有效测试覆盖成熟截止/留出/训练侧缩放、配对抵消和参与率、固定mask压力；只有009实际数据经011单次独审接受后才允许唯一实际72-fit实验。012独立审模型/数据/逻辑/置信度，不为恢复导出重fit。

实际生成器显式分类：协议/源/test/系数scaler/预测/指标/终态/独立证据属于复现资产；原始库/OHLC大表不得进入Git。模型比较预测输出不带原OHLC；没有commit/push/部署授权。按freeze skill只本地精确登记必要决策资产，保持原失败记录与其他脏改动。

调研：实际读MIT作者[Kaminski/Lo原文摘要](https://dspace.mit.edu/entities/publication/bb69ca4b-0cdc-487f-831d-63b2e84fafee)、Backtrader官方[执行假设](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[bracket关系](https://www.backtrader.com/docu/order-creation-execution/bracket/bracket/)，以及上轮DeePM作者论文/GitHub。判断：止损价值有条件，OHLC撮合有假设；跨市场滞后/成本目标值得一次配对反证，不证明本线alpha。未运行外部代码。0.25/4/DAY/.2不是作者唯一推荐，是本研究在收益前声明的一组独立假设。

开始新增选参过拟合：否，但已有研究选择风险、历史反复观察及未知执行边界明确保留。继续价值：是，一次固定真实数据上的识别实验，比继续源认证或旧19账户更接近新目标。所有真实金融绩效当前N/A，尚无新fit/alpha、目标active。
