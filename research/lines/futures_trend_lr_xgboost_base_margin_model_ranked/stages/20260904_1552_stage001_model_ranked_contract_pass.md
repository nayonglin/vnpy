# Stage001 正式模型排名层无标签合同通过

- line_id：`futures_trend_lr_xgboost_base_margin_model_ranked`
- 记录时间：2026-09-04 15:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：唯一冻结无标签模型层/发布层边界、因果特征与PIT折叠审计。
- 是否重要突破：否；只取得模型实验入口，没有收益证据。
- 是否触发独立reviewer：否；未产生回测数据。

## 变更

- 新增runner：`tools/stage001_model_ranked_contract.py`，SHA256=`b05799b8f0c8001f8719f1de7ef0790e1806913d7467a8404a8ecbd306de38f8`。
- 新增11项测试：10+1角色拆分、固定fu空特征/空模型rank、policy门、逐值门、PIT门和禁止读取前一final。
- 新增参数：正式模型排名数`10`、固定产品`fu.SHFE`、总发布数`11`；其余窗口、容差和折叠参数不变。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。

## 结果

- 当前身份：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`，指针与manifest一致。
- policy：`ranked=10`、`fixed=fu.SHFE`、`total=11`。
- 训练面板：`77`个月、`1,386`行、每月`18`品种、`108`项特征、非有限单元`0`。
- 历史逐值：`76`个月、`1,368`行、最大误差`1.4551915228366852e-11 <= 1e-10`。
- 最新发布池：总`11`行、model-ranked=`10`、fixed-fu=`1`；model-ranked完整特征行`10`，含固定fu行`0`。
- 固定fu：产品身份匹配；108项非空特征单元`0`；非空`model_ai_rank`行`0`。
- 最新10个模型行逐值：`10`行，最大误差`1.8189894035458565e-12 <= 1e-10`。
- label-end：`77`行、缺失`0`；PIT active/effect folds=`50/50`、训练月`24..74`、违规行/折=`0/0`。
- 前一闭线final读取`0`；输入身份不匹配`0`。
- 禁止列、标签值、fit/predict、策略回测、CTP、订单和生产写入全部`0`。

## 决策

- `stage001_model_ranked_boundary_contract_pass_allow_stage002_preregistration_only`。
- 只允许编写Stage002预注册；不得把本阶段称为XGBoost有效、收益提升或回撤下降。
- Stage002必须保持A=严格PIT正式LR、B=LR raw margin上的固定浅树残差，固定fu不参与模型。

## 回测指标

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 产物

- `artifacts/stage001_model_ranked_contract/summary.json`，SHA256=`63c63d729d693ac7cecb44ff3cefac2100c10dea7a2a4a13a2b3d550fffa0aa1`。
- `feature_contract.json`，SHA256=`64909eeca4d84348c9adea29062430d8010b0e194ab87edd37169752facfb182`。
- `fold_plan.csv`，SHA256=`a14fbde27943e1c73eaa8c1e2ea14834e212616e82fe024ba193697369a25e6c`。
- `input_identities.json`，SHA256=`44d10699ca26393479fb7e7ba05ba03e75595b2dbf2d18454c26dd334a541993`。
- `report.md`，SHA256=`ce8328109c058a552225b472e46453283a6d52f8c8c7b1d29545f0e9cce55586`。
- manifest复核：`valid=true`、errors=`0`。

## 过拟合反思

- 运行后判断：否。
- 原因：未读取标签或模型效果；10+1边界由运行前冻结的正式policy与runner决定，所有结构门逐项通过。

## 继续价值反思

- 当前判断：有，可以进入Stage002预注册。
- 原因：合法模型域、发布域、特征逐值和PIT折叠已经闭合；`base_margin`残差仍是未观察的新模型机制。

## 后续规划

- Stage002先冻结标签访问、A/B实现SHA、XGBoost参数、重复性门、产品路径收益/回撤代理和晋级门，再执行一次development OOS。
- Stage002产出未来损益评价后必须拉独立reviewer；未review不得进入真实C9引擎。
- 本阶段不追加根目录`memory.md`或`back_log.md`。
