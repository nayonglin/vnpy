# Stage003 原始概率输入修复独立复审

- 日期：2026-09-03（Asia/Shanghai）
- 决定：`ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_PROBABILITY_REMEDIATION_ONLY`
- 严重度：P0=0，P1=0，P2=0，P3=1
- 评审边界：仅只读核验原预注册、两份 remediation、既有 prereview/decision、概率缺口 review/decision 和修订机器合同；未读取任何标签数据行、job label、aggregate/reconciliation 数据行或 holdout，未运行实现、测试、fit、训练、预测、效果评价或回测，未创建 authorization。

## 身份核验

- 原始预注册 SHA256：`859d060217e6ef381170d439086ec0d7097d2c18152f2c0ff0aaacb78124cbea`。
- 第一次 remediation SHA256：`52bb25107cbd8b1848c2e9da0b138958ead54d7ca85f3a0a45fe4e6611baf1c1`。
- 概率缺口 review/decision SHA256：`59b6294dd380dce2cbadb087a669d28834e1ca45cc8804f2e6c593ee32e8cd53` / `5a48a80f165c468e09069261611c41b6b33646e41894c3661277459192d50762`。
- 本轮 probability remediation SHA256：`bf565a1c4be4b61992d6caccf208c984378c93b69c3127353f6b2aeb3d15d23a`，与委托值一致。
- 修订机器合同 SHA256：`37dc6533143d1ed457088400e75d7a04364f62a70ea4c4a8fb95bd26e9cbe698`，与委托值一致。
- 固定 authorization 与 consumption receipt 当前均不存在。

## Findings

### P0：0

未发现 holdout/标签提前开放、生产/CTP/order 触达或结果冒充正式收益的问题。

### P1：0

未发现可绕过授权、用概率差伪装原始概率、或让原始概率进入训练目标而不违反修订合同的路径。

### P2：0

原始概率输入缺口已由 Markdown 与机器合同共同关闭：

1. **精确六列投影。** full split 数据源及 SHA 不变；允许列按固定顺序精确为 `eval_date,next_eval_date,product_vt_symbol,a_rank,split,pit_logistic_probability`。明确要求显式 `usecols`，禁止读取 role、window、曲线、label-access/account-qid 或其他列。机器合同中的 `full_feature_split_allowed_columns` 与此逐项一致。
2. **连接与数值门。** 按 `eval_date,product_vt_symbol,a_rank` 一对一连接；两侧重复、缺失和额外连接均为0，Stage002 218行必须全命中并保持153 development、65 sealed holdout feature。原始概率拒绝 bool/string/NaN/Infinity，要求有限且位于闭区间 `[0,1]`。机器合同固定相同 join keys 和 range。
3. **跨文件一致性。** 每个活跃月恰有一个 rank10；逐行重算 raw probability 相对 rank10 的 delta，与 Stage002 `formal_probability_delta_vs_rank10` 的最大绝对误差必须 `<=1e-12`，rank10 两者精确0。机器合同把容差冻结为 `1E-12`，禁止用 delta 冒充 raw。
4. **用途隔离。** 原始概率只允许进入 LR percentile、selector tie-break、prediction payload 和 effect-open 重算；明确禁止进入 XGB feature matrix、qid、training target、label join/relevance、feature-use gate 或 derived feature。机器合同 allowed/forbidden use 集合与 remediation 一致，冻结六项 XGB 特征列表没有加入 raw probability。
5. **对抗测试合同。** 后续 TDD 必须用合成、无标签数据覆盖合法投影，并逐项拒绝 delta 冒充 raw、额外列、任一侧重复键、缺失/额外连接、非有限/越界概率、跨文件 delta 不一致和 raw 进入 XGB matrix；测试不得创建 estimator 或 fit。该要求属于本次 authorization 必须绑定的 remediation，最终实现 review 必须核验测试逐项存在且实际失败关闭。
6. **19文件完整绑定。** remediation 和机器合同均给出同一组19个唯一 exact keys；机器合同的 `bound_file_keys` 与 `bound_file_paths` 键集合完全相等，数量均为19。链中包含原预注册、第一次 remediation、两轮旧 prereview/decision、gap review/decision、本 remediation、本 rereview/decision、training contract、runner、三份 tests、runtime identity 和最终实现 review/decision。调用方不得增删或替换，实际 SHA 只能在文件全部形成后由未来单次 authorization 精确绑定。

机器 JSON 以结构化字段固定投影、join keys、range、容差、用途集合和19项路径；一对一基数、finite/type、固定行数及对抗反例的完整规范位于被同一 authorization 强制绑定的 remediation。两者联合后规则单义，足以授权 TDD；最终 implementation review 必须按联合合同核验，不能只检查 JSON 中出现的字段。

### P3：1

第一次 remediation 的 consumption receipt exact schema 只有两个 SHA 字段，但 prose 仍写“`三个SHA字段`”。exact 7-key schema 与机器合同均明确，因此不造成实现分支；实现应验证两个 SHA 字段并单独验证 nonce。该既有文字瑕疵未由本次概率修复覆盖，继续计 P3=1。

## 冻结设计无回归

- 样本仍为218行、153 development、65 sealed holdout feature；13初始 qid/62行、13个 active fold/91测试行、4个 fallback 月不变。
- 标签仍只允许153个 development main job JSON；aggregate/reconciliation 数据行、A2、其他113个 development main 和 holdout 标签读取均为0。
- 六项 XGB 特征顺序、joint maximin relevance、单个32树深度2 ranker、固定参数、26次 fit 与确定性门均未改变。
- A=正式 rank10、B=XGB percentile、C=LR/XGB 各50%月内 average percentile，以及既有 tie-break/替换规则未改变。
- 11项 effect gate、收益和回撤双约束、失败永久闭线及通过后仍只允许另写 true-engine A/C 预注册的边界未改变。

## 过拟合与继续价值

- 过拟合：否。本次只补齐已有 selector 输入的真实来源与可审计身份，没有读取标签、效果或修改样本、参数、融合及阈值。
- 继续价值：有，但仅限恢复冻结合同下的 TDD 和合成/对抗测试。若实现不能逐项证明投影、连接、数值、用途隔离和19项绑定，应在最终 review 再次阻断。

## 决策边界

P0/P1/P2 均为0，决定 `ALLOW_STAGE003_TDD_IMPLEMENTATION_AFTER_PROBABILITY_REMEDIATION_ONLY`。

本决定只允许按三份冻结预注册/修复及机器合同继续 TDD implementation、机器合同落地和无真实标签的合成/对抗测试。不授权读取任何标签值、fit、训练、真实预测、效果评价、回测、创建 authorization、读取 holdout、生产接入、CTP 或 order。实现完成后仍须独立最终 review 将 P0/P1/P2 清零，并由用户另行创建绑定完整19文件实际 SHA、一次性64hex nonce及 `scope=one_new_stage003_development_oos_run_only` 的 authorization，方可讨论一次运行。
