# Stage374：最新成熟训练薄入口独立审阅

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 04:43 CST；非重要突破。审阅者独立于373作者，只写本文及本线374小收据，不改源码、LINE、registry、359/T0或370初态。
- 当前结论（04:47更新）：**实现静审、唯一独立合成fixture与真实训练独审通过，无P0/P1/P2。** 算术与训练边界置信度高；支持root另记真实T1并按事前计划只作未来评价，不能证明盈利或窄损加注资格。

## 协议与实现静审

先读registry，确认归属本线。372协议实核7908B/SHA `d854a77e3935f290c554399718f51f8bb775849372d39e8ecd88b9cd72c85001`，130/071原源SHA均与协议相同。373工具20873B/SHA `d8a1fb886fe79b95e6c4e33c3c3973f05da715ceafdd3ad7c8b5716ce8598080`，prepare/source_bundle/未授权模板精确相符。

成熟筛选保持eligible=1、closed_complete、finite原net_R_stress、非空known以及u/known均严格早于2026-10-20。实体输入仍限定accepted129至16日快照；不能把16日open或19/20日新观察补造成成熟。old2023同门仅计数，新增成熟为0则fit前停止。输入原SHA、全1552456动作顺序、必要alias、26列顺序/float64形状及source冻结检查均保留；按明确限定不读mothers或重做原始行情资格。

AST提取原130并集/训练权重/design和071 finite_stats、COMMON字面量，避免导入旧runner。完整新成熟集重新计算family-u并集、同family并发uniqueness、组内均分、等u及均值1；scaler只用新训练集的原加权finite统计。52列、非有限标准化0与26missing、alpha1、intercept、cholesky、thread1保持；正规方程只惩罚52斜率，截距不惩罚。

新入口只有一个Ridge.fit调用及attempt/complete回调，没有旧六fold、历史pred/choices/held/cash分支。root精确协议/源码/输入/输出授权先于实体读取；失败保留输出、不自动重试。实际全局一次预算仍由root执行纪律与唯一授权落实；本文不签发授权、不重试。正常完成T1仍为空，后续必须另记真实冻结事件。

## 唯一独立合成fixture

审阅者另构造12行、其中5行成熟的单一case，未运行作者fixture或旧suite。两family、两个u日，包括跨组重叠并集与同组多月。手算期望权重为`[15/28,15/28,15/14,10/7,10/7]`；独立逐列计算加权finite mean/var/scale与52设计，核全missing和常数列fallback。

分别隔离u=cutoff、known=cutoff、blank、unknown、eligible0、nonfinite目标和open排除。剧烈毒化全部被排除行X/Y后，训练X/Y/权重/scaler逐项不变；无新增成熟的case在fit前返回。未授权模板在大实体I/O与目录创建前拒绝。唯一合成Ridge的predict被禁止，结果与独立53维加权正规方程线性解相符：最大系数误差`3.2751579226442118e-15`，最大方程残差`3.552713678800501e-15`。

[pre-actual收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage374_latest_mature_refit_review/pre_actual_fixture_receipt.json)保存精确绑定和检查清单。审阅者合成fit=1，真实fit=0，两大训练实体读取=0，历史预测/cash/SQL/API/Git=0。

## 调研判断、变更与反思

当前是372固定合同的实现审阅，不新选模型/字段/参数或启动新研究；方法依据沿371已经核对的官方时间序列与维护者评价文档。判断仍为：固定规则吸收后来合法成熟资料有有限价值，不能把已曝光历史重新称作未见检验，数学验收也不能证明盈利或窄损加注资格。

- 本阶段新增/修改/删除训练参数0；新增/修改/删除回测结果0。权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。
- 开始与结束过拟合判断：本轮按新成绩调参，否；理由是只验证固定训练合同及合成算术。既有历史择题偏差及新增版本自由度仍有，不以本轮消除。
- 开始与结束继续价值判断：是；理由是独立验证训练边界、重算权重/scaler与未来隔离，允许随后一次固定训练接受未来反证；重复旧史择优没有价值。
- TODO（初审时）：等待root实际训练完成后，必要actions/common各读一次，独立重算成熟mask、行/组权重、scaler、正规方程和portable模型一致性；不重新拟合、不跑旧财务回放。原2023参考和T0/370账户状态保持独立。

## 04:47：真实训练结果独审

root通知373唯一actual完成后才开始本节。核精确root授权、协议/源/输入/全部产物绑定、单条attempt/completed事件、terminal及manifest：真实fit=1、completed model=1，无自动重试、历史预测/选择/cash/SQL/download，T1仍为空。实际manifest6397B/SHA `7b6d0fa0ad5c27484330925ea2035ad96fc8eadca7f6c76eb47da305eab03cbe`。

