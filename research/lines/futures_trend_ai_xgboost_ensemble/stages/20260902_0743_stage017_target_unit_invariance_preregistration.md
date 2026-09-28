# Stage017：XGBoost目标单位不变性预注册

## 阶段信息

- 预注册时间：2026-09-02 07:43 CST。
- 当前线上：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`。
- 上游决定：Stage016技术门全过但30/30模型全部为单叶树，15个OOS月零替换，决定`stage016_development_oos_proxy_fail_stop_no_holdout`。
- 本阶段是新的“目标单位不变性”结构假设，不修改或重跑Stage016，不读取sealed holdout，不改生产、不连接CTP、不调用订单API。

## 外部调研与判断

- XGBoost官方参数文档定义：`gamma`是继续分裂所需的最小损失下降，`reg_alpha`是叶权重L1正则，`reg_lambda`是L2正则；这些都是作用在训练目标梯度/损失上的绝对尺度量。
- `reg:squarederror`的梯度随目标单位线性变化，而Hessian不随同一线性单位变化；固定`reg_alpha/gamma`下，把收益从小数换成百分数会改变树是否分裂。因此Stage016的单叶退化不能直接解释为“特征没有信息”，也可能是目标单位和绝对正则尺度错配。
- scikit-learn官方`TransformedTargetRegressor`明确支持在训练前变换目标、预测后逆变换；GitHub上的XGBoost sklearn实现也明确暴露`gamma/reg_alpha/reg_lambda`为绝对正则参数。
- 参考：<https://xgboost.readthedocs.io/en/release_3.2.0/parameter.html>、<https://github.com/dmlc/xgboost/blob/master/doc/parameter.rst>、<https://scikit-learn.org/stable/modules/generated/sklearn.compose.TransformedTargetRegressor.html>、<https://github.com/dmlc/xgboost/blob/master/python-package/xgboost/sklearn.py>。
- 判断：固定乘100或10000仍是在选择任意单位；采用每折训练标签自己的均值和标准差可使模型对线性单位变换不敏感，且不消费测试月标签。只验证这一种规格，不扫描transformer或正则。

## 唯一结构变化

- 每个PIT折、每个目标头分别只用该折训练标签拟合`StandardScaler(with_mean=True, with_std=True)`。
- 训练值：`z=(y-train_mean)/train_scale`，其中`train_scale`使用scikit-learn的总体标准差口径；若均值/scale非有限或scale不大于0，技术门失败。
- XGBoost只拟合`z`；OOS预测先得到`pred_z`，再严格逆变换为`pred_y=pred_z*train_scale+train_mean`。
- selector、双正门和效果门全部使用逆变换后的原始`return_delta/drawdown_improvement`单位。
- 保存每折两个scaler的mean、scale、训练目标均值/标准差和SHA；重复拟合时scaler与模型均必须确定。

## 保持不变

- 输入仍为Stage014九特征和Stage015 351条development账户边际标签；不做特征选择或新增特征。
- 两个目标仍为`return_delta`和`drawdown_improvement`。
- XGBRegressor参数逐项保持Stage016：64棵树、深度2、`learning_rate=0.03`、`min_child_weight=12`、`gamma=0.1`、`subsample/colsample=0.8`、`reg_alpha=1`、`reg_lambda=10`、hist、seed42、单线程。
- PIT仍为15折：测试`2024-04-30 -> 2025-06-30`，训练月数`24..38`，标签只有`next_eval_date<=test_date`才可训练。
- A/B/C、月内双头等权percentile、tie-break和C双正门完全不变。
- Stage016九项development效果门逐项不变，不降低最低替换月、年份覆盖、总增量、leave-best-out、分年非负或联合命中率要求。

## 技术审计新增项

1. 30个scaler都只绑定对应折训练索引，fit行数与模型训练行数一致，不读取测试标签。
2. 对每个头做固定单位不变性合成检查：训练目标乘100后重新拟合scaler，标准化数组与原单位最大差`<=1e-12`。
3. 每折模型重复拟合两次，逆变换前后预测差均`<=1e-12`，UBJ SHA一致。
4. 记录每个模型的树数、split node数和leaf数；分裂数只做结构诊断，不作为效果门，也不允许据此调参数。
5. 若技术门失败，禁止调用效果评价和发布真实效果值；发布纪律、三次授权身份检查和原子bundle沿用Stage016闭环。

## 决策边界

- 技术失败：`stage017_contract_or_unit_transform_invalid_stop`，只允许修复实现错误后重新审查。
- 技术通过但任一原九项效果门失败：`stage017_target_standardized_oos_fail_stop_feature_label_family`。停止当前九特征/账户边际标签的XGBoost开发，不继续换scaler、目标单位、损失函数、树参数、阈值、rank、年份或品种，不读取holdout。
- 全部效果门通过：`stage017_target_standardized_oos_pass_allow_development_true_engine_ac`。只允许冻结15个月OOS选择并运行一次development真实引擎A/C；仍不授权holdout或上线。

## 反思

- 运行前过拟合判断：有较高自适应风险，因为Stage016 development结果已知；但本假设只针对所有模型无分裂这一单位尺度结构问题，转换方式由标准回归方法固定，不根据月份、品种或效果值选取。
- 控制：唯一规格、原效果门不变、holdout继续不可见；Stage017失败后停止该特征/标签族。
- 是否值得继续：是，但只值这一次。它能区分“目标单位让正则压死所有分裂”和“即便单位无关仍没有稳定预测价值”；不能直接证明收益和回撤会改善。
