# Stage026 v2 派生交付独立复核

冻结时间：2026-10-23T20:31:20.550052+08:00。结论：**PASS_DERIVED_REPORT_DELIVERY / NO_PROMOTION**；未发现待修P0/P1。没有新金融回放、数据调整或修改已冻结Stage023审计。

独立逐行检查旧版至v2仅三项变化：修正facade私有helper访问为`base.math_report._direction`；entry_attribution后补收集直接entry_risk SHA；输出改为v2以保留失败空目录。旧版派生失败及红灯日志保留。reviewer现场重跑2个真实fixture全部通过，验证1.65/1.10区分、成交后品种数与收盘品种数区分、保证金参数冲突拒绝。

N/P summary与Stage023独立重算结果逐字段一致；N12/P7条年度记录、各19品种表、471/307个FIFO平仓段的收益、笔数、胜负数及末仓一致。真实1.65保证金峰值108.037125176%/102.685018600%、各2天超100%，日终最多7、每笔成交后最多9均准确。entry_risk已直接纳入source SHA。桥接共同截止差−2,970，新增10/23日P亏损−122,220，均一致。

已现场核验63个report source SHA、4个图表输出SHA，并复核原Stage023 review两文件及其181项绑定全部未变。图像已查看：N从2015、P从2020分别起算，同为初始15万；图例/日期/周三均线/日K开盘/零佣金/离线与不晋级标签清楚，回撤计算包含初始资金。两条为各自资金路径的名义权益，不能当作2020同起点的独立alpha比较。

交付接受仅覆盖派生报告。原有历史映射、供应商量差、非PIT/OOS、零佣金和容量限制继续成立，**真实保证金超限仍不能部署或晋级**。具体SHA见[配套JSON](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/stages/stage026_report_delivery_review.json)；图为[权益与回撤](/Users/mac/.codex/worktrees/weekly-no-half-r-20261022/fian/research/lines/futures_weekly_formal_no_half_r/artifacts/stage026_v2_history_equity_drawdown.png)。
