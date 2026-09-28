# Stage002 LR base-margin残差development OOS失败闭线

- line_id：`futures_trend_lr_xgboost_base_margin_model_ranked`
- 当前模式：冻结单次development OOS A/B；只评估正式18品种模型排名层，不含固定fu发布卫星。
- 记录时间：2026-09-04 16:09 CST；独立复核完成于16:20 CST。
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：首次标签访问、模型拟合及未来60交易日产品贡献路径代理评估；不是真实策略引擎回测。
- 是否重要突破：否；结果失败并关闭当前模型形状。
- 是否触发A/B：是；A为严格PIT正式LR，B为LR raw margin上的浅层XGBoost残差，仅属研究A/B。

## 外部调研与判断

- 参考资料：XGBoost官方`base_margin`/intercept文档`https://xgboost.readthedocs.io/en/stable/tutorials/intercept.html`、prediction文档`https://xgboost.readthedocs.io/en/stable/prediction.html`、learning-to-rank文档`https://xgboost.readthedocs.io/en/release_3.2.0/tutorials/learning_to_rank.html`。
- 我的判断：`base_margin`在语义上适合让树模型只学习LR剩余非线性；但架构合理不等于存在可交易增量，必须由冻结PIT效果门证伪。

## 本次变更

- 新增脚本：`tools/stage002_base_margin_development_oos.py`。
- 新增测试：`tests/test_stage002_base_margin_development_oos.py`。
- 新增授权：`stages/20260904_stage002_execution_authorization.json`，绑定19项输入/实现SHA，允许正常入口单次运行。
- 修改脚本：无；授权后未修改任何绑定实现或输入。
- 删除脚本：无。
- 新增参数：`n_estimators=32`、`max_depth=1`、`learning_rate=0.03`、`min_child_weight=20`、`gamma=0.1`、`subsample=0.8`、`colsample_bytree=0.8`、`reg_alpha=1.0`、`reg_lambda=20.0`、`max_delta_step=1.0`、`tree_method=hist`、`random_state=42`、`n_jobs=1`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：训练月按折从`2020-01-23`起扩展；development OOS测试月实际为`2022-04-29..2026-05-29`，效果路径最晚到`2026-08-24`。预注册误写`2022-03..2026-05`，独立review定性为文字错误；冻结fold未改变。
- 账户规模：不适用；无资金、保证金、整数手或账户持仓模拟。
- 成本口径：消费冻结正式`net_pnl`产品贡献路径；不等于完整组合执行成本口径。
- 样本过滤：50折、每折18品种、900个development OOS预测；固定`fu.SHFE`模型行固定为0。
- 策略/归因口径：A/B按分数稳定选Top10，比较未来恰好60交易日贡献和从0起点的路径最大回撤；只把Top10 membership不同的月份计入增量汇总。

## 结果

- 期末权益：不适用；未运行真实策略引擎。
- 总收益：不适用；`+2,170`是changed months的产品贡献代理差额，不是总收益率。
- 最大回撤：不适用；`+73,920`是changed months回撤代理改善合计，不是真实组合最大回撤。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 折/预测/特征：`50/900/108`；LR/scaler/XGBoost fit计数按控制流为`50/50/100`。
- PIT违规行/折：`0/0`；sealed holdout行：`0`；固定fu模型行：`0`。
- 重复预测最大误差：`0`；split nodes：`994`；有split折：`33/50`。
- correction绝对值中位数/最大值：`0.00965675/0.07318210`。
- 加权logloss A/B：`0.76290805/0.76197569`。
- 月均Spearman Rank IC A/B：`-0.02269769/-0.01897414`。
- Top10变更：`5`个月、`2`个年份；低于预注册门`8`个月、`3`年。
- changed months return delta合计：`+2,170`；drawdown improvement合计：`+73,920`。
- leave-best return delta：`-46,670`；leave-best drawdown improvement：`+35,350`。
- joint positive比例：`0.60`。
- 2025年：3个变更月，return delta `-20,550`，drawdown improvement `+64,310`。
- 2026年：2个变更月，return delta `+22,720`，drawdown improvement `+9,610`。
- 失败门：`xgboost_non_degenerate`、`minimum_action_coverage`、`leave_best_robustness`、`yearly_robustness`。

## 输出文件

- report：`artifacts/stage002_base_margin_development_oos/report.md`。
- summary：`artifacts/stage002_base_margin_development_oos/summary.json`，SHA256 `748708f2a444354666f1df72c01e176eeb55ef02d4634d02afec824e6e7ef59a`。
- predictions：`artifacts/stage002_base_margin_development_oos/oos_predictions.csv`。
- monthly/yearly：`artifacts/stage002_base_margin_development_oos/monthly_effects.csv`、`yearly_effects.csv`。
- manifest：`artifacts/stage002_base_margin_development_oos/artifact_manifest.json`，SHA256 `ac6d2c46dc1e2b3b4cf726aa0d3d1a24e64fbcb1fdb5e3504310d381cda89060`。
- orders：不适用。
- daily：不适用；未发布真实组合daily。
- quality：`--verify-only`通过；本线25项测试通过，前置线20项测试通过。
- review：`reviews/20260904_1620_stage002_independent_review.md`。

## 独立复核

- P0/P1：无发现。
- P2：授权nonce没有耐久消费账本，fit与副作用字段不是独立运行遥测；静态调用链未发现CTP、订单、true-engine或生产写入，因此不影响数值fail-close，但不得声称这些是独立证明的精确次数。
- P3：预注册测试区间起点文字误写为2022-03，实际冻结首折为2022-04-29；不构成事后删月或泄漏。
- 独立复算：base-margin恒等式最大误差`2.22e-16`，60日路径最大误差`2.91e-11`，PIT违规0，19项授权SHA与两级manifest均有效。
- 最终建议：`PASS`，只认可当前模型形状fail-close，不认可更强的运行遥测声明。

## 结论

- 本阶段结论：`stage002_base_margin_residual_development_oos_fail_close_no_true_engine`。
- 是否进入下一步：否；当前108特征/二分类标签/LR base-margin浅树残差形状永久关闭。
- 下一步：不得改树参数、特征、门槛、fold、TopN或删除失败月/年救援；不得运行真实C9、holdout、shadow或正式接入。未来若继续XGBoost，只能以新的事前经济信息机制或真正未见数据另立研究线。

## 过拟合反思

- 运行前判断：是，高风险。
- 运行后判断：是，高风险且结果不稳健。
- 原因：全部历史都是已观察development，sealed holdout为0；增量只改变5个月并集中在2年，剔除最佳月后收益为负，2025年度收益也为负，不能认为能穿越周期。

## 继续价值反思

- 运行前判断：有，限唯一冻结Stage002，用于证伪未训练过的base-margin结构。
- 运行后判断：当前形状无继续价值；XGBoost整体只有在新增独立信息或真正未见数据时才有继续价值。
- 原因：模型质量仅微升，17个fold无split，实际选择变化不足且收益改善依赖单月；同一数据和目标上调参只会扩大研究者自由度与过拟合。

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage002失败闭线。
- 是否更新`research/registry.md`：是，登记冻结失败结论和禁止项。
- 是否追加根目录`memory.md/back_log.md`：否；不是重要突破、正式候选或跨线合并。
