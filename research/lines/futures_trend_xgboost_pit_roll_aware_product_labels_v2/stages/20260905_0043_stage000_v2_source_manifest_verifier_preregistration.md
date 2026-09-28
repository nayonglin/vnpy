# Stage000 V2 source manifest verifier修正预注册

- line_id：`futures_trend_xgboost_pit_roll_aware_product_labels_v2`
- 记录时间：2026-09-05 00:43 CST
- 是否重要突破：否；仅修正上游manifest格式适配。
- 当前权限：只允许TDD、静态身份验证和一次无价格值Stage001；禁止close、收益、标签、训练、回测、CTP、订单和生产写入。

## 已证根因

- V1发布器的manifest形状是`artifacts[filename]={sha256,size}`。
- source rebuild的manifest形状是`artifacts[logical_name]={path,sha256,size}`，例如key=`mapping`、path=`.../pit_main_contract_mapping.csv.gz`。
- 原线错误复用V1 verifier，导致真实文件被报unmanifested、逻辑key被报missing；失败发生在任何CSV解析前。

## 唯一允许修正

- 新增path-based verifier：逐个读取source manifest artifact entry的`path`，要求路径位于冻结source final目录内，文件存在，size和SHA256精确匹配。
- 逻辑key不参与文件路径拼接；不得通过目录文件名反推key。
- source manifest本身仍由直接输入SHA固定；mapping和normalised bars仍各自做直接SHA固定。
- V1 manifest继续使用原filename-key verifier，不改变其语义。

## 不变研究合同

- 基础57,528行/1,067 qid；候选56,272行/1,046 qid；截止外1,256行/21 qid。
- 每行20段，总计1,125,440段；第一段query日合约，后续previous_date映射。
- 同合约起止bar存在，禁止跨合约比价、future mapping、fallback和缺失补值。
- `2024-01-31/sc.INE`必须从`sc2403.INE`开始、至少换月一次并完整到2024-03-08。
- close值、收益、标签、fit、predict、回测、holdout、CTP、订单和生产写入全部0。

## V2硬门与决策

- source path manifest verifier必须覆盖全部13个top-level artifacts且错误0；V1 final也必须复验错误0。
- 其余八项门与原Stage000逐字不变。
- 任一失败：`stage001_v2_roll_aware_label_plan_fail_close_no_labels`。
- 全门通过：`stage001_v2_roll_aware_label_plan_pass_allow_label_model_preregistration_only`；只允许另发标签值与XGBoost模型预注册。
- 原线和日级Ranker V2永久不重跑。

## 回测记录占位

- 新增/修改/删除回测结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。

## 过拟合反思

- 运行前判断：否；没有任何效果结果，只有静态接口格式错误。

## 继续价值反思

- 运行前判断：有；修正后可在不增加研究自由度的前提下完成一次原问题资格审计。
