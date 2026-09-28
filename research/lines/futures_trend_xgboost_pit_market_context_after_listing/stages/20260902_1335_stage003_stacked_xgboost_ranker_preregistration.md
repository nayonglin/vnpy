# Stage003 历史OOS堆叠月分组XGBoost Ranker预注册

- line_id：`futures_trend_xgboost_pit_market_context_after_listing`
- 预注册时间：2026-09-02 13:35 CST
- 是否重要突破：否；唯一一次固定Ranker预测资格
- 策略回测/CTP/订单：`0/0/0`

## 单句假设

在历史OOS逻辑回归已经确定Top9与rank10+候选集后，月分组XGBoost Ranker可利用六项独立市场组合上下文，在不改Top9的条件下选出比A rank10未来策略利润更高、同时未来市场组合路径回撤更浅的第十席。

## 证据边界

- 全部月份都已属于反复观察过的development历史，本阶段只能称为历史OOS堆叠资格，不能称为独立holdout或生产收益证据。
- 不读取`futures_trend_ai_xgboost_ensemble`的sealed holdout文件；但不能因为文件未读就把2025月份重新命名为未见数据。
- 本阶段只产生预测和未来60日代理比较；不运行策略引擎，不产生账户期末权益、收益率、最大回撤或Sharpe。

## 冻结输入

- Stage002特征面板：`market_context_feature_panel.csv`，SHA256=`3d77c8d1d4d9f95612ca4d9c4e0db1df5bc88a58eb8b0a5968a1eaf6bc7fcaf0`。
- Stage002 manifest：运行前冻结SHA256=`ef60982092f42e127533bc82cf462f68ec1aa0cefd7ed294381c899a850656a5`。
- Stage001完整A排序：`ranked_a_panel.csv`，SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`。
- Stage003条件PIT样本：`conditional_pit_samples.csv`，SHA256=`22fc20b184f1f0e283d0bc2041a37d9bc778646c6fcaad662235c87f2e216cfc`；只读取`eval_date/product_vt_symbol/future_net_pnl_60d/future_label_end_date/full_horizon_label`。
- PIT产品日收益：`product_daily_returns.csv.gz`，SHA256=`ff31d1bdf3ea3d8a309060243d165e82b5e7a0a8e26d26ba17f4a0ec926056fa`；只用于测试后的未来60日市场路径代理。

## 冻结标签与walk-forward

- 特征面板每月rank10和挑战者构成一个查询组，按`eval_date/a_rank/product_vt_symbol`稳定排序。
- 监督标签只用`future_net_pnl_60d`：在每个查询组内做升序dense rank并减1，得到非负整数relevance；未来利润越高，relevance越高；相同利润保持相同等级。
- 对每个潜在测试月`t`，训练组只允许满足`train_eval_date < t`且该组全部`future_label_end_date < t`的更早历史OOS月份。
- 至少18个训练月且120个训练行后才允许测试；不足月份C机械等于A，不删除也不回填。
- 每个测试月独立冷拟合；不使用测试月做early stopping、模型选择、特征选择或参数调整。

## 冻结模型

- `XGBRanker(objective='rank:ndcg', eval_metric='ndcg@1')`。
- `n_estimators=64`、`max_depth=2`、`learning_rate=0.03`。
- `min_child_weight=1`使用Ranker默认量级；`gamma=0`。
- `subsample=0.8`、`colsample_bytree=1.0`、`reg_alpha=1`、`reg_lambda=10`。
- `lambdarank_pair_method='topk'`、`lambdarank_num_pair_per_sample=3`、`ndcg_exp_gain=True`。
- `tree_method='hist'`、`random_state=42`、`n_jobs=1`、verbosity 0。
- 不标准化；只输入Stage002六项特征。每个测试月双拟合，预测逐值和模型dump SHA必须一致。

## 冻结A/B/C

- A：Stage003条件PIT LR的Top9 + 原rank10。
- B：Ranker在当月rank10及完整挑战者中按分数降序、A rank升序、产品代码升序选第一名。
- C：Top9完全不动，仅用B所选替换第十席；若该月无资格预测或B仍选rank10，则C=A。
- 不设置分数阈值、置信度阈值或融合权重，不扫描候选范围。

## 未来60日代理

- 收益代理：从条件PIT样本汇总Top9与A/B第十席的`future_net_pnl_60d`；C-A差只来自第十席。
- 市场路径回撤代理：对测试月后严格大于`eval_date`的前60个全局收益日，计算A/C等权Top10日收益、复利财富路径与最大回撤；要求全部产品60日完整。
- 上述市场回撤不是策略账户最大回撤，只是预测层风险方向门。

## 预声明技术门

- 特征/标签连接精确328行、43月，完整标签与有限值100%；标签结束日按组唯一。
- 产生不少于18个测试月，覆盖2024和2025且每年不少于6月；每个测试月至少18个训练月、120行。
- 所有训练标签结束日严格早于测试月；qid连续、组大小6至9；测试行和分数有限。
- 每个测试月模型至少一个split node、月内分数至少两个唯一值；双拟合预测差0且dump SHA一致。
- 未来60日市场路径完整，PIT收益源自身selection/return日期违规、fallback、跨合约均为0。

## 预声明效果门

- B与A不同的替换月不少于4。
- B分数月均Rank IC严格高于A概率，Rank IC中位数不低于A。
- C月均未来策略净利润合计严格高于A；月度差中位数不小于0；C的10%分位不低于A。
- C-A月度利润差为正比例不少于55%；2024和2025年度累计差均不小于0；剔除最佳单月后累计差仍严格大于0。
- C未来市场路径回撤的月均值和10%分位均严格优于A；2024和2025年度月均回撤差均不小于0。
- 技术门和效果门必须全部通过，才决策`stage003_stacked_ranker_pass_allow_engine_preregistration`；任一失败即`stage003_stacked_ranker_fail_stop_no_backtest`。

## 禁止项

- 禁止在结果后调整树数、深度、学习率、`min_child_weight`、pair数、训练月数、特征、标签、阈值、候选rank、年份或产品。
- 禁止把预测代理写成账户收益/回撤；禁止直接运行真实引擎、holdout、生产、CTP或订单。

## 运行前反思

- 是否过拟合：风险**高**，因为development历史被多次观察；本次固定一次、严格标签成熟和历史OOS堆叠可降低但不能消除该风险。
- 是否值得继续：**是**；Stage002已证明六项特征跨年非退化，Ranker是检验其是否具有组内排序价值的最小模型实验。

