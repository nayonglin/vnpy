# Stage003 full split SHA 身份修复独立复审

- 日期：2026-09-03（Asia/Shanghai）
- 决定：`ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_SHA_REMEDIATION_ONLY`
- 严重度：P0=0，P1=0，P2=0，P3=1
- 边界：只读核验既有治理链、新 SHA remediation、corrected machine contract 和冻结 full split 文件字节 SHA；未读取标签数据行或解析 full split 数据行，未运行实现、测试、fit、训练、预测、效果评价或回测，未创建 authorization，未修改其他文件。

## 身份与修复核验

- SHA remediation 实际 SHA256：`e9a14c35522c59f5393974d1b82614cbf1863b80ee3bb6724a0ad496cb685c47`，与委托值一致。
- corrected machine contract 实际 SHA256：`e894e93b697b313d55afbaab8f112efc2c877f9a5abd7200deba5af5377630d1`，与委托值一致。
- 冻结 `full_feature_split.csv` fresh SHA256：`a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`，与原始 Stage003 预注册、概率输入 remediation 和 corrected contract 完全一致。
- 缺陷合同 SHA256 `37dc6533143d1ed457088400e75d7a04364f62a70ea4c4a8fb95bd26e9cbe698` 及其49字符错误值已由前一 gap review/decision 和本 remediation 固定记录，未被当作可运行合同继续使用。

## Findings

### P0：0

未发现标签/holdout 开放、生产触达或结果污染。

### P1：0

未发现 SHA 前缀接受、身份门绕过或 authorization 链缺失。

### P2：0

1. **单叶 input identity 修复成立。** 对缺陷合同治理记录中的14项 `input_sha256` 集合逐键核对，development jobs、aggregate、reconciliation、runtime、Stage002四项身份、Stage003 summary及Stage005四项身份共13项均保持原值；只有 `full_feature_split` 从49字符截断值纠正为实际文件的64字符 SHA。没有替换输入文件或改变路径。
2. **统一格式门已机器化。** corrected contract 新增 `input_sha256_format="^[0-9a-f]{64}$"`；14个 input SHA 当前均为 native JSON string 并逐项匹配小写64hex。remediation 要求在特征表、任务表、job label、模型创建之前完成格式与现场文件 SHA 校验，并用合成测试拒绝49/63/65字符、大小写、非hex、bool、number和null。
3. **24文件 authorization 绑定完整。** remediation 与 corrected contract 的 exact key set逐项一致；`bound_file_keys` 与 `bound_file_paths` 均为24项、键唯一且集合完全相等。新增本 gap review/decision、SHA remediation、本 rereview/decision；`training_contract` 仍使用固定路径但未来必须绑定 corrected contract 的新 SHA。调用方不能动态增删、重命名或替换。
4. **TDD 阶段失败关闭仍成立。** 截断值必须在任何标签读取、feature parsing、fit和结果写入前失败；corrected value 只允许通过 identity-only。真实 aggregate/reconciliation 仍限表头与整文件身份，不允许解析数据行。

### P3：1

第一次 remediation 中 consumption receipt exact schema 只有两个 SHA 字段，但 prose 写成“`三个SHA字段`”。exact 7-key schema 和机器合同不含第三个 SHA，不造成实现分支；该既有文字瑕疵未由本次 SHA remediation 覆盖，继续计 P3=1。

## 无回归核验

- 原始概率精确六列投影、三键连接、`[0,1]`、`1e-12` delta gate及 raw-probability allowed/forbidden uses 均未改变。
- 样本仍为218行、153 development、65 sealed holdout feature；13初始qid/62行、13 active folds/91测试行、4 fallback 月不变。
- 标签预算仍为62 initial加91 test共153个 development main job JSON；aggregate数据行、其他113 main、A2及holdout标签读取均为0。
- 单 XGBRanker、六项特征顺序、32棵深度2、26次fit及全部固定参数不变。
- A/B/C selector、LR/XGB 50/50月内 percentile、tie-break与替换边界未改变。
- 11个 effect gate keys、`5`个替换月、`3`个品种、`2023/2024`覆盖及 joint positive rate `0.6` 等阈值未改变；失败闭线和通过后仅允许另写 true-engine 预注册的边界不变。

## Fresh 只读检查

- 机器合同 JSON 解析通过；14个 input SHA 全部为64位小写hex。
- 24个 bound keys唯一，key/path数量均为24且集合相等。
- 对样本、折、标签预算、模型核心参数、六特征、六列投影、11 gates及阈值执行结构化断言，全部为 true。
- 按委托未运行 pytest 或实现入口；本轮没有 test/fit/train/predict/backtest 结果。

## 过拟合与继续价值

- 过拟合：否。修复仅纠正不可用的文件身份，并加强统一 SHA 格式门；没有接触标签、效果或改变模型规则。
- 继续价值：有，但仅限恢复冻结合同下的 TDD、身份校验实现及无标签合成/对抗测试。最终实现仍需独立 review，当前不具备运行授权。

## 决策边界

P0/P1/P2均为0，决定 `ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_SHA_REMEDIATION_ONLY`。

本决定只允许依照完整治理链继续 TDD implementation、corrected machine contract 的身份门实现及无真实标签的合成/对抗测试。不授权读取标签值、fit、训练、真实预测、效果评价、回测、创建authorization、holdout、生产、CTP或order。未来一次运行必须先通过最终实现独立review，再由用户另行创建绑定24文件实际SHA、一次性64hex nonce和 `scope=one_new_stage003_development_oos_run_only` 的authorization。
