# Stage002 基差与会员持仓相对特征预注册

## 阶段身份

- 预注册时间：2026-09-03 02:56 CST
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 线上逻辑回归基准：`m0005_20260901T165450+0800_1961d98ccb2b`
- 上游决策：Stage001=`stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration`。
- 当前授权：只冻结Stage002无标签特征合同并申请独立预审；预审通过前不实现，且Stage002实现通过也不授权读取标签、训练XGBoost、回测、holdout、CTP或订单。
- 是否重要突破：否；本阶段只构造未来模型可能使用的输入。

## 已披露的无标签勘察

- Stage001之后仅使用其冻结面板做了无标签退化审计，没有读取收益、回撤、账户或holdout标签。
- 已观察固定候选子集为rank10及以后`374`行/`47`月/`18`品种。
- 基差与会员持仓同时完整且每月至少有rank10加2名挑战者的活跃月为`35/47`；前18月`13`个、后续17个development月`13`个、最后12月`9`个。
- 活跃月完整模型行`218`，其中rank10锚点`35`、挑战者`183`；前18月`62=13+49`行，后17月`91=13+78`行，最后12月`65=9+56`行。
- 五个物理差值在183个完整挑战者上分别都有183个唯一值且精确零为0。两项基差差值Spearman相关`0.8510`，其余绝对相关均不超过`0.2925`；因此保留两项基差原始含义，但不再增加派生交互。
- 上述数字已见，不是独立OOS结果。Stage002将其冻结为构造身份和退化门，不能用于声称模型有效。

## 冻结输入

- Stage001特征面板：`artifacts/stage001_physical_positioning_coverage/physical_feature_panel.csv.gz`，SHA256=`62ac505b07412bbd2f5110f6131ce9a9638a47942558ae93da28601731755d7e`。
- Stage001 summary：SHA256=`cc6c4ae3131928190f382da154af9460c2239d33c88665c3696987ea2cac99f1`。
- Stage001 family coverage：SHA256=`e96da5d74265a311b223a37245e31ae95f3c6b520df9947d010798c2113d69e6`。
- Stage001 manifest：SHA256=`c4436bef32a174e699a7f736a383591d3ef581c9c3fd00ee38ed076b562a29fa`。
- Stage001必须保持决策通过、合格家族精确为`basis/member`、诊断家族精确为`warehouse`、PIT违规0、标签/fit/回测/CTP/order均0。
- Stage002规格文件自身SHA将在独立预审前写入未来实现合同；任一输入身份漂移必须失败关闭。

## 候选和完整证据定义

- Stage002保留Stage001中`a_rank >= 10`的全部374行；每月必须有且仅有一个rank10，rank连续且不超过18，连接键`eval_date,product_vt_symbol,a_rank`唯一。
- 行完整定义：该行`basis_available=true AND member_available=true`。
- 月活跃定义：rank10行完整，且完整挑战者至少2行。
- `model_eligible=true`当且仅当该行完整且所在月活跃；禁止按产品、年份或未来结果覆盖此机械定义。
- 非活跃月和非完整候选保留在全量审计面板中，但不得进入未来XGBoost训练、预测或选择。它们的策略动作固定回退线上逻辑回归A，即rank10不变。
- 仓单及其可用性不能进入特征、模型资格或未来selector；不得为了扩大样本放宽Stage001结论。

## 冻结六项特征

对每个活跃月，以该月rank10为锚点，特征顺序固定如下：

1. `formal_probability_delta_vs_rank10 = pit_logistic_probability(candidate) - pit_logistic_probability(rank10)`。
2. `basis_dom_rate_delta_vs_rank10 = basis_dom_rate(candidate) - basis_dom_rate(rank10)`。
3. `basis_near_rate_delta_vs_rank10 = basis_near_rate(candidate) - basis_near_rate(rank10)`。
4. `member_net_position_ratio_delta_vs_rank10 = member_net_position_ratio(candidate) - member_net_position_ratio(rank10)`。
5. `member_net_position_change_ratio_delta_vs_rank10 = member_net_position_change_ratio(candidate) - member_net_position_change_ratio(rank10)`。
6. `member_turnover_pressure_ratio_delta_vs_rank10 = member_turnover_pressure_ratio(candidate) - member_turnover_pressure_ratio(rank10)`。

- 六项模型特征不包含`a_rank`、rank距离、产品、交易所、年份、月份、来源日期、来源年龄、可用性、仓单或历史策略结果。
- 不做填补、标准化、winsorize、clip、符号翻转、分位变换、阈值、交互项、PCA或特征选择。
- `model_eligible`行六项必须全部有限；每个活跃月rank10六项必须逐位精确为0。
- 挑战者五项物理特征各自唯一值必须`>=150`、非零行必须`>=150`；这是冻结数据退化门，不用于择优。
- `model_eligible`和可用性字段只允许进入审计元数据，不得进入未来模型矩阵。

## Stage002技术门与工件

- 输入运行前后SHA逐文件一致，双跑DataFrame逐值一致，输出稳定排序为`eval_date,a_rank,product_vt_symbol`。
- 全量候选面板必须精确`374`行/`47`月；活跃月精确`35`，模型资格行精确`218=35锚点+183挑战者`。
- 前18月、后17个development月、最后12月的活跃月必须分别为`13/13/9`，模型资格行分别为`62/91/65`。
- 活跃月按年份固定为2022/2023/2024/2025=`8/10/9/8`。
- 发布`candidate_physical_feature_panel.csv`、`model_eligible_feature_panel.csv`、月度资格表、特征退化表、summary、report和manifest；manifest必须覆盖全部持久工件并可现场复算。
- 标签列读取`[]`、标签值读取`false`、sealed holdout标签读取`0`、模型fit `0`、策略回测`0`、CTP连接`false`、订单API调用`0`。
- 通过决策固定为`stage002_physical_features_pass_ready_for_training_contract_preregistration`；任一门失败固定为`stage002_physical_features_fail_stop_no_model`，不得补值、删月、删品种或改门救援。

## 后续模型边界

- Stage002通过只允许另写Stage003训练合同并独立预审，不自动训练。
- Stage003必须保留逻辑回归A；XGBoost只挑战第10席，Top9、固定`fu.SHFE`和其他正式规则不变。
- 当前开发数据只有26个活跃月，首折只有13个训练查询组/62行，属于小样本高过拟合风险。未来模型必须比旧线更低复杂度、固定单一规格、无参数扫描，并对没有完整证据的月份机械回退A。
- 未来任何标签必须沿用已审计的35月正式账户边际标签及其逐折后开状态机；不能解析sealed holdout标签，也不能把Stage006失败结果用于调参数、selector或效果门。
- 后续是否采用单头还是双头、模型参数、qid、成熟期、selector、替换门、效果门、分年和leave-best-out要求，必须在Stage003一次性冻结，不能在本文件中保留可选分支。

## 开始反思

- 是否过拟合：**Stage002无标签构造本身否**，因为只做事前固定的相对特征和完整证据过滤；但样本资格数字已经被看过，所以Stage002通过不增加统计置信度。若为了增加35个活跃月而引入缺失指示器、原生NaN或放宽完整性，就是利用缺失结构救样本。
- 是否值得继续：**有条件地是**。183个完整挑战者上的五项外生差值均非退化，足以验证构造；但后续development OOS只有13个活跃月，模型实验必须被视为高风险、单次、可证伪资格实验，而不是上线候选。

