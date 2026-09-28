# Stage004 条件PIT冻结XGBoost融合预注册

- line_id：`futures_trend_ai_pit_scorer_rebuild`
- 记录时间：2026-09-02 12:59 CST
- 阶段性质：单一冻结XGBoost预测层A/B/C资格
- 是否重要突破：否；通过也只允许设计真实引擎候选
- 策略回测/CTP/订单：保持0
- 证据等级：`fixed_current_design_universe_only`

## 冻结输入

- Stage003 conditional samples SHA256=`22fc20b184f1f0e283d0bc2041a37d9bc778646c6fcaad662235c87f2e216cfc`。
- Stage003 fold audit SHA256=`92082f0791376e3b1df337e4b07a4bc7cb1ef0e0fd3c1672141e809e3e773c69`。
- Stage003 LR OOS predictions SHA256=`9ec713fd03d9f1131b22b5378a4b8feb9b1065660052cbeb427ab327b51ccce3`。
- Stage003 summary SHA256=`ea9766e9a2fa1856d1e178754350f7a805825dfb94ccb4c5758cced91d8cef83`。
- Stage003 manifest SHA256=`30ab79bd2373d0ad9c9e15ea1b0d013f657cd38b3474299146bb4b4140e40c59`。
- 旧daily SHA256=`9af514a3a5ab7ca4d982a31bd758522c32c4dec792f1b1819abb5462a391efcd`，仅用于同一未来60交易日路径回撤代理评估，不进入训练特征。

## 冻结模型与实验臂

- A：Stage003冻结逻辑回归概率，不重定义基线。
- B：单一`XGBClassifier`：`binary:logistic`、120树、depth2、learning_rate0.03、min_child_weight12、gamma0.10、subsample0.80、colsample_bytree0.60、alpha1、lambda10、hist、seed42、n_jobs1。
- C：每月A/B概率各自转横截面百分位后固定50/50平均；权重不得修改。
- B每fold独立训练两遍验证确定性；训练行、108特征、target、weight与Stage003完全一致。

## 收益与回撤代理

- 收益代理：每月所选Top10未来60交易日产品净利润合计。
- 回撤代理：对每月Top10的未来60交易日`net_pnl`按日聚合，计算累计路径相对历史高点的最小值；数值越接近0越好。
- 该回撤仍不是15万元账户真实最大回撤，因为未重放保证金、整数手、持仓竞争和复利；只作为进入真实引擎前的方向门。

## C相对A的全部效果门

1. 月均Rank IC严格提高。
2. Rank IC中位数不降低。
3. Top10月均未来净利润合计严格提高。
4. Top10月度未来净利润10%分位不降低。
5. Top10 target命中率不降低。
6. Top10月均未来路径最大回撤严格改善。
7. Top10未来路径最大回撤10%分位不降低。
8. 月度换入率不超过A的105%。
9. 四个OOS年度中Rank IC至少赢3年。
10. 最差年度Rank IC差不低于`-0.03`。

## 技术门与停止规则

- A预测必须与Stage003逐值一致；PIT、上市、完整标签、输入身份违规均为0。
- B重复预测与模型dump SHA必须一致，概率有限且在`[0,1]`。
- 全部技术门和10项C效果门都通过，才允许下一阶段构造同引擎候选排名；任一失败即关闭当前108特征/产品贡献标签/XGB参数/50-50融合形状。
- 失败后禁止扫描树深、树数、学习率、正则、采样率、融合权重、TopN、年份或品种。
- 不读取旧XGBoost sealed holdout，不运行策略回测。

## 运行前反思

- 是否过拟合：风险**高**，因为只有47个OOS月且108特征；控制方式是复用事前固定浅树参数、一次性A/B/C和严格年度/尾部门。
- 是否值得继续：**是，限本次**。LR接近随机可能意味着没有信号，也可能意味着关系非线性；一次冻结检验能区分，反复调参没有价值。

