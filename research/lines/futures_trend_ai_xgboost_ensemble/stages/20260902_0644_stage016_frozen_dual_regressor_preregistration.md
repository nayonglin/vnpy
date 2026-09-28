# Stage016：双XGBoost账户边际选择器冻结预注册

## 阶段信息

- 预注册时间：2026-09-02 06:44 CST。
- 研究线：`futures_trend_ai_xgboost_ensemble`。
- 当前线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`。
- 本文件与同目录机器合同写入时，尚未读取Stage015标签数据行或任何标签分布；此前只读取CSV表头、文件SHA、任务/账务审计字段和独立review结论。
- 本阶段允许读取development标签并训练模型；禁止读取或生成sealed holdout标签、修改生产目录、连接CTP、调用订单API或根据结果修改本合同。

## 外部调研与判断

- XGBoost官方文档支持用`XGBRegressor`训练连续目标，并以浅树、正则化、行列采样控制复杂度；本阶段固定单线程与随机种子，不做超参搜索。
- scikit-learn时间序列切分原则要求训练样本严格早于测试样本；本阶段进一步按真实`next_eval_date <= test eval_date`过滤，防止尚未结束的账户标签进入训练。
- XGBoost Learning-to-Rank适合单一相关性排序目标，但本问题要求收益和回撤两个目标同时成立；因此继续使用两个独立回归头，不把两个目标事后压成一个可调权重效用。
- 判断：逻辑回归和XGBoost可以同时接入，但不是把两者概率随意相加。A继续使用线上逻辑回归正式排序；C只让XGBoost竞争第10席，Top9和固定fu保持正式逻辑回归体系。
- 参考：<https://xgboost.readthedocs.io/en/release_3.2.0/python/python_api.html#xgboost.XGBRegressor>、<https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html>、<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。

## 冻结输入

- Stage014特征面板：`prelabel_feature_panel.csv`，SHA256 `e8272438cd69fe784b236ac91763f4ec0da71d2b711cd38b576c5e66d237f5fd`。
- Stage014特征合同：`feature_contract.json`，SHA256 `5c160660682d196613aab4467e7d97e2869ae12825cd2a179c91dce1266aeb0e`。
- Stage015 development标签：`development_labels.csv`，SHA256 `39e969783adc2ac54f771cf03e685a4cec45ce09adeb2d1eefc6ca54ef2cbce2`。
- Stage015 reconciliation：`reconciliation.csv`，SHA256 `d595547fa81906093c0fd530acbfa5d0f2b7c3fe489987efa79da304b977eb95`。
- Stage015完整独立复核：`20260902_stage015_full_development_labels_independent_review.md`，SHA256 `1ea63653ec6aa6cbb01bdcd794866506c9e4d880d099dddf54edb1fde34e3cf6`。
- 输入连接键固定为`eval_date,next_eval_date,product_vt_symbol,score_rank/candidate_rank`，必须一对一连接成39月×9候选=`351`行；rank10的五项相对标签必须为0。
- 任何SHA、行数、日期、rank、连接键、reconciliation误差或holdout边界异常均fail-closed，不能训练。

## 冻结特征与模型

- 九项特征严格沿用Stage014，顺序不变；不做标签后特征选择、缩放、填补或新增交互，缺失概率由XGBoost原生missing路径处理。
- 两个`XGBRegressor`分别预测`return_delta`与`drawdown_improvement`。
- 固定参数：`objective=reg:squarederror`、`eval_metric=rmse`、`n_estimators=64`、`max_depth=2`、`learning_rate=0.03`、`min_child_weight=12`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1`、`reg_lambda=10`、`tree_method=hist`、`random_state=42`、`n_jobs=1`。
- 运行版本冻结为Python `3.11.15`、numpy `2.4.4`、pandas `2.3.3`、scikit-learn `1.8.0`、xgboost `3.2.0`。
- 每折每个头以同一输入重复拟合两次；预测最大绝对差必须`<=1e-12`，原始UBJ模型SHA也必须一致，否则视为非确定性失败。

