# Stage026 - 恢复段右尾 episode 入场前识别只读归因

## 变更时间

- 2026-07-01T15:57:03 CST

## 是否重要突破版本

- 否。只读归因，不是真实引擎候选，不改线上。

## 本次版本改动内容

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage026_recovery_right_tail_episode_identifier.py`
- 将 Stage024 pause events 按 `source_start_month + event_date` 聚合为 episode。
- 合并入场前可见的 candidate、market daily、full-market AI、账户曲线状态，比较右尾错杀与暂停有益 episode。

## 新增参数

- `PRIMARY_HORIZON=252`
- `right_tail_miss_252d = delta_change_252d <= 0`
- `strong_right_tail_miss_252d = delta_change_252d <= -30000`

## 修改参数

- 无。

## 删除参数

- 无。

## 新增回测结果

- episode 数：`113`
- 右尾错杀 episode：`21`
- 右尾错杀率：`18.5841%`
- 暂停有益 episode：`92`
- `252d` delta 总和：`24949883.60`
- `252d` delta 中位数：`110065.00`
- 最强条件：`ai_consensus_any`，错杀率 `61.1111%`，样本 `18`
- 最强分桶：`ai_consensus_flag_share=high`，错杀率 `61.1111%`，样本 `18`

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 指标占位

- 期末权益：只读归因，不适用。
- 总收益：只读归因，不适用。
- 最大回撤：只读归因，不适用。
- Sharpe：只读归因，不适用。
- 总滑点：不新增交易，不适用。
- 总交易次数：不新增交易，不适用。
- 胜率：不新增交易，不适用。

## 调研与判断结论

- 外部资料判断：趋势跟随需要保留趋势延续右尾，whipsaw 是成本；因此不能只用 hard regime gate，而要找入场前可见的恢复段/假趋势差异。
- 本阶段判断：`stage026_no_stable_precursor_close_hard_regime_gate`。

## 过拟合与继续价值反思

- 运行前是否过拟合：否。本阶段只做预声明 episode 归因，不直接写规则。
- 运行前是否有价值继续：有。Stage025 已确认 hard gate 内部混合两类 episode，需要判断是否能被可见特征区分。
- 运行后是否过拟合：否。本阶段只产生候选前兆审计；若把窄样本最高 lift 条件直接上线会过拟合。
- 运行后是否有价值继续：否。Stage026 没有找到跨 source、足够样本且不依赖日期集中的强前兆；继续沿 hard regime gate 救参价值不高，下一步应转向 remaining worst-window holding_pnl/positions 或真正外生信息源。

## 后续规划和 TODO

- 本轮未找到跨 source 稳定、非日期/品种补丁且样本足够的前兆，关闭 hard regime gate 方向。
- 下一步转向 Stage024 remaining worst-window 的 holding_pnl/positions 拆解，或寻找真正外生信息源；不得把 `ai_consensus_any` 这种窄样本条件直接写成真实引擎。

## 输出文件

- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage026_recovery_right_tail_episode_identifier/rebuilt_c9_stage026_recovery_right_tail_episode_identifier_report_stage026_recovery_right_tail_episode_identifier_v1.md`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage026_recovery_right_tail_episode_identifier/rebuilt_c9_stage026_recovery_right_tail_episode_identifier_decision_stage026_recovery_right_tail_episode_identifier_v1.json`
- `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage026_recovery_right_tail_episode_identifier/rebuilt_c9_stage026_recovery_right_tail_episode_identifier_chart_stage026_recovery_right_tail_episode_identifier_v1.png`
