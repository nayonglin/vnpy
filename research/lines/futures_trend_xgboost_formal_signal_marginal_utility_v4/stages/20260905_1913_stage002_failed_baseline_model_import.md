# Stage002 正式基准模型导入被误拦截

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 记录时间：2026-09-05 19:13 CST；是否重要突破：否。
- 结果：唯一Stage002 claim已消费；A1在策略初始化失败，A2未启动；产物封存在`artifacts/stage002_event_feature_qualification_failed`。
- 错误：`sensitive_import_forbidden:sklearn.pipeline`。
- 调用链：`_run_live_c9 -> _run_profile -> engine.add_strategy -> SelectionPairwiseRuntimeModel.__init__ -> joblib.load -> sklearn.pipeline`。
- 已验证前一写路径修复生效，metadata/profile/setting均通过；尚未运行策略bar循环、提取事件或生成新绩效。
- 根因：守卫把正式基准已有模型与研究新增模型一并禁止；原输入清单也遗漏了实际joblib文件和summary。必须修正执行合同，不能关闭正式排序开关来伪造A。
- 模型只读结构：Pipeline(StandardScaler, LogisticRegression)，19项输入；未fit或predict。
- 模型SHA：`ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66`。
- summary SHA：`c399a5787577c1cb55276766ed28b0cad8385c063de5b492076dfa8e0619ee86`。
- Stage002代码、claim、冻结和失败文件保留；Stage003以新合同修复基准依赖识别，沿用本线经济假设和数据门。
- 策略参数新增/修改/删除：无；回测结果新增/修改/删除：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、胜率：无新结果；新事件/交易样本0。
- 过拟合反思：无收益或事件观察，因此修复依赖不构成按结果拟合；历史整体多重试验风险仍在。
- 继续价值：是，失败提供了基准必要依赖的直接证据。
- reviewer：未启动。
