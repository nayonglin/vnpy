# Stage217 当前正式 C9/15万全周期与 0.5R 完整性复核

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：离线只读回测与逐笔法证
- 记录时间：2026-08-08 21:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / 当前工作区
- 阶段性质：当前正式版本全周期真实性、可复现性与 0.5R 执行语义审计
- 是否重要突破：是。确认账本算术成立，但发现多个会改变正式回测数字的 P0，当前结果不能作为可信正式基准。
- 是否触发A/B：否。本阶段不提出新策略候选，不调整参数，不接实盘。
- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 安全边界：未连接 CTP，订单/撤单 API 调用均为 `0`，未修改正式配置、AI 池、mapping 或数据库。

## 外部调研与判断

- 参考资料：回看 vn.py 官方仓库及 portfolio strategy/backtesting 的公开框架，确认多合约回测框架本身支持成交、日结与费用参数；本次异常集中在仓库自定义的 next-real-open、Stage847 0.5R、Stage859 分钟补数、Stage861 拼接分钟源和正式 wrapper 输入血缘，而不是把框架能力当作结果真实性证明。
- 我的判断：框架能运行不等于正式结果可执行。0.5R 属于路径依赖日内规则，必须同时满足完整且完成态分钟 K、正确交易日/session、可成交价格、缺数 fail-closed 和完整成本；当前五项都未完全满足。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/audit_qmt_roll_stage217_current_official_c9_full_cycle_integrity.py`
- 修改策略脚本：无。
- 修改正式配置：无。
- 删除脚本：无。
- 新增参数：仅审计窗口 `2018-01-01 -> 2026-06-30`，以及只读 gap-aware 阈值成交诊断臂；不是交易参数。
- 修改参数：无。
- 删除参数：无。
- 新增结果：当前正式 fresh run、逐年 entry-day 分钟覆盖、事件 OHLC 审计、交易日边界审计、输入 SHA manifest、gap-aware 成交反事实。
- 修改结果：Stage153 的 `8,471.4361% / 807` 不再视为同名版本可直接复现；当前 fresh run 为 `8,527.5361% / 816`。
- 删除结果：删除“当前全周期每笔都执行了 0.5R”“当前收益是完整成本后可执行收益”“Stage898 旧 C9 覆盖结论能直接证明当前 15万 live profile”的可信声明。

## 回测/归因参数

- 数据区间：请求 `2018-01-01 -> 2026-06-30`，实际交易日 `2018-01-02 -> 2026-06-30`，`2058` 日。
- 账户规模：`150,000`。
- 正式逻辑：Stage819/C2 + broker10 margin cap + 开仓日 `0.5R` 先止损、回到原入场价最多重进一次、再次 `0.5R` 止损。
- 成本口径：固定滑点已计；`786/786` 合约 commission rate 为 `0`，手续费未计。
- 样本过滤：不筛年份、品种、方向；当前正式全量 `371` 笔原始开仓、`816` 条成交账本。
- gap-aware 诊断：只在分钟 open 已越过 Stage847 理论阈值时改用 open 成交；不修 C2 两笔越阈值、Stage859 未完成 K、缺分钟、交易日错位或手续费，因此不是修正后真值。

## 当前 fresh run 结果

- 期末权益：`12,941,304.10`
- 总收益：`8,527.5361%`
- 最大回撤：`-56.2069%`
- Sharpe：`1.3524`
- 总滑点：`1,568,650`
- 总手续费：`0`
- 总交易次数：`816`
- 胜率：`52.6786%`（非零日胜率）
- 最大 broker10 margin/equity：`91.4950%`
- 会计重建：`150,000 + 累计 net_pnl = 12,941,304.10`，最大误差 `0`。
- 成交数对账：逐日 `trade_count=816`，逐笔 ledger `816`，一致。

## 0.5R 与数据真实性 P0

### P0-1：entry-day 分钟覆盖缺失，逻辑静默 fail-open

- `371` 笔原始开仓仅 `128` 笔有对应合约/自然开仓日分钟 K，缺失 `243` 笔。
- Stage847 在分钟表为空或 entry_day 为空时直接 `return None`，没有 fail-closed；缺数据等价于静默不执行 0.5R。
- 分年覆盖：
  - 2018：`24/24`
  - 2019：`42/43`
  - 2020：`18/66`
  - 2021：`13/58`
  - 2022：`11/48`
  - 2023：`4/36`
  - 2024：`7/41`
  - 2025：`6/35`
  - 2026：`3/20`
- 当前分钟文件最大时间仅到 `2026-04-24 14:58`；Stage861 所谓 full minute 是多个定向样本与补丁的拼接，不是所有正式开仓的连续分钟历史。

### P0-2：Stage859 保存的是未完成新生分钟

- Stage859 在 TqSdk 的分钟 `datetime` 变化后立即读取 `klines.iloc[-1]`，没有等待该分钟完成。
- 当前 Stage861 中来自 Stage859 的 `31,128/31,128` 根全部 `O=H=L=C` 且 `volume=0`。
- 已记录 `107` 个日内事件中 `68` 个依赖该源；首次 0.5R/C2 止损事件中 `39` 个直接依赖该源。
- 这不是普通数据粒度问题，而是会改变 first-touch 顺序的错误输入。

### P0-3：理论阈值价不一定可成交

- 已记录 `107` 个事件均能证明 OHLC 越过触发条件，但 `60/107` 个理论成交价不在对应分钟 OHLC 内：
  - 首次 0.5R 止损：`37/58`
  - 重进：`13/30`
  - 重进后再止损：`8/15`
  - 继承 C2 止损：`2/4`
- 原逻辑越过阈值后仍按精确 stop/entry threshold 合成成交，跳空或新生快照会得到不可成交的乐观价格。
- gap-aware 诊断结果：期末权益 `8,871,353.80`、收益 `5,814.2359%`、回撤 `-56.4524%`、Sharpe `1.2586`、交易 `813`。
- 相对当前结果：期末权益 `-4,069,950.30`，收益 `-2,713.3002pp`，说明执行价问题已实际影响头部指标；但该诊断仍不是修正后真值。

### P0-4：自然日不是期货交易日

- Stage847 按开仓成交 `datetime` 的自然日筛整日分钟 K。
- 对夜盘入场，这会漏掉 signal_date `21:00-24:00` 的入场夜盘，同时错误纳入 fill_date 当晚实际属于下一交易日的夜盘。
- 当前输出有 `17` 个 fill_date `21:00+` 事件，涉及 `13` 笔开仓；其中两笔 raw-night 重进仓在下一交易夜盘 `21:08` 被错误记为 retry failed，已经改变持仓路径。

### P0-5：同名正式结果不可复现

- Stage153 同版本、同窗口、同本金：期末权益 `12,857,154.10`、收益 `8,471.4361%`、交易 `807`。
- 当前：期末权益 `12,941,304.10`、收益 `8,527.5361%`、交易 `816`。
- 漂移：期末权益 `+84,150`、收益 `+56.10pp`、交易 `+9`。
- Stage153 之后 Stage847/Stage901 代码、Stage182 combined AI 池、主力 mapping 和数据库均继续变化，旧结果没有完整依赖闭包和输入 hash，不能单归因某一个文件，也不能字节级复现。

## 其他问题

- P1：手续费率 `786/786` 全为 `0`；虽然计入 `1,568,650` 滑点，仍不是完整成本后收益。
- P1：`156/371` 开仓使用 daily-next-open fallback；`148` 笔被法证 matcher 归为夜盘代理，另有 `7` 笔 entry risk 未匹配。这些计数可表征风险量级，但 Stage847 没有直接导出原始 execution-source ledger，不能冒充严格成交源统计。
- P1：固定一跳滑点没有验证大手数容量与冲击成本；逐笔终审指出 `258` 个成交腿超过 `100` 手，最大 `503` 手。
- P1：唯一一笔重进 K 同根触止损确实存在，但当前最终本来是 `flat_retry_failed`，后来在 `11:02` 以同一止损价平仓；现有证据不支持它改变头部指标，降为状态机时序告警。
- 正面证据：AI pool signal date 未发现同日或未来日使用；已记录事件的方向性触发条件成立；账本算术、交易数和事件状态分布自洽。

## 独立复核

- 独立只读 reviewer：`review_stage215`（仅名称沿用早期任务号，最终审计记录为 Stage217）。
- reviewer 结论：账本算术可信，但 0.5R 执行链存在实际改变收益路径的 P0；`8,527.5361%` 不能作为真实可执行收益或正式基准。
- reviewer 修正：同根重进 K 问题从 P0 降为 P1；阈值成交从 P1 升为 P0；补充 Stage859 未完成 K、自然日/交易日错位、容量成本与完整 manifest 边界。
- 置信度：账本算术 `99.9%`；存在会影响结果的 bug `>99%`；当前收益真实可执行：否。

## 验证

- fresh baseline 全周期回测：完成，exit `0`。
- gap-aware 诊断全周期回测：完成，exit `0`。
- `python -m py_compile`：通过。
- `git diff --check`：通过。
- 回归测试：`7 passed in 0.70s`。
- 最终 decision：`current_official_full_cycle_not_verified_has_p0_integrity_failures`，P0 检查失败 `6` 项（部分为同一根因的检测与量化，不代表六个完全独立 bug）。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_report_stage217_current_official_c9_full_cycle_integrity_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_summary_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_decision_stage217_current_official_c9_full_cycle_integrity_v1.json`
- checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_checks_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_daily_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_trades_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_entry_day_coverage_by_year_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- event audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_event_price_audit_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- input manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage217_current_official_c9_full_cycle_integrity_input_manifest_stage217_current_official_c9_full_cycle_integrity_v1.csv`
- orders：无。

## 结论

- 本阶段结论：当前 `8,527.5361% / -56.2069% / Sharpe 1.3524` 是“当前代码与当前错误/不完整输入下能够自洽复算的账本快照”，不是已经验证真实可执行的正式全周期收益。
- 修正后真实收益、回撤和 Sharpe：现在无法给出。gap-aware 的 `5,814.2359%` 只是单项诊断下界/敏感性，不是新正式结果。
- 是否进入下一步：是，但只进入数据与执行语义修复，不进入 alpha 优化或 0.5R 参数扫描。
- 下一步顺序：
  1. 重建完整、完成态且有 volume 的 entry-session 分钟 K，并固定源 hash。
  2. 以交易日/真实入场时间切片；夜盘从上一自然日 21:00 开始，不能混入下一交易夜盘。
  3. 缺分钟或 session 无法证明时 fail-closed，不允许静默跳过 0.5R。
  4. 修正 stop/reentry 的 gap fill 与同根 K 顺序，导出引擎原生 execution-source ledger。
  5. 加入真实手续费、容量和冲击成本，冻结完整依赖闭包后再跑全周期与独立复核。

## 过拟合反思

- 运行前判断：否。固定当前正式配置、全周期窗口和既有 0.5R，不调整参数、不筛样本。
- 运行后判断：否。本次只做数据/执行真实性验证；gap-aware 是预先限定的单项诊断，不用其结果优化 R 倍数或重试次数。
- 原因：发现 bug 后如果直接围绕 `0.5R`、年份、品种或夜盘窗口调收益，会把错误输入反向拟合成规则，必须先清零 P0。

## 继续价值反思

- 运行前判断：是。0.5R 是正式版本的关键收益/回撤差异来源，必须验证每一笔是否真正执行。
- 运行后判断：是，且优先级高于任何 alpha 优化。
- 原因：当前 P0 已足以推翻“正式基准已验证”的口径；修好后可能显著改写收益、回撤、Sharpe、交易数和风险占用。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新。当前同线 Stage214/215/216 双盲工作仍在并行，按同线并行规则只写唯一 Stage217 文件，避免冲突；合入者统一整理。
- 是否更新 `research/registry.md`：否，由合入者统一更新。
- 是否追加根目录 `memory.md/back_log.md`：建议追加重要突破摘要；本阶段先在 Stage217 留全量证据，待并行工作合入时统一写总账。
