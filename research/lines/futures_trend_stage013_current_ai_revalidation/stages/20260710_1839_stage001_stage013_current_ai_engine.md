# Stage001 当前 AI Stage013 pilot A/C

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 记录时间：`2026-07-10 18:39 CST`
- 阶段性质：当前 AI 同引擎最小 A/C
- 是否重要突破：是；单起点同时通过收益保留、全周期/2022/压力窗回撤和 broker10 门槛
- 是否触发 A/B：是；A=当前 C9，C=A+冻结 Stage013 pilot

## 外部调研与判断

- 沿用前序 Stage013 的账户状态风险治理思想：只在深回撤且低持仓时限制重启风险，不按品种、日期、方向筛选。
- 运行前过拟合判断：低。`30%/<=1/1手` 来自 2026-07-01 前序冻结候选，本阶段只更换为当前 AI 做重验。
- 运行前继续价值判断：有。它不普遍压缩趋势右尾，直接针对深回撤后的大额重启失败。

## 本次变更

- 新增脚本：`research/lines/futures_trend_stage013_current_ai_revalidation/tools/stage001_stage013_current_ai_engine.py`。
- 新增参数：无；复用 `stage013_pilot_drawdown_trigger_pct=0.30`、`active_positions_max=1`、`pilot_min_volume=1`。
- 修改参数：仅 A/C eligibility 路径分别写入线内文件，但内容归一化相同。
- 删除参数：无。
- 正式配置、实盘、CTP、邮件、launchd：均未修改。

## 回测参数

- 区间：`2020-01-01 -> 2026-06-30`，实际 `2020-01-02 -> 2026-06-30`，`1571` 个交易日。
- 资金：`150,000`。
- AI：`504` 行、`55` 个 eval_date；归一化 hash `df020c940d576868`。
- 成本、保证金、forced-margin、相关门、单产品 cap、并发、退出和 0.5R stop/retry：当前 C9 原样。

## 结果

| 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 滑点 | 交易次数 | 非零日胜率 | 逐笔胜率 | broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| C | 5,984,961.70 | 3889.9745% | -38.1717% | 1.4585 | 489,650 | 639 | 53.0516% | 45.5385% | 81.5638% |

- 收益保留：`0.9980`。
- 全周期/2022/主压力窗回撤改善：`17.1984/5.3500/21.0464pp`。
- broker10 改善：`6.7760pp`。
- Pilot `55` 次、减少 `8,172` 手；2022/2023/2025/2026 分别 `8/17/13/17` 次。
- 55 次全部满足回撤、活跃持仓、flat-entry 和 1 手条件；首个权益分叉为首个 pilot 后的 `2022-05-10`，此前 A/C 完全一致。
- A 基准与前两次当前 C9 复算逐字段完全一致；曲线重算 summary 误差为 0（浮点尾差除外）。
- 单元测试：`.py311/bin/python tests/test_rebuilt_c9_stage013_pilot_gate.py`，`2/2` 通过；环境无 pytest 模块，使用 unittest 入口。

## 独立 review

- `P0=0/P1=0/P2=0`。
- 结论：A/C 同口径；drawdown 仅使用当日及历史状态；`0.30` 单位正确；55 次 pilot 条件与绩效复算一致。
- 允许保持参数冻结后扩逐半年。

## 结论与反思

- 决策：`stage001_continue_to_halfyear_if_review_passes`，review 已通过，进入 Stage002。
- 运行后过拟合判断：否；没有根据当前结果改原 Stage013 参数。
- 运行后继续价值判断：有，但异常强结果必须由逐半年独立冷启动验证，不能直接晋级。
- 下一步：运行 `2020-01` 到 `2026-01` 逐半年 A/C，终点 `2026-06-30`，再拉独立 review。

## 输出

- report：`research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage001_stage013_current_ai_engine/stage013_current_ai_stage001_stage013_current_ai_engine_report_stage001_stage013_current_ai_engine_v1.md`
- summary：`research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage001_stage013_current_ai_engine/stage013_current_ai_stage001_stage013_current_ai_engine_summary_stage001_stage013_current_ai_engine_v1.csv`
- chart：`research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage001_stage013_current_ai_engine/stage013_current_ai_stage001_stage013_current_ai_engine_equity_drawdown_stress_stage001_stage013_current_ai_engine_v1.png`
