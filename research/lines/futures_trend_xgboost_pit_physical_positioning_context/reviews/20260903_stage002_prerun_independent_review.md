# Stage002 基差与会员持仓无标签特征预运行独立评审

- 评审日期：2026-09-03（Asia/Shanghai）
- line_id：`futures_trend_xgboost_pit_physical_positioning_context`
- 评审对象：`stages/20260903_0256_stage002_physical_feature_preregistration.md`
- 预注册 SHA256：`1acaacc180b778d4f311aa7f54ecb66069016423242cbac4cc91741858569ad3`
- 决策：`ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY`
- 严重度：`P0/P1/P2/P3 = 0/0/0/2`

## 结论

Stage002 的无标签特征合同具备进入 TDD 实现的充分确定性：冻结输入、候选过滤、完整证据、PIT 继承、六项特征、禁止变换、精确计数、工件、零副作用和未来训练边界均可机器执行。独立复算确认核心计数和五项物理差值非退化结论成立，未发现会导致标签泄漏、伪 OOS、结果后特征救援或未经授权训练的 P0/P1/P2。

存在两个非阻断 P3：相关性陈述没有写明使用 218 个 eligible 行还是 183 个挑战者；完整挑战者实际只覆盖 13/18 个品种，规格虽用机械 complete-case 和 A 回退控制行为，但未把品种级集中度列为显式摘要。二者不改变冻结特征、资格定义或技术门，允许 TDD 实现，但实现产物应按冻结规则如实披露，不能据此扩张结论。

本决策只授权 Stage002 无标签特征构造的 TDD 实现和合成/身份测试，不授权读取账户收益或回撤标签、训练模型、效果评价、策略回测、true-engine、holdout、生产、CTP 或订单。

## Findings

### P0（0）

未发现 P0。

### P1（0）

未发现 P1。

### P2（0）

未发现 P2。

### P3-1：相关性陈述的统计分母未显式冻结

预注册披露“两项基差差值 Spearman 相关 `0.8510`，其余绝对相关不超过 `0.2925`”，紧接在“183 个完整挑战者”非退化陈述之后，但没有明确相关性使用哪个行集。

独立复算表明：

- 在全部 `218` 个 model-eligible 行上计算五项物理差值相关性，包含 35 个 rank10 全零锚点，得到基差相关 `0.8510219949765314`，其他最大绝对相关 `0.2925248716363609`；这与披露值精确对应。
- 在文字更容易理解的 `183` 个完整挑战者上计算，得到基差相关 `0.8679615110477548`，其他最大绝对相关 `0.3313836911484809`。

该差异不影响任何准入门，也没有触发特征选择、交互项或参数分支，所以不阻断实现。Stage002 实现报告应明确相关矩阵分母；若复算相关性，至少同时报告 eligible-all 与 challenger-only，不能把包含 35 个共同零锚点的较低相关性描述成 183 个挑战者统计。

### P3-2：完整证据子宇宙存在明显品种集中，需限制外推

独立复算得到：374 个候选中 model-eligible 为 218，整体资格率 `58.2888%`；327 个挑战者中完整挑战者 183，资格率 `55.9633%`。完整挑战者覆盖 13/18 个品种，`AP.CZCE`、`jm.DCE`、`lc.GFEX`、`lh.DCE`、`si.GFEX` 的 eligible challenger 均为 0。

这不是 PIT 泄漏：资格只由当时可见的 basis/member 完整性和月活跃机械定义决定，非完整候选保留在全量审计面板，未来动作固定回退线上 A；规格也禁止把可用性或产品身份放入模型矩阵。但未来模型证据只能解释为“完整物理证据子宇宙上的增量尝试”，不能外推到 18 品种完整候选池。Stage002 summary/report 应从全量候选面板显式列出品种级 candidate/eligible 行数；该披露是审计增强，不新增筛选门，不允许据品种分布删改样本。

## Stage001 manifest 与身份

- Stage001 manifest SHA256：`c4436bef32a174e699a7f736a383591d3ef581c9c3fd00ee38ed076b562a29fa`，与 Stage002 冻结输入一致。
- manifest 声明 6 个持久工件；Stage001 输出目录除 manifest 自身外实际也是 6 个文件，路径集合精确相等。
- 六项工件逐一复算 SHA，差异为 0：feature panel `62ac505b...`、family coverage `e96da5d7...`、month coverage `91843206...`、source summary `9e691e17...`、summary `cc6c4ae...`、report `0a77592c...`。
- Stage001 summary 决策通过，eligible families 精确为 `basis/member`，diagnostic-only 精确为 `warehouse`；PIT violation=0，label columns=`[]`、label values=false、fit/backtest/holdout/CTP/order 均为 0/false。
- Stage001 input before/after identities 相等，双跑 exact=true。

## 核心计数独立复算

直接读取 Stage001 无标签 `physical_feature_panel.csv.gz`，严格按 Stage002 定义重建：

