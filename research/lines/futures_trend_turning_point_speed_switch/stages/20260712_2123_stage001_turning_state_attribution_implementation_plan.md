# Stage001 严格 T-1 转折状态归因实现计划

- line_id：`futures_trend_turning_point_speed_switch`
- 当前模式：`day`
- 记录时间：`2026-07-12 21:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：实现计划；未运行回测
- 是否重要突破：否
- 是否触发A/B：否

## 实现边界

1. 在本线新增独立只读工具，不修改正式策略、旧研究线工具或任何实盘入口。
2. 先写纯函数测试：输入 SHA、T-1 窗口、MA 状态、逻辑 episode、换月排除、首次 onset、R 匹配、自然退出截断、双向 bootstrap 和硬门 fail-close。
3. 工具只读取冻结 A 五份输入，生成 line-local CSV/JSON/Markdown；运行前后复验输入快照。
4. 状态表保留 `action_date/asof_date/product/actual_contract/direction/episode_id/source_sha`，任何未来函数、重复键、短窗口或状态回退立即报错。
5. 输出至少包括：source manifest、position-state rows、opposite events、concordant references、segment/year/direction/product summaries、bootstrap draws summary、gate matrix、decision 和 report。
6. 首次运行只做归因，不实现减仓 hook、不运行策略回测。
7. 归因运行后立即拉独立 agent，全面复核数据、逻辑、统计、置信度和 bug；影响结果的问题修复后按原冻结合同重跑，不影响结果的问题写入本线 stage/LINE 日志。

## fail-close 检查

- 输入路径、SHA、行数、schema、版本标签必须完全匹配。
- positions 的 `start_pos[t] == end_pos[t-1]` 按 actual contract 守恒；异常必须解释为数据边界，否则停止。
- trades 聚合后的 signed volume 必须等于 positions `pos_change`；成本聚合必须守恒。
- MA 每行必须有严格前 40 个连续全市场交易日，且 `asof_date < action_date`。
- 候选风险匹配必须唯一且与真实首次 Open 的产品、合同、方向和时点一致；无法匹配不回填。
- opposite 事件同一 episode 不得重复；首状态 opposite 和换月首状态不得进入主事件。
- 任何 outcome 不得跨过逻辑 episode 的自然退出/反向日；聚类 block 只能由全市场交易日序号事前生成。
- decision 必须由固定 gate matrix 机械生成，不允许脚本外人工晋级。

## 预期测试

- synthetic long/short 的 concordant、neutral、opposite 状态。
- action day 当日价格冲击不影响 T-1 状态。
- 39 根、日期缺口、wrong contract、panel 旧 gzip 均 fail-close。
- 新开仓日、换月首状态、首状态 opposite、连续 opposite 和恢复后二次 opposite 不计事件。
- 自然退出前不足 5/20 日时正确截断且覆盖标记明确。
- 双向 bootstrap 固定 seed 可复现，单一产品/单一 block 不得伪造区间。
- 产品、年份、方向、三段、集中度、可执行手数和经济门任一失败都令 `canary_allowed=false`。

## 参数与结果

- 新增参数：仅预声明中的固定 MA、horizon、bootstrap 和硬门。
- 修改参数：无。
- 删除参数：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A（未回测）。

## 过拟合反思

- 运行前判断：否；实现只编码已冻结合同。
- 运行后判断：待 Stage001 完成。
- 原因：不得依据真实结果调整测试期望或硬门。

## 继续价值反思

- 运行前判断：有；一次只读归因能决定是否值得写真引擎。
- 运行后判断：待 Stage001 完成。
- 原因：未过门即关闭，不进行参数救援。

## 合入建议

- 更新本线 `LINE.md`：实现和归因完成后再更新。
- 更新 `research/registry.md`：本阶段不更新。
- 根目录 `memory.md/back_log.md`：本阶段不追加。
