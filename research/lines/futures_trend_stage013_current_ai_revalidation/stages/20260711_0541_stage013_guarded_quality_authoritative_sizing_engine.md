# Stage013 正确账本 + guarded quality 25% 三锚点真引擎

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 预声明时间：`2026-07-11 05:32 CST`
- 初版真引擎产物时间：`2026-07-11 05:41 CST`；独立审查发现 P1 后隔离
- 修复版真引擎产物时间：`2026-07-11 06:24 CST`；cap ratio 自动硬门修正后最终重跑 `06:45 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage012 正确账本上的唯一冻结右尾恢复候选
- 是否重要突破：否；恢复了 2021/2022 收益，但跨锚点硬门失败
- 是否触发 A/B：否；不扩 13 起点、不接正式版或 shadow

## 外部调研与判断

- [Trends' Signal Strength and the Performance of CTAs](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2772047) 支持趋势信号更强时提高风险暴露这一类机制，但不能证明本项目的 AI rank 选择器有效。
- [Markowitz Meets Technical Analysis](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4106932) 支持由趋势信号参数化组合权重；[Enhancing Time Series Momentum Strategies Using Deep Neural Networks](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3369195) 说明信号和仓位可联合优化，同时也意味着更高的模型复杂度和过拟合风险。
- 我的判断：文献只支持“按信号质量差异化配置风险”的方向，不替代本项目的真实组合引擎证据。Stage013 的冻结 selector 必须服从预声明三锚点硬门；本次结果不能因 2021/2022 收益好而放宽 2020 和回撤门。

## 本次变更

- 新增隔离策略/回测脚本：`tools/stage013_guarded_quality_authoritative_sizing_engine.py`。
- 新增测试：`tools/test_stage013_guarded_quality_authoritative_sizing_engine.py`；初版 `4` 个，P1 修复后增至 `9` 个。
- 新增参数：仅研究隔离开关 `enable_stage013_guarded_quality_overlay`；quality 规则固定为 `AI rank 1-8 + selected_volume>1 + risk_multiplier<2`，风险 floor 固定 `25%`。
- 修改参数：无；风险比例、AI、品种池、退出、止损重试、heat、强平、最大持仓、滑点、手续费、日期和 Stage012 权威账本均冻结。
- 删除参数/功能：明确不含 OI、xsmom、RSI、ceil、最小加 1 手、Stage013 account-state gate 和 Stage010 ramp。
- 新增结果：3 个 C 真引擎、A/B/C 三锚点对比、quality 计划事件、权威权益 reconciliation、即时成交修正、候选日 sizing、AI parity/usage、决策、lineage、图表和 manifest。
- 修改结果：05:41 初版因 quality 在最终风险门后加手而作废并隔离；修复后 A/B 继续复用 Stage012 冻结产物，C 三锚点全部重跑。
- 删除结果：无。
- 实盘/CTP/邮件/launchd：全部未改、未连接、未调用订单 API。

## 实现与回测参数

- A：旧 current C9/15w 目标参照；只作为用户原目标的收益和回撤参照，不代表正确 sizing 账本。
- B：Stage012 全局权威权益 sizing 冻结源。
- C：B + guarded quality 25% floor；在基础 volume-tilt hook 中对 `flat_entry` 提出 `floor(before * 1.25)` 请求，条件为 AI rank 1-8、原计划手数大于 1、risk multiplier 小于 2；请求先受 Stage830 broker10 可承受手数约束，再进入基础 incremental margin gate，最终只记录仍高于 before 的计划增量。
- 独立起点：`2020-01、2021-01、2022-01`；统一终点 `2026-06-30`；初始资金均为 `150,000`。
- 2022 主口径：从各独立起点累计的 account-history HWM；local-reset 只作辅助。
- 硬门：每个 C 正收益、相对 A 收益保留 `>=70%`、全期回撤至少改善 `3pp`、2022 account-history 回撤优于 A、broker10 不恶化、且 C 收益高于 B；任一失败即关闭。

## 回测结果

| 起点/臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 非零日胜率 | 逐笔胜率 | broker10峰值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 A | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| 2020-01 B | 2,714,114.10 | 1709.4094% | -44.8398% | 1.3218 | 322,870 | 624 | 52.7325% | 46.5190% | 60.6900% |
| 2020-01 C | 3,258,773.10 | 2072.5154% | -42.1405% | 1.3636 | 365,670 | 624 | 52.6829% | 46.6877% | 66.6180% |
| 2021-01 A | 2,404,539.80 | 1503.0265% | -54.3180% | 1.2873 | 290,880 | 500 | 51.2758% | 45.8498% | 80.7461% |
| 2021-01 B | 1,614,586.20 | 976.3908% | -44.5864% | 1.2790 | 185,490 | 500 | 51.7564% | 46.0317% | 62.2925% |
| 2021-01 C | 1,993,959.60 | 1229.3064% | -43.2564% | 1.3392 | 226,690 | 501 | 51.5625% | 46.8504% | 66.3986% |
| 2022-01 A | 319,909.00 | 113.2727% | -39.9820% | 0.6685 | 27,950 | 326 | 49.4327% | 41.4634% | 64.5100% |
| 2022-01 B | 207,673.20 | 38.4488% | -46.6358% | 0.3916 | 20,640 | 301 | 48.7179% | 42.3841% | 63.9737% |
| 2022-01 C | 383,674.50 | 155.7830% | -45.4853% | 0.7575 | 37,050 | 330 | 49.8377% | 43.7126% | 63.8943% |

## 锚点硬门

| 起点 | C/A收益保留 | 全期回撤改善 | 2022 account-history回撤 A/C | 2022改善 | C-B收益增量 | broker10变化 | 结果 |
| --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| 2020-01 | **53.1720%** | +13.2296pp | -43.5218% / -41.2566% | +2.2652pp | +363.1060pp | -21.7218pp | **收益失败** |
| 2021-01 | 81.7887% | +11.0616pp | -41.3929% / -41.1428% | +0.2501pp | +252.9156pp | -14.3474pp | 通过 |
| 2022-01 | 137.5292% | **-5.5032pp** | -35.7859% / -36.0771% | **-0.2912pp** | +117.3342pp | -0.6157pp | **回撤失败** |

- C 在三个锚点都正收益、都高于 B，broker10 都未高于 A。
- 2020 起点收益保留只有 `53.1720%`，仍明显低于 `70%`。
- 2022 起点虽然收益从 A 的 `113.2727%` 提高到 `155.7830%`，但全期最大回撤从 `-39.9820%` 恶化到 `-45.4853%`，2022 account-history 回撤也恶化 `0.2912pp`。
- 最终绩效门：`False`；决策：`stage013_anchor_fail_close_no_parameter_rescue`。

## 2022 回撤归因

- A：高点 `2022-07-15` 权益 `178,230`，低点 `2023-07-05` 权益 `106,970`，最大回撤 `-39.9820%`。
- B：高点 `2022-03-30` 权益 `174,780`，低点 `2023-07-05` 权益 `93,270`，最大回撤 `-46.6358%`。
- C：高点 `2022-07-15` 权益 `207,100`，低点 `2023-07-05` 权益 `112,900`，最大回撤 `-45.4853%`。
- Quality 单腿抬高了 2022 年中高点并最终提高收益，但没有消除随后到 2023-07-05 的同一亏损区间；因此“最终赚得更多”和“峰谷回撤比例更差”可以同时成立。
- 该归因不使用事后按品种/方向筛选来生成新规则；不据此调 rank、比例、月份或品种。

## 语义与数据审计

- Quality 最终风险门后计划事件为 `108/85/33` 条，计划增加手数合计 `943/582/79`；请求增量总计 `1,643` 手，broker10/incremental gate 后保留 `1,604` 手。Floor 请求公式最大误差 `0`，事件键重复 `0`，按日期/产品/合约/方向/信号/AI signal date 映射缺失或歧义 `0`，候选 selected volume 不一致 `0`。
- `5` 条请求被 broker10 cap 缩减；最终计划事件的 projected broker10 最大值 `99.9914%`，超过 100% 的事件为 `0`。
- 上述 `1,604` 手是候选生成阶段穿过最终风险门的**计划增量**，不是最终实际成交增量。后续价格变化、组合路径和订单执行仍可能改变成交；不得把该数字解释成已执行加仓手数。
- 保守成交映射中 `222/226` 条有后续开仓，`211/226` 条首次成交量等于计划；`4` 条未成交，`11` 条成交量不同。该映射只界定计划/成交边界，不把成交差异反推为策略规则。
- 权威权益 reconciliation 全部通过，最大权益误差 `4.65661e-10`；缺失日期、重复日期、区间内多余行、终点后行和未来交易违规均为 `0`。
- 即时修正覆盖 C 的 `624/501/330` 笔成交；累计修正分别 `-224,710/-323,145/-101,190`，逐日运行累计误差为 `0`。
- 候选日 sizing 对齐覆盖 `640/556/461` 天；最大 sizing 权益误差 `4.65661e-10`。
- A/B/C AI 均为 `504` 行、`55` 个 eval_date，normalized hash 均为 `df020c940d576868`；AI usage、signal-date 和未来日期审计通过。
- Stage013 gate/ramp/OI/ceil 禁用事件数 `0`。
- A/B 三锚点复用 Stage012 冻结曲线，全部日期连接成功，最大逐日误差 `0`；Stage012 源 manifest 通过。
- Stage013 manifest `47/47` 文件大小、SHA256 和文件集合复核通过；Stage005-013 全部 `50/50` 个 `unittest` 通过，其中 Stage013 `9/9`。
- lineage 已加入 Stage012 manifest 的路径和 SHA256；Stage013 tool/test 及上游 frozen proxy 的 hash 均落盘。
- lineage 明确 `history_database_snapshot_complete=false`；当前冻结产物可审计，未来数据库变化后不承诺字节级重跑。

## 独立 agent 审查

- 初审：`P0=0/P1=1/P2=3`。P1 确认 05:41 初版在基础 broker10 cap 和 incremental margin gate 之后直接加手；`15/236` 条事件从不超过 100% 变为超过 100%，最高 `106.5336%`，且 `17` 条计划随后被 forced-margin 部分或全部抵消。初版 `semantics_ok=true` 不成立，整批产物隔离到 `/var/tmp/vnpy_stage013_pre_review_p1_20260711_0541`。
- 修复：先增加失败测试，再把 quality 请求移到基础 `_apply_selection_pairwise_volume_tilt` hook；请求先受 broker10 max-affordable 约束，之后由原基础方法执行 incremental gate，返回计划只做 finalization，不二次加手。测试由 `4` 个增至 `9` 个，并加入 broker10、风险门吞掉增量、禁止二次加手、AI PIT 和 cap 后公式审计。
- 修复版首轮复审：`P0=0/P1=0/P2=2`，数字/语义/fail-close 置信度 `99.9%/97%/99.99%`，允许并要求 `stage013_anchor_fail_close_no_parameter_rescue`。审查确认风险顺序、226 条计划事件、权威账本、A/B 冻结复用、AI、指标和 manifest 均闭合。
- P2 1：审查发现自动 audit 的 cap ratio 因 sizing 未携带字段而成为 `inf`；独立复算虽确认最大 `99.9914%`、违规 `0`，仍按 TDD 从策略参数注入真实 `1.0` 并于 06:45 重跑。当前 226 行 cap ratio 全为 `1.0`，自动违规数 `0`。
- P2 2：`226` 条和 `1,604` 手仍是风险门后计划，不是成交；已按 `222/211/4/11` 显式披露，不把计划量称为成交量。
- 增量终审：`P0=0/P1=0/P2=1`；cap-ratio P2 已关闭，226 行 ratio 全为 `1.0`、breach `0`，Stage013 manifest `47/47`、tool/test/lineage SHA 和全线测试 `50/50` 复核通过。三锚点数字与 06:24 批最大差 `<5e-11`。
- 唯一剩余 P2：226 条和 `1,604` 手只能称最终风险门后的计划增量，不能称实际成交增量；本记录已按该边界表述。
- 最终数字/语义/fail-close 置信度：`99.99%/99%/99.99%`；允许并要求关闭，不扩样本、不救参。

## 输出文件

- report：`outputs/stage013_guarded_quality_authoritative_sizing_engine/stage013_current_ai_stage013_guarded_quality_authoritative_sizing_engine_report_stage013_guarded_quality_authoritative_sizing_engine_v1.md`
- decision：`outputs/stage013_guarded_quality_authoritative_sizing_engine/stage013_current_ai_stage013_guarded_quality_authoritative_sizing_engine_decision_stage013_guarded_quality_authoritative_sizing_engine_v1.json`
- summary：`outputs/stage013_guarded_quality_authoritative_sizing_engine/stage013_current_ai_stage013_guarded_quality_authoritative_sizing_engine_summary_stage013_guarded_quality_authoritative_sizing_engine_v1.csv`
- anchor gates：`outputs/stage013_guarded_quality_authoritative_sizing_engine/stage013_current_ai_stage013_guarded_quality_authoritative_sizing_engine_anchor_gates_stage013_guarded_quality_authoritative_sizing_engine_v1.csv`
- chart：`outputs/stage013_guarded_quality_authoritative_sizing_engine/stage013_current_ai_stage013_guarded_quality_authoritative_sizing_engine_anchor_equity_drawdown_stage013_guarded_quality_authoritative_sizing_engine_v1.png`

## 结论

- 正确性结论：Stage012 权威权益账本在 Stage013 三个 C 锚点继续机械闭合；AI 月池和输入一致。
- 绩效结论：目标失败。Quality 单腿明显恢复 2021/2022 的右尾收益，但没有同时解决 2020 收益保留和 2022 峰谷回撤。
- 是否进入下一步：否；不扩 13 起点、不修改 `25%/rank/risk_multiplier/floor`、不叠加 OI，不对失败版本做参数救援。
- 不影响实盘：本阶段只新增隔离研究脚本、测试、记录和回测产物，没有修改正式策略入口或执行配置。

## 过拟合反思

- 运行前：低到中等。规则来自本轮之前冻结的上游 proxy，不是看到 Stage012 结果后扫描出来；但 quality selector 本身仍需跨锚点证伪。
- 运行后：没有按结果救参，因此本阶段的评估过程未形成新的参数过拟合；候选本身跨锚点不稳定，不能晋级。
- 后续风险：根据本次 `2020/2022` 失败再调比例、rank、年份、品种或方向，会直接转化为隐性多重检验，因此停止。

## 继续价值反思

- 运行前：有；它是 Stage012 正确账本上唯一尚未被单腿真引擎证伪、且机制上能恢复右尾的冻结候选。
- 运行后：该版本无继续晋级价值；它证明 quality 暴露确实能恢复收益，但也证明单靠该腿不能跨周期压低回撤。
- 继续相邻 quality/OI/xsmom/rank/比例变体：无价值；会违反预声明停止边界并放大过拟合。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是，标记 Stage013 收益恢复但跨锚点绩效失败。
- 追加根目录 `back_log.md`：是；属于“正确账本 + 冻结 quality 单腿”的重要证伪结果。
- 追加根目录 `memory.md`：否；未形成可晋级正式候选。

## 07:00 截止审计

- 审计时间：`2026-07-11 06:56 CST`；未再启动新实验，符合“不晚于 07:00 停止”的边界。
- 收益要求：未达到。2020 起点 C/A 收益保留 `53.1720% < 70%`。
- 回撤要求：未达到。2022 起点全期最大回撤相对 A 恶化 `5.5032pp`，2022 account-history 回撤恶化 `0.2912pp`。
- 语义要求：达到。最终独立 review `P0=0/P1=0/P2=1`；唯一 P2 为计划量不等于成交量，已明确披露。
- 验证要求：Stage005-013 测试 `50/50`、Stage012/013 manifest `62/62、47/47`、cap ratio `226/226=1.0`、broker10 违规 `0`、`git diff --check` 均通过；后台研究进程为 `0`。
- 最终状态：用户目标仍未完成，不能把 Stage013 标记为成功或晋级；本轮按时间和过拟合停止边界结束，目标保持未完成。
