# Stage015：development账户边际标签完整生产与独立复核

## 阶段信息

- 完成时间：2026-09-02 06:40 CST。
- 研究线：`futures_trend_ai_xgboost_ensemble`。
- 是否重要突破版本：否；这是模型训练前的数据与审计基础设施里程碑，不是alpha候选或正式版本。
- 当前线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`，生产HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- 运行边界：只生成development账户边际标签；未训练模型、未生成或读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。

## 本次版本变更

- 新增结果：完整campaign `campaign_20260902T021241+0800_98656`，覆盖39个development月份、rank10..18共351个主任务，另有4个rank10 A2确定性哨兵，总计355个独立冷进程任务。
- 新增参数：无。
- 修改参数：无；Stage014冻结的样本、九项特征、双`XGBRegressor`参数、A/B/C实验臂与holdout边界均未改变。
- 删除参数：无。
- 修改结果：无；旧废弃campaign的任何输出均未复用。
- 删除结果：旧campaign继续永久废弃，不作为Stage016输入。

## 完整批次结果

- 355/355任务完成，351条主标签发布；sealed holdout任务和标签均为0。
- 355个PID、TMPDIR、MPLCONFIGDIR均唯一，`checkpoint_reused=false`与`completed_result_reused=false`均为355/355。
- 归一化runtime SHA唯一：`8b37a9dbf8de6b7774d08be4729b4a197a258abdf018ccdc2f52ec7abf991028`；单任务最大耗时`96.01085916601005`秒，小于冻结的600秒超时。
- campaign文件合同：`ac8e5a6e77b081eaad97bcc30ef89769d6586eecd1b079ccef713e8d3d8d5d4f`；2235项manifest在批次前后及复核后均无漂移。
- 四个A2哨兵的标签及六类目标期payload与对应A逐字节一致；39个月五类决策前payload逐月一致。
- 351条标签的金额、收益、最大回撤改善、滑点和交易数差额均可从原始输出重建；reconciliation全部误差最大绝对值为`0.0`。
- `development_labels.csv` SHA256：`39e969783adc2ac54f771cf03e685a4cec45ce09adeb2d1eefc6ca54ef2cbce2`。
- `reconciliation.csv` SHA256：`d595547fa81906093c0fd530acbfa5d0f2b7c3fe489987efa79da304b977eb95`。
- 决策：`stage015_development_account_labels_complete_allow_frozen_training`。

## 独立复核

- 复核文件：`reviews/20260902_stage015_full_development_labels_independent_review.md`。
- 结论：`ALLOW_FROZEN_STAGE016_TRAINING`，严重度`P0=0 / P1=0 / P2=0`。
- reviewer未采信机器自报结论，独立重建355个job、2840个固定输出、355份receipt、2235项manifest、351行标签和351行reconciliation。
- Stage015专项测试`30/30`通过，整线测试`98/98`通过；生产validator跨时间样本`4/4`通过，共享builder receipt gate `355/355`通过。
- 授权只绑定上述两个CSV SHA及campaign合同；任一身份变化均须停止并重新复核。

## 回测指标口径

- 本阶段运行的是351个逐月、逐候选的账户边际反事实标签任务，不是一条可复利的单一策略资金曲线。
- 因此期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数和胜率均为“不适用/不发布”；把351个互斥反事实臂直接相加会产生错误结论。
- 这些组合级指标只能在Stage016冻结选择器后，由A/C真实账户引擎在统一全周期口径下计算。

## 反思与下一步

- 运行前过拟合判断：否。任务网格、标签定义、输入身份和模型合同均在标签生成前冻结，且未按部分结果裁剪任务。
- 运行后过拟合判断：否。完整批次和独立复核只检查身份、隔离、账务与可复验性，没有分析标签分布、择优月份或修改模型参数；这不代表模型已经有预测力。
- 是否值得继续：是。现在首次具备未污染holdout的完整账户级development标签，可进入一次冻结的Stage016逐月扩展训练。
- 下一步：在读取标签取值前预注册Stage016的PIT切分、双回归头融合、确定性tie-break和开发集通过门；只运行一次，不做参数搜索。development门失败则停止该形状，门通过也只允许进入开发期真实引擎A/C验证，不直接读取holdout或上线。
