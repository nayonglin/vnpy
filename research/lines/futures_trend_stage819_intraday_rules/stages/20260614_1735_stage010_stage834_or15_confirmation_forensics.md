# Stage010 Stage834 OR15入场确认/假突破规避只读体检

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 17:35 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：分钟级入场确认/假突破规避规则的只读 lot-level overlay；不改正式策略、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。该阶段反证 OR15 确认形状，不形成候选。
- 是否触发A/B：否。当前只是只读逐笔覆盖与近似 lot-level overlay，尚未进入真实组合引擎 A/C。

## 外部调研与判断

- 参考资料：
  - GitHub `melkerliljegren/opening-range-breakout`：常见 ORB 结构是前几分钟定义 opening range，突破后入场，止损放在区间反侧，日内退出。
  - QuantConnect ORB research：ORB 是用开盘后前 `n` 分钟价格行为定义区间，再按突破方向入场的动量规则。
  - Investopedia range breakout risk：区间突破常见风险是假突破、回抽到突破点以及大行情稀少；更稳的思路是等待确认或趋势形成。
- 我的判断：
  - 外部资料支持“不要抢最早突破，等待确认并用反侧实时止损”的规则形状，但不支持直接复制参数。
  - Stage834 只固定两个低自由度规则：`OR15 close confirm + retry2` 与 `OR15 hold5 confirm + retry2`；不扫 OR 长度、确认分钟、重试次数、止损倍数。
  - 如果 OR15 主要通过“不交易”避免亏损，却同时显著削弱原 Stage819 的顺畅右尾，就不应进入真实引擎。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage834_stage819_or15_confirmation_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `OPENING_RANGE_BARS=15`
  - `CONFIRM_HOLD_BARS=5`
  - `MAX_ATTEMPTS=2`
  - `C6_or15_close_confirm_retry2`
  - `C7_or15_hold5_confirm_retry2`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-05-29`。
- 账户规模：Stage819 候选口径 `300,000`。
- 成本口径：沿用 Stage826 lot-level overlay 的执行成本代理，按每次开/平/止损/重试计入滑点。
- 样本过滤：
  - Stage825 全周期 closed lots `341` 笔。
  - 入场日分钟K覆盖 `227/341 = 66.5689%`。
  - 缺分钟数据 `114` 笔按原路径保留，不把缺数据误判为规则效果。
- 策略/归因口径：
  - C6：前 `15` 根 1分钟K 定义 OR；之后收盘价沿信号方向突破 OR 才入场；止损为 OR 反侧；止损后最多重试 `2` 次。
  - C7：C6 基础上，突破后要求连续 `5` 根 bar 收盘仍在 OR 外再入场；止损和重试同 C6。
  - 本阶段不是完整组合引擎，不重算资金路径、保证金路径和复利手数联动。

## 结果

- Stage819 基准期末权益：`26,322,730`
- Stage819 基准总收益：`8674.2433%`
- Stage819 基准最大回撤：`-54.7546%`
- Stage819 基准 Sharpe：`1.4363`
- Stage819 基准总滑点：`2,149,150`
- Stage819 基准总交易次数：`666`
- Stage819 基准胜率：`53.1069%`
- Stage819 基准 broker10 峰值：`90.6200%`
- C6 lot-level overlay：
  - 全部 lot 原始净额 `26,022,730`，调整后净额 `22,822,630`，净差 `-3,200,100`。
  - covered lots 原始净额 `23,482,615`，调整后净额 `20,282,515`，净差 `-3,200,100`。
  - no-confirm `37` 笔，避免亏损 lot `27` 笔、原始净额 `-8,965,730`；漏掉盈利 lot `9` 笔、原始净额 `1,733,240`。
  - confirmed-survived 原始净额 `33,209,725`，调整后 `25,354,380`，右尾被削弱 `-7,855,345`。
  - stopped-reentered-survived 净差 `-1,478,900`。
- C7 lot-level overlay：
  - 全部 lot 原始净额 `26,022,730`，调整后净额 `23,558,960`，净差 `-2,463,770`。
  - covered lots 原始净额 `23,482,615`，调整后净额 `21,018,845`，净差 `-2,463,770`。
  - no-confirm `56` 笔，避免亏损 lot `41` 笔、原始净额 `-12,296,960`；漏掉盈利 lot `14` 笔、原始净额 `2,457,320`。
  - confirmed-survived 原始净额 `34,517,965`，调整后 `25,613,440`，右尾被削弱 `-8,904,525`。
  - stopped-reentered-survived 净差 `-2,002,470`。
- 年度净差：
  - C6：`2022 +985,240`、`2025 +1,442,360`、`2026 +2,190,000`，但 `2020 -1,037,855`、`2021 -1,203,510`、`2023 -5,025,885`、`2024 -550,450`。
  - C7：`2022 +681,660`、`2025 +2,421,000`、`2026 +2,280,000`，但 `2020 -395,060`、`2021 -863,090`、`2023 -5,711,620`、`2024 -876,660`。
- 与 Stage827/C2 质量桶关系：
  - `stop_first` 桶明显改善：C6 `+10,369,355`，C7 `+11,302,320`。
  - `target_first` 桶严重受损：C6 `-14,395,710`，C7 `-14,591,315`。
  - 说明 OR15 不是一个更好的入场确认层；它主要是在已经快速走顺的交易里延迟/变差入场。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_report_stage834_stage819_or15_confirmation_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_summary_stage834_stage819_or15_confirmation_forensics_v1.csv`
