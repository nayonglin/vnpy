# Stage009 全起点 gate 机会成本归因

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 初次归因时间：`2026-07-11 00:57 CST`
- 加固复跑时间：`2026-07-11 01:21 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage007 原始产物只读归因，不是新策略回测
- 是否重要突破：是；纠正 2022 回撤主口径并确定唯一低自由度候选方向
- 是否触发 A/B：否；没有修改策略或生成新绩效

## 外部调研与判断

- Hsieh/Barmish《On Drawdown-Modulated Feedback Control in Stock Trading》从账户 running maximum 定义 drawdown，并让风险暴露随 drawdown 状态反馈变化。
- He《Drawdown Controlled Optimal Portfolio Selection with Linear Constraints on Portfolio Weights》使用历史高点相关的动态 floor；Mantilla-Garcia《Dynamic Allocation Strategies for Absolute and Relative Loss Control》强调在风险资产和现金之间动态分配。
- 我的判断：后续应使用账户历史高水位做主风险口径，并用连续账户状态释放风险；固定手数和从事后标签挑 AI/OI 豁免都缺乏跨周期依据。

## 本次变更

- 新增脚本：`tools/stage009_gate_opportunity_cost_attribution.py`
- 新增测试：`tools/test_stage009_gate_opportunity_cost_attribution.py`
- 修改策略：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 实盘/CTP/邮件/launchd：全部未改、未连接、未调用订单 API

## 归因参数与口径

- 输入：Stage007 的 13 个独立半年起点 A/C daily、entry candidates、trades、closed lots、pilot events、pilot audit 和 manifest。
- 事件覆盖：有事件起点 `2020-01/07、2021-01/07、2022-01/07`；其余 7 个起点显式保留为零事件审计行。
- 映射键：signal date、合约、方向、signal、opened candidate；开仓必须为下一交易日，随后按 open trade id 汇总同日重试和 closed lots。
- 同路径线性反事实：`C毛 realized PnL * selected_before / selected_after`。它不含佣金、滑点、权益、保证金、loss streak、后续信号和仓位反馈，只能作方向归因，不能当策略净绩效。
- 回撤主口径：从独立起点开始保留完整账户历史 `cummax`；局部窗口重置高水位只作辅助对照。

## 结果

- 路径事件 `237/237`，C/A 映射均 `237/237`；实际 open/closed lot 两边各 `242/242`，多出的 5 笔为同日止损重试。
- 下一交易日日历间隔：`1天=215、3天=19、春节10天=3`；最长 10 天均正确映射。
- 237 条是路径事件，不是独立样本；按 `signal_date+vt_symbol+direction+signal` 去重只有 `67` 个市场信号，其中 `63` 个跨起点重复，最高重复 6 次。
- Stage007 manifest `179/179` 在 Stage009 启动时 fail-closed 校验通过；Stage009 自身 manifest `10/10` 通过。

### 按起点的同路径毛损益归因

| 起点 | 事件 | C实际毛PnL | A同信号毛PnL | 按原手数线性值 | 压掉盈利 | 避免亏损 | 线性净差 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 | 58 | 16,955 | 331,140 | -291,460 | 2,220,885 | 2,529,300 | -308,415 |
| 2020-07 | 40 | 5,385 | -209,260 | -528,635 | 1,150,150 | 1,684,170 | -534,020 |
| 2021-01 | 63 | 15,495 | 68,500 | -299,365 | 918,045 | 1,232,905 | -314,860 |
| 2021-07 | 15 | -1,125 | -1,940 | -27,495 | 31,840 | 58,210 | -26,370 |
| 2022-01 | 29 | 3,970 | 10,775 | 11,720 | 41,910 | 34,160 | +7,750 |
| 2022-07 | 32 | -2,170 | -13,625 | -26,570 | 70,470 | 94,870 | -24,400 |

- 全体同路径线性值 `-1,161,805`；不能据此恢复原仓位。
- 固定 2 手在 `2022-01` 的同路径直接毛增益只约 `3,970`，而 70% 保留目标的期末权益缺口为 `20,873.5`，且会额外暴露 2023 路径亏损，不进入真实引擎。
- AI rank7+、非 OI-confirmed 等分桶事后较好，但只有 67 个去重信号、方向违反稳定“高质量”直觉，禁止据此挑豁免规则。

### 2022 双回撤口径

| 起点 | Account-history A/C | 主口径改善 | Local-reset A/C | 辅助口径改善 |
| --- | --- | ---: | --- | ---: |
| 2020-01 | -43.5218% / -40.0046% | +3.5171pp | -43.5218% / -31.5110% | +12.0107pp |
| 2021-01 | -41.3929% / -43.2622% | **-1.8693pp** | -41.3929% / -32.5808% | +8.8121pp |
| 2022-01 | -35.7859% / -33.3495% | +2.4364pp | 相同 | +2.4364pp |

- 结论：旧 local-reset 会显著高估 2020/2021 起点的 2022 风险改善；尤其 2021-01 路径在真实账户历史高水位口径下反而恶化 `1.8693pp`。

## 测试与加固

- 初版测试 `5/5` 通过；独立审查后补到 `8/8`：账户历史高水位、同日重试、候选歧义、下一交易日、分批平仓量守恒、线性反事实边界、零事件 coverage、manifest 篡改 fail-closed。
- 真实数据 C/A 均 237 条下一交易日与开平量守恒通过；当前样本没有真实分批平仓，分支由合成测试覆盖。
- 独立 review 后把 `path_events_are_independent_samples=false`、`feature_buckets_allowed_for_rule_selection=false`、`closed_lot_realized_pnl_includes_costs=false` 写入 decision。

## 独立 agent 审查

- `P0=0/P1=1/P2=4`；数字/语义置信度 `99.5%/91%`。
- P1：237 路径事件只有 67 个去重市场信号，特征分桶不能按 237 个独立样本解释；已明确降级为探索标签并禁止选规则。
- P2：下一交易日、signal、开平量和部分平仓防错不足；已补下一交易日、非空 signal 冲突、逐 open id 平仓量守恒和合成部分平仓测试。
- P2：反事实为毛损益且不可执行；报告和 decision 已明确。
- P2：历史数据库未完整快照，Stage007/006 当前源码与当时 hash 已不同；该限制仍保留，不能宣称未来字节级重跑。
- P2：报告/测试/独立记录不完整；本记录和加固复跑已补主要缺口。

## 输出文件

- report：`outputs/stage009_gate_opportunity_cost_attribution/stage013_current_ai_stage009_gate_opportunity_cost_attribution_report_stage009_gate_opportunity_cost_attribution_v1.md`
- events：`outputs/stage009_gate_opportunity_cost_attribution/stage013_current_ai_stage009_gate_opportunity_cost_attribution_event_attribution_stage009_gate_opportunity_cost_attribution_v1.csv.gz`
- coverage：`outputs/stage009_gate_opportunity_cost_attribution/stage013_current_ai_stage009_gate_opportunity_cost_attribution_coverage_stage009_gate_opportunity_cost_attribution_v1.csv`
- drawdown：`outputs/stage009_gate_opportunity_cost_attribution/stage013_current_ai_stage009_gate_opportunity_cost_attribution_drawdown_windows_stage009_gate_opportunity_cost_attribution_v1.csv`
- chart：`outputs/stage009_gate_opportunity_cost_attribution/stage013_current_ai_stage009_gate_opportunity_cost_attribution_opportunity_cost_stage009_gate_opportunity_cost_attribution_v1.png`

## 结论

- 本阶段结论：`stage009_attribution_complete_one_structural_test_allowed`。
- 允许且只允许一个真实引擎候选：基于账户历史高水位和本次深回撤 episode 低水位的恢复进度，连续释放原计划仓位；不增加年份、品种、方向、AI/OI 或固定手数阈值。
- 最终目标：未完成；`2022-01` 收益保留仍为 `57.7149%`，本阶段没有新回测。

## 过拟合反思

- 运行前：低；全 13 起点统一映射，无策略参数。
- 运行后：映射本身低；若从探索分桶挑 AI/OI 规则则高，已禁止。
- 原因：67 个去重信号不足以支持事后特征选择，连续账户状态公式自由度更低。

## 继续价值反思

- Stage009 继续细分标签：无价值。
- 唯一连续恢复候选：有价值；它直接解决固定 1 手无法自行恢复的结构死锁，并仍在新低保持最小暴露。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：待 Stage010 锚点结果后统一更新。
- 追加根目录 `back_log.md`：待 Stage010 锚点结果后与 Stage005-009 里程碑统一追加。
