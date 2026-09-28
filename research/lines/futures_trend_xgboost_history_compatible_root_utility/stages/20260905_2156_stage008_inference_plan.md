# Stage008 冻结月度模型推理实现计划

- 时间：2026-09-05 21:56 CST。
- line_id：`futures_trend_xgboost_history_compatible_root_utility`。
- 沿用Stage004固定假设和Stage006/007接口，不新增模型参数、阈值、样本选择或真实C结果。使用executing-plans和TDD执行；用户已授权持续研究，不重复申请，不启动reviewer。

## 架构与取舍

选择继承已有FrozenBaselineGuard，在本线新增受限月度推理类，保留正式LR唯一文件/调用栈白名单、网络/CTP/写入/回放次数门。不能全局解除XGBoost预测限制，也不另写简化交易引擎。

1. `tools/stage008_frozen_inference.py`及对应测试：只加载登记的月度metadata和UBJSON；每月一次，绑定文件哈希及对象身份，当前日期只选当月。只在受控入口允许已加载双头预测，禁止未登记模型、直接外部预测、训练/更新、替换模型、原生模型写出。继承原守卫恢复语义，并限制回放读取标签目录。
2. `tools/stage008_model_catalog.py`及对应测试：从完整Stage006成功产物核验summary、source/output身份、80个月模型索引及其原生文件；不读取训练标签数值，不训练。缺少完整训练产物则拒绝，不创建C目录。
3. 后续完整C入口复用Stage007已验证的after-snapshot/before-open位置；使用C当期10特征，不使用A事件ID作为动作开关。完成目录/模型核验后再冻结唯一C执行合同，不在标签未齐时运行模型C。

## 测试与顺序

- 先写合成数据用例并见失败，再实现登记加载/预测与安全门；实际XGBoost原生UBJSON保存加载，不用假估计器代替关键集成。
- 覆盖当前月份、无训练月份、FU、缺月、metadata和模型损坏、重复对象/不受控调用、fit/update/train/native训练/原生写出、生产外写/网络/CTP、正式LR限制及退出恢复。
- 再用合成完整campaign验证目录绑定、月份完整性及输出篡改；真实93标签快照不得越过历史训练门。
- 全线相关回归及原1511/1517输入复核，记录实现证据与策略收益证据的区别；仅写本线目录，不提交或改共享记录。

## 调研与判断

- [XGBoost模型IO](https://xgboost.readthedocs.io/en/stable/tutorials/saving_model.html)建议原生模型格式用于长期保存，并区分pickle内存快照；[v3.2.0官方GitHub实现](https://github.com/dmlc/xgboost/blob/v3.2.0/python-package/xgboost/sklearn.py)显示外层predict调用Booster.inplace_predict，加载时会创建Booster并设置属性。需要同时约束Python入口和原生训练/写出接口。
- [sklearn时序验证](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)说明不能用未来训练过去；本线仍按不等距事件成熟日期及月界切分，不直接使用等样本折。
- 开始过拟合判断：本次不是按收益调参；整体历史研究选择偏差仍存在。继续价值：是，受限真实C推理是验证完整收益/回撤目标的必要实现，单测本身不证明alpha。
