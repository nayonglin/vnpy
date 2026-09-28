# 正式信号账户边际效用XGBoost V4线

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 创建时间：2026-09-05 18:47 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 当前状态：Stage007反证当前模型形状无法满足联合目标，停止全量标签/训练。首个可训练月2023-09晚于A最大回撤2022-06，无法降低已发生的全周期最大回撤。Stage005/006工程资格保留；XGBoost总目标仍active，尚无达标版本。
- 上游反证：V3 Stage002在A1进入`_run_live_c9`后的profile构造阶段，再次调用`build_static18_plus_fu_universe()`并被workspace写保护阻断；V3 claim已消费且闭线。

## V4目标

- 在零`_run_live_c9`下验证正式回放的全部profile准备链可在同一私有Path上下文中完成。
- 双worker依次调用`_metadata()`、`s847._c9_profile(metadata)`和`build_official_live_strategy_overrides()`，保持两个派生Path重定向直到全部结束。
- 证明最终派生CSV逐bytes等于冻结正式文件、profile规范化结果一致、路径恢复且全部敏感计数为0。

## Reviewer策略

- 静态分析、代码修改、单元测试、profile预检和失败诊断均不启动reviewer。
- 只有未来真实回测同时改善收益和最大回撤，并通过预注册稳健性门后才启动独立reviewer。

## 后续边界

1. 不执行当前形状剩余158次标签回放，不训练该双头候选；不得降低60样本门槛、用未来模型回填、删年或缩短全周期来救援。
2. 另立历史兼容根事件研究线，先复核旧静态桶失败证据、2020起历史特征与成熟样本覆盖，以及模型生效前不可变回撤下界。先证明目标有可能达到，再投入标签批次。
3. 不修改或重跑V2/V3任何claim与失败产物。

## Stage003证据

- 2026-09-05 19:28 CST通过；多头113、空头48；2023/2024/2025各32/40/28；高唯一值特征11项。
- 数值最大差0；正式A回放2次；每worker冻结正式LR排序35次；新增模型训练/预测0。
- 结果：`artifacts/stage003_frozen_baseline_event_qualification/summary.json`。
- 本轮17项针对性测试分别通过；reviewer始终未启动。
- 收益提高且回撤下降的总目标仍未达到，不把事件资格当成策略效果。

## Stage004/004B证据

- 2026-09-05 19:59 CST完成；三个worker各1,614交易日，A/A0逐bytes一致；S干预及完整身份验证各1次。
- A/S期末权益12,226,270.60 / 11,766,718.50，最大回撤-45.921573% / -55.463132%；固定跳过方案无价值，不拉reviewer。
- 固定纸浆事件2022-02-09成交、2022-03-15最终空仓；接受减跳过收益/回撤标签为+0.1581762351 / -0.0124688474。
- 18项本轮测试通过；Stage004B只修复CSV浮点解析与中英文成交枚举，不改回放、不改原失败记录。
- 结果：`artifacts/stage004b_frozen_artifact_analysis/summary.json`；记录：`stages/20260905_1959_stage004_counterfactual_validation_result.md`。
- 没有新模型收益证据、没有生产改动；后续仍需验证全部事件标签、时序泛化和真实成本。

## Stage005证据

- 2026-09-05 20:10 CST：159成熟、2明确删失、0归属失败；9项测试通过，无新增回放/标签/模型。
- 根据Stage502先撮合后信号的执行顺序，正确识别同日平旧仓与下一根决策；未按收益删样本。
- 结果：`artifacts/stage005_event_lifecycle_audit/summary.json`；记录：`stages/20260905_2010_stage005_lifecycle_audit_pass.md`。

## Stage006/007证据

- Stage006/006B：两个截断回放各约147秒，14表与完整路径前缀逐值相同，标签不变；46.15MB无损压缩到1.69MB。原组件标识汇总失败保留，离线复核没有新增回放。
- Stage007：60成熟样本首个训练月2023-09-01；此前A已在2022-06-02达到全周期最大回撤-45.9215732345%，故当前形状不能严格降低该回撤。
- 本轮22项测试分别通过；无新模型、无生产修改、无reviewer。不是整个XGBoost方向无效，只关闭当前样本/训练时点形状。
- 决策记录：`stages/20260905_2020_stage007_joint_objective_impossible_close_shape.md`。
