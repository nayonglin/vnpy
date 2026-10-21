# Stage458：Con4 Ridge53 模型、完整选择与留出诊断独立复核

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20 22:19 CST。
- 当前模式：非实现者独立复核；非重要突破，不改正式 C9，不产生新 alpha 参数，不触发正式策略晋升。
- 冻结协议 SHA：`c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053`。
- 被审 Stage456 manifest：57,725 bytes，SHA `6fe8285b0b051d335187a9a20b0b5451a37a341396946c6fffd79869e2a63d78`。

## 调研与判断

本轮只消费 Stage453 已冻结的外部调研与身份合同：CFTC 官方定义、重建发布时间约束、原论文适用范围与 `cot_reports` GitHub 血缘。不新增网络下载，不重新读取 raw ZIP，不重新构建 Stage454 源。我的判断是：计算正确性可以独立验证；重建发布时间假设仍不是 strict PIT，美国周频集中度研究也不能直接证明国内窄止损做多或加注有效。

## 范围、参数与输入

新增脚本仅为本审查目录内 `review.py`、必要恢复的 `selection_continue.py`。新增/修改/删除金融参数均 0，原 52 列、scaler、成熟行、目标、原权重、alpha1、截距不罚、K、成本与风险未改。全程 0 fit、0 求解/推导 beta、0 cash、0 SQL、0 API、0 价格读取。

首轮六份原训练 CSV 各读一次，共 1,386,540 行（重叠 fold 的行数，不能当独立样本数）；COMMON26 一次、新母 q 一次、原母身份一次、旧 score 一次。核原 98 产品/95 家族、399,252 母行、1,552,456×26 COMMON、完整 1,933,480 main+held child score，以及 main 161,014 和 held 并集 161,014 母行。原大输入使用 accepted binding 与前后 stat，未额外预 hash。

## 首次审查器错误及必要恢复

首轮审查失败收据原样保留。错误是审查器把“score 中有 child 的母行数”强制等于原 fold 的 `prediction_mothers`；后者包含 `no_observed_children` 母行。这是本审查脚本的断言错误，不是 Stage456 模型、数据或选择错误。比如 main 2020 原全部母行 71,344，有 child 的母行 47,074，无 child 的母行 24,270。

首轮已经保存六 fold 方程与残差结果，且已通过 1,933,480 行总数、所有旧新 score 身份、复制旧 score 的逐浮点一致、q parent join 和全部便携预测检查，然后才在上述错误断言退出。首轮没有保存流式 argmax 中间文件，也未保留便携分数最大绝对误差的最终变量；没有声称误差实际为零。

root 明确授权一次 selection/held-only 必要续审：仅额外读取候选 score 一次，用完整候选母身份与 accepted 控制 choices 逐母对齐后独立重建 K/argmax/tie/family 次序；首次读取原/新 choices 与原 actions 五个标签字段。没有重读原六训练表、COMMON、新 q 向量、旧 score、原母表或方程，没有重跑模型或现金。候选 score 总读取 2 次，额外恢复读取 1 次，完整披露而非冒称一次全审成功。

## 结果与置信边界

- 最终独审 `status=completed`、`core_blockers=0`、`core_problems_remaining=0`；模型与选择计算接受。
- 六 fold 原始目标成熟性、Y/w 的 IEEE 解析、父子身份、held 训练排除、原 scaler、53 维列序、新 q 加权均值/方差、joblib/portable 系数均通过。
- 六份新 54×54 完整 lhs/rhs 重建最大绝对差均为 0；仅前 53 维加 alpha1，截距不罚。原 52 系数在同原行/Y/w 的正规方程残差也通过。原/新 beta 最大绝对残差均为 `1.8917489796876907e-08`。这是检验保存系数，不是重新求解。
- 全部 1,933,480 行便携新预测通过 `rtol=1e-12, atol=1e-12`。首轮最大误差变量未落盘；结合全域最大绝对 score `24.16348215212827`，可报告的保守绝对误差上界为 `2.5163482152153434e-11`，不是实际观测最大误差。
- 完整 K、product 内正分 argmax、epoch/action tie、普通/F family 优先、held scope，以及完整母域无 child 状态全部独立匹配。
- 相对 accepted A52 的真实选择差异为 main **83**、held **239**；Stage156 内部同新 score 无 K→有 K 的变化不计作此增量。

