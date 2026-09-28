# Stage001 PIT全市场日级XGBoost排序无标签合同预注册

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker`
- 记录时间：2026-09-04 22:55 CST
- 阶段性质：冻结无标签特征、同合约标签计划与purged walk-forward合同；本阶段禁止标签值、fit与回测。
- 前置决策：`stage000a_daily_query_feasibility_pass_allow_stage001_preregistration_only`。
- 用户授权边界：后续研究操作默认授权；本阶段只允许本线数据产物，生产、CTP和订单硬门不变。

## 冻结输入

- source manifest SHA256：`e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a`。
- `normalised_daily_bars.csv.gz`：`f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
- `pit_main_contract_mapping.csv.gz`：`1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d`。
- `asof_contract_catalog.csv.gz`：`c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc`。
- `invariant_product_metadata.csv`：`23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174`。
- `coverage_by_eval_product.csv.gz` / `monthly_coverage.csv`：`6b8a55f44aa9422653fd01eea667fcede59bedab9b2ef8e6cceba31e636cb30d` / `dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047`。
- 正式全排名：`b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`。
- 全部输入在运行前后复验size、mtime与SHA；既有final存在即失败，输出必须原子发布并生成manifest。

## 身份与query合同

- 只接受非空且源内resolved的`main_contract_vt`；13,787条未解析映射计入审计但不得补值。
- 基础资格保持上游语义：过去252个映射日、至少241个有限同实际合约日收益、主力close与元数据有效、保守一手保证金`<=150,000`、当日有效曲线合约`>=2`、CFFEX为0。
- 基础特征面板必须精确`1,067`个query、`57,528`行，日期`2022-01-28..2026-06-30`，组宽最小/中位/最大`49/53/61`。
- query内按`product_vt_symbol`排序；模型、标签和后续qid不得使用产品ID或交易所ID作为特征。

## 冻结原始特征

同实际主力合约收益先在每个具体合约内部计算，再按PIT映射拼接产品历史，禁止把换月价差当收益。原始数值特征固定17项：

1. `momentum_21/63/126/252`：窗口内有效同合约log return之和，按窗口长度/有效数缩放。
2. `trend_efficiency_21/63/126`：累计log return绝对值除以绝对日收益和。
3. `realized_vol_21/63`：样本标准差乘`sqrt(252)`。
4. `downside_vol_63`：负日收益的平方均值平方根乘`sqrt(252)`；无负收益时为0。
5. `max_drawdown_63`：从0起点的63日累计log return路径最大回撤，保留非正值。
6. `volume_ratio_20_60`与`open_interest_ratio_20_60`：正值短窗均值/长窗均值取log。
7. `front_next_basis_annualized`与`full_curve_backwardation_slope`：当日有效曲线的近次近年化log价差及全曲线log价格斜率取负年化。
8. `volume_hhi`与`open_interest_hhi`：当日有效曲线成交量/持仓量份额平方和。

- 收益窗口至少90%有限；任一收益、趋势、波动或曲线特征缺失即硬失败。
- 成交量/持仓量20/60日不足90%时，对应ratio保留NaN，不删行、不前向填充；冻结预期缺失行为为volume ratio 420行、open-interest ratio 80行。
- 每个query内对17项原始特征使用`rank(method='average', pct=True)`；ratio缺失排名统一设为中性`0.5`，并新增`volume_ratio_missing/open_interest_ratio_missing`两项0/1标志。
- 模型特征精确19项；不得加入产品、交易所、板块、年份、月份、正式分数、未来值或Stage000A失败位置。
- 每项连续模型特征必须在至少1,000/1,067个query中横截面标准差大于0；两个缺失标志必须与原始缺失逐行一致。

## 标签计划合同

- Stage001只写计划，不读取entry/exit close值，不计算未来收益或relevance。
- 每行冻结query日PIT主力实际合约；entry date为下一全局交易日，exit date为query后的第21个全局交易日，对应20个close-to-close持有区间。
- 只用日期、行存在与合约到期日判断计划可用；entry/exit必须为同一实际合约，且到期日不早于exit date。
- 计划必须精确`1,046`个query、`52,484`行，组宽最小/中位/最大`30/50/60`；5,044个不可用基础行保留在特征面板但不得伪造标签计划。
- Stage002若获授权，才允许读取计划行的entry/exit close并在query内把20日log return按稳定横截面五分位离散为0..4 relevance；Stage001禁止生成这些列或值。

## 正式评分与fold计划

- 正式action-ready月精确48个；每月基础评分横截面50..61个产品、formal rank10精确1个、池外挑战者至少34个。
- 前47个月formal rank10和至少10个挑战者具有20日计划；`2026-06-30`固定为inference-only，不读取截止日后数据。
- 训练只允许label end严格早于测试月的计划query；最低成熟训练query为252。
- active folds必须精确37折：首折`2023-03-31`有261个训练query，末折`2026-06-30`有1,045个训练query；36折effect-evaluable、最新1折inference-only。
- Stage001的fold plan不得包含标签值、模型参数输出、预测或效果指标。

## 未来模型形状预声明

- A：正式线上LR Top10 + 固定`fu.SHFE`，不变。
- C：`XGBRanker(objective='rank:ndcg', eval_metric='ndcg@10')`；每个日级query为qid，relevance为0..4；正式月度测试日最多用一个池外最高分候选挑战rank10。
- Stage002模型参数、替换门、重复fit、效果门和授权SHA必须另行预注册；本文件不授权训练。

## Stage001硬门

1. 所有输入身份、源manifest和输出manifest有效；输入运行前后不变。
2. query、基础行、组宽、日期范围精确命中`1,067/57,528/49-53-61/2022-01-28..2026-06-30`。
3. 原始17项、模型19项、来源最大日期和质量标志合同全部通过；除两项冻结ratio缺失外无NaN/inf。
4. 标签计划精确`1,046/52,484/30-50-60`，同合约、日期顺序、到期和行存在全部通过；标签值列0。
5. 正式48个月身份、formal rank10、挑战者与37折计划精确通过；未来训练query、sealed holdout均为0。
6. future close value reads、future return calculations、label values、fit、predict、strategy backtest、CTP、订单API和生产写入全部为0。

通过：`stage001_daily_ranker_contract_pass_allow_stage002_preregistration_only`。

失败：`stage001_daily_ranker_contract_fail_close_no_labels`。任一门失败即闭线，不删query、产品、月份、特征，不改20日、252训练query、缺失协议或门槛救援。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage001均不适用。

## 过拟合反思

- 运行前判断：Stage001否；后续训练高风险。
- 原因：本阶段只固定因果特征和标签计划，Stage000A也没有收益信息；但未来任何看标签/效果后改特征、qid、持有期或模型都会过拟合。

## 继续价值反思

- 运行前判断：有，限本次Stage001无标签合同。
- 原因：大日级query与原生LTR是独立结构增量；先验证所有因果、质量和耐久门，可以在标签前低成本证伪。
