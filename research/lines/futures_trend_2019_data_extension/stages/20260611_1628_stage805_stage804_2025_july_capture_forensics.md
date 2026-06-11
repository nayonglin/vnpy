# Stage805 Stage804 2025-07 右尾捕获差异归因

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-11 16:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：Stage804 固定版本归因，不新增策略参数
- 是否重要突破：是，解释 Stage804 为何早期起点强但部分起点错过 2025-07 右尾
- 是否触发A/B：否，本阶段只做固定 A777/C804 归因，不提出新候选接入

## 外部调研与判断

- 参考资料：
  - 公开趋势跟随研究普遍强调收益高度集中在少数大趋势窗口，是否持仓决定长期复利差异。
  - 仓位 sizing 与止损距离耦合会增强路径依赖；同一信号在不同起点下因为账户权益、回撤、保证金和风控状态不同，最终开仓/持仓完全不同。
- 我的判断：
  - 用户指出“Stage804 看起来比 Stage777 好”有事实基础，尤其 `2018/2019/2020` 起点。
  - 但 Stage804 的强来自更紧止损带来的更高仓位和更高复利弹性，不是无成本 alpha。
  - 部分起点没抓住 2025-07 不是 AI 没选，也不是没有信号，而是前序路径把账户推入更高热度/回撤状态，触发 `risk_cluster_heat_deleverage`，把关键仓位提前平掉。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage805_stage804_2025_july_capture_forensics.py`
- 修改脚本：将 Stage805 默认 `MAX_WORKERS` 设为 `1`，避免并发读取/生成 AI eligibility CSV 时出现 `EmptyDataError`
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：起点 `2018-01` 到 `2025-01`，统一归因窗口 `2025-06-16 -> 2025-07-25`
- 账户规模：`500,000`
- 成本口径：沿用 Stage777 / Stage804 原成本、滑点、真实主力 next-open 代理
- 样本过滤：只取窗口 daily、positions、trades、entry_risk、entry_candidates
- 策略/归因口径：
  - A：Stage777 baseline 复跑
  - C：Stage804 多头更紧初始止损复跑

## 结果

- 窗口总 PnL：
  - `2018-01`：A `8,519,730`，C `14,415,000`，C-A `+5,895,270`
  - `2019-01`：A `9,643,110`，C `14,415,000`，C-A `+4,771,890`
  - `2020-01`：A `5,712,780`，C `14,415,000`，C-A `+8,702,220`
  - `2021-01`：A `2,516,190`，C `1,664,040`，C-A `-852,150`
  - `2022-01`：A `418,620`，C `237,720`，C-A `-180,900`
  - `2023-01`：A `525,150`，C `188,940`，C-A `-336,210`
  - `2024-01`：A `316,560`，C `303,420`，C-A `-13,140`
  - `2025-01`：A `341,070`，C `455,100`，C-A `+114,030`
- 关键品种贡献：
  - 本窗口右尾主要来自 `jm.DCE` 和 `si.GFEX` 多头。
  - 早期起点 C804 吃满右尾，是因为 `jm.DCE` 和 `si.GFEX` 直接开到或接近上限：
    - `2018/2019/2020` C804：`jm` 最大持仓 `500` 手，`si` 最大持仓 `500` 手。
    - 对照 A777：`2020` 只有 `jm 218`、`si 138`。
  - 后期/反例起点 C804 没吃满，是因为 `jm.DCE` 被 `risk_cluster_heat_deleverage` 提前平掉：
    - `2021` C804：`jm 147` 手，`2025-07-09` 开仓，`2025-07-10` 因 `long_risk_cluster_heat_deleverage` 全平，只贡献 `171,990`；A777 `jm 96` 手持有到 `2025-07-25`，贡献 `2,200,320`。
    - `2023` C804：`jm 17` 手，`2025-07-09` 开仓，`2025-07-10` 因 `long_risk_cluster_heat_deleverage` 全平，只贡献 `19,890`；A777 `jm 20` 手持有到 `2025-07-25`，贡献 `458,400`。
    - `2022` C804 同样 `jm 21` 手次日热度降仓，只贡献 `24,570`；A777 `jm 16` 手持有到 `2025-07-25`，贡献 `366,720`。
- 关键入场不是被 AI 挡：
  - `2025-07-08` `jm.DCE` 多头在 A/C 都开仓，且 OI 确认均生效。
  - `2025-07-09` `si.GFEX` 多头在 A/C 都开仓。
  - 差异来自开仓后的组合热度/回撤风控，不是 AI 池没有选中。
- 窗口前后关键交易：
  - C804 `2021/2022/2023` 的 `fu` 也常在 `2025-06-13` 被 `long_risk_cluster_heat_deleverage` 提前平掉。
  - A777 同样信号通常按 `long_prev2day_stop` 或 `long_rsi_partial_exit_half` 退出，持有时间更长。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_report_stage805_stage804_2025_july_capture_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_summary_stage805_stage804_2025_july_capture_forensics_v1.csv`
- orders：无
- daily：本阶段不输出完整 daily，仅输出窗口 summary
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_product_contribution_stage805_stage804_2025_july_capture_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_entry_risk_window_stage805_stage804_2025_july_capture_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_trades_window_stage805_stage804_2025_july_capture_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage805_stage804_2025_july_capture_forensics_active_positions_stage805_stage804_2025_july_capture_forensics_v1.csv`

## 结论

- 本阶段结论：
  - Stage804 不应被简单判为“比 Stage777 差”；它确实增强了早期起点的右尾捕获。
  - 但它也不是简单“明显更好”，因为错过 2025-07 的反例起点不是随机噪声，而是更紧止损与组合热度降仓发生了结构耦合。
  - 核心矛盾是：更紧止损扩大手数，扩大手数提高右尾弹性；但路径走坏时又会推高回撤/热度，触发 `risk_cluster_heat_deleverage`，把后续大赢家提前平掉。
- 是否进入下一步：是，值得继续做结构验证。
- 下一步：
  - 不直接关闭 `risk_cluster_heat_deleverage`，这会明显提高尾部风险。
  - 更合理的下一步是研究“多头更紧退出止损 + sizing/heat 使用可持续风险距离”的解耦口径，或给热度降仓增加趋势盈利保护/延迟确认，但必须预声明、做多起点。

## 过拟合反思

- 运行前判断：低，固定版本归因不是调参。
- 运行后判断：归因本身不过拟合，但如果针对 `jm/2025-07/热度降仓` 写特例会严重过拟合。
- 原因：本次发现的是结构耦合，不能用单品种、单年份补丁解决。

## 继续价值反思

- 运行前判断：有价值，解释 Stage804 是否被过早淘汰。
- 运行后判断：有继续价值。
- 原因：Stage804 的收益增强是真实存在的，失败点也很清楚；下一步应验证是否能保留更紧止损的右尾弹性，同时避免热度风控在趋势启动初期过早清仓。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等下一步结构验证后再决定
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`
