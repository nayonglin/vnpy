# Stage000 PIT全市场日级XGBoost横截面排序设计

- line_id：`futures_trend_xgboost_pit_full_market_daily_ranker`
- 记录时间：2026-09-04 22:47 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线设计；未读取未来收益、未训练、未回测。
- 是否重要突破：否。
- 是否触发A/B：是；只设计未来A/C，当前不运行任何模型。
- 用户授权：后续研究操作默认授权；生产、CTP和订单硬门不变。

## 外部调研与判断

- XGBoost 3.2官方learning-to-rank文档要求样本按`qid`排序，并说明`rank:ndcg`使用LambdaMART直接优化组内排序；这比先做点式分类再排序更贴近选品：`https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html`。
- Poh等人的cross-sectional LTR研究指出，pairwise/listwise结构可优于regress-then-rank，但其证据来自更大的日级横截面，不支持在小月度样本上继续加树：`https://arxiv.org/abs/2012.07149`。
- 新近公开的中国商品因子统一对照中，XGBoost 5bps成本后年化收益约`-1.53%`、Rank IC约`-0.0025`、日均换手约`20.44%`，而简单线性与图模型表现不同；该仓库仅两次提交且主要是README，不能当作可复验收益证据，但足以作为“传统因子XGBoost不应被预设有效”的反例：`https://github.com/LiuFanyou/ML-Commodity-Factor-China`。
- 我的判断：XGBoost仍值得做的最后一个低自由度结构不是继续调月度树，而是扩大到严格PIT日级query并使用原生排序目标；若这一结构也不能在标签前形成足够宽且稳定的数据合同，应暂停XGBoost方向。

## 方案比较

1. 日级全市场XGBRanker：推荐。使用大量时间有序query学习组内排序，月度正式评估日才形成候选动作；样本结构与此前月度残差线不同。
2. 月度XGBoost继续调参：拒绝。ALFRED、base-margin、双Ranker和单槽特征线已给出退化或效果失败证据，继续属于救参。
3. GNN/HCGNN：暂缓。它利用商品关系图，机制上可能更适合跨品种信息，但超出当前XGBoost目标，参数和工程自由度也明显更高。

## 冻结上游身份

- source manifest：`research/lines/futures_trend_xgboost_pit_full_market_source_rebuild/artifacts/stage002_endofday_source_rebuild/artifact_manifest.json`，SHA256 `e3894cd20114182e9b3a9e986ed5e0310fe264de06368b5efe1b5efb6903681a`。
- 日线：`normalised_daily_bars.csv.gz`，SHA256 `f2cf98dbfde2e18031697d598c3147c0ee8f15d3feb6ab935b92bc44a919ece4`。
- PIT主力映射：`pit_main_contract_mapping.csv.gz`，SHA256 `1b9059e42161a71aaacd7d6367cbe4c7cd95eb944a1f463baf360aa038fec34d`。
- 截止日合约目录：`asof_contract_catalog.csv.gz`，SHA256 `c733e5d85bab4349efb9bd25e2afdd689562718ffd608bff9a4f11964ab13bfc`。
- 产品元数据：`invariant_product_metadata.csv`，SHA256 `23141510dc4b82f397db07f61d5bfce0cfe0621858f135f49c3044360dd46174`。
- 月度覆盖：`coverage_by_eval_product.csv.gz` / `monthly_coverage.csv`，SHA256 `6b8a55f44aa9422653fd01eea667fcede59bedab9b2ef8e6cceba31e636cb30d` / `dbd394954d92ef041dcc00f88c6ed90df62e7b2b3578fb6cabaafb848d1c2047`。
- 正式全排名：`research/lines/futures_trend_ai_xgboost_ensemble/artifacts/stage009_formal_full_ranking_recovery/formal_full_ranking.csv`，SHA256 `b2cb417b6c57a7679ae43a1e564c1e79683ca9644b3434cb6a3bfc9e039fcfc0`。

## Stage000A无标签探针

- 只读取冻结日线、PIT映射、目录、元数据、月度覆盖和正式排名中身份列。
- 候选query日期先取满足252日历史后的全部映射交易日；禁止根据未来收益或模型效果选日期。
- 每个query按当日可交易商品横截面组织；CFFEX、元数据无效、主力映射缺失、当日无有效主力close或曲线不足2个有效合约的产品在身份层拒绝。
- 探针只统计query数量、每组品种数、主力实际合约连续性、可形成20交易日同合约持有计划的比例，以及候选基础特征的缺失结构。
- 不读取未来close值，不计算收益、不生成相关性/IC、不拟合模型、不运行回测。
- Stage000A结果只用于冻结Stage001的特征、缺失协议、qid、20日标签计划、purge和最低覆盖门；不得根据任何收益结果调整。

## 预期模型边界

- A：当前正式月度逻辑回归Top10 + 固定`fu.SHFE`，不变。
- C：未来日级`XGBRanker(objective='rank:ndcg')`只在正式月度评估日对合格全市场横截面打分；最多用一个池外候选挑战rank10。
- 标签计划：信号日冻结主力实际合约，未来拟使用下一交易日close到第21个交易日close的20日同合约收益，在query内离散为0..4相关性等级；Stage000/001均不读取这些价格值。
- walk-forward：测试点只取正式action-ready月；训练query的label end必须严格早于测试日，并预留20交易日purge；全部历史只称development。
- 真实引擎、账户收益、组合最大回撤、成本、整数手与相关性只能在代理门通过后的独立阶段验证。

## 禁止项

- 不复活或修改`futures_trend_xgboost_pit_full_market_one_slot_ensemble`；不为已知`ZC/wr`两行降低旧20日成交量门。
- 不扫描持有期、qid频率、特征、树参数、替换阈值、年份或品种；不使用产品ID/交易所ID/赢家名单作为模型特征。
- 不把公开项目README中的收益数字当作本地有效性证据。
- Stage001未通过前，不读取标签、训练、回测、连接CTP、调用订单API或写生产。

## 回测记录占位

- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：Stage000均不适用。

## 过拟合反思

- 运行前判断：Stage000否；未来模型高风险。
- 原因：当前只冻结数据组织与验证顺序；真正风险在于全历史已被观察，后续任何看标签或效果后改变结构都会过拟合。

## 继续价值反思

- 运行前判断：有，先限Stage000A无标签可行性。
- 原因：日级大横截面和原生LTR是此前未执行的结构性差异；若无标签探针不能形成稳定query与同合约标签计划，应立即停止，不为XGBoost制造实验。
