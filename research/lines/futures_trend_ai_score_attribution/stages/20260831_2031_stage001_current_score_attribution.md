# Stage001 当期正式 AI 选品分数逐项贡献解释

- line_id：`futures_trend_ai_score_attribution`
- 当前模式：day。
- 记录时间：2026-08-31 20:31 CST；完成校验时间：2026-08-31 20:34 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`，`codex/stage130-option-probe`；只新增本研究线，不改当前分支已有脏文件。
- 阶段性质：原模型复现与只读归因，不是策略回测。
- 是否重要突破：否；形成精确解释证据，没有alpha晋级。
- 是否触发A/B：否；纯归因，无新候选。

## 外部调研与判断

- [SHAP LinearExplainer](https://shap.readthedocs.io/en/latest/generated/shap.LinearExplainer.html)：线性模型可按系数乘中心化特征解释；相关特征会影响归因语义。
- [scikit-learn GitHub逻辑回归源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_logistic.py)：核对decision_function与predict_proba关系。
- 判断：直接用原StandardScaler和逻辑回归系数做精确log-odds加法分解，无需近似SHAP采样。概率不做逐项线性相加，单项贡献不解释为因果。

## 本次变更

- 新增脚本：`tools/stage001_reproduce.py`、`tools/stage001_report.py`、`tools/stage001_verify.py`。
- 修改/删除已有策略脚本：无。
- 新增/修改/删除策略参数：无。
- 新增归因审计口径：概率容差1e-10；加法还原容差1e-12；相对非加权训练均值的标准化特征贡献；固定燃油单独处理。
- 来源：生产HEAD `1961d98ccb2b9129e35fe982b7330ae4217dcde6`；正式活动物料 `m0004_20260831T112631+0800_2485073e9594`。
- 原始模型元数据来自m0015保留的2026-08-03 Stage182快照；当前正式Top10沿用其评分。当前评分代码与原始代码同一内容；辅助函数输出与保存特征逐值相等。
- 两份原始输入SHA256：position_changes=`b3bacdf711c3282f703ea022332d89fc1fe007cc1fb25eb1a25abac7a1eff847`；entry_candidate_snapshots=`96a36c13cdccd5ce73e718d780b4122e2554959d60b697bfbc9f8f99176a33a2`。

## 归因参数

- 评估日：2026-07-31；源数据终点：2026-08-03。
- 训练样本评估月末：2020-01-23至2026-04-30，76个月，1368行；标签截止门：2026-05-07。
- 特征窗口：20/60/120个交易日；108项特征，纠正上轮机制回答中的111项。
- 训练目标：未来60交易日策略净利润横截面排名前半区；使用原样本权重。
- 模型：StandardScaler + LogisticRegression，C=0.20、solver=lbfgs、max_iter=3000、random_state=42，不改默认口径。
- 运行环境：Python .py311；sklearn1.8.0、numpy2.4.4、scipy1.17.1、pandas2.3.3。完整版本在summary中。
- 账户规模/成本口径：不重新模拟账户；全部使用原输入中已有策略盈亏、成本、交易和候选记录。
- 截距0.21139627933948926，训练均值的基准概率0.5526531337549588。
- 正式非燃油Top10由原18品种评分选出；燃油不在模型18品种中，其发布分数是第10名减1e-6，不能归因为模型预测。

## 结果

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均N/A，本次没有新策略回测。
- 新增/修改/删除回测结果：均无。
- 原18品种概率最大绝对误差：0。
- 正式Top10概率最大绝对误差：0；Top10名单和顺序完全一致。
- 保存特征值最大绝对误差：0。
- 108项贡献加截距还原logit误差：4.440892098500626e-16。
- 还原模型概率误差：1.1102230246251565e-16。
- 标准库csv/math.fsum独立核对：1944条贡献、1836条相邻排名差值、126条组贡献，均通过；概率误差1.1102230246251565e-16。
- 输入、正式物料、使用的代码文件前后哈希不变；CTP连接0，订单API0，生产文件写入0。
- 焦煤第1，0.6958488939899317：20日滑点贡献+1.060794、60日滑点+0.458742，20日盈亏波动-0.404163；滑点全窗口合计约+1.422，波动/盈利日组约-0.793。
- 碳酸锂第5，0.6202518246604328：120日最差日净利润贡献+0.766657；20/120日波动贡献-0.670828/-0.640915；多项正负明显抵消。
- 黄金第4，0.6287311070404366：基础策略120日持仓合约日累计0，贡献+0.204490；零活动特征也是排名来源。
- 菜油第10与玻璃第11相差0.7546概率百分点、0.030231 log-odds；完整108项差分已保留，不能只拿单个优势项解释。
- 未产生新回测数据，因此按用户规则不拉独立reviewer；本阶段做了独立于模型库的数值复核，不冒称独立人员评审。

## 运行命令

从生产目录运行纯读取的复现工具，使原模块的vn.py路径检查保持有效；输出绝对路径固定在本研究线。使用-B禁止在生产目录生成pycache。

```bash
/Users/bytedance/Desktop/person/vnpy_production_live/.py311/bin/python -B /Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_ai_score_attribution/tools/stage001_reproduce.py
```

以下两个命令从主工作区运行：

```bash
.py311/bin/python -B research/lines/futures_trend_ai_score_attribution/tools/stage001_report.py
.py311/bin/python -B research/lines/futures_trend_ai_score_attribution/tools/stage001_verify.py
```

## 输出文件

- report：`artifacts/stage001_20260731/report.md`。
- summary：`artifacts/stage001_20260731/reproduction_summary.json`。
- quality：`artifacts/stage001_20260731/verification.json`、`score_parity.csv`。
- 完整贡献：`feature_contributions_zh.csv`；完整系数：`model_coefficients_zh.csv`。
- 相邻排名差：`adjacent_rank_contributions.csv`；分组贡献：`factor_group_contributions.csv`。
- 可重算资产：`model_snapshot.json`、`training_samples.csv`、`product_scores_and_features.csv`、`formal_pool_snapshot.csv`。
- 图：`contribution_overview.png`、`selected_product_contributions.png`，已实际打开检查无裁切、遮挡。
- orders/daily：N/A；没有新委托、策略日权益或行情下载。

## 结论与后续

- 本期精确分数解释完成，决策`exact_current_score_reproduction_pass`。
- 最大价值是揭示评分混合了收益、规模/成本、风险尾部与零活动状态，不能简化成“近期表现越好越靠前”。
- 后续TODO：如要优化，另开预注册验证检验规模/成本代理和零值语义；本阶段不执行、不推荐基于单月贡献直接删因子或调权重。
- 当前生产选品和交易行为保持不变，不做正式发布或提交合并。

## 过拟合反思

- 运行前：否，只复现现有规则，不搜参数。
- 运行后：否，所有参数和输入冻结，精确复现后做加法解释，没有根据结果迭代alpha。
- 边界：本次不证明原模型没有过拟合，也不能从单月归因推出稳定因果。

## 继续价值反思

- 运行前：是，查清当期排名的真正来源。
- 运行后：是，解释层和输入语义审计有价值；当前任务已完成，进一步策略验证须另行冻结假设。

## 合入建议

- 已更新本线LINE.md，未修改其他研究线。
- registry.md留待统一合入时登记，遵循并行规则。
- 不追加根目录memory.md/back_log.md，也不修改Codex全局记忆。
