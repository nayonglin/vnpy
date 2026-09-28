# Stage002 PIT全曲线特征预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/标签前特征冻结
- 记录时间：2026-09-02 14:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage001通过后的特征合同
- 是否重要突破：否
- 是否触发A/B：是；不授权策略回测

## 外部调研与判断

- Gorton、Hayashi、Rouwenhorst以近远月价格和交割期限定义年化basis，说明期限结构是库存状态的价格代理：<https://www.nber.org/papers/w13249>。
- Erb、Harvey提示期限结构与权重共同影响商品组合，不能把单一carry方向规则直接视为稳健alpha：<https://www.nber.org/papers/w11222>。
- 我的判断：使用整条合约链的无阈值连续描述量，比复活旧Stage073的顺价/逆价过滤更符合当前问题；但它仍是同源数据，必须用直接账户标签和严格OOS判断增量。

## 冻结样本

- 输入只读Stage001的797行A排序与7,615行合格具体合约快照；不再读取SQLite，不读取未来标签。
- 只输出每月`a_rank>=10`的候选组：rank10为A锚点，rank11及以后为挑战者；预期47月、374行、47个锚点、327个挑战者。
- 每个产品的六项原始曲线描述量在`eval_date`同日计算；模型输入统一减去当月rank10对应值。

## 冻结8项模型特征

1. `formal_probability_delta_vs_rank10`：条件PIT逻辑回归概率减rank10概率。
2. `formal_rank_distance`：`a_rank - 10`。
3. `front_next_basis_annualized_delta_vs_rank10`：`log(front_close/next_close) * 365 / 交割月日差`的相对值。
4. `full_curve_backwardation_slope_delta_vs_rank10`：对全部合格合约以交割日差为横轴、`log(close)`为纵轴做无权重线性拟合，取`-365 * slope`后减rank10。
5. `full_curve_fit_rmse_delta_vs_rank10`：上述线性拟合的log价格残差RMSE减rank10。
6. `open_interest_hhi_delta_vs_rank10`：合约OI份额平方和减rank10。
7. `volume_hhi_delta_vs_rank10`：合约成交量份额平方和减rank10。
8. `oi_weighted_maturity_days_delta_vs_rank10`：OI加权交割日差减rank10。

## 明确禁止

- 不加入carry正负、分位、month-gap、品种、交易所、年份、月份、旧Stage073方向命中或阈值字段。
- 不加入历史策略收益、未来单品种收益、账户回放、标签任务状态、sealed holdout或标签派生统计。
- 不依据特征与未来收益/回撤相关性删特征、翻转符号或构造交互；Stage002只审计有限性和非退化。

## 技术门

1. Stage001快照、覆盖、summary和manifest SHA逐项绑定且运行前后不变。
2. 原始描述量797行全部有限；每条曲线至少3个合约且交割日差严格递增。
3. 候选矩阵恰47月/374行/47锚点/327挑战者，每月rank10及后续排名连续。
4. rank10的8项特征必须按同一公式得到精确0，不允许特殊填值。
5. 8项特征在挑战者上均非退化；六项曲线差值在8个`window_id`中均至少出现一个非零值。
6. 双跑逐值一致，标签列和标签值读取0，训练0，策略回测0。
7. 通过决策固定为`stage002_curve_features_pass_ready_for_account_label_contract`；失败固定为`stage002_curve_features_fail_stop_no_labels`。

## 回测/归因参数

- 数据区间：`2022-01-28`至`2025-11-28`。
- 账户规模：不适用，未运行账户。
- 成本口径：不适用，未回测。
- 样本过滤：只按A排序角色取rank10及以后，不按效果删行。
- 策略/归因口径：同日全曲线连续特征，仅做标签前数据质量检查。

## 结果

- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：0。
- 胜率：不适用。
- 其他关键指标：待Stage002运行。

## 结论

- 本阶段结论：允许按TDD实现并运行标签前特征矩阵；不授权读取标签或训练模型。
- 是否进入下一步：是。
- 下一步：冻结产物后与账户边际标签适配审计合并决策。

## 过拟合反思

- 运行前判断：否，但风险高于全新信息源。
- 运行后判断：待运行。
- 原因：特征在标签前冻结且无阈值；同源Stage073结果已知，因此禁止结果后改符号、删字段或加阈值。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：待运行。
- 原因：Stage001已证明完整覆盖；非退化门可以低成本判断是否值得进入昂贵账户标签阶段。

## 合入建议

- 是否更新本线`LINE.md`：是，追加冻结合同。
- 是否更新`research/registry.md`：Stage002出结果后更新。
- 是否追加根目录`memory.md/back_log.md`：否；没有回测。