- Stage001 全面板：`797` 行、`47` 月、`18` 品种。
- `a_rank >= 10` 候选：`374` 行、`47` 月、`18` 品种。
- 连接键 `eval_date,product_vt_symbol,a_rank` 唯一；每月恰有一个 rank10；每月 rank 从 10 连续到当月最大值，最大不超过 18。
- basis/member 同时完整且满足 rank10 完整、完整挑战者至少 2 行的活跃月：`35/47`。
- model-eligible：`218 = 35 anchors + 183 challengers`。
- 前 18 月：`13` 活跃月，`62 = 13 + 49` 行。
- 后 17 个 development 月：`13` 活跃月，`91 = 13 + 78` 行。
- 最后 12 月：`9` 活跃月，`65 = 9 + 56` 行。
- 活跃月年度计数：2022/2023/2024/2025=`8/10/9/8`。

上述结果与预注册的 `374/35/218`、`13/13/9`、`62/91/65`、年度 `8/10/9/8` 全部精确一致。

## 六项特征与退化审计

- 六项特征按当月 rank10 做直接减法，顺序固定；不包含 rank、产品、交易所、年月、来源日期/年龄、可用性、仓单或历史结果。
- 218 个 model-eligible 行六项全部有限；35 个 rank10 的六项差值逐位精确为 0。
- 183 个完整挑战者的五项物理差值各自唯一值均为 `183`，精确零行均为 `0`，超过冻结的 unique/nonzero `>=150` 门。
- 未发现填补、标准化、winsorize、clip、符号翻转、分位变换、阈值、交互、PCA 或特征选择的预留分支。
- formal probability delta 同样按 rank10 机械相减，不引入未来信息。

## PIT 与缺失模式

- Stage002 不重新连接外部数据，只消费绑定 SHA 的 Stage001 PIT 面板并做同月差值，不引入新的时间对齐自由度。
- Stage001 实现只允许 `feature_date + 1 calendar day <= eval_date` 的 backward as-of，source age 必须在 `[1,7]`；当前可用行中 basis/member source age 实际为 1..3 日，warehouse 为 1..5 日，同日或未来来源为 0。
- available=true 的 basis/member/warehouse 行对应指标均无 NaN；available=false 行没有残留有限指标。
- Stage002 的 model-eligible 必须 basis/member 同时 available、月活跃且六项全部有限；非活跃月和不完整候选保留审计但不得进模型。禁止缺失指示器、原生 NaN 分支、补值和扩大样本的规则足以防止模型暗中学习覆盖模式。
- Stage001 member 聚合在源列数值化时对缺失单元使用 0 后求和；当前输出 member 可用行三个指标均无 NaN 且无精确零，但 Stage002 不应再做任何补 0。该上游语义已冻结，当前评审不把它解释为新的统计证据。

## 样本选择与未来模型边界

- complete-case 过滤确实形成覆盖选择偏差，但选择变量完全来自事前可见数据，不依赖收益/回撤标签；全量 374 行和机械回退使未来策略效果可以按完整月份序列零填充评估，而不是只报 35 个活跃月的条件收益。
- Stage003 必须使用 26 个 development 活跃月，而不能把最后 12 月中的 9 个活跃月标签用于训练或调参；首折只有 13 个 qid/62 行，过拟合风险高。
- 预注册明确保留线上逻辑回归 A，只允许未来模型挑战第 10 席，Top9、`fu.SHFE` 和其他正式规则不变。
- 单头/双头、参数、qid、成熟期、selector、替换门、效果门、分年和 leave-best-out 均要求在 Stage003 一次性冻结；Stage002 没有留下按实现结果择路的可选分支。
- Stage006 失败结果不得用于本线参数、selector 或效果门，且当前 Stage002 不读取任何标签或模型结果明细。

## 可机器执行性

Stage002 实现可以直接把以下内容编码为 exact gates：输入 SHA、Stage001 decision/families/零副作用、374 行/47 月、唯一键和 rank 连续性、35 活跃月、218/35/183、三个时间段计数、年度计数、六项列顺序、finite/anchor-zero、五项 unique/nonzero、稳定 mergesort、双跑 exact、工件集合和所有禁止项零计数。失败 decision 和禁止补救规则也是单值，不存在运行后改门空间。

Fresh 相关测试：Stage001 专项 `3 passed in 0.30s`。未运行 Stage001/Stage002 真实入口，未创建任何 Stage002 工件。

## 过拟合与继续价值

- 过拟合判断：本次审计否。全程只使用无标签特征、覆盖和身份数据，没有读取收益/回撤、sealed holdout 或 Stage006 模型结果明细，没有训练或比较效果。已见覆盖、退化和相关性数字不增加 OOS 置信度；它们只能作为实现身份门。
- 继续价值判断：有条件地是。basis/member 提供与旧价格/曲线特征不同的物理和持仓语义，五项差值非退化，值得完成一次无标签 TDD 构造；但 13 个首折 qid 和品种覆盖选择使未来模型极易过拟合，Stage002 通过绝不等于模型有价值。

## 决策边界

`P0/P1/P2=0/0/0`，decision 为 `ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY`。仅允许按当前 SHA 的预注册实现无标签 Stage002 特征和合成/身份测试；不授权账户收益/回撤标签、sealed holdout、模型训练、参数搜索、效果评价、策略回测、true-engine、生产修改、CTP、实盘或订单。
