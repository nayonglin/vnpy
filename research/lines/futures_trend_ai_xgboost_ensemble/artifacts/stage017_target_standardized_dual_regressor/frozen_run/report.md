# Stage017 目标标准化双XGBoost development OOS评估

- 决策：`stage017_target_standardized_oos_fail_stop_feature_label_family`。
- 技术门：`True`；效果门：`False`。
- 唯一结构变化是每折、每目标仅用训练标签拟合StandardScaler；XGBoost参数、九特征、PIT、selector和九项效果门均与Stage016保持一致。
- A为线上逻辑回归正式rank10；C仅在XGBoost同一候选的两项逆变换预测均为正时替换第10席。
- 未读取sealed holdout标签、未修改生产目录、未连接CTP、未调用订单API。

## Development OOS结果

- OOS月份：`15`；C实际替换：`3`；替换年份：`[2024, 2025]`。
- 账户边际收益增量合计：`0.0911055166159`；剔除最好月：`0`。
- 账户边际回撤改善合计：`-0.00837318792338`；剔除最好月：`-0.00837318792338`。
- 分年收益增量：2024=0.0911055166159, 2025=0。
- 分年回撤改善：2024=-0.00837318792338, 2025=0。
- 实际替换月双目标联合命中率：`0.000000%`。
- 模型分裂节点合计：`5444`；该值仅作结构诊断，不是效果门。

这些数值是15个月互斥账户边际标签的资格代理，不是可复利策略曲线；本阶段不发布期末权益、总收益、组合最大回撤、Sharpe、总滑点、总交易次数或胜率。

## 技术门

- `all_input_identities_verified`: `True`
- `runtime_versions_match`: `True`
- `stage014_contract_match`: `True`
- `development_panel_integrity`: `True`
- `fold_count_and_test_boundaries`: `True`
- `expanding_train_month_counts`: `True`
- `test_rows_per_fold`: `True`
- `pit_violations_zero`: `True`
- `prediction_panel_shape`: `True`
- `monthly_selection_shape`: `True`
- `two_models_per_fold`: `True`
- `prediction_determinism`: `True`
- `model_byte_determinism`: `True`
- `arm_a_rank10_exact`: `True`
- `arm_c_prediction_gate_exact`: `True`
- `arm_selection_recomputed`: `True`
- `stage016_dependency_match`: `True`
- `two_scalers_per_fold`: `True`
- `model_scaler_names_aligned`: `True`
- `target_scaler_train_scope_and_metadata`: `True`
- `target_scaler_byte_determinism`: `True`
- `target_unit_invariance`: `True`
- `standardized_prediction_determinism`: `True`
- `tree_structure_recorded`: `True`

## 效果门

- `minimum_replacement_months`: `False`
- `required_replacement_years`: `True`
- `total_return_delta_positive`: `True`
- `total_drawdown_improvement_positive`: `False`
- `leave_best_out_return_delta_positive`: `False`
- `leave_best_out_drawdown_improvement_positive`: `False`
- `each_year_return_delta_nonnegative`: `True`
- `each_year_drawdown_improvement_nonnegative`: `False`
- `active_joint_positive_rate`: `False`

## 反思

- 过拟合风险：高。Stage016结果已知，但Stage017只验证预注册的单位不变性结构，未扫描参数、transformer、特征或门槛。
- 继续价值：当前九特征/账户边际标签XGBoost族到此停止，不再更换scaler、损失、树参数、阈值、rank、年份或品种，也不读取holdout。