| 范围 | 8 个精确映射产品差异 | 90 个结构 N.A 产品差异 | raw q 可见母行差异 | raw q N.A 母行差异 |
| --- | ---: | ---: | ---: | ---: |
| main | 37 | 46 | 35 | 48 |
| held 并集 | 65 | 174 | 64 | 175 |

| 年份 | main 选择差异 | held 选择差异 |
| --- | ---: | ---: |
| 2020 | 10 | 14 |
| 2021 | 23 | 58 |
| 2022 | 29 | 79 |
| 2023 | 2 | 23 |
| 2024 | 3 | 11 |
| 2025 | 3 | 30 |
| 2026 | 13 | 24 |

N.A 新项直接贡献为 0，但原 52 系数与截距联合重估确实改变 N.A score 和选择；上述分层说明不能把总体差异全部归为可见 Con4 数值本身。

原 actions 1,552,456 行只读 `action_id,label_state,participation_state,net_R_stress,label_known_date` 一次，保留原/候选 held 已选的 5,978 个 ID。独立重算全部 held daily、年度、family 差异与未知，和 Stage456 相同：

| 留出组 | 原 first-exit 目标逐 u 等权平均增量 R | 异动作未知 family-u | 同动作共同未解 |
| --- | ---: | ---: | ---: |
| holdout_0 | `+0.00001426227282361671` | 0 | 27 |
| holdout_1 | `-0.0004525141846933737` | 4 | 35 |

holdout_1 的 4 个异动作未知分布于 2021 年 2 个、2022 年 1 个、2026 年 1 个，未填 0。两组年度与完整 daily 逐行匹配。held 泛化门不支持；这不改变预冻结的 `held_diagnostic_is_cash_veto=false`，main 83 个真实选择差异满足现金诊断的身份前提，可以由 root 决定执行原已冻结四现金诊断，不能因此救参数或改变经济门。

新增/修改/删除回测结果均 0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率全部 N/A；本阶段是独审，不把模型目标 R 诊断写成现金收益，也不重复计入 Stage456 的六次实际 fit。所有统计仍受历史择题、重叠训练/窗口与重建时钟限制，不授予 strict PIT、加注、高杠杆或生产资格。

## 输出与后续

- 最终收据：[review_receipt.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage458_Con4_model_review/review_receipt.json)，19,732 bytes，SHA `1d76d2d072b344d499889e234dba00d6f064e5e0ff6d9858a5a761201b546729`。
- 父失败收据：[actual_run1/review_receipt.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage458_Con4_model_review/actual_run1/review_receipt.json)。
- 续审收据：[selection_held_receipt.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage458_Con4_model_review/selection_held_continue1/selection_held_receipt.json)。
- 年份/映射/可见性选择差异及 held family 差异均保存在 `selection_held_continue1/`。

运行前过拟合判断：本次独立计算复核本身否，未改变样本或按成绩寻参；长期历史择题风险仍然高。运行后判断相同，独审负泛化结果必须保留，不能因 q 系数全正或未来现金成绩漂亮而宣称稳健 alpha。

运行前继续价值：是，唯一固定增量需要可复验的模型/选择验算。运行后：该独审已完整结束，不需要重跑；按已冻结合同完成四现金诊断有结论闭环价值，继续扫 lag/符号/映射/阈值/风险或忽略 held 失败没有价值。LINE、registry、根 memory/back_log 与 Git 均由 root 统一处理，本 agent 未修改。
