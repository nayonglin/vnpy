# Stage267 严格月度样本独立审查

时间：2026-10-17 19:59 CST。line_id：futures_trend_rollover_shape_same_volume。本轮只读审查月度构造工具与最终输出，未运行金融引擎、重清洗、模型拟合或预测。开始过拟合判断：否，没有按收益修改参数；继续价值：是，需要确认新增历史究竟产生多少有信息、时间边界正确的样本，而不能以文件数代替训练资格。

## 最终判断与产物身份

**PASS，P0=0/P1=0/P2=1，限定月度样本构造、资格与标签数学。** 不把这些样本称为历史PIT、独立OOS、盈利或部署证明。

只绑定最终 `outputs/stage267_monthly_samples_final/`：工具SHA `e7932ba5b0669c80a1449da63487e3be909792d62571d3427880e959f48b2ccf`，与final sample_summary执行记录一致；tests SHA `0de9bae4553a17b68f6624beeb9d38de5b4616231f9261205e3b1581173eab9e`。原108特征函数文件SHA `7734d1768728a4e591b80e98da2b5bac90636904dad82e0fed5f331a6eb45de4`，窗口helper固定SHA `6617da56dded1d16eb7215affb966b7498063fc706b38562e91df7f574c2ba7c`。

独立证据 `tools/stage267_monthly_independent_review.json` SHA `bea343656b6719403e29499056fe6e170d356b7b0d66c3e83518281ade5bfd5d`，绑定最终代码、测试、helper、所有实际月样本、源calendar/coverage和来源PNL/候选CSV。

## 独立数值核对

没有调用月样本实现重算真实结果，而是从1,440,036条原合约日期PNL自行按产品聚合，结合明确源交易日历和coverage，对全部3,618条月样本重新计算120日历史/后60日覆盖、首尾日期、资格后截面、排名、target及weight。

| 层次 | 行数 | 月数 |
|---|---:|---:|
| 全部真实月末 ×18产品 | 3,618 | 201 |
| 完整历史/标签及截面至少8的资格样本 | 544 | 55 |
| 非常数、有排序信息的样本 | 535 | 54 |
| 同一clean source、2020年前有信息样本 | 61 | 7 |
| 同一clean source、2020年及以后有信息样本 | 474 | 47 |

- 实际源PNL合约日期重复0；聚合后48,530个有物理来源产品日。原PNL首日2010-05-18，日历开始2010-01-04；更早网格占位值没有被冒充观察，coverage失败会排除相应窗口。
- 全部3,618条月窗口的日期/coverage元数据错误0，资格和有信息键集合与独立结果完全一致。
- 所有完整60日标签与独立逐日和相比，最大绝对差 `2.1827872842550278e-11`，为浮点求和次序差；label区间严格为 `(eval_date,label_end]`，不含评估日、不含第61个未来源日。
- 独立检查20/60/120日PNL sum/mean/std/min/max五类，共14,595个特征哨兵值，最大绝对差 `1.929052473315096e-09`。108列完整名称和顺序与Stage263冻结schema精确一致；不声称这组哨兵等同重新独立实现全部108公式。
- 排名与weight最大绝对差分别 `1.11e-16`、`8.33e-17`，target不一致0；全部有信息截面均至少8个合格品种，排序在剔除不合格品种后重算。
- 2019-10-31一个合格截面9行未来PNL全零，保留在qualified，target/rank为空，从informative排除；非常数的非零全同月份0。535条informative中仍有120条单品种未来PNL恰为0，这些处在非恒定截面，相对排序有定义，不等于整月没有信息。
- asof为2026-10-14收盘后，535条有信息样本全部label_end<=asof，最大label_end为2026-09-22；最后有信息eval为2026-06-30。7月及以后不能用不足60个源日的旧partial label混入。

旧Stage263相比新增43键（2017年35、2018年8）、减少802键，只是不同条件来源的键可用性比较，不能归因为数据扩展提升或恶化。主要增量判断应使用同一clean source的61/7与474/47分层，避免拿不同收益路径混比。

## 源码与边界检查

`load_original`第50–61行核对原文件SHA；`frozen_features`第64–69行限定108个唯一有序列，构造第122–125行再核对生成集合和有限值；模型特征名单排除future/target/sample_weight。原函数只有向后rolling、当前及过去candidate/PNL聚合，未使用负shift生成输入特征；后续负shift只用于显式未来标签。全样本宽表包含标签和诊断列，未来训练仍必须显式选择冻结108列，不能使用所有数值列。

`construct_samples`要求完整源日历×18产品网格、无重复日期键、显式布尔coverage；缺失coverage填False，不作已观察零收益。history必须完整120日；未来必须完整60个严格后续源日，同时逐日coverage成立。原特征函数在网格上保留的0/中性占位不会让coverage失败窗口获得资格。

月末来自完整权威源日历的每月最后一个交易日，再与source_end相交，未把2026-10-14当成10月月末。截面数量在每产品资格确认后重算，少于8整月无资格。全零/常数标签月在建模可用集剔除，qualified仅作资格账，不应用来直接训练含空target的记录。

`mature_asof`明确要求label_end<=asof且eval_date<asof，是收盘后口径。时序训练须先于测试，不能随机打散互相重叠的60日标签；本轮只验证资格与计数，不训练。[scikit-learn官方TimeSeriesSplit说明](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)

唯一P2：工具第281–282行的asof检查验证午夜、无时区、不超过source_end，但没有明确验证其属于源交易日历；周末asof可通过，与错误文案“source date”不完全一致。不过成熟集合只会等价于此前源日收盘，未见额外未来行；本次实际10/14属于合法源日，没有实际结果影响。无需为此重跑金融来源。

## 发现修复与测试

首次20项小型测试有1项失败：重复(date,vt_symbol)原合约PNL未被拒绝，会被旧聚合器计两次。实现者已在prepare_daily第197–198行添加fail-closed重复guard，最终20/20测试独立复跑通过，含未来PNL扰动不改变eval108列、59未来日拒绝、缺history/未来mapping拒绝、截面7品种拒绝、全零/常数剔除、标签不含评估日和第61日、经济字段缺失拒绝、无openOI及空candidate来源等边界。

初始census执行版SHA也与修复后源码不一致；root仅重建纯月度census到final目录，未重跑金融来源。独立逐字段比较初始attempt与final五份CSV（all/qualified/informative/monthly/annual），全部列值完全相同；实际来源无重复，因此增加guard只改变错误输入的拒绝行为。最终执行SHA已正确绑定，两个P1均闭合。

## 结论适用范围

108列本身与窗口未来标签隔离成立，但上游收益源使用事后冻结策略和2020–2022训练的pairwise模型，早年反事实收益并未获得真实历史可见模型。正确的label_end成熟门不能反过来认证上游政策为PIT。这批资料可以作为条件化的研究样本和可用性审计，不能声称正式投资表现。

本轮只新增本review MD/JSON，没有改实现、LINE/registry、任何数据库、原始产物或正式入口。金融回放0、模型训练0、预测0、下载0；权益/收益/Sharpe等不适用。结束过拟合判断：否，没有收益导向救参数；继续价值：有，61条早年有信息增量真实存在，但规模有限且标签相关，后续研究须保持PIT和独立性边界。
