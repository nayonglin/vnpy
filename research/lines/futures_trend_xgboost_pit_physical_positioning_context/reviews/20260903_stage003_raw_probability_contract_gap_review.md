# Stage003 原始概率输入合同缺口独立评审

- 日期：2026-09-03（Asia/Shanghai）
- 决定：`BLOCK_STAGE003_IMPLEMENTATION_FOR_RAW_PROBABILITY_CONTRACT_GAP`
- 严重度：P0=0，P1=0，P2=1，P3=0
- 边界：只读合同、代码、两个 CSV 首行及文件 SHA；未读取任何标签或数据行，未运行 fit、训练、预测、效果评价或回测，未创建 authorization。

## Finding

### P2-1：冻结输入白名单与 selector/payload 语义不可同时满足

原预注册把 `full_feature_split.csv` 的允许读取列严格限制为：

`eval_date,next_eval_date,product_vt_symbol,a_rank,split`

但冻结 A/B/C selector、prediction payload 和 effect-open 重算均要求原始 `pit_logistic_probability`。Stage002 的冻结 `model_eligible_feature_panel.csv` 只包含 `formal_probability_delta_vs_rank10`，不包含原始概率；其 SHA256 仍为 `12b1e6afc5b4411e0cbab9b9ea59a6137eefcd7358decd69d2c327cae1407547`。已冻结 full split 的首行确实包含 `pit_logistic_probability`，其 SHA256 仍为 `a87c73e94eb2afae47ffb106ec60d2720ff881fcecda496aa81af5895165c2b1`，但当前合同禁止读取该列。

`formal_probability_delta_vs_rank10` 在同月内与原始概率保持相同排序，因此可能得到相同 percentile 和 tie-break 顺序；这不构成合同等价。把 delta 写入名为 `pit_logistic_probability` 的 payload 会 falsify 字段语义，使 seal 后磁盘重算无法证明 payload 来自约定原始输入。实现若直接读取 full split 原始概率，则违反冻结读取白名单。两条路径均不合规，所以当前 TDD implementation 必须暂停。

## 对候选修复的评估

**接受其数据来源方向，但 authorization 绑定方案需要补全。** 最小无标签 remediation 应满足：

1. 不修改或替换既有预注册、review、decision；新增一份 remediation，明确只覆盖该输入来源缺口。
2. 对已经 SHA 冻结的 full split，将允许投影精确扩展为原 5 列加 `pit_logistic_probability`，不得读取该文件其他列。
3. 原始概率按 `eval_date,product_vt_symbol,a_rank` 与 Stage002 面板一对一连接；必须无缺失、无重复、全部有限且位于 `[0,1]`。
4. 增加无标签一致性门：逐月以 rank10 原始概率为锚，验证 `pit_logistic_probability - rank10_pit_logistic_probability` 与 Stage002 `formal_probability_delta_vs_rank10` 一致，固定绝对容差 `1e-12`；任一不一致失败关闭。
5. 明确原始概率只可用于 LR percentile、selector tie-break、prediction payload 及 effect-open 重算，不得进入冻结六项 XGB feature matrix、qid、训练目标或任何标签逻辑。
6. 合成/对抗测试必须拒绝：用 delta 冒充 raw、读取额外 full-split 列、缺失/重复连接键、非有限或越界概率、跨文件 delta 关系不一致、原始概率进入 XGB 矩阵。
7. authorization 的 exact `bound_files` 必须绑定新增 remediation。仅增加该 remediation 仍不完整：还必须绑定本次 gap review、gap review decision，以及 remediation 后的新一轮独立 prereview/decision；机器合同、runner、tests 和最终实现 review/decision 继续绑定其最终 SHA。应在 remediation 中列出完整 exact key 集合并相应更新数量，禁止调用方动态附加。

该修复只扩展一个已经冻结文件的精确无标签列，不改变样本、标签、六项模型特征、XGB 参数、A/B/C 算法或 11 项效果门，是当前最小且可审计的修复。重新预审通过前不得继续实现；实现和最终 review 完成前不得创建 authorization。

## 过拟合与继续价值

- 过拟合：本次未接触标签或效果，修复只恢复输入来源与 payload 语义一致性，不是结果后调参；因此本次行为不构成过拟合。
- 继续价值：有，但仅限新增无标签 remediation 和独立预审。该缺口修复后，磁盘 payload、selector 和 effect-open 才具有可证明的数据来源。

## 决策边界

由于存在 1 个 P2，决定为 `BLOCK_STAGE003_IMPLEMENTATION_FOR_RAW_PROBABILITY_CONTRACT_GAP`。当前不得继续 Stage003 实现、读取标签、fit、训练、预测、评价、回测或创建 authorization。只有第二份 remediation 与其独立预审将 P0/P1/P2 清零后，才可重新决定是否恢复 TDD implementation。
