# Stage002：收益与路径回撤双目标XGBRanker资格赛

## 阶段信息

- 开始时间：2026-09-01 15:23 CST
- 是否重要突破版本：否，结构性资格实验
- 完成时间：2026-09-01 15:30 CST
- 状态：已完成，资格失败，不进入真引擎
- 线上版本：`ai_top10_plus_fu_official_live_v1`
- 冻结release：`m0004_20260831T112631+0800_2485073e9594`
- 目标：在严格时间外样本中同时提高Top10未来净利润并改善Top10未来聚合路径最大回撤；通过后才运行真实策略回测。

## Stage001证据与本次假设

- Stage001的B XGBoost总体略优但2024年失稳；C固定分类融合降低Top10未来净利润并恶化尾部。
- Stage001标签只回答未来60日净利润是否位于横截面上半区，没有训练模型关注未来路径回撤，也没有直接优化Top10排序。
- Stage002采用XGBoost官方Learning-to-Rank，把每个月18个品种作为一个`qid`组，直接学习多级相关性排序。

## 冻结标签

对每个品种月末，仅用月末之后的60个交易日：

1. `future_net_pnl_60d`：60日策略净利润合计，越高越好。
2. `future_max_drawdown_60d`：60日每日净利润累计曲线的最大回撤，越接近0越好。
3. 在当月18品种内分别转换为百分位。
4. `future_dual_utility_60d = 0.5 × pnl_percentile + 0.5 × drawdown_percentile`。
5. 按该综合值生成`0..17`整数相关性等级供`rank:ndcg`训练。

收益与回撤固定等权，不扫描权重。标签只用于历史训练与OOS评价，测试月标签不进入该月模型。

## 冻结实验臂

- A：线上同构`StandardScaler + LogisticRegression(C=0.20)`。
- B：固定浅树`XGBRanker(objective=rank:ndcg, eval_metric=ndcg@10)`，按月`qid`训练。
- C：A/B测试月内高分优先百分位各50%融合。
- TopN：10个模型品种；正式固定`fu.SHFE`为三臂共同项，不参与模型标签和资格差异。

## 时间与模型约束

- 与Stage001一致：最少24个训练月，测试日前保留至少92自然日标签隔离，预计49个逐月OOS测试月。
- XGBoost继续使用单一浅树、低学习率、行列采样、L1/L2正则和单线程确定性配置。
- Ranking固定使用`lambdarank_pair_method=topk`、`lambdarank_num_pair_per_sample=10`，不扫描objective、pair method或pair数量。

## 预声明资格门

B与C分别对A评估。候选只有同时满足以下全部条件才通过：

1. 输入身份、面板复现、未来路径计算、时间隔离和重复训练确定性全部通过；OOS测试月不少于45。
2. 月度双目标Rank IC均值严格高于A，中位数不低于A。
3. Top10月均未来净利润合计严格高于A。
4. Top10月度未来净利润合计10%分位不低于A。
5. Top10月均未来聚合路径最大回撤严格优于A，即更接近0。
6. Top10月度未来聚合路径最大回撤10%分位不低于A。
7. Top10月均换入率不超过A的105%。
8. 候选年度双目标Rank IC至少3年高于A，且最差年度差值不低于`-0.03`。

晋级顺序：C与B都通过时优先C；仅一个通过时使用该臂进入真实组合回测；两个都失败则停止Stage002，不跑回测。

## 后续真实回测门（仅资格通过后）

- A：当前线上AI Top10+固定fu。
- B/C：通过资格的Stage002月池+固定fu，其他策略逻辑、资金、手续费、滑点、保证金和回测区间与A完全一致。
- 全周期必须同时满足：总收益严格高于A、最大回撤严格优于A、Sharpe不低于A、滑点不超过A的105%、交易次数和broker约束不过门。
- 通过全周期后再做固定多周期/随机多周期；任何策略回测数据生成后立即拉独立reviewer。

