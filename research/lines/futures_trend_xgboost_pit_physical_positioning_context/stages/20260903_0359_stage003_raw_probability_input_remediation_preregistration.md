# Stage003 原始逻辑回归概率输入修复预注册

## 修复身份与边界

- 修复时间：2026-09-03 03:59 CST
- `line_id`：`futures_trend_xgboost_pit_physical_positioning_context`
- 原始Stage003预注册：`stages/20260903_0318_stage003_joint_ranker_development_oos_preregistration.md`，SHA256=`859d060217e6ef381170d439086ec0d7097d2c18152f2c0ff0aaacb78124cbea`。
- 首次治理修复：`stages/20260903_0331_stage003_prerun_block_remediation_preregistration.md`，SHA256=`52bb25107cbd8b1848c2e9da0b138958ead54d7ca85f3a0a45fe4e6611baf1c1`。
- 原始概率缺口独立review：`reviews/20260903_stage003_raw_probability_contract_gap_review.md`，SHA256=`59b6294dd380dce2cbadb087a669d28834e1ca45cc8804f2e6c593ee32e8cd53`。
- 缺口decision：`reviews/20260903_stage003_raw_probability_contract_gap_review_decision.json`，SHA256=`5a48a80f165c468e09069261611c41b6b33646e41894c3661277459192d50762`，决定=`BLOCK_STAGE003_IMPLEMENTATION_FOR_RAW_PROBABILITY_CONTRACT_GAP`，`P0/P1/P2/P3=0/0/1/0`。
- 当前授权：只允许修订无标签输入合同并再次独立预审；不得继续Stage003实现、读取任何标签值、fit、训练、预测、效果评价、回测、创建authorization、读取holdout、修改生产、连接CTP或调用订单API。
- 本文件只覆盖原预注册中full split投影白名单与authorization绑定链；样本、标签、六项XGB特征、模型参数、qid、A/B/C算法、11项效果门和停止规则全部不变。

## 缺口与最小修复

- 冻结A/B/C规则和prediction payload要求原始`pit_logistic_probability`，但Stage002模型资格表只含`formal_probability_delta_vs_rank10`；原预注册又把full split允许读取列限制为5项元数据，因此实现无法同时满足数据来源和payload语义。
- 数据源不新增、不替换：继续使用已经冻结的`full_feature_split.csv`，SHA256=`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`。
- 该文件允许读取的投影从原5列精确扩展为6列，顺序固定为：
  1. `eval_date`
  2. `next_eval_date`
  3. `product_vt_symbol`
  4. `a_rank`
  5. `split`
  6. `pit_logistic_probability`
- 禁止读取full split中的`role,window_id`、曲线特征、`label_values_read_allowed,account_label_qid`及任何其他列；实现必须使用显式`usecols`并在测试中证明投影精确。

## 无标签连接与一致性门

- 原始概率按`eval_date,product_vt_symbol,a_rank`与Stage002 `model_eligible_feature_panel.csv`一对一连接；Stage002文件SHA仍为`12b1e6afc5b4411e0cbab9b9ea59a6137eefcd7358decd69d2c327cae1407547`。
- 连接前后两侧键重复数必须均为0；Stage002 218行必须全部命中，得到development `153`行/`26`活跃月及sealed holdout feature `65`行/`9`活跃月，缺失和额外连接均为0。
- `pit_logistic_probability`必须是有限数，且逐值位于闭区间`[0,1]`；bool、字符串、NaN和Infinity均失败关闭。
- 每个活跃月必须恰有一个rank10。以该月rank10原始概率为锚，逐行重算：
  `raw_delta = pit_logistic_probability - rank10_pit_logistic_probability`。
- `raw_delta`与Stage002 `formal_probability_delta_vs_rank10`逐行最大绝对误差必须`<=1e-12`；rank10两者必须精确0。任一不一致直接技术失败，不得改用差值冒充原始概率。
- 原始概率只允许进入LR percentile、B/C tie-break、prediction实际payload及effect-open机械重算；不得进入冻结六项XGB矩阵、qid、训练目标、标签连接、标签相关性、特征使用门或任何额外衍生特征。

## 对抗测试增量

- 合成测试必须证明合法原始概率投影可与差值在`1e-12`内复核，并且传给ranker的矩阵列精确等于冻结六特征。
- 对抗测试必须分别拒绝：用概率差冒充原始概率、请求full split额外列、任一侧重复键、缺失连接、额外连接、非有限概率、越界概率、跨文件delta不一致、原始概率进入XGB矩阵。
- 上述测试只使用合成数据和无标签真实元数据；不得读取job label、聚合标签数据行或reconciliation数据行，不得创建XGB estimator或fit。

## authorization完整绑定链

- 第一次治理修复中的14项绑定键被本文件完整替换为以下19项exact key set，调用方不得增删或替换：
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
  12. `training_contract`
  13. `runner`
  14. `test_contract`
  15. `test_state_machine`
  16. `test_adversarial`
  17. `runtime_identity`
  18. `final_implementation_review`
  19. `final_implementation_review_decision`
- 新一轮独立预审文件固定为`reviews/20260903_stage003_raw_probability_remediation_rereview.md`及`reviews/20260903_stage003_raw_probability_remediation_rereview_decision.json`。
- authorization只能在新预审允许TDD、实现及测试完成、最终实现review再次`P0/P1/P2=0/0/0`且用户另行明确授权后创建；届时19个文件的实际SHA必须全部绑定。

## 未改变项

- 218行连接、153 development、65 holdout feature、13初始qid/62行、13折/91行、4回退月不变。
- 六项XGB输入、joint maximin相关性、单头32棵深度2、26次fit、LR/XGB月内percentile各50%和tie-break不变。
- 标签访问仍固定为153个main job JSON；聚合/reconciliation数据行、A2、其他113个development main、holdout标签读取均为0。
- 11项development效果门、失败永久闭线、通过也只允许另写true-engine A/C预注册的边界不变。

## 反思

- 是否过拟合：**否**。本次只让既有selector所需的原始概率获得明确、可审计的数据来源，没有接触标签、效果或修改统计规则。
- 是否值得继续：**仅在本修复独立预审P0/P1/P2清零后值得恢复一次TDD实现**。若仍不能证明原始概率来源与六特征隔离，就应继续阻断。
