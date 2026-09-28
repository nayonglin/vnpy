# Stage017 目标标准化双XGBoost development OOS结果

- line_id：`futures_trend_ai_xgboost_ensemble`
- 当前模式：冻结development OOS资格评估
- 记录时间：2026-09-02 08:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`，当前工作区研究改动未提交
- 阶段性质：Stage016单叶退化后的唯一结构性单位不变性验证
- 是否重要突破：否；属于重要反证和当前特征/标签族关闭结论
- 是否触发A/B：触发冻结A/B/C资格比较，未触发development真实引擎A/C

## 外部调研与判断

- 参考资料：XGBoost官方参数文档、XGBoost GitHub参数说明、scikit-learn `StandardScaler`与`TransformedTargetRegressor`文档。
- XGBoost的`gamma`、`reg_alpha`和`reg_lambda`作用在绝对损失/梯度尺度上；Stage016用小数收益目标时30/30模型无分裂，目标单位错配是可证伪的结构假设。
- 固定乘100或10000仍会选择任意单位，因此Stage017只允许每折、每目标用训练标签拟合`StandardScaler`，预测后逆变换；不扫描transformer、损失、树参数、特征或门槛。
- 调研判断：该变化值得验证一次，但只能证明Stage016单叶退化是否由单位尺度造成，不能证明存在稳定alpha。

## 本次变更

- 新增脚本：`tools/stage017_target_standardized_dual_regressor.py`
- 新增测试：`tests/test_stage017_target_standardized_dual_regressor.py`
- 新增合同：`artifacts/stage017_target_standardized_dual_regressor/training_contract.json`
- 新增运行前/运行后独立review、一次性授权和73项冻结结果文件。
- 修改脚本：无生产脚本修改；Stage016 runner保持冻结SHA不变。
- 删除脚本：无。
- 新增参数：每折、每目标`StandardScaler(with_mean=True, with_std=True)`，只拟合训练标签并逆变换OOS预测。
- 修改参数：无；XGBoost参数、九特征、两个目标、PIT、selector、A/B/C和九项效果门与Stage016一致。
- 删除参数：无。

## 回测/归因参数

- 数据区间：development `2022-04-29 -> 2025-06-30`；OOS测试`2024-04-30 -> 2025-06-30`。
- sealed holdout：`2025-07-31 -> 2026-06-30`，标签读取0。
- 账户规模：15万元正式口径。
- 成本口径：Stage015线上同构账户边际标签已包含正式成本、保证金、整数手、相关性和最多4持仓约束。
- 样本过滤：39月×rank10..18共351条development标签；15折PIT，训练月`24..38`，每折测试9候选。
- 策略/归因口径：A为线上逻辑回归正式rank10；B为两个标准化目标XGBRegressor头的等权月内percentile选择；C仅在B同一候选的逆变换收益增量和回撤改善预测均大于0时替换第10席。
- XGBoost参数：64棵树、深度2、学习率0.03、`min_child_weight=12`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1`、`reg_lambda=10`、hist、seed42、单线程。

## 结果

- 技术门：全部22项通过。
- OOS月份/预测/模型/scaler：`15 / 135 / 30 / 30`。
- PIT违规：0；重复标准化预测差、逆变换预测差、模型SHA差、scaler SHA差均为0。
- 单位不变性最大差：`1.7763568394002505e-15 <= 1e-12`。
- 模型结构：30个模型均为64棵树，split nodes合计`5444`、leaf nodes合计`7364`；目标标准化消除了Stage016的单叶退化。
- B选择非rank10：6/15个月；C实际替换：3/15个月，分别为`2024-04-30 AP rank16`、`2024-08-30 OI rank14`、`2025-05-30 FG rank12`。
- 九项效果门：3项通过、6项失败。
- 通过项：替换年份覆盖`[2024, 2025]`、总收益增量为正、分年收益非负。
- 失败项：替换月`3<4`、总回撤改善非正、两项leave-best-out非正、分年回撤非负失败、替换月双目标联合命中率失败。
- 账户边际收益增量合计：`0.09110551661593003`，约`+9.11`个百分点；全部来自一个月，leave-best-out为`0.0`。
- 账户边际回撤改善合计：`-0.008373187923382819`，即约恶化`0.84`个百分点；leave-best-out仍为同一负值。
- 替换月双目标联合正收益率：`0.0`。
- 期末权益：不适用；本阶段是15个月互斥账户边际资格代理，不是可复利策略曲线。
- 总收益：不发布；不得把边际增量合计当作组合全周期收益。
- 最大回撤：不发布；这里只发布边际回撤改善标签合计。
- Sharpe：不适用。
- 总滑点：不适用；未运行新的development真实引擎组合。
- 总交易次数：不适用。
- 胜率：不适用；联合命中率仅为资格统计，不是交易胜率。
- 新增评估结果：上述Stage017冻结结果。
- 修改评估结果：无。
- 删除评估结果：删除“折内目标标准化后当前九特征/账户边际标签XGBoost族可同时提高收益并降低回撤”的假设。

## 输出文件

- report：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/report.md`
- decision：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/decision.json`
- technical：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/technical_qualification.json`
- effect：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/effect_qualification.json`
- predictions：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/oos_predictions.csv`
- selections：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/monthly_arm_selections.csv`
- models/scalers：`artifacts/stage017_target_standardized_dual_regressor/frozen_run/models/`、`scalers/`
- manifest：SHA `6613eebd7a0db12d94ae3304600c1b129ef5d0d88d0413f4f7298f9849ecfb81`，72项非manifest文件逐项匹配，加manifest共73项。
- authorization：SHA `366a36fffe05c542136530a6dd4112387ce6a7af878e0f9ea25e461e392c132b`。
- postrun review：`reviews/20260902_stage017_postrun_independent_review.md`，`P0=0/P1=0/P2=0`。
- orders/daily/quality：不适用；本阶段未运行真实组合引擎。

## 结论

- 本阶段结论：`stage017_target_standardized_oos_fail_stop_feature_label_family`。
- 目标标准化证明Stage016的单叶退化主要受目标单位与绝对正则尺度影响，但学出大量分裂后仍未同时改善收益与回撤。
- 是否进入下一步：否。不运行development真实引擎A/C，不读取sealed holdout，不接入正式版。
- 下一步：停止当前九特征/账户边际标签XGBoost族；不得继续更换scaler、目标单位、损失函数、树参数、阈值、rank、年份或品种。未来若探索XGBoost，只能基于不同特征或不同标签机制另立研究线，不能视为Stage017续调。

## 过拟合反思

- 运行前判断：是，风险较高。Stage016 development结果已知，Stage017属于自适应后续实验。
- 运行后判断：本次唯一冻结规格的失败结论有效；从现在开始继续修补同一形状会构成明确的事后过拟合。
- 原因：正收益增量完全由一个月贡献，剔除最好月归零，同时回撤恶化、联合命中率为0；继续搜索只会放大选择偏差。

## 继续价值反思

- 运行前判断：有，但只值一次。它能区分单叶退化与真实预测价值不足。
- 运行后判断：当前特征/标签族没有继续建模价值。
- 原因：结构问题已被修复，但收益稳健性和回撤目标仍失败；继续调当前族不能满足“提高收益、降低回撤”的共同目标。

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage017失败并关闭当前特征/标签族。
- 是否更新`research/registry.md`：是，更新当前状态与失败边界。
- 是否追加根目录`memory.md/back_log.md`：追加`back_log.md`重要路线关闭摘要；`memory.md`不追加。
