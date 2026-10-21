# Stage022：固定20bar历史信息对照协议

line_id=`futures_full_market_long_signal_ai`；2026-10-18 12:29 CST。当前分支沿用codex/ai-training-data-expansion。用户完整目标为全市场全品种超高质量long信号、更高净收益和更低回撤，随后独立验证极窄止损与加注。本次是该目标的单项信息筛选，既非正式A/B/C晋升，也非账户收益回测。沿Stage021预结果设计，不改官方代码/配置、行情、资金或执行。

## 本轮问题与判断

同一个固定小容量非线性学习器，能否利用过去20bar在S11摘要之外的值和时间顺序，改善固定OPEN代理的样本外机会识别？主要对照为ORDER与BAG；S是次参考。可检验的信息来自同epoch历史价量的低压缩表示，而非新增外生源。继承四market-lag与单项CONFIRM失败，禁止更换其参数救参；本轮不复跑旧研究。

已查原作者Lo/Mamaysky/Wang (2000) MIT全文 https://www.mit.edu/~alo/Papers/1705-1765.pdf 、Rahimi/Recht随机特征原论文 https://people.eecs.berkeley.edu/~brecht/papers/07.rah.rec.nips.pdf 、MiniRocket原作者 https://github.com/angus924/minirocket 。借鉴可检验统计表示与固定随机映射接凸头，不复制金融收益、不安装/运行外部代码。MiniRocket默认10000映射不是本轮小容量；采用128个预先固定RFF只限制成本和容量，不预设最佳模型或信息论公平。

开始过拟合判断：新增选参否，本轮先固定单一表示、容量、种子、带宽和门；研究员反复看历史与新增表示维度仍有选择风险。继续价值：是，限一次固定试验，直接接近用户的全市场AI识别，不继续盘点或工程代替结果。

## 母体与特征

沿009/011接受的399252品种日母表、全部194709 feature_ready，同样的真实reference_epoch与21个连续有效bar、source calendar跨度恰20。完全不以D是否可评价决定输入准入，541 ready未知标签必须保留/预测。六所全历史范围、F归家族规则、排除无效历史及标签合同不变。新矩阵只存ready身份，不删除原母表状态；没有新setup、AI池、C9过滤。

窗口j=0..20，j20=u，输出j=1..20四通道：(Cj-Cj-1)/ATR20(u)、(Hj-Lj)/ATR20(u)、(Cj-Lj)/(Hj-Lj)（平价0.5）、log(Vj/mean(V0..V19))。ATR20复用009的20TR均值。不得为每个j另加暖机，不拼逐日主力，不跨epoch、不补缺口、不读D作特征。

序列数值先以float64计算，再统一转little-endian float32存为ordered[N,20,4]，全表有限断言；消费时float64计算。此量化是固定存储合同，可能损失小数信息，不按结果改精度。event_id伴随映射CSV，顺序与009原文件ready行完全一致。npz只存ordered，无原始绝对OHLC、成交量或绝对ATR，不复制raw DB/CSV。BAG由已存四元组完整字典序(收益,振幅,位置,相对量)排序得到，各字段一起移动，相同四元组不加日期/index tie；不重算收益。ORDER按旧→新20位置展开，BAG按排序后位置展开，二者保留同一S11。

三臂：S=原OWN11；ORDER=[S11,ordered80]；BAG=[S11,canonical_bag80]。日期、产品、epoch、family只切分审计，不入X；原四market-lag、D坐标/原价/标签不得入X。

## 固定学习器、成熟与留出

S训练侧按原日期等权样本权重做加权population均值/方差标准化，零方差scale=1，无clip。四序列通道仅在当年同训练集合、跨20位置池化，以每样本原日期权重/20计算共享4个均值/尺度；ORDER/BAG共用，不能按lag独立缩放。S也使用相同训练行与S scaler。

固定numpy default_rng(20261018)，先生成normal(0,1) W_base[91,128]，再生成uniform(0,2pi) b[128]，保存实际数组。S使用W_base前11行/sqrt(11)，ORDER/BAG使用全部/sqrt(91)，即gamma=1/(2*d_active)。phi=sqrt(2/128)*cos(z@W+b)。三个头输入均为[S_scaled11,phi128]，139项加截距；Ridge alpha=1, solver=cholesky,fit_intercept=True,原日期权重均值归一至1。RFF与头后不再fit第二scaler，W/b不学习，alpha/window/gamma/seed/宽度不搜索。最多108个真实fit=12年×3scope×3arm，fixture另计，不看收益中途停选臂。

