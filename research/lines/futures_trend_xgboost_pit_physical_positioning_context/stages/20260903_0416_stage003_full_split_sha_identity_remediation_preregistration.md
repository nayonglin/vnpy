# Stage003 full split SHA身份修复预注册

## 修复身份与边界

- 修复时间：2026-09-03 04:16 CST
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 缺陷机器合同SHA256：`37dc6533143d1ed457088400e75d7a04364f62a70ea4c4a8fb95bd26e9cbe698`。
- 缺口独立review：`reviews/20260903_stage003_full_split_sha_contract_gap_review.md`，SHA256=`7fa0daffdfa0fb455ab0368f279f67499662dc8e21a366457cf7a6ecfbf60aac`。
- 缺口decision：`reviews/20260903_stage003_full_split_sha_contract_gap_review_decision.json`，SHA256=`fed1b067435cd9c65f3670b64c10fecf32ebf1b162c9756259b4537dd80fa0f3`，决定=`BLOCK_STAGE003_IMPLEMENTATION_FOR_FULL_SPLIT_SHA_CONTRACT_GAP`，`P0/P1/P2/P3=0/0/1/0`。
- 当前授权：只允许纠正机器合同中的一个截断SHA、冻结SHA格式门、补无标签身份测试并再次独立预审；不得继续其他Stage003实现、读取标签值、fit、训练、预测、效果评价、回测、创建authorization、读取holdout、生产、CTP或订单。

## 唯一字段修复

- 缺陷字段：机器合同`input_sha256.full_feature_split`为49字符`a87c73e94eb2afae47ff881fcecda496aa81af5895165c2b1`，无法满足SHA256身份语义，导致合法运行必然在identity-only阶段失败。
- 冻结源文件未改变：`research/lines/futures_trend_xgboost_pit_curve_account_labels/artifacts/stage003_account_label_plan/full_feature_split.csv`。
- 文件现场SHA256及原始Stage003预注册值均为：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- 机器合同只把该字段纠正为上述64字符值；不得修改任何其他`input_sha256`值。
- 机器合同新增统一格式约束`^[0-9a-f]{64}$`；实现必须在打开特征表、任务表、job label或创建模型前，对`input_sha256`全部14个键逐项要求JSON string、小写64hex，再现场比对文件字节SHA。
- 合成测试必须拒绝49字符截断值、63/65字符、大小写、非hex、bool、number和null；真实无标签身份测试必须证明full split现场SHA精确匹配合同，聚合标签/reconciliation仍只读表头且数据行解析0。

## authorization完整绑定链

- 前一轮19项exact key set由本文件完整替换为以下24项；调用方不得增删、重命名或动态附加：
  1. `stage003_original_preregistration`
  2. `stage003_remediation_preregistration`
  3. `stage003_initial_review`
  4. `stage003_initial_review_decision`
  5. `stage003_rereview`
  6. `stage003_rereview_decision`
  7. `stage003_probability_gap_review`
  8. `stage003_probability_gap_review_decision`
  9. `stage003_probability_remediation_preregistration`
  10. `stage003_probability_remediation_rereview`
  11. `stage003_probability_remediation_rereview_decision`
  12. `stage003_full_split_sha_gap_review`
  13. `stage003_full_split_sha_gap_review_decision`
  14. `stage003_full_split_sha_remediation_preregistration`
  15. `stage003_full_split_sha_remediation_rereview`
  16. `stage003_full_split_sha_remediation_rereview_decision`
  17. `training_contract`
  18. `runner`
  19. `test_contract`
  20. `test_state_machine`
  21. `test_adversarial`
  22. `runtime_identity`
  23. `final_implementation_review`
  24. `final_implementation_review_decision`
- 新独立复审路径固定为`reviews/20260903_stage003_full_split_sha_remediation_rereview.md`和`reviews/20260903_stage003_full_split_sha_remediation_rereview_decision.json`。
- `training_contract`键在未来authorization中绑定纠正后的机器合同实际SHA；缺陷合同SHA保留在本文件和gap review中作为不可变审计证据，不再作为可运行合同。

## 未改变项

- 原始概率六列投影、218行连接、153 development、65 holdout feature、13初始qid/62行、13折/91测试行和4回退月不变。
- 六项XGB特征、joint maximin标签、32棵深度2、26次fit、A/B/C 50/50融合、tie-break和11项效果门不变。
- 标签访问、失败闭线、true-engine/holdout/生产/CTP/order边界不变。

## 反思

- 是否过拟合：**否**。本次只纠正文件身份字符串，既没有读取标签，也不可能改善模型效果。
- 是否值得继续：**仅在新复审确认P0/P1/P2=0后值得恢复TDD**。身份合同若不能引用真实冻结文件，任何训练结果都不可复验。