审阅者原actions与common各只读一次，读入时核原byte/SHA；没有重拟合、正规方程求解或预测。独立重算原成熟门：全域1552456动作，成熟788336＝旧445475＋新增342861，排除764120；4054个u日、94个family，最大u为2026-10-15、最大known为2026-10-16。保存训练表的动作顺序与各身份、入退区间、状态及成熟日期核对一致，eligible均为1。

独审首进程在目标字段逐bit比较触发审阅器的过严检查：保存17g目标文本再次用`pd.to_numeric`解析，与原内存double有35878行微差，最大`5.684341886080802e-14`，并非目标单位、筛选或实质数值偏移。现场与累计actions=1/common=0保存在[action解析说明](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage374_latest_mature_refit_review/action_pass_numeric_parse_note.json)。root明确同意有限解析适配后，从已核身份的保存训练表以Python float roundtrip继续，不重读actions、不追逐bit0、不改模型。

独立实现并集合并，并按每段逐日直接求逆并发平均，区别于原函数的prefix积分；全部191284组的身份、成员数、并集长度/区间及uniqueness一致。全部788336行的组内均分、等u、均值1与保存权重一致，最大行权重绝对差`1.9308998844280723e-12`。只用对应训练行的原common26重算26列加权finite mean/var/scale/count，最大统计绝对差`5.3290705182007514e-14`。

分块独立重建52设计加截距的53维充分方程，只对52斜率加alpha1：与保存lhs最大绝对差`7.217749953269958e-08`、rhs差`3.841705620288849e-09`，属于浮点求和顺序误差，均通过既定数值容差。portable系数与保存方程向量逐项一致；独立方程乘portable的最大残差`1.1117663234472275e-08`，最大缩放残差`1.2267288373437176e-13`。没有实际模型重解或重fit。

[实际独审收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage374_latest_mature_refit_review/actual_training_review_receipt.json)11370B/SHA `8eab6012aeae1d016ef83b92db61eb45a3e09040b9271ebc6fbfb66f38a5df72`保存绑定、全部统计差值与边界。审阅者累计actual fit/solve/predict/cash均0、合成fit1另计，两大输入各1read；不扩展旧suite、原始行情资格、生产门或其他候选。

结论：**PASS，无剩余P0/P1/P2；精确accepted129与固定372范围内算术置信度高。** 原始标签/OHLC资格沿接受链继承，本文没有重新证明其经济真实性；更没有证明未来收益、窄损加注、C9接入或生产资格。训练更新的价值仍是让单一固定候选接受之后真实新数据反证，不能用旧成绩择优。结束过拟合判断：本轮没有结果驱动调参，但继承历史偏差与新增版本自由度仍在；继续价值：有限未来验证有，重复历史筛选无。

本stage不创建T1或资金状态。后续由root375完成新模型独立身份/实际T1冻结，按事前评价计划仅接真实T1之后完成且按时收到的新u；原2023参考/T0与370初态不借用。所有金融指标仍N/A，完整目标尚未达成。

## 04:51：新T1冻结的小型关系补核

root已签新T1为`2026-10-19T20:48:38.399842+00:00`（北京时间20日04:48:38.399842）。本次只核375冻结小材料、模型/scaler副本及journal关系，没有再读actions/common、71MB训练表、2.7MB组表，没有fixture、fit、算术扩展、预测或资金状态。

375 manifest22456B/SHA `a0f810e1bd68c9aca27f34f707e94414905c51c455c39dd9881fb1017c5f1d37`、event2084B/SHA `c7722a82f22b9a281e813c15c843365014da88e6965d32b8c2939a8f250a1235`关系一致。17资产中15个小副本逐项byte/SHA核对通过，2个新训练identity/groups只核既有绑定引用；4个accepted训练输入只核引用保留。model/scaler副本精确保持实际373 SHA、main/cutoff20与52列，未混入359旧2023模型或370账户状态。359 sourceclosure只作原因果特征/选择定义的引用，没有因此认定新模型forward wrapper已完成。

审阅器初次假定canonical没有结尾换行，entry hash不相符；随后只定位321原`_canonical`定义，确认排序compact JSON必须加终端LF。按原规则核policy、payload、entry三层hash均通过；唯一genesis entry为`ac189736efe1f921df70d6579a26fb3801755609dd712b4cead3a82ccf6a8b13`。这是审阅器假设适配，不是冻结材料变更，没有自写或重签journal。event/result/journal的T1一致，晚于manifest准备及实际独审；manifest本身保留事件前T1=null，真实时点取journal/event。

[T1小补充收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage374_latest_mature_refit_review/newT1_small_freeze_review_receipt.json)6001B/SHA `708322172d344f84c8c20a197897cb816c27cd0c1b3625f287a6719557beb72d`。结论**PASS，无P0/P1/P2**；active=false、account_states=null、alpha=false、future_predictions=0边界保留。冻结仅确认本地新模型身份和真实未来起算点，未建立forward评分wrapper、资金封印、跨机runtime、生产资格或外部时间戳证明。无需追加验证或重读训练实体；完整目标仍需之后真实新观察反证。