- lot_outcomes：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_lot_outcomes_stage834_stage819_or15_confirmation_forensics_v1.csv`
- events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_events_stage834_stage819_or15_confirmation_forensics_v1.csv`
- action_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_action_stats_stage834_stage819_or15_confirmation_forensics_v1.csv`
- yearly_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_yearly_delta_stage834_stage819_or15_confirmation_forensics_v1.csv`
- rule_quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_rule_quality_stage834_stage819_or15_confirmation_forensics_v1.csv`
- delta chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_delta_chart_stage834_stage819_or15_confirmation_forensics_v1.png`
- atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_atlas_manifest_stage834_stage819_or15_confirmation_forensics_v1.csv`
- atlas pages：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_atlas_page001_stage834_stage819_or15_confirmation_forensics_v1.png` 到 `atlas_page008`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage834_stage819_or15_confirmation_forensics_decision_stage834_stage819_or15_confirmation_forensics_v1.json`

## 结论

- 本阶段结论：`stage834_or15_confirmation_not_promoted`。
- 是否进入下一步：不进入真实组合引擎 A/C。
- 原因：
  - C6/C7 covered-lot 总体净差均为负，分别为 `-3,200,100`、`-2,463,770`。
  - 虽然 OR15 能过滤 `stop_first` 左尾，但对 `target_first` 快速走顺交易伤害更大，净效果不成立。
  - 年度效果集中在 `2025/2026` 近端和 `2022` 左尾，`2023` 大幅恶化，不能据此接正式候选。
- 下一步：
  - 停止 OR15 长度、hold bars、重试次数、OR反侧止损小参数扫描。
  - 若继续本研究线，建议回到“入场后实时失败退出”而不是“入场前等待 OR 确认”：优先只读归因 C2/C4 中真正盈利的 stop-first 修复事件与 target-first 右尾保留之间的分界，寻找不延迟顺畅赢家的规则。

## 过拟合反思

- 运行前判断：否，风险低到中。OR15/close confirm/hold5/retry2 都是运行前固定，且来自外部常见 ORB 结构，不按结果选参数。
- 运行后判断：继续调 OR 长度、hold bars、attempt 次数就是过拟合。
- 原因：负结果不是 `15` 或 `5` 两个数字略有偏差，而是机制本身伤害 Stage819 的核心右尾；继续细扫会把近端年份的局部改善包装成规则。

## 继续价值反思

- 运行前判断：有价值。Stage009 要求回到分钟级入场质量，本阶段正好验证最直观的“等确认再入场”。
- 运行后判断：本规则形状无继续价值；研究线仍有价值。
- 原因：OR15 反证了“等待开盘区间确认”对 Stage819 不合适；但 Stage827/830 仍显示实时止损能释放收益潜力，下一步要找“不延迟右尾，只切失败”的机制。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为内部反证，不是正式候选、重要突破或跨线合并。
