# Stage003 条件PIT逻辑回归特征合同修复预注册

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 记录时间：2026-09-02 12:54 CST
- 阶段性质：Stage002实现缺陷的单点修复
- 是否重要突破：否
- 策略回测/CTP/订单：保持0

## 唯一允许修改

- 特征名必须在合并任何PIT标签字段之前，从SHA冻结的旧samples原始列中发现并冻结。
- 同时增加防御门：任何以`future_`、`target_`、`sample_weight_`、`pit_future_`、`pit_target_`开头的字段都不得进入特征；发现结果必须恰好等于Stage002预注册的108项原始历史滚动特征。

除此之外，Stage002的样本过滤、上市资格、target/weight、9个calendar fold、严格`label_end < test_start`、最小train/test行、LR参数、双跑确定性和全部技术门保持不变。不得依据Stage002无效的AUC/Rank IC修改任何特征、参数、窗口或门槛。

## 冻结失败证据

- Stage002 summary SHA256=`2be847d9b0df073d5492656d2a134ac8a03e3828f7f0478d262bc901151b3411`。
- Stage002 manifest SHA256=`20ccebe644f955015326faefa1fa572fcefa8bdded039a2ad983d29e8aa50589`。
- Stage002实际特征数111；非法字段固定为：`pit_future_rank_centered_60d`、`pit_future_rank_pct_60d`、`pit_target_future_top_half_60d`。

## 决策门

- 108项原始特征必须与旧samples源码合同逐项一致；非法字段数0。
- Stage002其余技术门全部重放，不降低阈值。
- 通过只允许冻结Stage004 XGBoost预测层A/B/C设计，不允许策略回测或读取旧XGBoost sealed holdout。

## 运行前反思

- 是否过拟合：**否**。修复只排除名称和来源明确的标签字段，是数据隔离纠错，不依据无效效果挑选特征。
- 是否值得继续：**是**。这是让同构LR基线具备最低可信度的必要修复；若仍失败则停止本数据管线。

