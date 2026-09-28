# 线上LR基准偏置XGBoost残差修正线

- line_id：`futures_trend_lr_xgboost_base_margin_residual`
- 研究对象：当前正式AI选品逻辑回归的独立残差修正研究；逻辑回归保持主模型，XGBoost只学习其未解释的非线性部分。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；正式C9/15w、成本、保证金、整数手、相关性和最多4持仓规则均不变。
- 当前状态：Stage001唯一冻结无标签审计已失败并闭线。77个月/1386行、108项特征、旧76个月逐值和50个PIT折均通过；最新正式池合同错误地要求11行都有模型特征，但固定`fu.SHFE`不是LR打分行，唯一门失败。未读取标签值、训练模型或回测。
- 核心假设：正式LR已经提供稳定线性先验；将其每折raw log-odds作为XGBoost `base_margin`，可让浅树只补充有限的非线性交互，而不是重新学习一套与LR竞争的排序。
- 证据边界：`2020-01..2026-05`均是已观察开发期，不是独立holdout；即使后续development OOS通过，也必须等待未来新增月份并跑正式A/B真实引擎，才可能形成目标证据。
- 隔离边界：只写本研究线；禁止修改正式模型、生产release、共享Stage183数据、CTP、订单和旧研究线。

## 冻结研究臂

- A：每个严格PIT折内按正式代码重训`StandardScaler + LogisticRegression(C=0.20)`，以LR概率排序。
- B：同折先拟合A，再把LR `decision_function`输出作为逐样本raw `base_margin`；固定浅层XGBoost只学习残差，最终概率由`sigmoid(LR raw margin + tree correction)`给出。
- 不保留直接XGBoost臂，不做LR/XGBoost固定平均，不扫描参数、阈值、月份、品种或特征子集。

## 阶段

- Stage000：`stages/20260904_1532_stage000_base_margin_residual_design.md`。
- Stage001：`stages/20260904_1543_stage001_label_free_contract_fail_close.md`；决策`stage001_m0005_causal_feature_or_pit_contract_fail_close_no_labels`。
- Stage002：禁止实现或执行；Stage001前置合同已失败。
- Stage003：不适用。

## Stage001结论

- m0005正式身份、m0004/m0005模型及月更源码逐字节一致、Stage183输入运行前后SHA均通过。
- 正式训练面板精确`77`个月、`1,386`行、每月`18`品种、`108`项有限特征；与旧正式`76`个月/`1,368`行最大逐值误差`1.4551915228366852e-11 <= 1e-10`。
- 真实60交易日label-end生成`77`行、缺失0；严格PIT active folds=`50`，训练月`24..74`，泄漏行/折=`0/0`。
- 最新池共11行，但只有10行`selection_role=model_ranked`且具有108项特征；`fu.SHFE`为`fixed_fu`、`model_ai_rank`为空、108项模型特征为空。Stage000的11行逐值门不成立，按冻结规则失败。
- 标签值、LR/XGBoost fit/predict、策略回测、CTP、订单和生产写入均为0；正式A未改变。
- 禁止把11行门事后改成10行并在本线重跑；若未来继续，必须另立合同并从“18品种LR排序 + 固定fu卫星”真实结构重新预注册。

## 过拟合反思

- 当前判断：Stage001没有效果过拟合；事后把11行改成10行后重跑会形成合同救援。
- 原因：本阶段没有读取标签值或效果；但失败位置已经暴露，修改样本身份门再继续会利用本次结果，即使不涉及收益也会破坏唯一冻结审计。

## 继续价值反思

- 当前研究线：没有继续价值，关闭。
- XGBoost总方向：仍有条件研究价值，因为`base_margin`机制尚未训练；但下一步不能复用本线final或改门重跑，必须新合同先正确隔离10个模型选品席位与固定fu卫星。
