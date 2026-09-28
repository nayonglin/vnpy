# Stage006 首次预审阻断修复预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：Stage006标签值盲态/训练合同治理修复
- 记录时间：2026-09-03 01:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：首次独立预审三个P2的合同修复，不实现、不测试、不训练
- 是否重要突破：否
- 是否触发A/B：否；未产生模型或效果结果

## 阻断结论

- 首次review结论：`BLOCK_STAGE006_IMPLEMENTATION`，`P0/P1/P2/P3=0/0/3/0`。
- review SHA256：`0afee27b68f7a34c12dfcc18326604e52c3bba4b9b4dd95116cecf4ce5410286`。
- decision SHA256：`9d40e3ca946e9009f02159c8ffce8ccd2dad7dcc3463ee99e9cbaa96e3f9704a`。
- P2-1：机器合同没有封死测试标签访问阶段和holdout prediction为0。
- P2-2：Markdown中的变换禁令、rank/qid/sort、percentile、zero-fill、manifest和scope规则没有逐项机器化。
- P2-3：`mean` pair随机采样只冻结包版本，没有冻结平台、解释器和XGBoost二进制身份。
- 判断：三个finding都成立；若直接实现，会留下伪OOS和结果解释空间，因此必须先修合同再复审。

## 修复内容

- 标签值源改为266个main `job_outputs/<job_id>/label.json`逐月后开；聚合`development_labels.csv`和`reconciliation.csv`只允许整文件身份与表头核验，不解析数据行。
- 首折前只开放已成熟前18月115行；17个测试月共151行必须逐折先训练、预测、选择并fsync `pre_effect_seal`，再开放当月标签做效果评价。
- 状态机显式要求测试标签在本折seal前读取0、同折训练/预处理/调参/选择/tie-break使用0、seal后效果读取151；holdout feature prediction及label读取/生成/训练/效果均为0。
- 8项特征必须全有限；缩放、填补、winsorize、符号翻转、交互、特征选择和品种/年份编码全部固定为`none`。
- 每月rank10数量、rank连续性、产品唯一性、`mergesort(eval_date,candidate_rank,product)`、零基`int64 qid`、`average percentile (0,1]`和完整17月未替换`0.0`填充全部机器化。
- 训练固定34主模型+34重复模型=`68 fit`；训练入口恰好1次，参数搜索、early stopping、额外fit、意外命令/产物、生产写、CTP和订单均为0。
- 新增冻结运行时身份：Darwin `24.6.0` / macOS `15.7.4` / arm64 / CPython `3.11.15`，并绑定Python可执行文件、`xgboost/__init__.py`和`libxgboost.dylib` SHA及XGBoost build info；训练前、模型后、效果后必须完全一致。
- 未来单次run authorization必须绑定runner、tests、修订后预注册、机器合同、runtime identity、最终独立预审和唯一64位hex nonce。

## 修订后身份

- 预注册：`stages/20260903_0101_stage006_dual_ranker_development_oos_preregistration.md`，SHA256=`53c9a6e0caad907d21c4fc4e94052836978dd8f81b74ede4e825d94a2b265525`。
- 机器合同：`artifacts/stage006_dual_ranker_development_oos/training_contract.json`，SHA256=`543bd677790fd4d28ed429ae743af39a57f94dece26dfa9fae898b318e6b06ac`。
- 运行时身份：`artifacts/stage006_dual_ranker_development_oos/runtime_identity.json`，SHA256=`f0a469f5a8387ba8171be5b3e2c8c6b0d9fc0e8de7f5b0914e08ef4f327fddbc`。
- 修订只改变治理合同，没有改变8项特征、35月样本、17折切分、双Ranker参数、A/B/C选择器或9个效果布尔门。

## 结果

- 期末权益：不适用；未训练、未回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 模型训练/测试标签读取/holdout预测/holdout标签/CTP/订单：全部0。

## 结论

- 当前决策：`stage006_prerun_block_remediated_pending_independent_rereview`。
- 是否进入下一步：只进入修订后独立复审。
- 只有复审`P0/P1/P2=0/0/0`且明确`ALLOW_STAGE006_IMPLEMENTATION_ONLY`，才允许按TDD实现；仍不授权训练。

## 过拟合反思

- 是否过拟合：否。此次只收紧信息访问、运行身份和机械审计，没有读取标签值、比较模型或修改效果门。
- 风险：整体方向仍高，因为它是多条失败路线后的自适应后继实验；修复合同不能降低历史选择偏差，只能阻止新增自由度。

## 继续价值反思

- 是否值得继续：是，但仅值得重新独立复审。
- 原因：三个P2均已用机器字段闭合；如果复审仍发现P0/P1/P2，应继续停止，不能以用户目标为由绕过。

## 合入建议

- 更新本线`LINE.md`和`research/registry.md`为“Stage006首次预审阻断已修复、等待复审”。
- 不追加根目录`memory.md/back_log.md`；本阶段没有真实回测、突破或路线关闭。
