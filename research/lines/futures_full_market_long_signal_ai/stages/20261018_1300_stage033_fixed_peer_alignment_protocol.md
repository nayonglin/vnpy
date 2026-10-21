# Stage033：同行关系对应信息的固定对照协议

line_id=`futures_full_market_long_signal_ai`；2026-10-18 13:00 CST，实际冻结时刻自动记录。完整目标仍是六所全市场全部历史品种的超高质量long识别，真实净收益更高与回撤更低，之后独立验证窄止损和加注。上一goal轮029/030已完成政策反证及归档，分类progress；本轮沿独立032预结果建议检验新增同行对应信息，不以029成绩选标签、不重评024失败模型。

## 单一问题与输入来源

S11及其他family上一源日收益分布摘要无法还原“哪个历史相关同行正在怎样动”。只用一个固定相关加权投影q，主对照ALIGNED与SHUFFLED同值不同对应，COMMON作次参考。它是此前模型未见的跨family输入，不是新外生源，不是因果lead-lag证明，不是完整面板穷尽，也不采用GNN/PCA/交互/embedding或复杂头。

已核[原作者研究](https://arxiv.org/abs/2201.08283)和[作者GitHub](https://github.com/stefanosbennett/mlj-lead-lag)及README；美股网络/预测实验仅支持问题可研究，不提供国内单方向窄损盈利证明。关系不是因果；本协议用同步20日Pearson及滞后shock，不能把它描述为直接复现该论文。未执行或安装外部代码。

当前branch codex/ai-training-data-expansion，不新worktree/branch。只读009/011已接受CSV和4074源日历，核绑定SHA；不SQL/大库重hash/新盘点/下载。399252母表/194709ready/194168known/541unknown不变。features只读identity、S11、r1、ready；不得用label_identified/D结果筛ctx。源有真实status observed_long_research_opportunity/no_accepted_observation，不能再用简写observed。原始价量/audit/024模型不输入、不归档。

## 固定上下文：日历、peer与null

按date,family对ready r1_atr均值聚合（含未知D），family去_F。每个r1来自当时代表epoch的合法相邻真实bar，允许各日代表变化但不拼接不同合约绝对价。u的shock日t=u−1源日；关系窗口[t−20,t−1]共20源日，不含shock t，不含u。D=u+1，shock与执行相距两源日索引，检验保守状态而非直接一日传播。

边(i,j)仅当own i与peer j在关系窗口20个值全有限、各自去均值平方和>0，且j在t有有限shock时可用。无前填、插值、pairwise删日、全样本相关、显著性/topK或sector阈值。rho=sumdemean(x)*demean(y)/sqrt(sumx2*sumy2)，所有正负及零rho参与，n为有效边数，Z=sumabsrho；数值浮点超界仅可在证明1e-12内的数学roundoff上夹[-1,1]，超过即输入错误，不做预测clip。n=0或Z=0时q=0,relation_missing=1；其他q=sumrho*rj(t)/Z，relation_missing=0，允许真实抵消为0。own关系窗不完整则无边n=Z=0/缺失，原ready不删。

main同行池为当时可观察的全部family，先移除目标own family，包括其_F，不能漏掉自身表达。holdout_g同行池仅family hash%2!=g，再移除own；训练和测试均如此。四个market lag摘要也在同允许pool（仅t shock有限、不要求关系窗完整）算median、正值比例、linear IQR、missing；无peer=[0,0,0,1]，按009公式。main四摘要全ready与009在atol=rtol=1e-12数值一致，容差不用于经济门。严格held输入不复用009全市场四列，防held历史进入训练context。

ALIGNED按照peer family字典序排列rho槽，原j shock进原槽。SHUFFLED保留同一有效边、rho、n/Z/missing与同批shock值，只把shock按key=sha256('stage032-peer-alignment-null-v1|'+u+'|'+i+'|'+j)的升序对应原槽；hash完全相同再按j排。只此一个确定null，不搜索seed，不强制去除identity排列；one-peer两者相同。COMMON raw q=0。新上市/缺失不补成0收益边，完整scope-grid留NaN；未来catalog节点名不入X。所有ready含541未知均输出，额外warmup仅ctxmissing不得删样本。

## 存储与学习器接口

034一次构建，event_ids.csv.gz列sequence_index,event_id按009原ready顺序。contexts.npz仅三个key main/holdout_0/holdout_1，各shape[N,9] little-endian f8，列依次market_lag_median_r1,market_lag_breadth,market_lag_iqr_r1,market_lag_missing,peer_count,rho_abs_sum,relation_missing,q_aligned,q_shuffled。语义state及诊断可另存身份/状态gzip，无原始绝对价格或大图。manifest包含protocol、parent_manifest、parent_review、context_npz(binding shape dtype columns)、event_ids_csv、calendar、counts、源码/终态及required角色。不可多scope覆盖、ID重复或错位。SQL/fit/金融=0。

三个模型相同19槽：公共18=S11+market4+n/Z/missing，q第19。COMMON原q0，ALIGNED q_aligned，SHUFFLED q_shuffled。公共18 scaler仅当年train/date weights加权population；q scaler把同训练行ALIGNED/SHUFFLED两值按各w/2合并fit，三臂共享mean/scale；COMMON经过同一scaler后仍是常数，截距吸收、有效方向18，不能靠次比较冒充同容量主对照。零方差scale1，不clip。所有模型Ridge(alpha1,solvercholesky,interceptTrue)，日期等权weights归一mean1，同19槽无额外head scaler/非线性。save pooledq scalers及每fit coefficients、ID/权重哈希/实际membership，最多108实际fit=2015..26×main/holdout0/1×三臂，fixture另计。所有ready先预测，score>0唯一mask，不topN或rare阈值。

## 成熟、留出与固定评价

年度扩窗cutoff=当年第一source date；train u<cutoff且label_known_date非空且<cutoff、feature_ready和identified为1，2010起；test当年全部ready。holdout_g训练排除g，测试仅g；peer输入与四摘要也排除g。测试query可用自己过去观察形成rho，不是zero-shot；不以当前query进入训练peer池或scaler。main/held覆盖差异完整报告，不能选较好组。

沿007原OPEN/0.25ATR SL/4R PT/DAY、0.2R基础与1R压力、proxy_lower训练；029没有改变本信息实验标签。双触达保留区间、未知不填负/0。相同事件payoff乘mask，ALIGNED-COMMON/SHUFFLED系数差乘共区间求精确端点，相同mask完全抵消；参与率诊断系数mA-日内p，非u可执行随机策略。date_equal/commonidentified，source-grid空日NaN。

报告2015..2026年度、all2015/primary2020、main/两个held/combined；main两期间60源日moving-block bootstrap2000/seed20261018、列共用索引，固定预测CI不含重训/研究选择/真实金融。20门沿022结构：primary已知入选dates>=60/families>=8（2）；ALIGNED自身lower95%CI下端>0、两pairedlower95%CI下端>0、参与率lowerCI下端>0（4）；all2015自身/两paired/参与率lower均值>0（4）；primary同mask1R自身lower>0（1）；2020..25至少4/6年两pairedlower各>0（2）；2026自身lower>0（1）；两个held primary自身/两pairedlower各>0（6）。NaN失败。事后profit_only/双触达目标先达比例上下界、误删确定PT及unknown选择率只诊断，不叫真实胜率、不改mask。

## 运行、独审、停止与反思

034数据、035模型各唯一完整run；root fresh接收034且037设计无阻塞、必要fixture绿色后才启动108fit，真实失败保留源/终态再判断必要适配，不因观察超时重启。037独立review（036保留root决策编号）审时钟/own与held污染边界、保存数据、108fit训练成员/缩放/全预测、预选6正规方程、全部统计/CI/20门；不复训，不SQL，不导入作者计算功能。必要资产显式requiredrole，本地登记不commit/push/生产。

成功仅支持这一个固定关系投影对DAY代理有继续价值，不是因果、真实收益/DD或加注资格。失败停止20rho/单q/此null/Ridge/OPEN包，不换窗口、lag、相关度、peer subset、seed、阈值或GNN救参；不把COMMON或SHUFFLED事后变赢家。大母体及复杂表示都不自动带来alpha。

开始新增按结果救参：否，032前于029结果，本协议前于新ctx/新fit；研究员历史多次择题风险有。继续价值：是，限这次真正新增对应输入的固定检验。重要突破否；新增参数relation20/null/19槽共享scaler，旧正式/已有模型参数与成绩修改删除0；当前新fit/金融/下载0。期末权益/总收益/DD/Sharpe/总滑点/交易次数/真实胜率N/A。目标继续active、未达成，不以本小代理替代原目标。
