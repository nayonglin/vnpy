# AI选品XGBoost PIT物理供需与会员持仓线

## 研究线身份

- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 创建时间：2026-09-03 02:50 CST
- 当前状态：Stage003唯一一次授权已消费，冻结运行在首折训练准备阶段因`joint_relevance_degenerate:2022-01-28`技术失败；没有模型fit、效果结果或回测。失败后独立复核为`BLOCK`、`P0/P1/P2/P3=0/0/1/1`，当前冻结形状永久停止，不得重跑、救参、访问holdout或真实引擎。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b`
- 研究目标：保留线上逻辑回归排序，以基差、仓单、会员持仓提供独立PIT信息，研究低复杂度XGBoost能否提高全周期收益并降低最大回撤。
- 隔离边界：不修改正式release、生产checkout、CTP、持仓、订单、邮件或定时任务；覆盖失败不补值、不删月、不改陈旧度和门槛；真实回测前通常不追加根目录`back_log.md`，但路线废弃按总账规则追加；产生回测数据后必须独立review。

## 为什么另立本线

- `futures_trend_xgboost_pit_curve_account_labels`已在严格PIT流程中反证当前8项全曲线/账户边际双Ranker形状，禁止继续调参救援。
- 历史入场meta-label研究也已在同类价格/策略字段上失败；继续换模型而不换信息源没有价值。
- 本线只引入物理供需与会员持仓外生源，不复用旧失败线的市场收益上下文、全曲线特征或账户状态特征，因此假设机制不同。

## 当前合同

- Stage000预注册：`stages/20260903_0250_stage000_physical_positioning_preregistration.md`。
- Stage001固定`797`行、`47`月、`18`品种，严格T+1、最大陈旧7自然日。
- 家族准入统一要求：行覆盖`>=50%`、活跃月`>=24`、前18开发月活跃`>=12`、每年活跃`>=4`。
- 至少2个家族合格且必须含基差；任一外生源总覆盖`>=95%`。
- Stage001不读取标签、不训练、不回测；通过只允许继续编写Stage002合同。

## Stage001结果

- 决策：`stage001_physical_positioning_coverage_pass_ready_for_feature_preregistration`，7项总门`7/7`通过。
- 面板`797`行/`47`月/`18`品种；任一外生源覆盖`793/797=99.4981%`；PIT日期违规`0`，输入身份稳定，双跑逐值一致。
- 基差覆盖`746/797=93.6010%`、活跃`43/47`月、开发期活跃`16/18`、最弱年份`10`月，合格。
- 会员持仓覆盖`626/797=78.5445%`、活跃`38/47`月、开发期活跃`14/18`、最弱年份`8`月，合格。
- 仓单覆盖`468/797=58.7202%`、活跃`25/47`月，但开发期仅`6/18`、最弱年份仅`3`月，不合格并固定排除。
- 标签读取、模型fit、策略回测、holdout、CTP和订单均为0；专项测试`3 passed`，manifest六项工件现场复算一致。

## Stage002结果

- 决策：`stage002_physical_features_pass_ready_for_training_contract_preregistration`，技术门`15/15`。
- 374行/47月候选中，完整物理证据子宇宙为218行/35月，其中183个挑战者；development前18月和后17月各有13个活跃月。
- 六项特征全部有限、rank10精确0，183个挑战者上每项均有183个唯一非零值；仓单、缺失指示器、产品/年月和rank距离均未进入特征。
- 完整挑战者覆盖13/18品种，`AP/jm/lc/lh/si`为0；未来结果只能解释该子宇宙，不能外推全品种池。
- 独立预审`ALLOW_STAGE002_TDD_IMPLEMENTATION_ONLY`，`P0/P1/P2/P3=0/0/0/2`；两个P3的相关性分母和品种集中度已在结果工件显式披露。
- 标签、fit、参数搜索、回测、holdout标签、CTP和订单均为0；整线`6 passed`，8项manifest工件现场复算一致。

## Stage003实现、运行与复审

- 冻结样本为153行development/26月，其中13个active OOS折共91个测试行，首折62行/13个qid；另有4个fallback月。65行sealed holdout feature只建立边界，不允许预测或读取标签。
- 模型固定六特征、`XGBRanker` 32棵深度2、13折主/重复最多26次fit、LR/XGB月内百分位50/50融合和11项效果门；实际在首折构造训练标签时终止，未进入fit或效果评价。
- full split冻结374行，Stage002 feature为218行，合法right-only为156行并绑定canonical key SHA；额外右侧键反例失败关闭。
- label和execution scope计数改由单一append-only事件账本、绑定runner AST审计及实际artifact差集派生；最终expected artifact集合在rename前后逐文件复核size/SHA。
- authorization链扩为27项，保留旧BLOCK链并绑定修复预注册和最终复审；runner SHA=`2bbd6af436af2b761720269695e1c052aee3980ed7bedcc4969b1483b10d0a86`，contract SHA=`e800b2b347bcb92472234a0a391b77b487de27de1f79ee191354b635232c15a2`。
- 本地整线测试`74 passed`；运行前独立复审核心测试`68 passed`且py_compile通过，允许申请一次性运行授权。
- 用户随后明确授权；authorization SHA=`8b7b77c037419702e40390945e48a274bdb61d10722a0d583ce82c099b4c348f`，receipt SHA=`11cbb1af3806707368e6269c8aff5c5441fa36ef8bbf381b51f80116f16ab127`，27项绑定identity SHA=`e6355d8a06161cfa36968fdf10f0865ca8514301d7fed8afb100700b069d000c`。
- 唯一一次入口在首个active fold失败：`Stage003Error: joint_relevance_degenerate:2022-01-28`。合同要求每个训练`qid`至少两个joint relevance等级，禁止删月、换标签或改目标绕过。
- temp目录存在但条目数0，final结果目录不存在；没有模型、预测、selector、效果指标或回测结果。合同处置语义为`stage003_contract_or_pit_invalid_stop_no_effect_claim`，操作处置为`STOP_STAGE003_FROZEN_SHAPE_NO_RERUN`。
- 失败后独立review为`BLOCK`、`P0/P1/P2/P3=0/0/1/1`；P2是异常路径未持久化nonce绑定事件账本，导致精确label/fit/predict零计数只能从未落盘traceback和控制流推断。该审计缺口不授权修复本线或重跑，只作为未来独立研究线的事前设计约束。

## 调研与判断

- NBER关于商品期货收益基本面的研究支持basis/库存具有经济信息，但不证明当前数据或模型可盈利：<https://www.nber.org/papers/w13249>。
- XGBoost官方LTR要求同月候选按`qid`组织，后续若进入模型阶段必须采用月内查询组：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 冻结前已做一次无标签覆盖勘察，因此Stage001只能作为数据工程准入和可复验工件冻结，不能视为独立OOS证据。

## 当前反思

- 是否过拟合：**本次冻结单次运行本身否，但当前再救援是**。运行没有按效果调参，也未训练；然而已知首月标签退化后再删月、换标签、改目标、参数或权重，会直接使用development结果塑形。
- 是否值得继续：**同一研究线否**。联合标签机制未通过首个训练窗口的可辨识门，唯一授权也已消费；更广泛目标只有通过新的经济假设或未来未见数据另立预注册线才值得讨论。

## 下一步

- 本线关闭：禁止再次运行Stage003，禁止修改或删除authorization、receipt、temp现场，禁止调参、删月/品种、换标签/目标/权重/门或读取更多标签。
- sealed holdout标签、真实策略引擎、生产、CTP和订单保持禁止。
- 若用户决定继续更广泛XGBoost研究，必须另立独立预注册线，先设计异常时的nonce绑定最小审计bundle，并采用新的事前经济目标或真正未见数据；不得把本次退化月份作为新合同的定制依据。
