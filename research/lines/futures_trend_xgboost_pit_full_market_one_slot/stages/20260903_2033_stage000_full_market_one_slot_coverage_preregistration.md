# Stage000 全市场PIT单槽替换覆盖审计预注册

- line_id：`futures_trend_xgboost_pit_full_market_one_slot`
- 当前模式：day
- 记录时间：2026-09-03 20:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线与Stage001无标签数据覆盖合同；不是模型、标签或回测。
- 是否重要突破：否。
- 是否触发A/B：是，冻结未来A/C结构；本阶段不运行A/C。
- 用户授权：2026-09-03明确回复“授权”；授权范围只覆盖本Stage001无标签审计。

## 外部调研与判断

- XGBoost官方Learning-to-Rank说明LambdaMART依赖每个query内有可学习的标签差异；上一条物理持仓Ranker首折发生joint relevance退化，继续修同一排序目标没有价值：<https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html>。
- 中国商品期货横截面研究支持动量与carry具有经济含义，但它们只能作为事前特征假设，不能把历史赢家反推为候选：<https://www.sciencedirect.com/science/article/pii/S0927538X20301086>。
- 商品期货波动管理存在样本外失效证据，因此本线不做XGBoost账户波动开关：<https://strathprints.strath.ac.uk/82764/>。
- 我的判断：唯一仍值得验证的结构性差异，是把候选空间移出静态18，并把未来模型目标改为单槽账户动作。Stage001先验证这个候选空间是否在历史时点具备足够、无回填的数据覆盖。

## 已知本地证据

- Stage122发现2022亏损窗全市场强趋势`12`个、静态池强趋势`4`个，但该结果只是库存，不可按赢家扩池。
- Stage124的57品种单品种回放中全样本盈利`26`个、2022亏损窗盈利`10`个；Stage126同时确认35/57提前结束、54/57存在分钟缺口，因此这些结果不是上线证据。
- `futures_trend_full_market_ai_filter_002risk`已反证全市场score-only和veto/guard overlay；本线禁止复刻这些动作。
- 静态18内的108特征二分类、九特征账户标签、市场上下文Ranker、曲线双Ranker和物理持仓Ranker均已失败或闭线；本线禁止在这些冻结形状上救参。

## 冻结研究结构

- A：正式release的线上逻辑回归Top10 + 固定`fu.SHFE`，不改前9名、成本、保证金、整数手、相关性、最多4持仓和C9规则。
- B：未来才可能建立的全市场池外候选动作概率诊断；Stage001不存在B模型。
- C：仅在A-rank10具备同一PIT数据资格时，最多用一个静态18之外候选替换A-rank10；否则C=A。
- 未来标签方向：二分类账户动作，只有替换在冻结未来窗口中同时满足净收益增量`>0`和最大回撤改善`>0`才为1；不使用LambdaMART、不要求月内relevance等级。
- 未来模型输入原则：只允许事前冻结的价格动量、趋势路径效率、实现波动、成交量/持仓量、期限结构及其横截面变换；禁止产品ID、交易所ID、赢家名单、历史全样本产品PnL和结果后黑名单。
- Stage001通过不代表允许生成标签、实现XGBoost或回测；每一步都须新预注册和单独授权。

## Stage001冻结输入

1. 正式18品种月度全排名：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv`，SHA256=`b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`。
2. 全市场主力映射：`examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_main_contract_mapping_2010_2026_04.csv`，SHA256=`1fa32afab0bc9a490711aa66a716fa78fd52ebbb2c1680d77ce20eadcad617c2`。
3. 合约元数据：`examples/portfolio_backtesting/backtest_outputs/tqsdk_all_futures_contract_metadata.csv`，SHA256=`24a3573e847e024411b13a3a3b775791ded57563b0a68b717d1065078201635a`。
4. 日线数据库：`.vntrader/database.db`，SHA256=`7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a`，只读URI和`PRAGMA query_only=ON`。
5. 允许读取的正式排名列仅为`eval_date/product_vt_symbol/score_rank/score_type`；禁止读取任何收益、未来PnL、回撤、标签或封存holdout文件。

## Stage001冻结时间与PIT规则

- 评估月：正式全排名中`2022-01-28`至`2026-06-30`的54个月；`2026-07-31`因冻结数据库不能覆盖而事前排除。
- 信息截止：允许使用`date <= eval_date`；不得读取未来映射、未来行情、未来元数据快照或任何fallback。
- 市场范围：只允许`CZCE/DCE/GFEX/INE/SHFE`商品期货；CFFEX全部排除。
- 历史资格：截至eval_date至少有252个非空主力映射日；eval_date必须存在非空主力映射。
- 主力日线资格：最近252个映射日中有效close至少241天；eval_date本身必须有有效close；最近60个映射日中close、volume、open_interest同时为正的比例至少90%。
- 曲线资格：eval_date同日必须有至少2个可解析、到期月严格递增且close、volume、open_interest均为正的具体合约；不得使用合成连续合约或邻日回填。
- 元数据资格：产品连续合约`price_tick>0`且`volume_multiple>0`；仅为一手可执行性使用固定保守保证金率15%，不得把当前元数据时间戳或产品身份作为模型特征。
- 一手资格：`eval_date主力close * volume_multiple * 0.15 <= 150000`。
- 静态18：由54个月正式全排名的产品并集冻结，必须恰为18个；池外挑战者必须不属于该并集且不等于`fu.SHFE`。
- A-rank10资格：只有该月正式rank10也通过同一历史/日线/曲线/元数据/一手资格，该月才可成为未来单槽动作月；否则未来C必须等于A。

## Stage001硬门

1. 输入SHA在运行前后完全一致，数据库只读；输出采用临时目录原子发布，既有结果禁止覆盖。
2. 正式排名必须为54个月、每月18行、rank 1..18连续、静态并集18个。
3. 映射/行情读取未来行、fallback、CFFEX合格行、重复`eval_date+product`均为0。
4. 每个评估月至少30个全市场合格商品期货。
5. 至少36个月的A-rank10通过同一PIT资格。
6. 每个A-rank10合格月必须至少有10个池外挑战者；不得因不足而删除月份。
7. 标签读取、模型fit/predict、策略回测、CTP连接、订单API、生产文件写入计数全部为0。

通过决策：`stage001_full_market_coverage_pass_allow_feature_preregistration_only`。

失败决策：`stage001_full_market_coverage_fail_close_shape_no_labels`。任何硬门失败后，不得降低252/241/90%/2合约/30品种/36月/10挑战者门槛，不得按品种、月份、交易所或已知收益补洞；若未来获得全市场统一数据源，只能另立新版本合同。

## 预期输出

- `artifacts/stage001_full_market_coverage/coverage_by_eval_product.csv.gz`
- `artifacts/stage001_full_market_coverage/monthly_coverage.csv`
- `artifacts/stage001_full_market_coverage/rejected_rows.csv.gz`
- `artifacts/stage001_full_market_coverage/stage001_summary.json`
- `artifacts/stage001_full_market_coverage/report.md`
- `artifacts/stage001_full_market_coverage/artifact_manifest.json`

## 回测记录占位

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 过拟合反思

- 运行前判断：Stage001本身否；整个XGBoost研究目标为高风险。
- 原因：本阶段不读标签、不看收益，只检查事前冻结的数据可得性；但2022-2026历史已被多条研究线反复观察，未来不能再把这段数据当作独立效果证据。

## 继续价值反思

- 运行前判断：有，但仅限本次覆盖审计。
- 原因：它检验尚未被直接做过的“动态PIT全市场池外单槽动作”是否有数据基础；若覆盖门失败，当前形状不再值得继续。

