# Stage537：固定产业截距残差试验的最小输入盘点

记录时间：2026-10-21 04:12 CST；line_id=`futures_full_market_long_signal_ai`；非重要突破。仅输入inventory，不实施拟合。root已选择唯一规格：冻结52、centered one-hot、sumw1、lambda1、不zscore、不新增global intercept、df<=1；不采用κ252或其他候选。开始判断：本次没有新收益调参过拟合，但同史反复择题风险仍高；继续盘点有价值，因为可以减少大表重复读取，不把准备工作当收益进步。

**可执行路径成立：**一次白名单读取129 actions，一次COMMON，一次完整mother身份；在RAM按当前且与accepted SHA完全一致的130代码重建六fold cohort/weights，复用六个小portable/scaler计算训练残差。原52不重训，不SQL。新头全部支持及训练完成后，accepted完整1933480行old scores最多流一次加offset；不从旧正分或已成交赢家缩域。六旧training_identity_weights大表只登记binding/stat，本轮不读，后续建议读预算也为0。

机器清单：`outputs/stage537_sector_inputs_inventory/inputs_inventory.json`，53398B，SHA256=`015c814fe1298c7ee7e8808ef03330dcd14532e5f11796ee390bcba35a17ba2b`；schema=`stage537_sector_residual_input_inventory_v1`。含全部精确path/size/SHA、12小模型/scaler绑定、六fold摘要、24列actions白名单、14列scores、全部98目录与94普通映射。本轮只生成这一个新JSON，没有生成另一份新map。

## 固定map与catalog

注册map：`/Users/mac/Desktop/fian/research/ai_assets/futures_trend_rollover_shape_same_volume/stage269/20261017_market_efficiency_attribution/payload/market/product_sectors.json`，3530B，SHA256=`04bd27f400bfcf3a0abea283b62bf2ae20e41bd1975c2173b7229870f5fec7e2`。八类顺序沿原JSON；94ordinary映射原样继承，三个_F仅按既有family去后缀获得普通类别。结果97/98，唯一DCE.S未知，修正严格0；训练未见sector也回52。上游为市场聚合排F的限制不能移植成本线删F。534/535已直接获知map路径及这项边界。

catalog：`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage004_product_day_opportunities/export/manifest.json`，257576B，SHA256=`1c1c28e54af995dbe4aa516fcd0d7aa80e9be347fe0efaa4408f329425274003`；只用product_year_counts的product_id集合得到98/95，不读PnL。原始map来源、收益前声明与来源界限沿Stage533及其实际原作者论文调研，不重复联网、查GitHub或造第二套理论规格。本阶段是既定方案的输入工程盘点，不是新alpha研究或数据认证。

## 大输入只继承accepted SHA并当前stat核尺寸

| 输入 | 压缩/文件字节 | 后继读取建议 |
|---|---:|---|
|129 actions.csv.gz|334909637|一次24列白名单，完整1552456行保留|
|129 common26.npz|146877351|一次，common为1552456×26及columns|
|129 mothers.csv.gz|19551936|一次7身份列，399252母体/161014前向|
|130 child_scores.csv.gz|124127126|一次14列全流，main/held union各966740，不能先筛正分|
|原calendar.npy|44824|绑定原5587日calendar供K与选择；本轮不打开|

这些路径/SHA见JSON的input_bindings；本轮没有读取其内容、header或重hash。原129 manifest为9137B、130 manifest21264B、fit_records13952B；实际打开小文件并核sha。12个portable/scaler已核scope/cutoff、52列名、原alpha1/intercept/cholesky及binding；没有运行任何预测。原normal_equations只绑定/stat，未打开。

## 六原训练cohort与权重恢复边界

|scope|cutoff|训练行|训练日期|family|family-u组|旧训练表字节（不读）|
|---|---|---:|---:|---:|---:|---:|
|main|2020-01-01|247795|2411|69|82929|25557698|
|main|2023-01-01|445475|3139|77|125955|43860164|
|holdout_0|2020-01-01|171712|2411|44|55688|17576860|
|holdout_0|2023-01-01|297404|3139|47|82519|29180322|
|holdout_1|2020-01-01|76083|2411|25|27241|7961159|
|holdout_1|2023-01-01|148071|3139|30|43436|14655051|

训练cohort严格沿130第60-67行：原u可行动、完整闭合、u和非空known时钟都严格早于cutoff且Y有限，held_g整族训练排除g。**不能顺手加K/D<K筛选，不能改DOMAIN或Ktarget。** 129原actions的身份、entry/exit索引、label状态/known和原stressR足以在RAM构建。原数据读取需按sequence_index保留原顺序；没有必要流六份高度重复训练表。

权重算法沿130第28-58行：同family-u的所有月份区间union，按同family并发机会的倒数均值定义uniqueness，再组内均分，逐u等总量，最后均值1。候选才把原weight归一sum1。held不能直接切main的最终weight，因为逐u总量随训练family补集改变；cutoff也影响并发支持。建议每fold在RAM依原函数恢复，不需原生行情或新标签。

尚未实际恢复，不声称现在已逐行验证旧weight文件或数据。actual前六fold都核完整计数、日期/family/groups、max_u/max_known、成熟/held/finite，并可用RAM的X/Y/w重建原小充分方程与accepted normal_equations比较；该比较不是原52重新拟合，也不能单靠汇总等式声称新做过逐行旧文件审计。遇到不符先停，不能换模型/权重配成绩。

模型训练原base s52由对应portable+scaler在RAM评估，不必打开joblib；前向直接沿完整accepted旧score加修正，不必重新计算全forward52。旧现金/旧正分/旧已选交易不读作训练或预测样本。后继root协议才决定actual，当前inventory不是授权。

## 实际工作量、反思与TODO

新fit/cash/SQL/下载/旧score内容读取/COMMON读取/旧训练表读取/大source fullhash全部0；只写本stage与一个inputs_inventory.json。累计仍511fit、278完成cash与1旧partial。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。LINE/registry/其他线/代码/正式/Git均未改。

结束过拟合：本轮收益后调参否，历史选择风险是，固定df<=1不能免除；继续一次预先固定的有限证伪有条件价值，继续新增规格/重复大表盘点无价值。TODO交root冻结精确绑定、单次必要输入及六fold支持；如启动任何现金，照用户要求拉独立agent全面复核结果/数据/逻辑/置信度/bug。全市场高质量long、成本后收益更高且DD更低与加注目标仍未完成。
