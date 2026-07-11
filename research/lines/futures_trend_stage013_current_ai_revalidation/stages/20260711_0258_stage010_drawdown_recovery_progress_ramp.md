# Stage010 低水位恢复进度连续释放锚点真引擎 A/C

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 真引擎产物时间：`2026-07-11 02:58 CST`
- 独立审查完成时间：`2026-07-11 03:50 CST`
- P2 测试加固时间：`2026-07-11 03:52 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage009 唯一允许候选的三锚点真实组合引擎证伪
- 是否重要突破：否；2022 独立起点明显改善，但跨起点硬门失败
- 是否触发 A/B：否；不得晋级、不得接正式版、不得扩 13 起点

## 外部调研与判断

- Hsieh/Barmish 的 drawdown-modulated feedback control 从账户 running maximum 定义回撤，并按回撤状态反馈调整风险暴露：<https://arxiv.org/abs/1710.01503>。
- He 的 drawdown-controlled portfolio selection 使用历史高点相关的动态 floor：<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=288321>。
- Mantilla-Garcia 的 dynamic allocation 把损失控制放到账户资产与现金的动态分配层：<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=223323>。
- 本阶段判断：连续恢复进度比固定 1 手自由度更低，也更符合“新低防守、恢复后释放”的账户状态逻辑；但该理论不能替代跨起点证伪。2021-01 锚点的账户历史高水位 2022 回撤恶化后，必须按预声明关闭。

## 本次变更

- 新增策略隔离脚本：`tools/stage010_drawdown_recovery_progress_ramp.py`。
- 新增测试：`tools/test_stage010_drawdown_recovery_progress_ramp.py`。
- 新增参数/状态：沿用 `30%` 深回撤线、`active_positions<=1`、最小 `1` 手；新增 episode 是否激活、episode 内最大回撤和恢复进度状态。
- 修改参数：无；未修改 C9、AI、止损重试、退出、保证金、broker10 或风险基数。
- 删除参数：Stage010 C 臂明确关闭 Stage013 固定 1 手 gate，二者不叠加。
- 实盘/CTP/邮件/launchd：全部未改、未连接、未调用订单 API。

## 冻结公式与回测参数

- A：当前 AI + 当前 C9/15w。
- C：A + Stage006 权威权益跟踪 + Stage010 恢复进度 ramp。
- 独立起点：`2020-01、2021-01、2022-01`；统一终点 `2026-06-30`；初始资金均为 `150,000`。
- 回撤主口径：从每个独立起点开始的账户历史高水位；2022 local-reset 只作辅助。
- 公式：`progress=clip((episode_peak_dd-current_dd)/(episode_peak_dd-0.30),0,1)`。
- 手数：`after=min(before,1+floor((before-1)*progress))`。
- 新低处为 1 手；恢复到 30% 边界时回到原计划手数；没有年份、品种、方向、AI/OI 或事后 PnL 例外。
- 硬门：三锚点 C 正收益、收益保留 `>=70%`、全期回撤改善 `>=3pp`、broker10 不恶化，并且三个起点的 2022 account-history 回撤都必须优于 A；任一失败即关闭公式。

## 回测结果

| 起点/臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 非零日胜率 | 逐笔胜率 | broker10峰值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 A | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| 2020-01 C | 4,701,513.40 | 3034.3423% | -40.0625% | 1.4013 | 520,880 | 641 | 52.5763% | 44.9541% | 88.3322% |
| 2021-01 A | 2,404,539.80 | 1503.0265% | -54.3180% | 1.2873 | 290,880 | 500 | 51.2758% | 45.8498% | 80.7461% |
| 2021-01 C | 1,964,216.40 | 1209.4776% | -43.4546% | 1.2743 | 205,100 | 499 | 51.2881% | 44.0476% | 80.4611% |
| 2022-01 A | 319,909.00 | 113.2727% | -39.9820% | 0.6685 | 27,950 | 326 | 49.4327% | 41.4634% | 64.5100% |
| 2022-01 C | 309,106.30 | 106.0709% | -33.4619% | 0.6737 | 24,130 | 317 | 49.7537% | 42.1384% | 64.5100% |

## 锚点硬门

| 起点 | 收益保留 | 全期回撤改善 | 2022 account-history回撤 A/C | 2022改善 | broker10变化 | 结果 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| 2020-01 | 77.8485% | +15.3076pp | -43.5218% / -40.0625% | +3.4592pp | -0.0076pp | 通过 |
| 2021-01 | 80.4695% | +10.8633pp | -41.3929% / -43.4546% | **-2.0617pp** | -0.2849pp | **硬失败** |
| 2022-01 | 93.6421% | +6.5201pp | -35.7859% / -33.3495% | +2.4364pp | 0pp | 通过 |

- 2022-01 独立起点相对 Stage007 固定 1 手的收益保留 `57.7149%`，提升到 `93.6421%`；C 总收益从 `65.3752%` 提升到 `106.0709%`。
- 但 2021-01 的 2022 local-reset 显示 `+7.4050pp`，账户历史高水位主口径却恶化 `2.0617pp`。不能用局部窗口重置、全期回撤或收益保留掩盖该硬失败。
- 最终绩效门：`False`；决策：`stage010_anchor_fail_close_formula_no_parameter_rescue`。

## 语义与数据审计

- A 三锚点逐日复现 Stage007，核心日线最大绝对差 `4.65661e-10`。
- C 三锚点权威权益 reconciliation 全通过，最大权益误差 `2.79397e-9`；缺失日、重复日、区间内多余日、终点后日、未来交易均为 `0`。
- Ramp 事件 `61/65/14`，合计 `140`；公式、回撤线、episode peak、progress 区间、active positions 和手数边界违规均为 `0`。
- 候选重建覆盖 `61/65/14`，candidate/event mismatch 和事件权威回撤 mismatch 均为 `0`。
- Episode 日状态分别 `1571/1328/1085` 行，缺失、重复、区间外和状态递推违规均为 `0`。
- A/C AI 都为 `504` 行、`55` 个 eval_date，normalized hash 均为 `df020c940d576868`；AI usage、signal date 和未来日期审计通过。
- Stage013 固定 1 手已关闭，事件数 `0`。
- Stage010 manifest `64/64` 文件大小和 SHA256 校验通过；Stage006-010 相关测试最终 `27/27` 通过。

## 独立 agent 审查

- 独立 reviewer：Stage009 reviewer 的增量复核；`P0=0/P1=1/P2=2`。
- 数值正确性置信度 `99.5%`；语义正确性置信度 `95%`。
- P1：2021-01 起点在账户历史高水位口径下，2022 最大回撤从 A `-41.3929%` 恶化为 C `-43.4546%`，改善值为 `-2.061718pp`，真实触发预声明失败；必须 fail-close。
- P2：原负例测试只改结果字段且仅保留一个锚点，实际由“锚点数量不足”失败，属于假覆盖。已改为完整三锚点，并由 `_anchor_gate_row` 重算 2021 负例，验证单锚点和总门同时关闭；测试 `7/7` 通过。
- P2：lineage 明确 `history_database_snapshot_complete=false`。当前冻结产物可审计，但未来数据库变化后不能承诺字节级重跑；该限制无法通过策略代码修复。
- 审查结论：禁止改 rounding、30% 触发线、最小手数、episode 定义或加入质量豁免；禁止扩 13 起点。

## 输出文件

- report：`outputs/stage010_drawdown_recovery_progress_ramp/stage013_current_ai_stage010_drawdown_recovery_progress_ramp_report_stage010_drawdown_recovery_progress_ramp_v1.md`
- decision：`outputs/stage010_drawdown_recovery_progress_ramp/stage013_current_ai_stage010_drawdown_recovery_progress_ramp_decision_stage010_drawdown_recovery_progress_ramp_v1.json`
- summary：`outputs/stage010_drawdown_recovery_progress_ramp/stage013_current_ai_stage010_drawdown_recovery_progress_ramp_summary_stage010_drawdown_recovery_progress_ramp_v1.csv`
- anchor gates：`outputs/stage010_drawdown_recovery_progress_ramp/stage013_current_ai_stage010_drawdown_recovery_progress_ramp_anchor_gates_stage010_drawdown_recovery_progress_ramp_v1.csv`
- chart：`outputs/stage010_drawdown_recovery_progress_ramp/stage013_current_ai_stage010_drawdown_recovery_progress_ramp_anchor_equity_drawdown_stage010_drawdown_recovery_progress_ramp_v1.png`

## 结论

- Stage010 有局部机制价值：它解决了 2022-01 固定 1 手恢复过慢的问题，同时保留 `93.64%` 收益并改善全期回撤 `6.52pp`。
- Stage010 没有晋级价值：同一公式在 2021-01 起点的 2022 account-history 回撤恶化，说明风险改善不具备锚点一致性。
- 最终目标未完成；当前不存在通过全部硬门的候选。
- 07:00 前不再启动第二个新真引擎形状。Stage009 只允许一次结构候选，该额度已由 Stage010 使用；失败后临时选择第二公式属于顺序试错和隐性调参。

## 过拟合反思

- 运行前：低到中等。公式无参数扫描，但方向来自 2022 恢复缺口。
- 运行后：Stage010 本身没有救参，不能称为参数过拟合；但结果明显偏向 2022。若继续改阈值、取整或连续试第二结构，会转为结果驱动过拟合。

## 继续价值反思

- 继续 Stage010 公式：无价值，硬门已失败。
- 继续立即跑新真引擎：无价值，既有连续 DD 降仓、固定手数、现金储备和质量豁免路线均已关闭。
- 保留只读归因价值：有。未来若重新开题，应先解释 2021-01 账户历史高水位恶化，再在新阶段预声明真正不同的信息源或结构。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是，登记本线并标记候选关闭。
- 追加根目录 `back_log.md`：是，Stage005-010 属于重要账户语义纠错与负面里程碑。