## 冻结PIT切分

- development月份固定为`2022-04-29 -> 2025-06-30`共39个月；sealed holdout `2025-07-31 -> 2026-06-30`不得进入本阶段。
- 最少训练月份固定为24；测试月固定为第25至第39个development月，即`2024-04-30 -> 2025-06-30`共15折。
- 某训练月只有在`train eval_date < test eval_date`且该月所有标签的`next_eval_date <= test eval_date`时才允许进入。
- 预期每折训练月份数依次为`24..38`，每月9行；测试月每月9行。任何PIT违规、缺月、少rank或重复键都停止。

## 冻结A/B/C选择器

- A：线上逻辑回归正式rank10，不训练新逻辑回归。
- 每个测试月内，两个预测分别按升序`average percentile rank`转成`(0,1]`分位，数值越大越好；`dual_head_score=(return_percentile+drawdown_percentile)/2`，两头固定等权且不训练权重。
- B：在rank10..18中选择`dual_head_score`最高者。并列时依次选择预测收益增量更高、预测回撤改善更高、正式rank更低、`product_vt_symbol`字典序更小者。
- C：复用B选中的同一个候选；仅当该候选`predicted_return_delta > 0`且`predicted_drawdown_improvement > 0`时采用B，否则保持A的rank10。B若本身选中rank10，C与A相同。
- 禁止按真实标签修改候选、融合权重、阈值、tie-break、确认月数或TopN。

## 冻结development资格门

技术门全部必须通过：

1. 所有输入身份、351行一对一连接、rank10零基准、reconciliation和sealed holdout隔离通过。
2. 15折、每折9个测试候选、训练月数`24..38`精确成立，PIT违规为0。
3. 30个折内模型的重复拟合预测与UBJ SHA均确定。
4. A每月严格为正式rank10；C只有在同一B候选两个原始预测都大于0时才允许偏离A。

候选C还必须同时通过以下预声明效果门：

1. 相对A实际替换月份数`>=4`，且替换覆盖2024和2025两个日历年。
2. 15个月`return_delta`合计严格`>0`。
3. 15个月`drawdown_improvement`合计严格`>0`。
4. 从收益增量序列剔除最好一个月后，合计仍严格`>0`。
5. 从回撤改善序列剔除最好一个月后，合计仍严格`>0`。
6. 2024和2025各自的收益增量合计都`>=0`。
7. 2024和2025各自的回撤改善合计都`>=0`。
8. 实际替换月份中，真实`return_delta > 0`且真实`drawdown_improvement > 0`的联合命中率`>=50%`。

这些是账户边际标签代理门，不是组合收益/回撤门。不得把15个月标签增量合计称为策略总收益或最大回撤。

## 决策与后续边界

- 技术门失败：`stage016_contract_or_pit_invalid_stop`，修复只能针对实现错误；若合同或输入身份需要变化，必须新阶段重审。
- 技术门通过但任一效果门失败：`stage016_development_oos_proxy_fail_stop_no_holdout`，停止当前九特征/固定浅树/双头门控形状，不调参救援、不读取holdout。
- 全部门通过：`stage016_development_oos_proxy_pass_allow_true_engine_ac`，只允许把15个月OOS选择冻结成eligibility，进入一次development真实账户引擎A/C验证；仍不允许读取holdout或上线。
- 真实引擎阶段必须计算统一全周期A/C的期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率，并做独立review。只有真实引擎同时改善收益和最大回撤且通过稳健性门，才允许另立一次sealed holdout阶段。

## 反思

- 运行前过拟合判断：风险高，但当前动作本身不是结果后过拟合。原因是仅15个development OOS月；控制手段是标签读取前冻结全部规则、单一模型参数、双目标同时过门、剔除最好月份和分年度非负。
- 是否值得继续：是。Stage015已解决旧代理与真实账户错位；Stage016是检验九项PIT特征是否能学习账户边际价值的最低自由度实验。若失败，继续扫树参数、阈值、年份、品种或rank将没有价值并构成过拟合。