## 变更与回测记录

- 新增参数：双目标标签、`rank:ndcg`、月度`qid`、固定Top10 pair构造。
- 修改参数：模型任务从二分类改为月度排序；不修改线上参数。
- 删除参数：资格候选不使用二分类概率阈值。
- 新增回测结果：无，预注册阶段。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：暂不适用，尚未运行策略回测。

## 过拟合与继续价值（运行前）

- 是否过拟合：风险是。新标签仍来自同一历史，且Stage001结果已经可见。
- 控制：结构性目标预注册；所有权重、模型参数、TopN和门槛在结果前固定；失败后不救参。
- 是否值得继续：是。当前分类目标没有表达回撤，月度排序任务与Top10选品及最终双目标更一致。

## 外部依据

- XGBoost Learning to Rank：https://github.com/dmlc/xgboost/blob/master/doc/tutorials/learning_to_rank.rst
- XGBoost ranking parameters：https://github.com/dmlc/xgboost/blob/master/doc/parameter.rst
- Machine Learning and the Implementable Efficient Frontier：https://academic.oup.com/rfs/advance-article/doi/10.1093/rfs/hhag022/8524346

## 资格赛结果

- OOS：49个月，2022-04至2026-04，共882条预测。
- 数据：1368行、76个月、每月18品种、108项特征。
- 最小实际标签隔离：92自然日。
- 未来60日净利润独立路径复算最大误差：`2.91e-11`。
- XGBRanker重复训练预测最大误差：`0`；源文件运行前后未变化。

| 指标 | A 逻辑回归 | B XGBRanker | C 50/50融合 |
| --- | ---: | ---: | ---: |
| 双目标Rank IC均值 | 0.057798 | 0.094831 | 0.087715 |
| 双目标Rank IC中位数 | 0.147191 | 0.055886 | 0.032495 |
| Top10月均未来净利润 | 40,787.76 | 56,310.20 | 55,028.06 |
| Top10未来净利润10%分位 | -131,975 | -110,776 | -119,838 |
| Top10月均未来聚合最大回撤 | -169,782.04 | -158,430.10 | -161,254.08 |
| Top10未来聚合最大回撤10%分位 | -271,486 | -224,084 | -236,105 |
| Top10月均换入率 | 23.7500% | 27.0833% | 26.2500% |

### 门槛结论

- B失败：Rank IC中位数非劣、换入率不超过A的105%、最差年度Rank IC差值三项。
- C失败：Rank IC中位数非劣、换入率不超过A的105%两项。
- B、C均显著改善收益和回撤代理，但没有通过全部预声明稳定性/成本门。
- 决策：`stage002_dual_objective_ranker_fail_stop_no_backtest`。

## 回测记录要求对应

- 新增/修改/删除回测结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：不适用。
- 原因：Stage002是预测资格赛，未运行策略真引擎。
- 独立reviewer：不适用，尚无策略回测数据。

## 过拟合与继续价值（运行后）

- 是否过拟合：没有通过事后调参制造晋级，但月度中位数偏低和换入率偏高说明模型仍含时序噪声。
- 是否值得继续：原始B/C形状不值得直接回测；有价值继续一次固定的时间确认，因为它直接处理失败的稳定性与交易成本机制，不改变模型和标签。
- 禁止：不改双目标权重、rank objective、树参数、TopN、年份或品种。

## 产物

- `artifacts/stage002_dual_objective_ranker/summary.json`
- `artifacts/stage002_dual_objective_ranker/report.md`
- `artifacts/stage002_dual_objective_ranker/oos_predictions.csv`
- `artifacts/stage002_dual_objective_ranker/monthly_metrics.csv`
- `artifacts/stage002_dual_objective_ranker/yearly_metrics.csv`
- `artifacts/stage002_dual_objective_ranker/dual_objective_labels.csv`
- `artifacts/stage002_dual_objective_ranker/xgboost_ranker_feature_importance.csv`
