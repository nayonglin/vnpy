# Stage057：固定pairwise19模型的真实训练来源与历史可用性审计

- line_id：futures_trend_triple_screen；时间：2026-10-18T05:24:31.502602+08:00。独立只读置信度审计，不读取B中间PnL，不网络/训练/预测/金融回放；未修改模型、配置、已消费源码、LINE或registry。
- 本agent未写035 alpha或账户算法，曾参与040/044/051数据恢复编排；本次审计的是另一项固定pairwise模型时钟依赖，数据编排仍由其他审者交叉复核。

## 结论

**当前2020—2026回放使用一个固定的后期训练pairwise模型，不具备逐历史日“当时已经训练且标签已成熟”的证明，不能称严格PIT/OOS。** 不是根据训练脚本默认值、文件mtime或发布日猜测；B preflight确切绑定joblib SHAba982708…9d66和summary SHAc399a578…ee86，runtime在策略初始化只加载一次固定路径，预测接口无fit-before-candidate、training-label cutoff或按日期换模门。特征按候选日截断，并不等于模型的训练截止也早于该日。

## 实体资产与训练队列的实际证据

1. 实际sidecar记录train50行/25日，valid_start=2023-01-01，test_start=2024-01-01。现有v2样本CSV按这个sidecar切分，恰50行25日，candidate_date为2020-09-17—2022-12-08。
2. 为避免仅凭同名sidecar断言，使用冻结sklearn1.8.0/pandas2.3.3/numpy2.4.4/joblib1.5.3，仅对已核SHA的可信joblib做一次只读加载。物理StandardScaler的n_samples_seen_=50，19列名称、分类器全部系数、均值、scale与sidecar逐项差0；该50行CSV的19列均值/总体标准差与实体scaler也全部差0。未fit或predict。这是强队列佐证，但不是不可变训练运行证明。
3. 训练pair关联61个不同candidate，逐个按原合约CSV与精确candidate_date找到真实标签终点，61/61的20bar forward R与候选标签一致；最大实际标签终点为2023-01-06，来自2022-12-08的MA301/lh2301。部分临近到期候选沿原构造逻辑截断未满20bar，完整明细保留于JSON，不伪称所有标签20日完整。
4. 物理payload和sidecar没有真实fit时刻、训练标签可用截止、不可变model→训练dataset/标签manifest。故2023-01-06是**现存且与实体拟合统计完全吻合队列的标签终点复算值**，不能冒称原训练作业记录的精确cutoff，更不能据此把2023以后全部自动认证PIT。

## 月度AI池与pairwise模型必须分开

B monthly pool的58张快照/eligibility时钟审查是另一条链。m0008 manifest.provenance.training_label_cutoff=2026-07-07，generator是Stage182月度选品发布；它不是此pairwise19模型的训练元数据，不用于替代本次缺失的cutoff证据。当前release文件清单也没有该实体joblib及sidecar的专属训练运行声明；本B离线preflight对它们另有内容SHA绑定。

## 对当前结果与后续资格的影响

- 发现P1两项：历史按日模型可用性无门；缺精确训练作业/label-asof证明。2020及早期历史使用了有力证据指向后期训练的固定资产，早期段不能被称为真实样本外。A/B使用相同固定模型也不能抵消这个问题，因为候选与资金路径改变，训练偏差和新signal类别域偏移对两臂的作用不相同。
- 原B继续按冻结反事实完成，禁止为此重启、改模型、改分数或挑段报喜。此审计不推翻已核现金/库存账本的算术，也不把账本正确等同于历史可交易性。
- 若出现高收益且低回撤候选，晋级前需另冻结严格as-of模型版本：每训练行的observation时点与label_end、purge/embargo、过去已成熟标签、按日版本选择和真实独立OOS；A/B使用同一PIT规则。不得靠分段好看替代该资格。
- 策略参数/金融结果新增/修改/删除0；权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A。
- 开始与结束过拟合判断：本次审计新增过拟合为否，不按PnL调参；既有模型早期历史的未来训练信息及研究选择风险为是。继续价值：是，当前冻结反事实仍可筛机制，正候选必须经过上述PIT门。production_qualified=false。

证据与所有只读来源SHA：outputs/stage057_pairwise_training_asof_audit/evidence.json。
