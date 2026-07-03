# Stage030 - Stage029 暂停规则失败归因

- 时间：`2026-07-01T16:50:56`
- 是否重要突破版本：否；这是失败归因，不是候选策略。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增回测结果：无新增真实回测；复用 Stage006/Stage029 已有产物做只读归因。
- 修改回测结果：无。
- 删除回测结果：无。
- 暂停事件：`2869`。
- Stage006 同日同品种方向候选匹配：`2794`，匹配率 `97.3858%`。
- Stage006 实际打开候选匹配：`2587`，打开匹配率 `90.1708%`，selected_volume 合计 `203281`。
- Stage006 closed-lot 匹配事件：`22`，匹配率 `0.7668%`。
- 被暂停事件 Stage006 realized PnL 代理：`1249440.00`。
- 正/负 PnL 代理事件：`15` / `7`。
- Stage029 正收益起点：`9/17`。
- Stage029 80% 收益保留：`1/17`。
- 期末权益差合计 Stage029-Stage006：`-62204602.80`。
- 胜率：不新增逐笔胜率口径；使用 Stage006 closed-lot PnL 代理正负事件。
- 过拟合反思：否。本阶段没有生成交易规则，也没有按回测结果调阈值；如果据此直接改 DD/loss_streak 阈值才是过拟合。
- 继续价值反思：有，但方向要收窄。继续价值在识别不切断右尾的外生/质量信息，或非交易账户层资金安排；直接暂停/小手数化 flat_entry 的价值下降。
- 后续规划：不继续扫 DD/loss_streak 阈值；下一步只允许研究不切断右尾的外生/质量信息，或转非交易账户层资金安排。

## 输出

- 报告：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage030_stage029_failure_attribution/rebuilt_c9_stage030_stage029_failure_attribution_report_stage030_stage029_failure_attribution_v1.md`
- 决策：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage030_stage029_failure_attribution/rebuilt_c9_stage030_stage029_failure_attribution_decision_stage030_stage029_failure_attribution_v1.json`
- 图表：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage030_stage029_failure_attribution/rebuilt_c9_stage030_stage029_failure_attribution_failure_attribution_chart_stage030_stage029_failure_attribution_v1.png`
