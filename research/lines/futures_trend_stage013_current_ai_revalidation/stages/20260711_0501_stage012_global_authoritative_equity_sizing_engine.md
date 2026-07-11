# Stage012 全局权威权益 sizing 三锚点真引擎 A/C

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 真引擎产物时间：`2026-07-11 05:00 CST`
- 独立审查完成时间：`2026-07-11 05:18 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：由 Stage011 账户恒等式问题触发的参数无关正确性实验
- 是否重要突破：是；证明正确 sizing 账本能显著改变路径，但不满足收益/回撤晋级门
- 是否触发 A/B：否；三锚点硬失败，不扩 13 起点、不接正式版或 shadow

## 外部调研与判断

- 本阶段未新增外部策略资料；实现依据为 Stage005/006/011 已验证的重复项、vn.py 正式日结恒等式和候选生成时序。
- 我的判断：账户账本正确性不应以收益好坏决定，必须单独修正并验证；但“正确”不等于“可晋级”，绩效仍须服从预注册的跨锚点硬门。

## 本次变更

- 新增隔离策略/回测脚本：`tools/stage012_global_authoritative_equity_sizing_engine.py`。
- 新增测试：`tools/test_stage012_global_authoritative_equity_sizing_engine.py`。
- 新增参数：仅研究隔离开关 `enable_stage012_global_authoritative_equity_sizing`；不新增收益参数。
- 修改参数：无；风险比例、AI、品种池、退出、止损重试、heat、强平、最大持仓、滑点、手续费、日期和取整均冻结。
- 删除参数/功能：C 臂明确关闭 Stage013 固定 1 手 gate 与 Stage010 ramp，不叠加账户防守结构。
- 新增结果：3 个 C 真引擎、即时成交修正、候选日 sizing 对齐、A 复现、AI parity/usage、权威权益 reconciliation 和三锚点绩效门。
- 修改结果：无历史结果改写；A 直接复用 Stage010 冻结 current C9 产物，并再次与 Stage007 对账。
- 删除结果：无。
- 实盘/CTP/邮件/launchd：全部未改、未连接、未调用订单 API。

## 实现与回测参数

- A：Stage010 manifest 冻结的当前 AI + C9/15w 对照。
- C：A + 全局权威权益 sizing；每笔成交先让 Stage006 计算当前重复项，再立即从 `settled_balance` 和 `estimated_equity` 扣回该笔重复项。
- 每日权威刷新：corrected equity 直接取正式 `_estimate_equity`；旧账反事实只作审计，`legacy = corrected + cumulative_duplicate`。
- 独立起点：`2020-01、2021-01、2022-01`；统一终点 `2026-06-30`；初始资金均为 `150,000`。
- 2022 主口径：从各独立起点累计的 account-history HWM；local-reset 只作辅助。
- 硬门：每个 C 正收益、收益保留 `>=70%`、全期回撤改善 `>=3pp`、2022 account-history 回撤优于 A、broker10 不恶化；任一失败即关闭。

## 回测结果

| 起点/臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 非零日胜率 | 逐笔胜率 | broker10峰值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 A | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| 2020-01 C | 2,714,114.10 | 1709.4094% | -44.8398% | 1.3218 | 322,870 | 624 | 52.7325% | 46.5190% | 60.6900% |
| 2021-01 A | 2,404,539.80 | 1503.0265% | -54.3180% | 1.2873 | 290,880 | 500 | 51.2758% | 45.8498% | 80.7461% |
| 2021-01 C | 1,614,586.20 | 976.3908% | -44.5864% | 1.2790 | 185,490 | 500 | 51.7564% | 46.0317% | 62.2925% |
| 2022-01 A | 319,909.00 | 113.2727% | -39.9820% | 0.6685 | 27,950 | 326 | 49.4327% | 41.4634% | 64.5100% |
| 2022-01 C | 207,673.20 | 38.4488% | -46.6358% | 0.3916 | 20,640 | 301 | 48.7179% | 42.3841% | 63.9737% |

## 锚点硬门

| 起点 | 收益保留 | 全期回撤改善 | 2022 account-history回撤 A/C | 2022改善 | broker10变化 | 结果 |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| 2020-01 | **43.8563%** | +10.5304pp | -43.5218% / -41.2440% | +2.2777pp | -27.6498pp | **收益失败** |
| 2021-01 | **64.9616%** | +9.7315pp | -41.3929% / -40.8065% | +0.5864pp | -18.4535pp | **收益失败** |
| 2022-01 | **33.9436%** | **-6.6537pp** | -35.7859% / -34.9582% | +0.8277pp | -0.5364pp | **收益与全期回撤失败** |

- 三个锚点 C 都正收益、2022 account-history 回撤都小幅改善、broker10 都未恶化。
- 三个锚点收益保留全部低于 `70%`；2022 起点全期最大回撤从 `-39.9820%` 恶化到 `-46.6358%`。
- 最终绩效门：`False`；决策：`stage012_anchor_fail_close_no_parameter_rescue`。

## 账户语义与数据审计

- A 三锚点复用 Stage010 冻结产物，且 Stage010 已逐日复现 Stage007；本阶段 reproduction 再次全部通过。
- C 真引擎运行 `3` 条；权威权益 reconciliation 全通过，最大权益误差 `4.65661e-10`，缺失/重复/区间内多余/终点后/未来交易违规均为 `0`。
- 即时修正覆盖 `624/500/301` 笔成交，Stage006 correction 与 Stage012 immediate correction 均逐笔一一对应；累计重复项分别 `-434,725/-279,240/-38,925`，运行累计误差均为 `0`。
- 候选日 sizing 对齐覆盖 `640/556/463` 天；最大 sizing 权益误差分别 `4.65661e-10/1.16415e-10/0`，正式日结恒等式最大误差 `2.32831e-10`。
- A/C AI 均为 `504` 行、`55` 个 eval_date，normalized hash 均为 `df020c940d576868`；AI usage 和 signal-date 审计通过。
- Stage013/ramp 禁用事件数 `0`。
- Stage012 manifest `62/62` 文件大小、SHA256 和文件集合复核通过；Stage005-012 全部 `41/41` 个 `unittest` 通过，其中 Stage012 `4/4`。
- lineage 明确 `history_database_snapshot_complete=false`；当前冻结产物可审计，未来数据库变化后不承诺字节级重跑。

## 输出根目录故障与处置

- 首次正确性运行把 `ROOT` 错写成 `TOOLS_DIR.parents[4]`，产物落到仓库外 `/Users/bytedance/Desktop/person/research/...`。
- 已先新增失败测试 `test_output_directory_is_inside_current_repository_line`，再把输出根修为当前研究线的 `TOOLS_DIR.parent / outputs / STAGE_ID`。
- 错根产物没有删除，整体隔离到 `/var/tmp/vnpy_stage012_wrong_root_20260711_0500`；正确产物在修复后重新执行真引擎生成。
- 正确输出及 lineage 未引用错根目录；仓库外旧父目录只剩空目录，不参与任何报告、manifest 或结论。

## 独立 agent 审查

- 审查结果：`P0=0/P1=0/P2=3`；数值正确性置信度 `99.9%`，语义/逻辑置信度 `98%`，关闭置信度 `99.9%`。
- 审查独立逐笔复核：duplicate 公式最大误差 `3.64e-12`，即时扣回误差 `5.82e-11`，累计误差 `2.33e-10`；无二次扣减。
- 审查独立落盘复核：authoritative 对正式 `account_equity` 最大误差 `9.31e-10`，完整日结恒等式最大误差 `6.98e-10`；所有候选行同日 estimated equity 最大误差 `9.31e-10`，日内候选权益范围均为 `0`。
- 审查确认 A 六类文件在三个锚点都与 Stage010 冻结源逐行一致；A/C 公共 `65` 个 strategy override 相同，差异仅为 AI 路径/名称、Stage012 开关和明确关闭的 Stage013 参数。
- P2 1：自动 `_immediate_audit` 只核对数量、累计和总和，没有把逐 trade id 公式以及“同日所有候选值唯一”写成硬门；本次由独立审查逐笔补验通过。
- P2 2：Stage012 只有 `4` 个合成单测，缺冻结产物、逐笔映射、硬门和 manifest 的专属集成测试；本次由全线 `41/41` 测试、manifest 和独立产物复算补足当前证据，但未来应在新阶段加强。
- P2 3：lineage 的直接 A 引用列表遗漏 `stop_retry_events`，且 `history_database_snapshot_complete=false`；Stage010 manifest 仍覆盖该文件，不影响当前比较，但限制未来字节级复现。
- 审查员在只读 profile 对比时误调用 `_eligibility()`，使正确目录两份 eligibility CSV 的 mtime 更新；内容、大小和 SHA256 未变化，`62/62` manifest 复核仍通过，不影响结论。
- 审查结论：明确允许并要求关闭 Stage012；不得扩 13 起点、不得晋级、不得参数救援。关闭的是 Stage012 的晋级/继续实验资格，不代表旧错误 sizing 账本的高收益重新有效。

## 输出文件

- report：`outputs/stage012_global_authoritative_equity_sizing_engine/stage013_current_ai_stage012_global_authoritative_equity_sizing_engine_report_stage012_global_authoritative_equity_sizing_engine_v1.md`
- decision：`outputs/stage012_global_authoritative_equity_sizing_engine/stage013_current_ai_stage012_global_authoritative_equity_sizing_engine_decision_stage012_global_authoritative_equity_sizing_engine_v1.json`
- summary：`outputs/stage012_global_authoritative_equity_sizing_engine/stage013_current_ai_stage012_global_authoritative_equity_sizing_engine_summary_stage012_global_authoritative_equity_sizing_engine_v1.csv`
- anchor gates：`outputs/stage012_global_authoritative_equity_sizing_engine/stage013_current_ai_stage012_global_authoritative_equity_sizing_engine_anchor_gates_stage012_global_authoritative_equity_sizing_engine_v1.csv`
- chart：`outputs/stage012_global_authoritative_equity_sizing_engine/stage013_current_ai_stage012_global_authoritative_equity_sizing_engine_anchor_equity_drawdown_stage012_global_authoritative_equity_sizing_engine_v1.png`

## 结论

- 正确性结论：全局权威权益 sizing 已在三个锚点机械闭合，并显著改变后续下单手数和路径。
- 绩效结论：目标失败；收益保留全部低于 `70%`，且 2022 起点全期最大回撤恶化。
- 是否进入下一步：否；不扩 13 起点、不调整风险比例/资本利用率/阈值/方向/品种/日期，不对失败版本做参数救援。
- 当前 C9 研究回测的高收益依赖已证实存在错误内部 sizing 账本；这不等同于实盘券商权益错误，正式实盘路径需另行按 live SOP 审计。

## 过拟合反思

- 运行前：低；修复由账户恒等式唯一决定，没有收益参数。
- 运行后：本阶段本身不是过拟合；三锚点结果全部如实保留，没有根据结果救参。
- 后续风险：在看到 `43.86%/64.96%/33.94%` 后再调风险比例、阈值或选择月份，会成为隐性参数搜索，因此停止。

## 继续价值反思

- 运行前：有；旧 sizing 权益偏差达到十万级，必须知道正确账本的真实路径。
- 运行后：该候选无继续晋级价值；账户正确性发现仍有工程价值，但必须与绩效优化分开处理。
- 07:00 前继续相邻真引擎变体：无价值；Stage010 已失败，Stage012 又触发全部收益硬门，继续顺序试公式只会增加过拟合。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：是，标记 Stage012 语义闭合但绩效失败。
- 追加根目录 `memory.md/back_log.md`：是；属于当前 C9 内部 sizing 账户语义的重要纠错里程碑。
