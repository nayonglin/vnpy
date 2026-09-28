# Stage002 LR base-margin残差development OOS预注册

- line_id：`futures_trend_lr_xgboost_base_margin_model_ranked`
- 记录时间：2026-09-04 15:54 CST
- 阶段性质：首次且唯一标签访问、模型训练和产品贡献路径development OOS预注册。
- 前置决策：`stage001_model_ranked_boundary_contract_pass_allow_stage002_preregistration_only`。
- 是否重要突破：否；尚未读取标签或训练。
- 用户目标：提高全周期收益、降低最大回撤。
- 用户授权边界：用户已要求继续XGBoost研究并授权数据源重建；执行前仍需生成绑定本文件、实现和测试SHA的本线授权receipt，runner只接受一次性`--authorized-development-oos`。

## 研究问题

在不改变正式108项特征、正式二分类目标、样本权重和Top10发布语义的条件下，以每折正式LR raw log-odds作为XGBoost `base_margin`，浅树残差能否相对严格PIT LR同时：

1. 改善development OOS概率/排序；
2. 提高所选Top10未来60交易日产品净贡献；
3. 改善所选Top10未来60交易日聚合贡献路径最大回撤；
4. 在删除最佳月份和逐年检查后仍成立。

## 数据与PIT

- 输入身份沿用Stage001全部冻结m0005/Stage183/正式代码/旧特征面板，并新增Stage001 summary、fold plan、manifest及本阶段代码/receipt SHA。
- 只使用Stage001冻结的`50`个fold；每折测试一个月、18个产品，共`900`个development OOS预测行。
- 训练日期直接读取Stage001 `fold_plan.csv`的`train_eval_dates`；每个训练月的60交易日label end必须`<= test_eval_date`。
- 标签只来自冻结正式函数：`target_future_top_half_60d`；权重只用`sample_weight_future_rank_60d`。
- 全部`2022-03..2026-05`测试月标记为development；sealed holdout行数固定为`0`，不得把历史尾段改名为holdout。
- 固定`fu.SHFE`不在18品种模型面板中，不产生训练行、预测行、标签或模型效果行。

## 冻结A/B

### A：严格PIT正式LR

- 特征：正式108项。
- `StandardScaler`仅拟合本折训练行。
- `LogisticRegression(C=0.20, solver='lbfgs', max_iter=3000, random_state=42)`。
- 使用正式样本权重。

### B：LR raw margin上的XGBoost残差

- 先拟合A；训练集与测试集分别取A的`decision_function`作为raw `base_margin`。
- XGBoost输入仍为相同108项原始特征，不增加scaler、身份特征或特征筛选。
- 固定参数：`objective='binary:logistic'`、`eval_metric='logloss'`、`n_estimators=32`、`max_depth=1`、`learning_rate=0.03`、`min_child_weight=20`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1.0`、`reg_lambda=20.0`、`max_delta_step=1.0`、`tree_method='hist'`、`random_state=42`、`n_jobs=1`。
- 每折B独立重复fit一次；两次预测最大绝对差必须为0。
- 不训练直接XGBoost臂，不做LR/XGBoost平均，不用early stopping或任何参数扫描。

## 产品贡献路径代理

- 对每个测试月，A/B分别按分数降序、`product_vt_symbol`升序稳定选Top10。
- 每个产品未来路径固定为`eval_date`之后恰好60个全局交易日的正式`net_pnl`；禁止使用当日或第61日。
- 月度Top10路径是10个所选产品逐日`net_pnl`之和。
- 月度未来贡献是60日Top10路径之和。
- 月度最大回撤从0起点计算：对`[0, cumulative_path]`取`min(equity - cummax(equity))`。
- `return_delta = B贡献 - A贡献`。
- `drawdown_improvement = B最大回撤 - A最大回撤`；正数表示B回撤较浅。
- 这是产品贡献代理，不含固定fu、账户持仓互斥、资金、整数手、相关性和执行成本；不得称期末权益、总收益或真实组合回撤。

## 技术硬门

1. 输入/receipt/实现SHA全部一致；Stage001 manifest复核有效；最终输出不存在并原子发布。
2. `50` folds、`900`预测行、每折18产品、108特征；LR fits=`50`、XGBoost fits=`100`、scaler fits=`50`。
3. PIT违规行/折=`0/0`；sealed holdout行=`0`；固定fu模型行=`0`。
4. 全部预测、raw margin、correction和路径指标有限；每月A/B分数横截面标准差均大于0。
5. B重复预测最大绝对差=`0`；XGBoost split nodes总数`>0`，有split的fold=`50`。
6. correction绝对值中位数`>1e-6`且`<=0.5`，最大值`<=2.0`，防止退化或完全覆盖LR先验。

## 效果硬门

以下门全部通过，才允许独立review；任一失败即闭线：

1. B相对A加权logloss严格下降；B月均Spearman Rank IC严格提高。
2. A/B Top10不同的月份至少`8`个，覆盖至少`3`个年份。
3. changed months的`return_delta`合计`>0`，`drawdown_improvement`合计`>0`。
4. 删除单个最佳return-delta月后，剩余return delta合计仍`>0`。
5. 删除单个最佳drawdown-improvement月后，剩余drawdown improvement合计仍`>0`。
6. changed months中`return_delta>0 && drawdown_improvement>0`比例`>=0.55`。
7. 每个发生变化的年份，年度return delta与年度drawdown improvement都必须严格`>0`。

通过决策：`stage002_base_margin_residual_development_oos_pass_require_independent_review_before_true_engine`。

失败决策：`stage002_base_margin_residual_development_oos_fail_close_no_true_engine`。

## 禁止救援

- 不得改树参数、LR参数、特征、权重、TopN、标签、fold、日期、年份、品种、路径定义、门槛或排序tie-break。
- 不得删除失败月/年、只看changed子集之外的有利口径、换成直接XGB、增加blend权重或重跑第二次效果实验。
- Stage002失败后不运行真实C9、holdout、shadow或生产接入。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：是，高风险。
- 原因：即使按真实label-end walk-forward，全部月份都已在多轮研究中被观察；固定模型和门只能降低研究者自由度，不能制造独立holdout。

## 继续价值反思

- 运行前判断：有，限唯一Stage002。
- 原因：`base_margin`残差是尚未训练的独立架构，且A/B只改变一个结构因素；预先要求收益和回撤代理同时改善，可以快速证伪。
