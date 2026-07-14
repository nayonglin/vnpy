# AI 排名年度 Jackknife 资格线

- line_id: `futures_trend_ai_rank_year_jackknife_qualification`
- 创建时间: `2026-07-13 01:30 CST`
- 当前模式: `day`
- 资产/策略: 商品期货趋势 / 当前 C9 15w 全市场固定评分研究分支
- 当前状态: Stage001 资格审计已完成并关闭；年度 jackknife 共识换入跨期弱于换出，未形成策略候选
- 当前基准: `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 独立性: 只写本研究线目录；不改当前正式实盘、CTP、邮件、launchd、AI 月池或其他研究线

## 第一性问题

- 当前 full-market “AI” 不是可重新训练的黑箱模型，而是固定权重 PIT 横截面评分：全历史累计单品种策略 PnL `24%`，近126日收益 `20%`，近63日收益 `15%`，低近期亏损 `14%`，近期 Sharpe `10%`，低回撤 `7%`，活跃度 `6%`，旧市场特征 `4%`。
- 因此本线不做 model bootstrap。真正要回答的是：Top8 是否因累计收益中某一个已发生年份而改变；若删除任一过去完整年度后排名大幅漂移，原榜单可能在追逐历史赢家。
- 资格方法只扰动 `rank_all_cycle_profit`，其余 PIT 特征、固定权重、数据可用门与 Top8 不变；这能隔离全历史收益记忆的稳定性，不把所有特征同时改乱。

## 外部调研与判断

- Stability selection 说明对子样本扰动后的选择频率可用来审计结构稳定性，但其经典有限样本结论依赖 IID，不能直接外推到月度时序排名。
- 时间序列 bagging / moving-block bootstrap 可保留部分序列相关，却会引入块边界并在非平稳数据上改变依赖结构；本线不使用随机 bootstrap。
- 排名聚合研究支持简单 scoring/Borda 类平均名次作为透明共识，不需要再训练权重。
- 我的判断：采用 expanding-window `leave-one-completed-calendar-year-out` 是更保守、可复验的敏感性审计。它不是因果证明，也不保证组合回撤改善；只有换入相对换出在严格未来60交易日跨年稳定，才允许进入下一阶段四锚点 canary 预声明。

## Stage001 固定输入

- full-market eligible universe：`57` 品种，SHA `7d97dd4c112721a577eb89c4007606fc444fcc16173f1c11a9538a73490c2bac`。
- Stage124 单品种 C9 daily：`57` 文件、`73,251` 行，内容 manifest SHA `6827ebbae5fa395ab96f4b3d8d9f533210293fb082ebe6c95607ca400dcddb0d`。
- 旧 PIT 市场特征：SHA `fc0b62d42c0c8551b241bb8dabd15373fa3acec354c10cf8d72ef265b352c83b`。
- Stage167 日历源：SHA `72130cbb9260973bdfda6bf3119503a242db451516fbb7472a6165134ac379fd`。
- Stage001 v2 baseline feature panel：`4,446` 行、`78` 个 eval_date、`57` 品种，SHA `dccd393bed6509a42f8642445313432a00b656fd599ee491da08877c1c4a5efa`；只用于 baseline 重现与固定特征，不把其未来标签作为输入。

## Stage001 固定方法

- 评估月从 `2022-01` 起；每个 eval_date 的扰动集合为 baseline 加上逐个删除 `2020 -> eval_year-1` 的完整已发生自然年度。
- 只从 `cumulative_net_pnl_to_date` 扣除被删年度、重新计算当月横截面 `rank_all_cycle_profit`；其余排名、权重、history gate 与 score 公式不变。
- 每个扰动按 score 降序、product_vt_symbol 升序取固定 Top8；共识按所有扰动的平均 ordinal rank 升序、product_vt_symbol 升序取固定 Top8。
- 标签为 eval_date 后严格下一 `60` 个 global trade dates 的 Stage124 单品种 net PnL；产品不足完整60行则该月换入/换出比较不合格，不用较短窗口补齐。
- 月度比较只看等数量的 `consensus_only` 换入与 `baseline_only` 换出；同时输出原始60日 PnL edge 与当月完整产品横截面 future-PnL percentile edge。

## Stage001 硬门

- baseline Top8 必须逐月与冻结 panel 完全重现；输入 SHA、行数、唯一键、PIT 时间与60日标签边界必须全通过。
- 完整可比较月份至少 `42`，发生实际换仓月份至少 `24`，每个有效年份至少 `3` 个换仓月。
- 换入减换出：全期总 raw PnL `>0`、月度 raw PnL 中位 `>0`、月度 percentile edge 中位 `>0`。
- 有效年份中正 edge 年份至少 `4`、负 edge 年份为 `0`；`2022-2023` 与 `2024-2026` 两段总 edge 均 `>0`。
- 单一最好年份占全部正 edge 不得超过 `60%`。
- 所有硬门通过只允许 `ALLOW_STAGE002_FOUR_ANCHOR_CANARY_PREDECL_ONLY`；否则 `CLOSE_LINE_YEAR_JACKKNIFE_RANK_INELIGIBLE`。
- 两种结果都保持 `ready_for_backtest=false`、`ready_for_live=false`；Stage001 不跑资金曲线、不改月池。

## Stage001 结果

- 冻结源、57个 Stage124 daily、73,251行、4,446 base rows、54个资格月 baseline Top8 全部重现；variant 13,265行、future60 label 3,078行，omitted-year/PIT/重复键/换仓守恒错误均0。
- 完整比较月 `47>=42`，实际换仓月 `21<24`；每次只换1个 Top8 产品。
- 换入减换出 future60 raw edge 合计 `-54,520`，月度中位 `-1,550`，percentile edge 中位 `-0.0943396`。
- 年度 edge：2022 `-25,590`、2023 `-17,905`、2024 `-885`、2025 `-10,140`；early/late 为 `-43,495/-11,025`，有效年份正/负 `0/3`。
- gate `2/12` 通过、`10/12` 失败，decision `CLOSE_LINE_YEAR_JACKKNIFE_RANK_INELIGIBLE`；未运行回测，总交易0，ready_for_backtest/live=false。
- 独立 agent 全量终审 `P0/P1/P2/P3=0/0/3/2`，数字/语义置信度 `99%/97%`；重叠窗口、最新7月缺60日和inf展示等边界均不改变闭线，详见 `stages/20260713_0148_stage001_year_jackknife_closed.md`。

## 反过拟合边界

- 不扫 `24%` 权重、TopN、年度定义、平均名次方法、60日标签、年份门、正年份数或集中度阈值。
- 不根据 2022 结果删除产品、方向、月份或交易所，不换成随机 bootstrap、rolling block、median rank、Borda 分数或 score 均值救参。
- 不把资格标签写回评分，不以未来 PnL 选择删哪个年份；每个月所有过去完整年份都进入扰动集合。

## 当前 TODO

1. 本线关闭，不进入四锚点 canary、月池、资金曲线、A/B 或实盘。
2. 禁止修改24%权重、TopN、年度块、平均/中位名次、60日标签、年份门、产品、月份或交易所救参。
3. 后续只能另开真正新外生 PIT 信息或独立收益源研究线；不得把本线局部正月份包装成候选。


## 外部资料

- https://arxiv.org/abs/0809.2932
- https://papers.ssrn.com/sol3/papers.cfm?abstract_id=540262
- https://www.sciencedirect.com/science/article/pii/S037722171830081X
- https://ojs.aaai.org/index.php/AAAI/article/view/25685
