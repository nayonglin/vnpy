# Stage000 全市场PIT单槽LR/XGBoost融合模型合同

- line_id：`futures_trend_xgboost_pit_full_market_one_slot_ensemble`
- 当前模式：day
- 记录时间：2026-09-04 14:41 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线、模型设计和Stage001无标签特征资格预注册。
- 是否重要突破：否；数据资格已恢复，但模型效果尚未产生。
- 是否触发A/B：是；冻结未来A/B/C，Stage001不运行模型或回测。
- 用户授权：用户在获知“另立模型合同预注册线，冻结LR A、XGBoost B/融合C、walk-forward和收益/回撤双门”后明确回复“好的，你继续吧”。本次先执行最小Stage001无标签审计。

## 外部调研与判断

- XGBoost 3.2参数文档说明 `binary:logistic` 输出二分类概率；更深的树更易过拟合，较大的 `min_child_weight`、`gamma` 和正则更保守：<https://xgboost.readthedocs.io/en/release_3.2.0/parameter.html>。
- XGBoost上游 `XGBClassifier` 默认使用 `binary:logistic`，本仓安装版本为`3.2.0`：<https://github.com/dmlc/xgboost/blob/master/python-package/xgboost/sklearn.py>。
- scikit-learn时间序列切分文档明确普通随机交叉验证会产生未来训练、过去测试问题，并支持在训练尾部设置gap：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。
- Moskowitz、Ooi、Pedersen的期货时间序列动量研究支持以过去收益方向定义未来持有期趋势代理，同时指出价格变化与期限结构roll成分都可能贡献：<https://fairmodel.econ.yale.edu/ec439/mosk.pdf>。
- 我的判断：直接为1,771个池外候选运行完整账户反事实成本过高，且旧静态18账户标签家族已经失败；先用月度持有期固定方向趋势代理筛选模型，再由真实C9组合A/C否决代理错配，是当前最小且可证伪的路线。

## 已知本地证据与禁止复刻

- `futures_trend_ai_xgboost_ensemble` Stage017已关闭“九项正式策略历史特征 + 账户边际双回归头”家族；禁止换scaler、树参数或阈值救援。
- `futures_trend_xgboost_pit_curve_account_labels` Stage006已关闭“六项曲线差 + 双XGBRanker + 严格双头selector”形状；禁止复用其标签和selector。
- `futures_trend_xgboost_pit_market_context_after_listing`已关闭原六项市场上下文Ranker；禁止照搬。
- 新路线的结构差异只来自两个事前事实：候选空间扩展到严格PIT池外全市场；标签改为下一月固定方向趋势路径的联合收益/回撤胜负。
- 不允许产品ID、交易所ID、赢家名单、历史全样本产品PnL、黑名单、已知月份或未来标签驱动特征选择。

## 方案比较

1. 全候选真实账户反事实：标签最接近目标，但约1,771个候选任务，成本、运行身份和异常审计复杂度过高；当前不选。
2. 下一月固定方向趋势代理，再过真实C9 A/C：成本低、经济机制清晰、可严格PIT；本线采用。
3. 复用旧静态18标签或旧XGBoost产物：数据空间和失败家族均不匹配；明确拒绝。

## 冻结输入身份

1. Stage002源manifest：`research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/artifacts/stage002_endofday_source_rebuild/artifact_manifest.json`，SHA256=`e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a`。
2. 归一化日线：`normalised_daily_bars.csv.gz`，SHA256=`f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
3. PIT主力映射：`pit_main_contract_mapping.csv.gz`，SHA256=`1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d`。
4. 截止日合约目录：`asof_contract_catalog.csv.gz`，SHA256=`c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc`。
5. 产品元数据：`invariant_product_metadata.csv`，SHA256=`23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174`。
6. 覆盖面板：`coverage_by_eval_product.csv.gz`，SHA256=`6b8a55f44aa9422653fd01eea667fcede59bedab9b2ef8e6cceba31e636cb30d`。
7. 月度覆盖：`monthly_coverage.csv`，SHA256=`dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047`。
8. Stage002 summary：`stage002_summary.json`，SHA256=`67dcdb174bf7e253e100138eff1ec0b644c6a7cc68c0806f71aff10c66f00939`。
9. 正式18品种全排名：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv`，SHA256=`b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`。

## 冻结特征

每个action-ready月只保留正式rank10锚点和严格池外候选。日收益使用当日主力具体合约相对其自身上一交易日close的log return；换主力时仍使用新主力合约的前一交易日close，避免把跨合约价差当收益。固定14项产品原始特征：

1. `momentum_21/63/126/252`：对应尾窗有效主力日log return之和，按窗口长度/有效天数缩放。
2. `trend_efficiency_63/126`：尾窗累计log return绝对值除以绝对日收益之和。
3. `realized_vol_21/63`：有效日log return样本标准差乘`sqrt(252)`。
4. `volume_ratio_20_60`：正成交量20日均值/60日均值的log。
5. `open_interest_ratio_20_60`：正持仓量20日均值/60日均值的log。
6. `front_next_basis_annualized`：eval_date最近两个有效到期月log价差按月份间隔年化。
7. `full_curve_backwardation_slope`：eval_date全部有效曲线log价格对到期月线性斜率取负并年化。
8. `volume_hhi/open_interest_hhi`：eval_date曲线成交量和持仓量份额平方和。