沿007年度扩窗2015..2026：cutoff为当年第一source trading date，train要求feature_ready=1,label_identified=1,u<cutoff,label_known_date非空且<cutoff，2010起；test当年所有ready。主main与两个sha256(family_id)%2留出：held组所有历史不得训练，test仅该组；F同族不泄漏。原重叠窗、同步品种与伪PIT历史重建限制保留；预测保存所有ready，成熟只用于训练与事后评价。score>0唯一mask，不topN、不挑rare阈值。

## 标签、统计与20个门

OPEN、0.25ATR止损、4R目标、DAY退出、0.2R基础研究成本与1R压力完全沿007/009；双触达保留[lower,upper]、缺D/删失保留未知，不重标负类。训练y=proxy_lower。所有统计是date_equal normalized代理效用，N/A现金权益/收益/DD/Sharpe/真实滑点/真实交易胜率，不将事件路径累加为组合回报。

每source day只在共同identified cohort评价，mask m_A乘同一[L,U]，不选=0；无identified日NaN而非0。ORDER-S、ORDER-BAG用系数(m_ORDER-m_ref)乘共同区间求精确端点；相同mask完全抵消，不用不同入场的018外界。ORDER减日内参与率p=m_ORDER均值的共同机会随机参与诊断，同样系数区间，不冒充u可执行随机策略。压力成本为同mask每选中事件再减0.8R。对已知/未知样本分别报参与率和支持；未被选中的profit_only/双触达机会以诊断记录，不反选阈值。

年度2015..2026、all_2015及primary_2020各报main/holdout0/holdout1/holdout_combined，source grid保持空日。主main两期间60source-day moving-block bootstrap，2000次，seed20261018，所有列共享索引；固定预测CI不包含重训/研究选择不确定性。主结论同时需ORDER自身保守代理及两个对照增量；部分识别界与CI分别解释。

20门全部通过才允许称固定信息筛选有继续价值：2020+选中已知日期>=60、family>=8；ORDER自身lower的95%CI下端>0；ORDER-S及ORDER-BAG的paired_lower95%CI下端均>0；参与率诊断lower95%CI下端>0；all2015 ORDER自身/两paired/参与率lower均值全>0（4门）；2020+同mask1R压力自身lower均值>0；2020..2025完整6年中至少4年ORDER-S lower正且至少4年ORDER-BAG lower正（2门）；2026 ORDER自身lower正；两个family留出各要求自身、两paired2020+ lower均值正（6门）。支持不足/NaN视失败。

稀有高质量只做预声明诊断：mask入选identified样本profit_only比例下界及加double_touch比例上界、区间宽度、事件/日期/族支持、误删确定profit_only数，注明不是胜率或可交易质量证明。BAG胜S但ORDER不胜BAG仅支持值分布；ORDER胜BAG不胜S不支持新增表示价值。正结果最多是固定学习器可利用表示，不是模型无关或因果顺序证明，不直接窄损/加注。

## 运行、独审与后续

023负责一次只读SQL建立序列、必要行为tests及source/schema适配，不重hash378MB DB、不跑旧套件。024负责冻结协议实际108fit+预测/统计，不导入018标签结果，不调整策略参数；每个fit保存训练ID/权重/scaler/RFF/头系数/版本，完成后可export-only不重训。失败尝试/实际句柄/终态保留，必要修输入不可静默重跑。025独立验算新表示/成熟族留出/系数预测/区间/CI/20门，不复跑模型fit或旧金融回测。归档必要决策资产，不复制原始行情、秘密或模型缓存替代实际输入。root维护LINE/registry，不修改他线。

本协议冻结时新增fit/金融/下载0；参数新增为20bar×4/三臂128RFF固定映射，修改/删除既有策略参数和成绩0；财务指标全N/A。若失败停止本表示+学习器+OPEN包，不扫窗口/形态/深度/种子/bag/止损/加注救参。目标仍完整active，金融净收益/回撤、执行容量、窄损与加注生存门未达成。结束反思在root结果stage按真实证据另记，不能提前声明成功。
