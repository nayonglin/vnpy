# Stage088 OI信息对照独立审查（协议预审；尚未冻结最终记录）

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 17:41 CST。
- 独审角色不参与085来源、086拟合或087现金实现。既有081/072全部冻结不改；不修改LINE/registry。
- 重要突破：否。此阶段只有084协议有限静态反证，来源/模型/现金尚未接受，所有金融指标为N/A。

## 调研与判断

重新读取研究registry、084固定JSON/中文计划，并核已接受common26列清单和Stage266单位合同。primary网上调研：[CME OI/volume定义](https://www.cmegroup.com/trading/about-volume.html)、[vn.py维护方BarData实现](https://github.com/vnpy/vnpy/blob/master/vnpy/trader/object.py)。OI是未平仓匹配合约存量，不能解释成净多资金；字段独立存在或默认值0也不能替代真实观测来源。该固定OI数量变化可在OHLCV/common26相同时不同，所以不是已接受特征的纯代数换分母；不可恢复并不证明可预测。

## 有限科学预审结论

Critical/Important均0。唯一标量为同一真实epoch、相同可比source、完整源索引v=u−1及w=u−2的 `(closeOI_v−closeOI_w)/V_v`；canonical单边不二次除2，0OI/0变化合法，非正分母和不可比来源保留missing，不裁剪/拼接/按结果修复。current u和D不进入该OI输入。历史归档不是首次发布PIT，这个已披露限制不扩成生产来源资格门。

CONTROL/OI共同26因果值+26missing+1共享OI-missing+1标量，共54槽；CONTROL最后槽恒0，fold成熟训练内加权均值/总体std，固定Ridge1加性线性检验。自身NARROW标签/maturity/family并发唯一性再u等权不改，2020/2023两截点，各main/两个训练外familyhash组，合计12fit。held组只诊断、不选现金模型/组；已知标签按u聚合的差异不是现金收益。

主预测保留完整161014身份，ready只用于动作门；missing和未来未知/开放标签不筛交易。main两臂×两起点×两成本共8个新内生账户，回到accepted070原分配，不叠加已停止080。原.25N/Wilder/20low、成本、风险率、保证金和D只减配额不变；共同固定索引CI与冻结继续条件不改。若CONTROL空账户，DD继续继承accepted070的NA/unidentified处理，不能用0DD机械否定非空信息臂。未知动作差异不填0，名义通过也不自动宣称经济资格。

继续价值：有，限一次固定弱先验信息增量反证。新增按成绩调参：否，当前无新结果且公式/模型/预算已冻结；但已见多轮同历史，仍有研究者选择偏差，不能称全新OOS。若收益/风险/置信证据不支持，应停该固定包，不改OI变换、方向、阈值、窗口或品种救结果。全市场高质量long及未来加注目标仍未达成。

## 参数、结果与待办

本轮预审新增/修改/删除实盘参数均0。拟议研究新增仅一个OI标量；原标签/stop/资金参数不变。实际新增或修改回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。独审0SQL/fit/cash/金融回放/旧suite/旧模型核验，没有下载市场数据。

协议精确绑定和11项有限检查见 `outputs/stage088_oi_independent_review/protocol_preflight.json`。085/086/087最终代码SHA收到后只做一次聚焦源码预审；三个最终实际manifest由root精确绑定并另授权后，才进行唯一一次完整实际总审。允许的真正新OI SQL独立重构尚未执行，不重复旧清洗链或全DB/H5哈希。本文保持未冻结，最终源码/实际章节后续追加；预审收据不绑定本文可变SHA。

## 2026-10-18 17:50 085一次有限来源源码预审

C/I均0，来源实现静态通过，不代表来源actual或金融结果已通过。最终085源18,962B SHA256 `a49ec12a3c5978846f0b3c9c2033c0f856f411d4a6efc734c04d62db6f5d4ccd`；测试5,645B SHA256 `6e3c95cb9992b4bc4f27178743a2417004d9c26a79a85a34c0018e186b33c5df`；作者实现收据4,541B SHA256 `37522873dc91f056161bb2aa6d667b47a1541d20dce855c65d826f0765aab99a`。并绑定收益前澄清2,167B SHA256 `b72cfec8e934a9e347359f1a6f3bbb1384de2a6303c0b6b0bf5089bdab23b776`，原084协议不改。

已读源全文和七个新边界fixture：严格current epoch两calendar lag、缺日不跳、同source、canonical因子不重除、合法零、大比率不裁剪、无openOI依赖、无证据单位/分母无效保留missing。official来源继承既有acceptedcanonical，不要求不存在的raw unit_regime；RQ制度切换同样按已接受合同的canonical数量比较。只从原标签读身份字段，不读取价格或未来结果。单只读SELECT接sources.family，DB前后stat绑定，不做整库哈希或raw再认证。

已保存作者7新测试exit0/TDD RED记录，本独审只读收据与测试源码，另做2个AST语法检查，没有重复suite。具体manifest/terminal字段与projection消费者接口均按085真实schema核对，不假设别的stage字段形状。精确证据见 `outputs/stage088_oi_independent_review/source_preflight.json`。root可据此签085唯一source具体授权；086/087最终源及三项actual终态仍待后续审查。独审本轮0SQL/投影/fit/cash/网络下载，未改其他owner或既有冻结资产。

新增收益调参：否，本轮仅检查固定实现；继续一次预声明信息实验有价值，数据合格本身不构成alpha。本文仍live，最终金融阶段后再整体冻结；旧协议预审收据保持不变。

## 2026-10-18 17:52 086＋087唯一聚焦源码预审

Critical/Important均0。086最终源25,937B SHA256 `4af8d8ce1861eef9e16d87d8e6b338e23573da5a930e44045f642c42ceacc1a0`，新测试7,389B SHA256 `aeb1819a26481ef1e0ccc7575d9340cb6d1b08b30a1918f3758bc407cf7a442b`。087最终源25,330B SHA256 `162921962e5ef210a8a298f52494a1eb88102fdfcb6760a611f8e053e95713b8`，新测试8,808B SHA256 `59393252b4f8710c21c824f17c38a31afb5fea5c01f837ccba63602b63697277`。精确source/test/dependency/receipt/协议/澄清绑定见 `outputs/stage088_oi_independent_review/code_preflight.json`。085继续引用已冻结source_preflight，不重复审。

086排除held族后重算训练family区间并发唯一性、u等质量与均值1权重；各fold只用自身成熟NARROW closed，u与known都严格早于cutoff。26共同值及26missing、共享OI-missing组成53相同槽，CONTROL最后一槽0，OI只加单一标准化scalar，共54槽。common和scalar统计只来自当前成熟训练fold。固定2cutoff×3scope×2arm=12fit，保存独立重算所需weights/scaler/normal-equation/portable。总644,056预测：main每臂161,014，held两组并集每臂161,014，不因缺失、ready或未来结果缩母体。

held诊断只在已闭合、known不晚于source末日且ready20共同域内，先每u均值（含相同动作0），再u等权；保留两组完整2020前向mosaic、年度/2023视图、MSE差、完整标签状态与未知动作差异。名义known增量不能自动推成全机会价值。现金严格只消费main CONTROL/OI，不用held筛选；它们的共同系数可随新增标量重估，因此是固定线性信息包增量，不冒称纯OI因果效应。

087使用accepted070原run/reserve/quote/exit，未导入080、没有二次分配或评分投注。具体085、086 manifest/terminal结构已按真实源码核对；086需attempted与completed都12，禁止第13次或partial输入。8账户共用一次cash行情SQL，沿已绑定共同indices复算四对比较。空CONTROL DD为NA/unidentified；潜在score动作标签未知只进入signal_identification，不自动当u预算0/取消事件的实际现金未知敞口；正常开放仓按既定close mark并保留零价情景，不自动unknown；真实stale/held未决差异继续限制资格。

作者保存6个新模型测试及10个新cash测试通过，另明示累计12次极小fixture fit；这些不是研究实际12fit，本独审没有重复执行。当前只做4个AST语法检查及源码/收据读取，0fit/cash/SQL/旧suite/下载/085重审。该结论仅允许root在085完整source终态后，逐phase签实际fit与cash授权；三个实际manifest最终精确绑定、root另授权后，才执行088唯一完整总审。没有提前接受收益/alpha，目标仍active。新增收益调参：否；继续价值仍限原固定对照，不新增门或救援变换。

## 2026-10-18 18:05 088唯一完整实际独审：计算通过，固定OI包不支持

重要突破：否。085来源一次1SQL/24.653秒，086研究一次12fit/43.872秒，087一次8cash共享1SQL/18.579秒均已完成。研究累计345fit/78现金（作者另记12次极小合成fixture fit，不混入研究计数）。088完整独审于18:02启动、18:03终态，session `21674` / PID `21097`，64.955秒、exit0，**1次启动/1次完整，C/I/M均0**；无实际失败或重试。root已在收益前冻结协议/澄清和各源码，独审checker也先冻结后执行，源、参数、结果没有改动。

### 新OI来源与因果派生

唯一新OI列只读SQL独立重构399,252完整母体：206,012 observed、193,240 missing、1,826合法零变化、34个已接受canonical因子制度转换。只保留当期原epoch的224,647个v/w所需key，查得217,836个原始lag行；同source、质量/单位继承、源日连续索引、全部数量/因子/出处/missing原因和标量逐行一致，398条coverage行与7个确定性首例一致。DB前后stat相同，无整DB哈希、H5/旧清洗或原始单位/PIT链重建。该唯一SELECT仅读OI/V及其已接受出处、因子/质量字段；不读openOI、价格或结果，也不把当前u/D放入输入。

来源canonical沿已接受Stage266单边合同，不二次除2；真零保持为零，缺失保持共享missing。归档历史与完整前日lag仍是假设，不声称首次发布PIT。OI的非OHLCV可恢复性只是信息差，CME定义不把它解释成净多资金。

### 12模型、644,056个分数与held诊断

独立复算所有fold自身成熟u/known<cutoff的闭合训练身份、held族排除、family闭区间并发唯一性→u等质量→均值1权重，所有train-only weighted finite mean/总体std和imputation/共同54槽；CONTROL scalar恒0、OI只占最后一槽。逐模型重构55维增广正规方程（截距不罚，前54维Ridge1），核portable系数、保存lhs/rhs及全部644,056个分数、selected与完整前向身份。最大正规方程残差 `4.38012648374e-09`；跨全部数值比较最大误差 `2.07364792004e-10`，均在预定容差内。没有调用fit或加载作者core计算自证，旧966,084预测/旧模型和标签金融生成均继承接受而未重核。

|main截点|成熟训练行|CONTROL selected|OI selected|动作分歧|OI标准化scalar系数|
|---|---:|---:|---:|---:|---:|
|2020-01-01|81,903|548|546|4|-0.0030180458|
|2023-01-01|121,467|407|403|8|-0.0037997100|

主两臂在161,014个共同event中总共12个selected分歧（2020块4、2023块8），分歧是事先固定score>0的结果。四对资金fill的经济签名均有差异，不能把微小收益差写成同一交易碰巧估值差；新增标量引起共同系数重估，系数符号也不是纯OI因果证明。CONTROL同样拥有共享OI-missing，原070不能替代本轮必要CONTROL。

|held组|known共同闭合事件|known源日|每u等权名义增量R|未知动作分歧|状态|
|---|---:|---:|---:|---:|---|
|holdout_0|39,712|1642|-0.0013624123|0|unsupported|
|holdout_1|62,228|1642|-0.0009287227|2|unsupported|

两组known-u增量都为负，名义held门已失败。所有held按每u已闭合共同机会均值再u等权，包含动作相同的0，未知/未闭合不填0；完整标签状态、年度/2023重叠视图、全family-year和MSE差均核对。held_1另有2个未知结果动作分歧，限制全机会泛化。它们不是额外现金账户，也不拼接主账户、挑组或救阈值。

### 8现金账户独立算术

核3,008条fill、10,232个daily、4,386条position、5,434条预算（含6条既有持仓减量），1,499个closed root和8个open root。u权益/占用、原070共同scale/lot floor、所有因果selected事件保留或明确拒绝、D本事件配额只减、单family/总risk/margin预留、费用滑点、现金、浮盈、权益、风险冻结、root净盈亏与胜率逐项一致。全root初损、全部gap诊断、14个有限原生案例Wilder暖机/首次退出分支也一致，0完整策略/旧现金重放。86个gap止损fill中66个gross loss超过1R，窄初损没有被误写成每次最多亏1R。

|账户|期末权益CNY|总收益|最大回撤|Sharpe|总滑点CNY|总费用CNY|关闭交易|胜率|
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|CONTROL_primary_2020_base|1,125,252.8245|12.525282%|-11.748152%|0.297288|21,510.5905|8,992.1755|280|12.5000%|
|CONTROL_primary_2020_stress|1,183,779.6610|18.377966%|-7.993152%|0.487794|42,087.0837|20,550.3390|264|12.1212%|
|CONTROL_cold_2023_base|1,253,214.6225|25.321462%|-5.059567%|1.081092|6,514.1364|3,330.3775|108|12.9630%|
|CONTROL_cold_2023_stress|1,138,445.0910|13.844509%|-5.444063%|0.779726|13,996.9295|8,184.9090|98|12.2449%|
|OI_primary_2020_base|1,124,652.4730|12.465247%|-11.748152%|0.295000|21,520.4923|9,017.5270|280|12.5000%|
|OI_primary_2020_stress|1,184,637.2760|18.463728%|-7.993152%|0.489688|41,943.8229|20,552.7240|263|12.1673%|
|OI_cold_2023_base|1,252,230.7545|25.223075%|-5.350092%|1.064692|6,535.0381|3,364.2455|108|12.9630%|
|OI_cold_2023_stress|1,138,254.0050|13.825401%|-5.461627%|0.777545|13,980.2990|8,245.9950|98|12.2449%|

|窗口/成本|OI−CONTROL收益差pp|DD差pp（正较浅）|共同252日block均值日log差95%CI|
|---|---:|---:|---:|
|primary_2020/base|-0.06003515|+0.00000000|[-0.0000016513, 0.0000010299]|
|primary_2020/stress|+0.08576150|+0.00000000|[-0.0000028144, 0.0000039651]|
|cold_2023/base|-0.09838680|-0.29052416|[-0.0000034377, 0.0000017210]|
|cold_2023/stress|-0.01910860|-0.01756355|[-0.0000077763, 0.0000054811]|

既存两个共同indices精确绑定，独立复算4对配对日log差2000次/252日block/seed20261018、分布、CI及唯一gate。四CI均跨0；2023冷启与主窗重叠，不当独立复制。95family×year含零、年度连续切片、family totals、费滑/fillcount/qty归因、贡献集中与状态统计通过。

**接受研究算术；冻结继续门为 `unsupported`，固定lag deltaOI/V＋54槽Ridge＋NARROW包不支持增量优势。** 主stress略增0.0857615pp且DD相同，但主base和两成本冷启收益差为负，冷启DD更深，CI下端不为正，两held组known-u也负。即使忽略所有未知资格限制，该固定包仍不满足预声明名义门。结论范围限这次固定观测、加性线性模型与原止损/预算，不证明OI普遍无信息，更不是完成全市场高质量long或加注目标。

### unknown与可识别性

主信号未知标签动作分歧0，已知非参与动作分歧0；潜在标签不确定没有被当成实际零预算/取消事件的未知现金曝险。每账户期末1个正常open root，均非stale；按既定close mark估值并保留全开放仓零值情景，普通未来风险没有自动变成financial_unknown。两臂2020base/stress各有2/1个历史stale日；按冻结保守语义保存financial_unknown=True，held_signal_unknown=True，主signal_unknown=False。这些资格标志与名义unsupported分开，不以未知掩盖已观察到的负证据。

缺价执行、日OHLC内触发/队列/跳价和归档snapshot经济信息仍有限；14个有限案例不等于全库native重放。零价仅研究情景，不是普遍损失下界；未建立未知收益的有限置信界。单位/来源继承不成为新的生产或正式候选认证。

### 反思、变更与后续

新增按成绩调参：否。实际前固定公式、两臂/held、模型、参数、止损、成本、资金和继续门，actual后只读验证，负结果保留。研究者已见多轮同一历史，弱先验与模型选择偏差仍在，现有CI不能消除多轮研究选择。继续同一固定OI包救特征/方向/阈值/窗口/模型/品种：否，按原协议停止；全市场高质量long、窄损和未来加注总体目标仍active，后续需另有可反证的新机制/信息及事前预算，而非本轮自动触发下一实验。

新增研究参数/观测只有既定lag OI标量与共享missing；模型仍Ridge1、54槽，现金仍原070。实盘交易参数新增/修改/删除0；旧结果修改/删除0；本轮新增12个研究模型、8账户结果。没有应用已停止080、没有采用被否决083目标换分母、没有正式A/B、晋级、生产或加注授权。

### 冻结资产与复验入口

- checker freeze（2754B）SHA256 `83d3a0516297fdad49ae1c780ed621f9051f8039a41d53ce8103eb70694c1c7a`，含唯一命令与7模块源SHA；主checker（14164B）SHA256 `4fd7f4e875ab27f542adc0721bcb1bc54fd020d56d63189788eec2f70205f3d4`。
- 实际独审命令：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage088_independent_review.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage088_oi_independent_review/actual_review1`；保存命令使用绝对路径。外层process收据885B SHA256 `8c3cd1106d2e48a4da14ca47fd4c4c97eb5775c1a59614f543aa2de77754641e`。
- 最终独审receipt `actual_review1/review_receipt.json`（1,492,674B）SHA256 `c0a5e35dd15b9ac09a57b5c8853681415133be1103a704ae313561951e0e8da7`；terminal（320B）SHA256 `035e339cdccd69972c37eab69130380e15fcf5b080a12a384bf4f7667e874d6d`。
- 三个最终manifest：085 `a2b7c284ef2755ce0103c24cf16874fd66ae734ca9ba1cdc08e53cf76876c159`、086 `6b7f4e45b39663bcf9c356132d45bd4abc7d143b9f6846f58908ade56a27374c`、087 `4bd03bbf9862c021bb2de967f1d06a9ead6373f25f973dd64deca58312215784`。各自terminal、授权、源码、具体输入链和全部实际资产由闭包receipt绑定。
- `protocol_preflight.json`、`source_preflight.json`、`code_preflight.json`保持原冻结；分段证据及checker快照均在088目录。必要资产清单为 `artifact_inventory.json`，包含本中文stage最终SHA及作者/协议闭包入口。
- 本轮未修改081/072冻结物、作者源或结果、LINE/registry及其他线。本文在本次追加后整体冻结，后续决策由root另记。
