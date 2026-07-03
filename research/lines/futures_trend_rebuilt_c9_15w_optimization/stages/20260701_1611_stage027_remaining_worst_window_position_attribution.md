# Stage027 - Stage024 剩余 worst-window 持仓路径归因

## 变更时间

- 2026-07-01T16:11:00 CST

## 是否重要突破版本

- 否。只读归因，不是真实引擎候选，不改线上。

## 本次版本改动内容

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage027_remaining_worst_window_position_attribution.py`
- 从 Stage024 top `1000` worst windows 中抽取 `50` 个代表窗口。
- 用 Stage024 真实引擎重放相关 source 到 `2024-03-15`，输出 positions 并做窗口级 PnL 闭合校验。
- 将窗口损失拆成 `existing_at_window_start` 与 `opened_or_traded_after_window_start`。

## 新增参数

- `TOP_WORST_ROWS=1000`
- `SELECTED_WINDOW_COUNT=50`

## 修改参数

- 无。

## 删除参数

- 无。

## 新增回测结果

- 代表窗口：`50`
- 重放 source：`10`
- 最大一致性误差：`0.000000`
- 窗口聚合净 PnL：`-6,468,110.00`
- 窗口聚合 holding PnL：`-6,135,740.00`
- 窗口聚合 trading PnL：`-14,390.00`
- 已有仓位亏损占比：`11.03%`
- 窗口后新开/交易仓位亏损占比：`88.97%`
- 决策：`stage027_left_tail_dominated_by_new_or_traded_positions`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 指标占位

- 期末权益：只读归因，不适用。
- 总收益：只读归因，不适用。
- 最大回撤：只读归因，不适用。
- Sharpe：只读归因，不适用。
- 总滑点：`317,980.00`
- 总交易次数：`4,066`
- 胜率：不新增交易，不适用。

## 调研与判断结论

- 外部资料判断：趋势跟随左尾治理应优先看仓位路径、风险预算和分散化，不应从单窗口回测 winner-picking。
- 本阶段判断：`stage027_left_tail_dominated_by_new_or_traded_positions`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。本阶段只做 representative worst-window 路径归因，不写规则。
- 运行前是否有价值继续：有。Stage024 仍有 `298,012` 个严格负窗口，必须确认剩余损失来自已有仓位还是新增仓位。
- 运行后是否过拟合：否。本阶段没有按品种、方向、日期或阈值拟合规则；最差品种只作为归因证据。
- 运行后是否有价值继续：有。归因可以把下一步从 hard regime gate 转向账户状态下的新开仓风险释放顺序；但真实候选仍必须预声明并做多起点严格窗口验证。

## 后续规划和 TODO

- 若损失由窗口后新开/交易仓位主导，下一步应研究账户状态下的风险释放顺序，而不是 hard regime gate。
- 若损失由已有仓位主导，下一步应研究持仓期减风险或退出纪律，但必须避免切断趋势右尾。
- 不得把最差品种/方向直接做成黑名单。

## 输出文件

- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage027_remaining_worst_window_position_attribution/rebuilt_c9_stage027_remaining_worst_window_position_attribution_report_stage027_remaining_worst_window_position_attribution_v1.md`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage027_remaining_worst_window_position_attribution/rebuilt_c9_stage027_remaining_worst_window_position_attribution_decision_stage027_remaining_worst_window_position_attribution_v1.json`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage027_remaining_worst_window_position_attribution/rebuilt_c9_stage027_remaining_worst_window_position_attribution_chart_stage027_remaining_worst_window_position_attribution_v1.png`
