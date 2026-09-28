# Stage002 趋势质量 XGBRanker 样本外技术失败

- 记录时间：2026-09-05 04:21 CST
- 实际运行时间：2026-09-05 04:17-04:18 CST
- 是否重要突破：否；37 折模型已完成，但最终持久化证据复核失败，不能形成模型效果或真实引擎候选。
- 决策：`stage002_trend_quality_ranker_contract_or_pit_invalid_stop_no_effect_claim`

## 本次版本改动

- 新增固定 19 特征、固定浅树 `XGBRanker` 的 37-fold walk-forward runner。
- 新增固定 `fu.SHFE` 排除与 AI universe relevance 重算。
- 新增 A=正式 LR Top10、C=仅第 10 席 XGB Top10 共识替换结构。
- 新增 durable execution/access event、逐月 seal、最终落盘 replay、失败证据包。
- 新增参数：无可调参数；模型参数与阈值全部继承预注册。
- 修改参数：无。
- 删除参数：无。

## 唯一执行证据

- 授权 nonce：`943161d8-9ecc-4e90-a340-1f80153ceafd`，已消费。
- 37 个 fold、74 次 fit、74 个模型、37 个 seal、36 个效果标签 access event 全部完成。
- AI 标签 55,226 行/1,046 qid；最终成熟训练 55,168 行/1,045 qid；36 个效果 qid 逻辑开放 1,940 行。
- 最终 bundle manifest SHA256：`a20fa63a1c95a9d37fdc0485ddebd9e5ff403e36d4349d79b04e81e87143e904`，159 个产物、13 个输入。
- 最终错误：`pre_effect_seal_mismatch`，发生阶段：`fold_completed`。
- 从第一折冻结模型重建的 prediction/selection SHA 与 seal 精确一致；CSV 往返预测最大误差仅 `9.71445146547012e-17`，但 37 行浮点均发生二进制变化，导致落盘 CSV 哈希与 seal 不一致。
- 这是持久化证据精度错误，不是模型不确定性；Stage002 仍必须按预注册技术失败处理。

## 回测结果字段

- 新增回测结果：无；本阶段不是策略撮合回测。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益：N/A。
- 总收益：N/A。
- 最大回撤：N/A。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。

## 隔离边界

- strategy backtest、sealed holdout、CTP、订单 API、生产写入均为 0。
- 未读取或汇报 `predictive_monthly.csv`、`effect_monthly.csv` 的效果值；不得从失败包得出收益或回撤结论。
- 不删除、不覆盖、不重跑 Stage002；原 nonce、event、模型、seal、access event 和失败 manifest 永久保留。

## 结束反思

- 是否过拟合：**没有新增效果过拟合，但开发样本已见风险仍在**。本次只诊断首折模型与 CSV 的 `1e-16` 级序列化差异，没有查看效果指标、改参数、改门槛或删样本。
- 是否还有价值继续：**是，但仅限无 fit 证据恢复**。74 个冻结模型与 37 个 seal 已存在，重新训练没有必要且会增加双重使用风险；应另立 Stage003，在查看效果值前预注册模型重放与 lossless 证据门。

## TODO

- Stage003 只加载冻结模型，重建 37 折预测与选择并逐 seal 精确核验，fit 必须为 0。
- 全部技术恢复门通过后，才允许按 Stage002 原门槛汇总已合法开放的开发 OOS 标签。
- 独立 reviewer 复核 Stage003；失败则本模型形状闭线，不做参数救援。
