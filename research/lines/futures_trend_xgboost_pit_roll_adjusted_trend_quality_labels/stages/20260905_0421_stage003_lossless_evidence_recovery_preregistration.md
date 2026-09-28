# Stage003 XGBRanker 无拟合证据恢复预注册

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- stage：`stage003_lossless_evidence_recovery`
- 预注册时间：2026-09-05 04:21 CST
- 工作类型：Stage002 技术失败后的证据重放；禁止重新拟合，禁止改变任何模型/标签/选择/效果语义。

## 开始前反思

- 是否正在过拟合：**没有新增调参，但开发样本已使用，风险存在**。目前只查看了 Stage002 失败 summary、第一折模型重建哈希和 CSV 浮点差异；尚未读取全周期预测门或 A/C 效果值。本阶段必须在读取这些效果值前冻结全部恢复门。
- 是否还有价值继续：**是**。原 74 个模型、37 个 pre-effect seal 和 36 个合法 access event 完整存在；通过无 fit 重放可以区分“模型无效”与“CSV 非 lossless”而不重复使用标签训练。

## 冻结输入

1. Stage002 技术失败 bundle，manifest SHA256 必须为 `a20fa63a1c95a9d37fdc0485ddebd9e5ff403e36d4349d79b04e81e87143e904`，159 个产物、13 个输入。
2. Stage002 授权、execution event、37 行 fold audit、74 个模型、37 个 seal、36 个 effect access event。
3. Stage002 原 13 个冻结研究输入，身份必须继续与失败 bundle manifest 一致。
4. Stage002 冻结 core/runner、V1 特征合同、V2 ranker 实现、XGBoost sklearn 源码和原生库；不得修改后伪装重放。

## 冻结恢复流程

1. 先验证 Stage002 失败 decision/error、已消费 nonce、completed execution event 和完整 manifest；此时禁止读取效果 CSV 或未来标签值。
2. 对 37 个 fold 按日期升序加载 primary/repeat 两个冻结模型，共 74 次 `load_model` 和 74 次 `predict`，`fit` 调用必须为 0。
3. 使用原 19 特征、原 `fu.SHFE` 排除、原测试 qid 排序，重建 prediction frame；primary/repeat 预测必须逐元素完全一致。
4. 重建 prediction SHA 和 A/C selection SHA，必须分别与原 seal 完全一致；模型文件 SHA 和 seal 文件 SHA 必须与 fold audit 一致。
5. 全部 37 折通过后，才允许逻辑打开 Stage001 路径标签；按原规则排除 `fu.SHFE` 并重算 relevance。
6. 将重建预测以 `float.hex()` 写入 lossless CSV，再读回 `float.fromhex()`；2,000 行预测必须逐元素 bit-exact，重放 SHA 必须仍与 seal 一致。
7. 原 Stage002 普通 CSV 的差值只作根因诊断，不作为模型门，也不得用于选择或效果计算。
8. 使用重建的内存预测/选择和原始标签重新生成 36 个月 predictive/effect 表；效果门严格调用 Stage002 已冻结函数，不得修改阈值。

## 技术恢复硬门

- Stage002 bundle、13 个输入和所有实现身份完全有效。
- Stage002 decision 精确为技术失败，error 精确为 `pre_effect_seal_mismatch`，失败阶段为 `fold_completed`。
- 37 folds、74 model files、37 seals、36 opened access events、`fit=0`、`load_model=74`、`predict=74`。
- 74 个模型文件 SHA 全匹配；37 个 fold 的 primary/repeat 预测逐元素完全一致。
- reconstructed prediction seal match=`37/37`；reconstructed selection seal match=`37/37`。
- lossless hex round-trip 行数 `2,000`、bit mismatch=`0`、seal replay=`37/37`。
- 36 个 access event 均为 `opened`，expected/opened 行数相等，合计 `1,940`；其 seal SHA 全匹配。
- 标签技术合同仍为 55,226 行/1,046 qid，最终训练元数据仍为 55,168 行/1,045 qid。
- strategy backtest、sealed holdout、CTP、订单 API、生产写入全部为 0。

任一技术恢复门失败，决策为 `stage003_lossless_evidence_recovery_fail_close_no_effect_claim`，不得开放效果结论。

## 冻结效果门

技术恢复全部通过后，严格复用 Stage002 预注册门：

- 全截面：36 月 mean/median Rank IC `>0`，正 Rank IC 月至少22，leave-best sum `>0`，正年份至少3；平均 NDCG 随机期望差 `>0` 且胜出月至少22。
- A/C：替换月 `[8,32]`；质量改善率 `>50%`、中位/总和/leave-best `>0`、正年份至少3；绝对趋势幅度与 oriented path drawdown 两个分量的总和及 leave-best 均 `>0`。
- 所有代理仍不是策略收益或账户最大回撤；通过只允许真实撮合 A/C 预注册。

## 决策

- 技术恢复与两组效果门全通过：`stage003_lossless_evidence_recovery_pass_allow_true_engine_ac_preregistration_only`。
- 技术恢复通过、任一效果门失败：`stage003_lossless_evidence_recovery_effect_fail_stop_no_true_engine`。
- 技术恢复失败：`stage003_lossless_evidence_recovery_fail_close_no_effect_claim`。

本阶段不得重写 Stage002 失败 bundle，不得重新拟合，不得用效果结果救援门槛。
