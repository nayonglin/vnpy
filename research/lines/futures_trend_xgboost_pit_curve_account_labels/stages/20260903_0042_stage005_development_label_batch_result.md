# Stage005 development账户边际标签完整批次结果

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/完整development账户边际标签生产
- 记录时间：2026-09-03 00:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage006训练前的冻结标签数据集生产与技术验收
- 是否重要突破：否；本阶段只证明标签生产可靠，不证明XGBoost能提高收益或降低回撤
- 是否触发A/B：是；产生互斥账户反事实标签，但未训练模型、未生成统一策略A/B/C曲线

## 外部调研与判断

- XGBoost官方Learning to Rank要求每个查询组内样本可比较，并要求`qid`排序后保持组连续：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 我的判断：35个月内rank10至rank18的候选都采用同一正式账户、同一历史和同一决策前状态重放，才具备后续按月排序的标签语义。完整跑完266个互斥主任务是必要的数据工程门，不是alpha证据。

## 本次变更

- 新增脚本：无；运行冻结的`tools/stage005_development_label_batch.py`及其worker/runtime core。
- 修改脚本：无；运行授权后未修改Stage005 runner、runtime core或测试。
- 删除脚本：无。
- 新增参数：无；执行参数沿用预注册的并行数`2`、单任务超时`600s`。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：35个月、266个main账户反事实任务和4个A2哨兵全部完成。
- 修改回测结果：无。
- 删除回测结果：无。

## 回测/归因参数

- 数据区间：35个development月，`2022-01-28 -> 2024-11-29`；每个任务从`2018-01-01`运行到对应`next_eval_date`，标签只取`eval_date`之后的目标账户区间。
- 账户规模：正式15万元账户口径。
- 成本口径：正式滑点、手续费、保证金、整数手、相关性和最多4持仓约束均保持不变。
- 样本过滤：无；开发集266个main任务全部保留，另跑4个冻结A2哨兵。
- 策略/归因口径：A为严格PIT逻辑回归rank10；每个挑战者任务只替换目标月第10席，其他历史、未来资格和固定`fu.SHFE`语义不变。
- 金额对账：每个操作数先量化到`0.000001`再加减，最大绝对误差必须`<=1e-9`。

## 结果

- 决策：`stage005_development_account_labels_complete_allow_stage006_training_preregistration`。
- 任务完成：`270/270`，其中main `266/266`、A2 `4/4`；development月份`35/35`。
- 标签：`development_labels.csv`共266行，月份、任务ID和连接键均完整且唯一。
- 决策前原始证据：`35 x 5 = 175`个canonical文件全部通过逐月SHA核对。
- A2一致性：4个哨兵的`label/curve/combined/trades/entry_candidates/entry_risk/trade_events`七类文件与对应rank10逐字节一致。
- 账户对账：266行全部通过，最大绝对误差`0.0`。
- worker隔离：270个receipt对应PID、TMPDIR、MPLCONFIGDIR唯一；checkpoint/result复用均为0；最大worker wall time `85.2773285s`。
- attempt恢复审计：同一campaign仅1次attempt，序号连续且唯一，start/end精确，最终`complete`，失败后attempt数为0。
- 产物：manifest覆盖除自身外`3,431`个文件；campaign运行前后输入身份SHA一致。
- scope审计：holdout job/output/label、模型训练命令/日志/产物、CTP连接命令/日志、订单命令/日志、意外worker命令/产物均为0。
- 期末权益：不适用/不发布；266个main是互斥候选臂，不能复利串联成一条策略曲线。
- 总收益：不适用/不发布；不得把互斥任务的`future_return`相加称为组合收益。
- 最大回撤：不适用/不发布；每行是候选边际路径标签，不是统一组合净值的最大回撤。
- Sharpe：不适用/不发布。
- 总滑点：不适用/不发布；不得跨互斥反事实求和。
- 总交易次数：不适用/不发布；不得跨互斥反事实求和。
- 胜率：不适用/不发布；本阶段没有统一策略交易序列。

## 输出文件

