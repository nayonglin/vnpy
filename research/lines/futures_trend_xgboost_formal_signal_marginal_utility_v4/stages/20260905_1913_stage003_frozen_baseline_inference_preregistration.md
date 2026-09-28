# Stage003 冻结正式基准推理的事件资格合同

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 记录时间：2026-09-05 19:13 CST；是否重要突破：否；reviewer：否。
- 新阶段原因：Stage002在bar循环之前被误拦截；正式基准含已有pairwise逻辑回归，须允许其必要推理以准确复现A。
- Stage002记录不可覆盖；Stage003使用独立claim和输出目录。

## 经济对象与数据门

- 完整继承Stage002的m0005/C9-15w、2020-01-02至2026-08-28、根入场样本和12项特征。
- 全部覆盖/多空/品种/唯一值/双worker精度门保持不变。
- A为完整正式基准；B/C、XGBoost训练和预测尚未开始。
- 本阶段仅提取样本，无绩效选择；失败不按收益调整规则。

## 基准模型例外

- 增加冻结输入：实际pairwise joblib与summary；共1469项输入。
- 仅允许SHA固定的正式Pipeline(StandardScaler, LogisticRegression)、19输入，加载恰好一次。
- 模型SHA：`ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66`。
- summary SHA：`c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86`。
- sklearn推理只允许该Pipeline及其两个step对象，由冻结生产源码`qmt_roll_ai_selection_pairwise_runtime._predict_daily_scores`调用。
- 既有模型的推理调用单列计数并要求A1/A2一致，不冒称全部预测为0。
- 未注册模型加载/推理、任何fit/fit_transform/fit_predict/partial_fit均阻断；XGBoost等新增模型、网络、外部写入、账户/CTP仍阻断。
- 延续Stage002整个回放期间的私有派生Path，策略逻辑、模型内容和数据均不改。

## 调研与反思

- scikit-learn官方持久化文档区分加载已拟合模型与训练，并强调版本与来源可信性：https://scikit-learn.org/stable/model_persistence.html。
- 判断：准确基准必须运行冻结模型，允许这部分推理是语义修复；新增XGBoost仍需后续时间顺序验证。
- 运行前过拟合：本工程修复未使用收益调参；历史多重试验风险仍高。
- 继续价值：是，直接纠正正式A的依赖执行合同，下一步检验真实事件样本。
- 新增参数：已知基准模型路径、SHA和推理来源检查；策略参数修改/删除：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：执行前没有新结果。
- 通过后推进单事件反事实标签；有价值候选达到收益与回撤双改善后才启动reviewer。
