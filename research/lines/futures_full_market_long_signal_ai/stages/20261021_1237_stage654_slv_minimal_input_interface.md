# Stage654：SLV 固定实验的最小输入接口交接

- 时间：2026-10-21 12:37 CST；line_id `futures_full_market_long_signal_ai`。先读 registry 本行；本次仅收益前接口准备，不是重要突破。不改 LINE/registry/根日志/Git/正式 C9。
- 开始/结束新增按收益调参过拟合：否，未读任何新 Y/score/模型内容或源 daily。长期同史择题风险仍高。继续价值：有，仅把已接受新数量源落实为一次 NAV/共同可用性控制后的固定增量检验；重复验源或改参数救分无价值。

## 调研与判断

沿648/650与652已接受官方源语义和本线605/607/608、564/566方法；本任务遵root明确禁止网络，不重复官方/GitHub请求。只读必要小manifest/protocol/审查元数据及3个源码文件（607、538、567），没有打开 COMMON、Y/score CSV、portable模型内容或 wholemodels。结论：**原52六组的538已审投影完整覆盖训练查询；607 Corn缓存不能替代全98/95六scope。**

607 only-main Corn的7146/10120训练、9640前向是旧玉米源小切片，无法恢复全部产品与族留出。567的PMI report缓存也按另一资料可用域压过，不能当本次SLV母体。应复用564接受的538六train_compact和完整forward_base_compact；它们保留原成熟stressR、身份、权重和各自原Ahat/score，丢弃旧sector B_offset/C_offset。

## 六fold与固定目标

|scope|cutoff|成熟训练行|训练family|训练压缩字节|前向child|
|---|---|---:|---:|---:|---:|
|main|2020-01-01|247,795|69|29,438,246|366,634|
|main|2023-01-01|445,475|77|50,602,127|600,106|
|holdout_0|2020-01-01|171,712|44|20,253,104|138,837|
|holdout_0|2023-01-01|297,404|47|33,674,964|249,829|
|holdout_1|2020-01-01|76,083|25|9,171,194|227,797|
|holdout_1|2023-01-01|148,071|30|16,917,127|350,277|

训练总1,386,540行/160,056,762B，完整前向1,933,480行/142,867,173B，main及两held合各966,740child；完整main或合并held母体均161,014。保持98历史产品/95族、两个原部署段及两个family-heldout，不选来源最受益品种。held以SHA256(family_id)%2排除自身组全部训练标签，forward须用其自身scope原score，不拿main冒充。

原目标是130的 `net_R_stress`，成熟态 `closed_complete_bar_model`，known字段 `label_known_date`。训练必须u/known均严格早于cutoff；前向known<=固定END=2026-10-16；未知/未成熟/已知不参与分别计数，不填0，不新增D<K训练筛选，也不把原H目标换成K现金目标。原52、scaler、标签、风险和stop一律不重建。训练Ahat仍同样本残差，不宣称全管线OOF/DML；原forward score是真cutoff前向。

## 完整身份绑定与真实性

每fold原portable model/scaler及对应compact的准确绝对路径、bytes、继承SHA与本次stat全部写入 `input_handoff.json`。本次仅确认文件类型/size/inode/mtime，不读模型coef、不重新hash大源。538生成器保留全部原成熟训练行/权重；其Ahat来自原26列、固定scaler及52coef。539已独立重构六fold基准预测，最大绝对差3.552713678800501e-15，权重最大差9.947598300641403e-14，C/I/M=0/0/0；这些是已接受审查事实，不是本次重算。

- 538 manifest：13,210B，SHA `8caff080ca76235b642fb2c3155cc7be1e5191674b40c109f931e59a28e1ff53`。
- 538 full forward：142,867,173B，SHA `2ff4fdcbfcada3a2381bb330886b72e6cd26dc9d330fabce6cea47e4e86d446b`。
- Calendar：89,395B/5587日，SHA `c3dc1d8da02e21bf93716e8b762e637d43d181426a4cff21ec4bf04d0e03ba0a`。
- 已验SLV daily：73,203B/5160行/5158有效Shares，SHA `0dfc76c172793134fb6d7a184da906c1c07cc14397eee2db8ddb4e5bd47ff72e`；本次未再读取内容。

训练最小白名单含action identity/product/family/u、eligibility/state/known、stressR、sample_weight、Ahat；forward保留原18列（不含旧B/C_offset）。训练唯一键为自身scope/cutoff+action_id；前向不得只用action_id跨main/held合并。`u_index`必须索引原calendar并与u_date相等；母映射mother_sequence_index/event_id保持。完整列名与键已列JSON。

## 最小未来IO建议与预算

653结果前冻结单一时钟、共同可用性/缺失fallback、源更新聚合/权重/scale/penalty和门之后，才读取SLV daily一次做u连接。六train各一次顺序gzip usecols流扫，完整forward一次；核心金融压缩IO合302,923,935B，无COMMON/actions/native/SQL/下载/原52重训/wholemodels。若653仅做残差预测诊断，不需mothers和A choices；若真做原完整政策选择，mothers另7,903,291B，A choices仅按所需角色读取，准确绑定已作为optional列出。

对共同加性头，按653冻结的source-update和各自scope/cutoff在一次扫描中压成必要统计，保留known/unknown计数、原身份digest及sumw/sumw*r/sumw*r²（r=Y−Ahat）。新臂共享source map。必要的独审窄切片应在这一次actual读取中同时保存/绑定，避免后来重读巨大原表。此处仅建议，没有生成任何可拟合表或数据切片。

注意：**不能直接复用567 `read_table_once`/538 `HashedInput`，该helper会在流读时重新hash整个旧流。** 本轮应沿607的stat前后/继承SHA，另用白名单chunk读取；没有随机gzip产品索引，也不能声称无需解压全流。新增实验最多2arms×2cutoffs×3scopes=12fit、0cash，实际由root653冻结并授权唯一actual。

## 当前记录

新增/修改/删除策略参数、回测结果均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部N/A。新增fit/cash/Y/score/模型内容/COMMON/native/SQL/网络读取均0；累计551fit/294完成cash+1旧partial保持，629 conditional false/fullE inconclusive、646关闭不变。本阶段只有唯一stage及小input_handoff，没有实施/拟合，等待root653冻结。
