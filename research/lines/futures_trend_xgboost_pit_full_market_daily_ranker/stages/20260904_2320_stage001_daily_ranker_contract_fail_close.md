# Stage001 PIT全市场日级排序无标签合同失败闭线

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker`
- 记录时间：2026-09-04 23:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 是否重要突破：否。
- 阶段性质：唯一Stage001无标签合同执行；未读取未来close、未计算未来收益或标签值、未训练、未预测、未回测。
- 决策：`stage001_daily_ranker_contract_fail_close_no_labels`。

## 本次版本改动

- 新增纯函数合同：实际合约内收益、PIT产品历史、基础qid资格、17项原始特征、19项横截面模型特征、固定合约标签日期计划、正式评分身份和purged fold计划。
- 新增Stage001 runner：9项冻结输入的SHA/size/mtime前后绑定、源manifest复验、随机临时目录、原子发布、10项输出manifest和离线verify-only。
- 新增参数：`capital=150000`、`margin_ratio=0.15`、收益窗口有效比例`90%`、标签entry/exit偏移`1/21`个全局交易日、最低成熟训练qid `252`。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。

## 执行与产物

- final：`artifacts/stage001_daily_ranker_contract/`；已有final禁止覆盖，当前未重跑。
- manifest：10项产物、9项输入，`--verify-only`结果`verified=true`、错误0。
- 回归：本线及两个前置线共`60 passed`；本线`22 passed`；两个Python模块编译通过。
- 输入前后SHA、size和mtime完全一致；源manifest与正式rank10身份均通过。

## 无标签结果

- 基础qid/行：`1,067/57,528`，组宽`49/53/61`，日期`2022-01-28..2026-06-30`。
- 标签计划qid/行：`1,046/52,484`，组宽`30/50/60`；拒绝`5,044`行。
- 正式评分：48个月、48个formal rank10、1,771个池外挑战者，最少挑战者34。
- fold：37折，36折effect-evaluable、1折inference-only；训练qid最小/最大`261/1,045`，首末折`2023-03-31/2026-06-30`。
- 17项原始特征和19项模型特征均无意外NaN/inf；每项连续模型特征都有`1,067`个非零横截面qid；来源日期越界0、未来特征行0。
- open-interest ratio缺失`80`行，精确命中冻结值。
- volume ratio缺失实际为`460`行，不等于冻结值`420`，因此feature gate失败；其余五个门全部通过。

## 失败根因

- volume正值覆盖不足：20日窗`273`行，60日窗`420`行。
- 两个失败集合并非包含关系：20日only `40`行、60日only `187`行、两窗均失败`233`行，并集为`460`行。
- 冻结公式要求20日和60日窗同时达到90%，任一失败都应令ratio缺失；所以实现的`460`符合公式。
- Stage000A把60日窗失败数`420`误写成ratio缺失总数，预注册硬门因此少计40行。该错误与标签、收益、模型效果无关，但冻结硬门不得在执行后修改。

## 零副作用计数

- future close value reads：0。
- future return calculations：0。
- label value reads：0。
- model fit/predict：`0/0`。
- strategy backtest：0。
- CTP连接、订单API、生产写入：`0/0/0`。
- sealed holdout：0。

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行后判断：否。
- 原因：全程没有标签值、未来收益、预测或回测结果；失败由两个事前成交量覆盖集合的并集计数揭示，不涉及按效果改特征或样本。

## 继续价值反思

- 本线继续价值：否；冻结Stage001已失败，禁止重跑、改420硬门、删40行、补值、缩窗或进入Stage002。
- 日级排序结构的独立继续价值：有，但只能另立全新预注册线，事前把同一未改公式的缺失并集冻结为460，并复用本次已验证的其余合同；仍不得读取标签或训练，直到新无标签合同完整通过。