每个21/63/126/252日收益窗口至少90%的同合约日收益必须有限；20/60日成交量和持仓量窗口也分别至少90%为正。任何不足均为Stage001特征资格失败，不允许填0、前向填充或缩短窗口。

模型行使用14项“当月action set内百分位 - rank10百分位”差值，并增加两个不含身份的当月环境项：`market_median_abs_momentum_126`、`market_median_realized_vol_63`，共16项。锚点14项差值必须精确为0；不得基于标签选择或删除特征。

## 冻结标签与PIT折叠

- Stage001只生成标签计划，不计算或读取标签值。
- 对每个action-ready eval_date，持有窗口固定为 `eval_date < date <= next_formal_eval_date`；最后一个月没有next date，仅作inference plan。
- 产品方向固定为eval_date时 `sign(momentum_126)`；方向为0时代理日收益为0，不按未来方向重定向。
- 产品窗口代理收益为固定方向乘主力同合约日log return的累计值；代理最大回撤由该累计路径计算。
- 候选标签相对正式rank10：`return_delta > 0`且`drawdown_improvement > 0`时`joint_win=1`，否则0；不使用未来最佳方向、产品赢家名单或账户标签。
- 扩展窗测试：测试月必须是action-ready月；训练只允许使用 `label_end_date < test_eval_date` 的action-ready标签月，至少24个训练月。按当前冻结月历应形成23个active folds，首月`2024-06-28`，末月`2026-06-30`；其中前22折有成熟测试标签，可进入代理效果统计，`2026-06-30`仅为inference-only折。
- 2022-01至2026-06全部标为development；sealed holdout行数固定为0，不得将历史尾段改名为holdout。

## 冻结模型与研究臂

- A：正式线上逻辑回归Top10 + 固定fu，不替换。
- B：`StandardScaler`仅拟合训练行；`LogisticRegression(C=1.0, penalty='l2', solver='lbfgs', max_iter=2000, random_state=42)`；选择概率最高候选，且概率必须严格大于0.5，否则B=A。
- XGBoost组件：`XGBClassifier(objective='binary:logistic', eval_metric='logloss', n_estimators=64, max_depth=2, learning_rate=0.03, min_child_weight=20, gamma=0.1, subsample=0.8, colsample_bytree=0.8, reg_alpha=1.0, reg_lambda=10.0, tree_method='hist', random_state=42, n_jobs=1)`。
- C：同折LR和XGBoost候选概率固定50/50平均；选择融合概率最高候选，且融合概率严格大于0.5，否则C=A。
- 不允许参数扫描、early stopping、标签驱动特征选择、阈值调整、月份/品种删除或失败后重跑。

## Stage001无标签硬门

1. 冻结输入运行前后SHA一致，输出只写本线临时目录并原子发布，既有final禁止覆盖。
2. action-ready月精确48，特征面板精确1,819行，其中rank10锚点48行、池外候选1,771行。
3. 14项原始特征与16项模型特征全部有限；未来行情/映射使用、fallback、标签读取、fit/predict、策略回测、CTP、订单和生产写入全部为0。
4. 14项pairwise差值的锚点值精确为0；每项至少在44/48个月对候选具有非零横截面标准差。
5. 标签计划精确47个可成熟月份、1,729个候选标签任务和1个最新inference-only月；不包含标签值列。
6. 折叠计划精确23个active folds，其中22个effect-evaluable、1个最新inference-only；每折训练label end严格早于测试月，训练月数24..46，未来标签行与sealed holdout均为0。

通过决策：`stage001_full_market_feature_contract_pass_allow_label_proxy_preregistration_only`。

失败决策：`stage001_full_market_feature_contract_fail_close_no_labels`。任一硬门失败后关闭本线，不删特征、月份、品种或降低门槛救援。

## Stage002效果门预声明

以下门在Stage001通过后仍须另发绑定实现SHA与单次授权的Stage002预注册，不能由本文件直接启动：

1. 技术门全部通过、重复预测逐字节一致、PIT违规0、XGBoost总split nodes大于0。
2. C至少替换6个月且覆盖至少2个年份。
3. C替换月代理收益增量合计`>0`、代理回撤改善合计`>0`。
4. 删除单个最佳收益月后，收益增量合计仍`>0`；删除单个最佳回撤月后，回撤改善合计仍`>0`。
5. C替换月`joint_win`比例`>=0.55`。
6. 有替换的每个年份，年度收益增量和回撤改善均不得为负。
7. C相对B的收益增量合计与回撤改善合计均不得更差；否则XGBoost没有证明增量价值。

通过也只允许真实C9 A/C预注册；代理指标不是期末权益、总收益或组合最大回撤。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：Stage001否；整体模型实验风险高。
- 原因：Stage001不读标签，特征、标签语义、折叠、模型和未来效果门全部先冻结；但历史期已被观察，不能称独立样本外。

## 继续价值反思

- 运行前判断：有，先限Stage001。
- 原因：统一源已解除候选覆盖阻断，16项低维、无身份特征是否能在全部48个action月稳定生成，是进入任何标签工作的必要条件。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记Stage000和Stage001边界。
- 是否更新 `research/registry.md`：Stage001形成结论后统一登记。
- 是否追加根目录 `memory.md/back_log.md`：Stage001无回测，不追加。