- campaign：`artifacts/stage005_development_label_batch/campaigns/campaign_20260902T214308+0800_13888/`
- report：`report.md`
- decision：`decision.json`，SHA256=`1cffbfcf0872de9c2a0256071de95ca4a750a72b74025865a1beb8b18fe8a111`
- labels：`development_labels.csv`，SHA256=`b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d`
- reconciliation：`reconciliation.csv`，SHA256=`f964992306202c2589a6ff20962aa10144beca58fa393a93dc650b543073b75c`
- execution scope：`execution_scope_audit.json`，SHA256=`182ab3b9f74827c1e89e2c439bee8778cfa923fe520e5f5c8319a08adf2155a4`
- A2 audit：`A2_audit.json`，SHA256=`d8c8b626e870643edf216d2280d6188e3f1cfb740c824b7988110b365bb170aa`
- predecision audit：`predecision_evidence_audit.json`，SHA256=`95f694fe73ee53c253aff49f5ff269d8c6e6d9c8ca9dcb996c56c630af40d380`
- attempt audit：`attempt_audit.json`，SHA256=`70fc4f0e326fb9c90a1d6c15dd8aebdafea7cba6454f8d630b0ab319c0c7dcf9`
- artifact manifest：`artifact_manifest.json`，SHA256=`526f945c2e7523b78076331a2473a606f6f8ce775a0a8ac7850dcd593a31eedf`
- run authorization：`reviews/20260902_stage005_run_authorization.json`，SHA256=`fe83c65963b94a645426794544c1e653bd060717cd4911cc4c71083446481132`
- authorization consumption：`authorization_consumption.json`，SHA256=`3886e95ff87e7b64ec5e6df222a74b342dede839e419bda1bea9efeb23dea342`
- 独立运行后review：`reviews/20260903_stage005_postrun_independent_review.md`，SHA256=`d1933474704dfa116bb88ca5c32465c686166f5541755081e559af9db5816d32`。
- review decision：`reviews/20260903_stage005_postrun_review_decision.json`，SHA256=`d35d46f90614e3c8a4c59510b05de845afedae5a1db8c8ca1a17913fad1fc6b0`；结论`ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY`，`P0/P1/P2/P3=0/0/0/1`。
- 唯一P3是review读取时`research/registry.md`仍写“Stage005批次未运行”；本记录落地时已同步为270/270完成，故该状态滞后已关闭，不改变独立review原始结论。

## 结论

- 本阶段结论：Stage005完整标签数据集在身份、PIT、任务完整性、账户reconciliation、worker隔离、A2一致性和执行范围方面通过本地技术门。
- 收益/回撤结论：没有。尚未训练XGBoost，也未形成统一A/C组合曲线，不能声称收益提高或回撤下降。
- 是否进入下一步：是，但仅进入Stage006训练方案预注册和独立预审；当前不授权实现、训练或读取sealed holdout。
- 下一步：冻结Stage005所有输入和产物；预注册单一浅树双`XGBRanker`、按月qid和严格PIT OOS门，独立预审后再决定是否允许实现和一次development训练。

## 过拟合反思

- 运行前判断：本阶段本身否，但整个XGBoost方向已有较高先验选择风险。
- 运行后判断：否。
- 原因：任务、样本、标签定义、金额量化、执行顺序和所有硬门在运行前冻结；运行后没有按标签分布删月、删候选、改特征、调模型或换目标。Stage006开始读取标签后风险会明显升高，必须坚持一次性冻结规格和失败即停。

## 继续价值反思

- 运行前判断：是；完整账户边际标签是验证新曲线信息源的必要条件。
- 运行后判断：是，但只限独立复核后的Stage006预注册和一次冻结development OOS训练。
- 原因：数据集解决了旧代理与真实账户目标错位，但还没有任何预测价值证据。若Stage006效果门失败，继续扫树参数、融合权重、年份、品种或候选rank将没有价值并构成结果后救援。

## 合入建议

- 是否更新本线`LINE.md`：是，记录Stage005完成和独立review放行预注册。
- 是否更新`research/registry.md`：是，更新为标签完成、模型未训练。
- 是否追加根目录`memory.md/back_log.md`：追加`back_log.md`真实回测标签批次摘要；`memory.md`不追加，因为尚无模型突破、正式候选或路线关闭。
