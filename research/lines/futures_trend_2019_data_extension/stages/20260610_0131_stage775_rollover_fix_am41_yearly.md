# Stage775 AM41 冻结残仓修复与年度重跑

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-10 01:31 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：bug 修复 + 年度起点稳健性重跑
- 是否重要突破：是。Stage773/774 中 AM41 2018 起点的冻结低回撤被确认为无效样本，已修复残仓执行问题并重新回测。
- 是否触发A/B：触发候选纪律但不进入正式 A/B。AM41 属于可能有价值的工程门槛候选，但当前只完成年度起点，不足以接正式版。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub `ArrayManager` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
- 我的判断：
  - `ArrayManager` 需要攒满窗口才 `inited` 是正常机制，不是 bug。
  - 但旧真实合约残仓在主力切换后不再出现在当日 `bars`，导致 `rebalance_portfolio(bars)` 只设置目标、不实际发平仓单，这是组合回测执行语义 bug。
  - 因此 Stage774 的“AM41 低回撤”不能解释为策略稳健，只能解释为残仓冻结；必须修复后重跑。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
    - `rebalance_portfolio` 增加旧持仓合约的 engine last bar，使目标为 0 的旧合约可以实际生成平仓单。
    - `_handle_rollover` 改为可从当前 bars 或 engine last bars 获取旧合约 bar；平旧仓只要求旧合约 bar，新合约 bar 只影响是否重开。
    - `on_bars` 在目标合约 AM 未 ready、目标合约缺 bar 或映射缺失时，先处理旧合约残仓。
    - 新增 `_close_position_when_target_unavailable` 与 `_bar_from_current_or_engine`。
- 删除脚本：无
- 新增参数：无
- 修改参数：无正式参数修改；研究脚本继续比较 `am120/am80/am40`，其中 `am40` 是研究专用 AM=41 口径。
- 删除参数：无

## 回测/归因参数

- 数据区间：年度启动 `2018-01-01` 到 `2026-01-01`，统一跑到 `2026-05-29`
- 账户规模：50万研究口径
- 成本口径：沿用 Stage773 年度验证成本口径，并输出 2x/3x 成本压力统计
- 样本过滤：成熟样本为启动后至少 `252` 个交易日
- 策略/归因口径：
  - `no_oi`：不开 OI 恢复规则
  - `oi_restore`：Stage757 OI 上升 + 价格沿方向恢复风险规则
  - `am120/am80/am40`：分别为不同 AM 可用门槛，`am40` 实际是最小可用 AM41

## 结果

- 聚焦修复验证：
  - `no_oi_am40` 2018 起点修复后期末权益 `8,032,075`，总收益 `1506.415%`，最大回撤 `-39.0134%`，总滑点 `467,250`，总交易次数 `645`，最终非零残仓 `NONE`。
  - `oi_restore_am40` 2018 起点修复后期末权益 `18,251,265`，总收益 `3550.253%`，最大回撤 `-49.4213%`，总滑点 `1,145,460`，总交易次数 `648`，最终非零残仓 `NONE`。
- 年度成熟样本关键结果：
  - `no_oi/am120`：成熟样本 `8/8` 正收益，中位收益 `271.2395%`，p10 `87.6142%`，最小收益 `64.202%`，最差回撤 `-40.4414%`，DD40 失败 `2`，Sharpe 中位 `1.2042`，交易数中位 `451`。
  - `no_oi/am40`：成熟样本 `8/8` 正收益，中位收益 `461.4540%`，p10 `75.6679%`，最小收益 `71.645%`，最差回撤 `-39.2549%`，DD40 失败 `0`，Sharpe 中位 `1.3229`，交易数中位 `325`。
  - `no_oi/am80`：成熟样本 `8/8` 正收益，中位收益 `207.1445%`，最差回撤 `-40.5979%`，DD40 失败 `3`。
  - `oi_restore/am40`：成熟样本中位收益 `653.1200%`，但最差回撤 `-49.4213%`，DD40 失败 `4`。
- 相对 AM120：
  - `no_oi/am40` 成熟收益胜出 `6/8`，收益胜率 `75.0%`，中位收益差 `+150.162pp`，中位回撤差 `+0.788pp`，但 p10 收益差 `-15.188pp`。
  - `oi_restore/am40` 收益胜出 `6/8`，但回撤胜出仅 `2/8`，中位回撤恶化 `-2.974pp`，不通过防守口径。
- 胜率：本阶段年度聚合报告未输出单组胜率字段；下一轮若进入月度/逐年交易明细复核，应补充。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_report_stage775_am40_80_120_oi_yearly_rollover_fix_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_summary_stage775_am40_80_120_oi_yearly_rollover_fix_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_curves_stage775_am40_80_120_oi_yearly_rollover_fix_v1.csv`
- quality/decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage775_am40_80_120_oi_yearly_rollover_fix_decision_stage775_am40_80_120_oi_yearly_rollover_fix_v1.json`

## 结论

- 本阶段结论：
  - 41K 版本出现冻结残存确实是 bug，不应该解释为策略收益或低回撤。
  - 修复后 AM41 2018 起点不再冻结，2019-04 后仍持续交易，最终无残仓。
  - `no_oi/am41` 从年度起点看有研究价值，明显强于 AM120/AM80；但这只是年度样本，不能直接改正式版。
  - `oi_restore/am41` 右尾很强但回撤明显过高，不应推广。
- 是否进入下一步：是，但只进入验证，不进入正式合入。
- 下一步：
  - 对 `no_oi/am41` 跑逐月启动、成本压力、全起点残仓审计和逐年交易结构归因。
  - 同时复跑当前正式 Stage372/20万，确认本次执行 bug 修复是否改变官方影子盘/正式回测输出。

## 过拟合反思

- 运行前判断：否，先修 bug 再重跑，不是为了救某个参数。
- 运行后判断：AM41 候选仍有中等过拟合风险。
- 原因：
  - 修 bug 本身不构成过拟合。
  - 但 AM41 是显著低于原工程预热窗口的研究门槛，年度起点只有 8 个成熟样本；即便结果变好，也必须通过逐月启动和成本/残仓审计后才能讨论 A/B。

## 继续价值反思

- 运行前判断：有价值，因为残仓冻结会污染所有关于 AM40/41 的判断。
- 运行后判断：有价值，但方向应收敛。
- 原因：
  - 修复后 `no_oi/am41` 不再是冻结假象，并且年度成熟样本表现强。
  - 但 `oi_restore` 仍是高回撤右尾放大器，下一步不应再扫 OI 阈值，应优先验证 AM 门槛本身。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：暂不更新，等逐月验证后再决定。
- 是否追加根目录 `memory.md/back_log.md`：追加简要重要修复摘要到 `back_log.md`；`memory.md` 只在后续确认影响正式研究政策时再追加。
