# Stage027 正式 Q 换月新合约自身历史修复 A/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-26 13:50 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/fix-rollover-new-contract-history` / `codex/fix-rollover-new-contract-history`
- 阶段性质：基于当前正式 Q 的单变量语义修复与 A/C 真引擎回测
- 是否重要突破：否；修复语义成立，但完整周期绩效门失败
- 是否触发A/B：是，`A=当前正式Q`，`C=正式Q+新主力自身日K换月形态`

## 外部调研与判断

- 参考资料：vn.py 官方 GitHub `ArrayManager` 源码与 CTA 文档；`ArrayManager` 维护单一标的时间序列，指标窗口需要相应历史长度。
- 我的判断：换月执行合约已经改变时，是否在新主力继续持仓应由新合约自身可见历史判断，而不是由旧主力复权序列替代。该修复不针对某个收益窗口或参数寻优，规则层过拟合风险低。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/qmt_roll_candidate_stage027_target_contract_history_config.py`。
- 新增脚本：`research/lines/futures_trend_rollover_shape_same_volume/tools/stage027_q_target_contract_history_ac.py`。
- 新增测试：`tests/test_stage027_q_target_contract_history.py`。
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py` 的共享 `target_contract_only` 分支补齐当日行情与合约元数据 fail-closed；活动正式 Q 仍使用 `backwards_ratio_continuous`，正式配置、正式物料和生产目录未修改。
- 删除脚本：无。
- 新增参数：候选版本 `stage027_q_target_contract_history_v1`；无新增数值参数。
- 修改参数：仅 `rollover_shape_history_mode: backwards_ratio_continuous -> target_contract_only`。
- 删除参数：不再在候选换月形态中使用旧主力 backward-ratio 复权历史；其余 Q 参数完整保留。

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-08-25`，统计首日 `2018-01-02`。
- 账户规模：`150,000`。
- 成本口径：沿用当前正式 Q/C9 的费率、滑点、合约乘数、broker10 保证金口径。
- 样本过滤：当前正式 AI 池与产品池；换月候选 C 需要新主力自身至少 `40` 根可见日K，策略 `ArrayManager size=41`。
- 策略/归因口径：A/C 都使用正式 ruleset `stage021_q_rollover_volume_atr_v1`；C 唯一改变换月形态历史来源。
- 数据快照：从生产目录复制只读 SQLite 快照到隔离 worktree；JM2701 截至 `2026-08-19` 有 `79` 根日K。

## 结果

### A 当前正式 Q

- 期末权益：`14,989,515.10`
- 总收益：`9893.0101%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.468555`
- 总滑点：`1,741,690`
- 总交易次数：`846`
- 胜率：`52.6728%`（非零交易日胜率）
- 其他关键指标：broker10 峰值 `99.6724%`，超过100%天数 `0`。

### C 新主力自身历史修复版

- 期末权益：`13,868,439.90`
- 总收益：`9145.6266%`
- 最大回撤：`-47.9843%`
- Sharpe：`1.418929`
- 总滑点：`1,685,830`
- 总交易次数：`834`
- 胜率：`52.6274%`（非零交易日胜率）
- 其他关键指标：broker10 峰值 `87.7838%`，超过100%天数 `0`。

### A/C 差异与合同

- C-A 期末权益 `-1,121,075.20`，收益 `-747.3835pp`，最大回撤恶化 `-3.0810pp`，Sharpe `-0.049627`。
- C 滑点减少 `55,860`，为 A 的 `96.7928%`；交易减少 `12`；broker10 峰值改善 `11.8886pp`。
- A 的24次换月为 `23` 次 targeted、`1` 次 skipped；C 为 `15` 次 targeted、`9` 次 skipped，其中 `5` 次因新主力不足40根，另外4次因自身形态/MACD不一致或容量为零。
- 候选24次诊断全部满足 `history_mode=target_contract_only`、`history_source=target_contract_observed`、`source_count=target_count`、`roll_adjustment_ratio=1.0`；所有续开样本均至少40根。
- JM2701 专项：截至8月19日数据库79根，策略取最近41根；`MA5=1528.2 > MA10=1484.8 > MA20=1440.05`，但 `MA20 < MA40=1462.925`，MACD histogram `42.946968 > 0`，多头完整排布不成立，预期动作是 `skip`。
- 完整回测在8月19日没有持有 JM，故不会自然触发 JM 换月；专项验收使用相同策略函数和点时截止数据，不把该账户路径差异伪装成完整回测事件。

## 输出文件

- report/decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_decision.json`
- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_ac_summary.csv`
- comparison：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_ac_comparison.csv`
- daily/equity：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_ac_curve.csv`
- orders/trades：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_trades.csv`
- quality：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_rollover_diagnostics.csv`
- chart：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage027/stage027_full_period_equity_ac.png`

## 结论

- 本阶段结论：代码与数据合同通过，但绩效 gate 未通过；决策 `stage027_target_contract_history_fail_full_period_keep_research_only`。
- 是否进入下一步：不自动进入多周期，不自动晋升，不修改 master/正式物料/生产。
- 下一步：等待用户决定是优先采用更正确的换月语义继续做多周期，还是因完整周期风险路径变差保持正式 Q 不变；禁止围绕 MA、MACD、40根、品种或年份救参。
- 独立 reviewer：初审发现 `target_contract_only` 绕过 readiness 的 P1 后已修复；修复后独立复验 `17 passed + 14 subtests`，全量重跑 CSV/PNG 与修复前字节级一致，最终 `P0=0/P1=0`。JM 8月19日未形成完整回测持仓路径，保留为透明 P2 边界，不影响指标函数与数据库点时验收结论。

## 验证记录

- 本次改动聚焦测试：`17 passed + 14 subtests`；`py_compile`、`git diff --check` 均通过。
- 独立 reviewer 使用同一数据快照重跑完整 A/C，CSV 与 PNG 的 SHA256 字节级一致。
- 顶层 `tests/`：`1667 passed + 850 subtests`，另有 `8 failed`；失败分布为既有 Alpha101 `cast_to_int` 缺失4项、worktree 固定路径/虚拟环境路径2项、Stage179 性能与双进程时序2项，均与本次策略/配置/回测工具改动文件无直接交集。
- 仓库根目录无约束执行 `pytest -q` 会递归收集不可变正式物料快照中的同名测试，产生 `746` 个 import-file-mismatch 收集错误；因此以顶层 `tests/` 与本次聚焦套件分别记录，不把收集冲突伪装成策略回归。

## 过拟合反思

- 运行前判断：否；这是单一历史来源语义修复，不按已知输赢窗口调参。
- 运行后判断：否（规则层），但不能因 JM 个案再增加例外或调整指标周期；任何基于结果救参都会转为过拟合。
- 原因：候选只改变一项历史来源，在2018至2026完整区间统一生效；结果变差也被如实保留，没有做后验阈值搜索。

## 继续价值反思

- 运行前判断：有价值；正式换月判断应与新合约真实结构一致。
- 运行后判断：仍有决策价值，但没有自动继续跑参数实验的价值。
- 原因：JM2701 个案和24次换月合同证明语义差异真实存在；同时 C 的回撤和 Sharpe 明显变差，需要把“语义正确”与“历史绩效更优”分开，由用户决定是否继续固定规则多周期验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage027 为研究候选且未晋升。
- 是否更新 `research/registry.md`：否，本阶段不改变正式状态。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不更新根 `memory.md`，因为尚未形成正式策略政策变更。
