# Stage000 XGBoost账户组合上下文书面设计

- line_id：`futures_trend_xgboost_account_context`
- 当前模式：设计冻结，等待用户书面规格确认
- 记录时间：2026-09-02 11:07 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`，当前工作区已有其他未提交研究改动
- 阶段性质：新研究线架构与实验合同；不实现、不训练、不回测
- 是否重要突破：否
- 是否触发A/B：尚未触发；只冻结未来A/B/C定义

## 外部调研与判断

- 参考资料：XGBoost论文与官方参数/单调约束文档、XGBoost GitHub、scikit-learn时间序列拆分、Roncalli风险预算材料、`pysystemtrade`组合构建文档；完整URL见本线`LINE.md`。
- 仓库反证：Stage017已证明目标标准化可消除单叶退化，但原九特征的九项效果门仅3项通过；入场meta-label及两条直接组合风险缩手路线也已分别失败。
- 我的判断：继续调Stage017参数没有价值。唯一仍可辩护的XGBoost方向，是补上“候选相对正式Top9的组合上下文”这一明确缺失变量，并让正式逻辑回归继续掌握Top9。

## 本次变更

- 新增文件：`research/lines/futures_trend_xgboost_account_context/LINE.md`
- 新增阶段记录：本文件
- 修改文件：`research/registry.md`仅新增本研究线索引并更新时间
- 删除脚本：无
- 新增参数：仅冻结六项120日账户组合上下文特征、Stage001-003门禁和真引擎最小经济显著性门；尚未进入代码配置
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：未来development特征/标签范围冻结为`2022-04-29`至`2025-06-30`；sealed holdout为`2025-07-31`至`2026-06-30`
- 账户规模：未来真引擎固定15万元；本阶段未运行账户
- 成本口径：未来真引擎沿用正式成本；本阶段未产生交易成本
- 样本过滤：未来仅rank10..18；120个截至`eval_date`的全局交易日；不删月份、年份或品种
- 策略/归因口径：正式Top9不动，XGBoost仅挑战rank10；详细公式、固定模型、A/B/C和门禁见本线`LINE.md`

## 结果

- 期末权益：不适用；未回测
- 总收益：不适用；未回测
- 最大回撤：不适用；未回测
- Sharpe：不适用；未回测
- 总滑点：不适用；未回测
- 总交易次数：不适用；未回测
- 胜率：不适用；未回测
- 其他关键指标：冻结15项特征，其中保留9项、新增6项；冻结Stage001标签前可行性、Stage002一次development OOS、Stage003条件式真引擎三层门禁

## 输出文件

- report：本文件
- summary：`research/lines/futures_trend_xgboost_account_context/LINE.md`
- orders：不适用
- daily：不适用
- quality：待书面规格确认后进入实现计划

## 结论

- 本阶段结论：`stage000_account_context_design_frozen_pending_user_review`
- 是否进入下一步：等待用户确认书面规格；确认前不写实现计划、不写实验代码
- 下一步：用户确认后读取`superpowers:writing-plans`，形成逐文件、测试先行的实施计划；随后才进入Stage001

## 过拟合反思

- 运行前判断：是，研究序列存在高自适应风险；Stage016/017已经观察相同development OOS月份
- 运行后判断：本阶段没有读取新结果，未新增结果拟合；但后续风险仍高
- 原因：设计只允许一个结构性缺失变量假设、一个固定15特征合同和既有资格门，且任何失败即停

## 继续价值反思

- 运行前判断：有，但只值得验证一次
- 运行后判断：有，前提是严格按书面门禁执行
- 原因：账户边际标签与单品种输入之间的语义缺口真实存在；如果六项组合上下文仍不能稳定改善双目标，应停止XGBoost当前数据路线，而不是继续扫参

## 合入建议

- 是否更新本线`LINE.md`：是，已建立
- 是否更新`research/registry.md`：是，新增索引
- 是否追加根目录`memory.md/back_log.md`：否；设计阶段不是重要突破、正式候选或跨线合并

