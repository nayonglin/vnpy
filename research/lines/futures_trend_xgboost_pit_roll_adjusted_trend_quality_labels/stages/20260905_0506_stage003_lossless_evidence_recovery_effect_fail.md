# Stage003 XGBRanker 无拟合证据恢复失败停止

- line_id：`futures_trend_xgboost_pit_roll_adjusted_trend_quality_labels`
- stage：`stage003_lossless_evidence_recovery`
- 记录时间：2026-09-05 05:06 CST
- 实际执行时间：2026-09-05 04:54 CST
- 是否重要突破版本：**否**。本阶段修复了 Stage002 的证据序列化歧义，但模型效果为明确负结果。
- 决策：`stage003_lossless_evidence_recovery_effect_fail_stop_no_true_engine`

## 本次版本变更

- 新增无拟合恢复器：只加载 Stage002 的74个冻结模型，执行74次预测，训练次数为0。
- 新增 `float.hex()` / `float.fromhex()` 无损预测证据，2,000条预测逐 bit 回读。
- 新增 Stage002 bundle、authorization/event/nonce、模型、seal、access event、输入身份和 durable 访问状态硬门。
- 新增独立 pre-run 与 post-run review；最终均无 P0/P1。

## 参数变更

- 新增参数：无模型参数；仅新增固定恢复合同 `37 folds / 74 loads / 74 predicts / 0 fits / 2,000 predictions / 1,940 effect labels`。
- 修改参数：无。
- 删除参数：无。
- Stage002 的19个特征、浅树参数、Top10单槽 selector 与全部效果阈值均未改变。

## 技术结果

- Stage003 manifest SHA256：`c423ded94b0c7bedc3eaa339a027d23695dbec5460447c6a30ebe5604baa7ebe`。
- 10个产物、16个输入验证通过；输入 before/mid/after 一致。
- `fit/load/predict=0/74/74`；模型身份错误0，repeat bit mismatch折数0。
- 原 prediction/selection seal=`37/37`；lossless replay seal=`37/37`。
- access event=`36/36`，effect labels=`1,940`，opened-label SHA mismatch=`0`。
- 标签=`55,226`行/`1,046` qid；最终训练元数据=`55,168`行/`1,045` qid。

## 新增模型代理结果

- mean/median Rank IC：`-0.0232133/-0.0229765`。
- 正 Rank IC 月：`16/36`；leave-best Rank IC sum：`-1.3866123`；正年份：`2`。
- NDCG 相对随机均值：`-0.0530824`；胜出月份：`13/36`。
- 替换次数：`28`；质量改善率：`0.5000`；中位质量差：`-0.0030311`。
- quality sum/leave-best：`-0.5742274/-0.6548494`；四个年度质量差均为负。
- 绝对趋势幅度 sum/leave-best：`-0.1511225/-0.2654736`。
- oriented path drawdown 代理 sum/leave-best：`-0.4231049/-0.4728027`。

## 回测结果

- 新增回测结果：无，本阶段策略回测次数为0。
- 修改回测结果：无。
- 删除回测结果：无。
- 期末权益：N/A（未运行策略撮合回测）。
- 总收益：N/A（未运行策略撮合回测）。
- 最大回撤：N/A（路径标签代理不是账户最大回撤）。
- Sharpe：N/A。
- 总滑点：N/A。
- 总交易次数：N/A。
- 胜率：N/A。

## 独立复核

- pre-run reviewer 经两轮阻断修复后给出 PASS；授权显式绑定 publisher，access event 与 durable 访问账本完整。
- post-run reviewer 复算全部技术门和效果门，P0/P1=`0/0`，确认必须 fail-stop。
- 唯一 P2 是冻结报告措辞“失败或未开放”不够精确，不影响 summary 或 decision，也不改写已封存产物。

## 结束反思

- 是否正在过拟合：**Stage003 本身否**。全程没有训练、调参、改阈值或删样本，只恢复冻结模型证据。若根据本次负结果反转分数、改门或选择月份，则会是明显过拟合，明确禁止。
- 是否还有价值继续：**当前标签/特征/XGBRanker/单槽 selector 形态没有继续价值**。预测能力低于随机代理，A/C质量、幅度和回撤代理均恶化，不应投入真实撮合。
- 总目标是否还有价值继续：**是，但必须换独立经济机制**。下一步只考虑与当前可交易趋势方向一致、包含净收益与下行风险的事前标签机制，并从无标签合同重新开始。

## TODO

- 关闭本模型形态；禁止重跑、调参、改门、删月/年、符号反转、true-engine、holdout、shadow 或正式接入。
- 完成下一条方向一致净效用标签的只读代码与数据覆盖勘察。
- 只有新机制具备独立经济依据和完整PIT覆盖时，才另立研究线并预注册无标签资格门。
