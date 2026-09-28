# Stage001 XGBoost账户组合上下文标签前可行性结果

- line_id：`futures_trend_xgboost_account_context`
- 当前模式：标签前数据与公式可行性验证
- 记录时间：2026-09-02 11:33 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`，`codex/stage130-option-probe`，当前工作区保留其他未提交研究改动
- 阶段性质：Stage000确认后的唯一冻结Stage001；未训练、未回测
- 是否重要突破：否；属于数据机制反证和闭线结论
- 是否触发A/B：否

## 外部调研与判断

- 参考资料沿用Stage000：XGBoost论文/官方参数/GitHub、scikit-learn时间序列拆分、Roncalli风险预算和`pysystemtrade`组合构建资料。
- 运行前判断：候选与Top9的组合上下文是可证伪的缺失变量假设，但只有冻结实际损益源能为每个rank10..18候选提供足够历史活动时，六项公式才可定义。
- 运行后判断：当前`position_changes`记录的是正式策略实际参与路径，不是每个候选的连续反事实收益。它对未持有候选存在结构性零活动，不能作为完整候选组合上下文源。

## 本次变更

- 新增脚本：`tools/stage001_account_context_feature_contract.py`
- 新增测试：`tests/test_stage001_account_context_feature_contract.py`
- 新增失败回执、零活动明细和失败报告。
- 修改脚本：无上游或生产脚本修改。
- 删除脚本：无。
- 新增参数：冻结120日窗口、最少20个Top9下行日、六项上下文公式和稳定错误码。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：51个`eval_date`，`2022-04-29`至`2026-06-30`；每月rank10..18。
- 账户规模：不适用；未运行账户或回测。
- 成本口径：不适用；未产生交易。
- 样本过滤：459行全部检查；每行严格使用截至`eval_date`的120个全局交易日，不删月份、年份或品种。
- 策略/归因口径：只读正式完整排序、Stage014标签前面板和冻结逐日`position_changes`；未读取Stage015账户标签。

## 结果

- 正式入口：退出码`1`，错误码`candidate_activity_days_zero`。
- 首个失败：`2022-04-29 / rank11 / lc.GFEX`，120日候选活动天数`0`。
- 完整诊断：459行/51个月；零活动`27`行、`16`个月、`11`个品种。
- 正式rank10零活动月份：`2022-11-30`、`2023-06-30`、`2023-11-30`、`2026-02-27`。
- 候选下行标准差为0：`32`行、`19`个月；rank10下行标准差为0：`6`个月。
- Top9下行日不足：`2025-10-31`仅`18<20`天。
- 测试：`14 passed`；真实输入连续运行稳定得到同一错误码，且没有正式或临时部分输出。
- 身份复验修复：正式运行时`LINE.md` SHA为`ec3e5856...`；结果写回会自然改变该文件，故长期不可变锚点改为Stage000设计记录SHA `1591494f...`。该修复只解决结果后复验，不改变数据、公式或失败结论。
- 期末权益：不适用；Stage001未回测。
- 总收益：不适用；Stage001未回测。
- 最大回撤：不适用；Stage001未回测。
- Sharpe：不适用；Stage001未回测。
- 总滑点：不适用；Stage001未回测。
- 总交易次数：不适用；Stage001未回测。
- 胜率：不适用；Stage001未回测。
- 新增回测结果：无。
- 修改回测结果：无。
- 删除回测结果：无。
- 独立reviewer：未触发；本阶段没有产生回测数据或模型评估结果。

## 输出文件

- failure receipt：`artifacts/stage001_account_context_feature_contract_failure/failure_receipt.json`
- zero activity rows：`artifacts/stage001_account_context_feature_contract_failure/zero_activity_rows.csv`
- report：`artifacts/stage001_account_context_feature_contract_failure/report.md`
- artifact manifest：`artifacts/stage001_account_context_feature_contract_failure/artifact_manifest.json`，SHA256 `7f4dc5e5729dd74178d99333f6f65327a616819f283f69ea264d95312e7e45e7`；manifest内三项SHA已逐项复算一致。
- 正式pass目录：未创建。
- orders/daily：不适用。

## 结论

- 本阶段结论：`stage001_account_context_prelabel_contract_fail_sparse_position_history_close_line`。
- 是否进入下一步：否。不写Stage002训练合同，不训练XGBoost，不读取development标签或sealed holdout，不运行真引擎。
- 原因：六项上下文特征在冻结完整候选面板上不可定义；删除27行、缩短窗口、把零活动当零相关或换20天下限均会改变已确认合同并制造选择偏差。
- 下一步：本线关闭。若继续账户组合上下文，只能另立研究线并先找到对所有候选可用的独立PIT日收益/持仓模拟源；不得把本线改成参数或缺失值救援。

## 过拟合反思

- 运行前判断：研究序列过拟合风险高，但Stage001自身不读取标签，不产生结果拟合。
- 运行后判断：本阶段没有过拟合；失败来自标签前可观测覆盖硬条件，不是收益结果不理想。
- 原因：公式、窗口、候选范围和停止条件在真实覆盖可见前已冻结，失败后没有删除样本或修改门槛。

## 继续价值反思

- 运行前判断：有，但只值得一次冻结可行性验证。
- 运行后判断：当前研究线没有继续价值。
- 原因：核心数据源无法支持完整候选组合上下文；继续补值、删样本或改窗口不能增加真实信息，只会把缺数据伪装成模型输入。

## 合入建议

- 是否更新本线`LINE.md`：是，标记Stage001失败闭线。
- 是否更新`research/registry.md`：是，更新当前状态和下一步禁区。
- 是否追加根目录`memory.md/back_log.md`：否；未形成重要突破、正式候选或跨线合并。
