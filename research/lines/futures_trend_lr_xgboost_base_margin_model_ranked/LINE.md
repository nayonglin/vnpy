# 正式模型排名层LR-XGBoost残差线

- line_id：`futures_trend_lr_xgboost_base_margin_model_ranked`
- 研究对象：正式18品种LR排名层的XGBoost `base_margin`残差修正；固定`fu.SHFE`属于发布层卫星，不参与模型训练和打分。
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`；正式C9/15w与执行规则均不变。
- 上游事实：正式policy冻结`10`个模型排名席位、固定`fu.SHFE`和总发布`11`席位；前一研究线因把11个发布行误当11个模型行而在无标签门失败，未查看任何效果。
- 当前状态：Stage002唯一冻结development OOS已完成并失败闭线；仅33/50折产生split，Top10只变化5个月/2年，leave-best收益和2025年度收益均为负。独立review为`PASS`，只认可fail-close；不进入true engine。
- 证据边界：全部历史均为已观察development，sealed holdout为0；本次是未来60交易日产品贡献路径代理，不是真实组合回测。一次性nonce和副作用字段没有耐久运行遥测，只能由正常入口与静态调用链支持。
- 隔离边界：只写本线；前一闭线代码只按冻结SHA只读复用，禁止修改旧线、生产、CTP或订单。

## 冻结研究臂

- A：每折正式`StandardScaler + LogisticRegression(C=0.20)`。
- B：以A的`decision_function`为训练和预测`base_margin`，固定浅层XGBoost只学习残差。
- 固定fu永远在模型排名完成后追加；A/B都只决定18品种中的Top10。

## 阶段

- Stage000：`stages/20260904_1547_stage000_model_ranked_boundary_design.md`。
- Stage001：`stages/20260904_1552_stage001_model_ranked_contract_pass.md`；决策`stage001_model_ranked_boundary_contract_pass_allow_stage002_preregistration_only`。
- Stage002：`stages/20260904_1609_stage002_base_margin_development_oos_fail_close.md`；决策`stage002_base_margin_residual_development_oos_fail_close_no_true_engine`。

## Stage001结论

- policy精确`ranked=10/fixed=fu.SHFE/total=11`；前一final读取`0`，全部输入与只读工具运行前后SHA一致。
- 正式训练面板`77`个月/`1,386`行/每月`18`品种/`108`项有限特征；旧`76`个月/`1,368`行最大误差`1.4551915228366852e-11`。
- 最新池`11`行中`10`行model-ranked完整，模型特征最大误差`1.8189894035458565e-12`；固定fu恰好1行，模型特征非空单元0、模型rank非空行0。
- label-end`77`行/缺失0；PIT active/effect folds=`50/50`、训练月`24..74`、违规行/折=`0/0`。
- 标签值、fit/predict、回测、CTP、订单和生产写入均为0。通过只允许Stage002预注册，不代表XGBoost有效。

## Stage002结论

- 50折/900 OOS行/108特征；PIT违规0，固定fu模型行0；LR/scaler/XGBoost拟合按控制流为`50/50/100`。
- 加权logloss从`0.76290805`降至`0.76197569`，月均Rank IC从`-0.02269769`升至`-0.01897414`，但只改变5个月/2年。
- changed months产品贡献代理`+2,170`、回撤改善代理`+73,920`；leave-best收益`-46,670`，2025年度收益`-20,550`。
- 失败门为`xgboost_non_degenerate`、`minimum_action_coverage`、`leave_best_robustness`、`yearly_robustness`。
- 独立review `P0/P1=0/0`、`P2/P3=1/1`并`PASS`认可fail-close；P2是缺少耐久运行遥测，P3是预注册起始月文字误写。
- 当前108特征/二分类标签/LR base-margin浅树残差形状永久关闭，禁止调参、改门、删月/年、真实引擎、holdout、shadow或正式接入。

## 过拟合反思

- 当前判断：是，高风险且结果不稳健。
- 原因：全部历史已观察、sealed holdout为0；只变化5个月/2年，剔除最佳月和2025年度收益均为负，不能证明穿越周期。

## 继续价值反思

- 当前判断：当前模型形状无继续价值。
- 原因：模型质量只有微小改善，17个fold无split，选择变化不足且收益依赖单月；在同一信息集上调参只会提高过拟合风险。未来只有新增独立经济信息或真正未见数据才值得另立研究线。
