# Stage009 Stage833 C4叠加持仓后保证金生存线压力起点验证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 17:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结 C5 stress-start 验证；不改正式策略、不连接 CTP、不调用下单。
- 是否重要突破：否。该阶段是 C4 尾部风险修复尝试，结论为失败。
- 是否触发A/B：否。只在 Stage831/832 已知压力起点内验证 C5，不构成正式候选 A/B。

## 外部调研与判断

- 参考资料：
  - RePEc/Umea Economic Studies ORB 论文摘要：机械日内突破规则可以被统计检验，但必须处理预设阈值、假突破和执行风险。
  - NinjaTrader futures risk management：期货风险管理需要 margin、leverage、stop-loss、position sizing 共同约束；止损要绑定交易假设失效点。
  - Optimus Futures position sizing：多持仓必须考虑组合暴露、相关性和可用保证金，不能只按单笔止损距离定手数。
  - Investopedia range breakout risk：突破后常有假突破和回抽，等待确认/回抽再进场通常比抢最早突破更稳。
- 我的判断：
  - Stage833 的 C5 是合理的生存线验证，但不是分钟级 alpha；它只回答“C4 尾部能否靠持仓后强制减仓修复”。
  - 结果显示 C5 没有修复 broker100，说明继续围绕保证金阈值、target ratio 或 broker multiplier 小数扫描会走向过拟合。
  - 后续如果继续回到用户目标，方向应从“止损释放资金后再用什么保证金阈值兜底”转向“入场前/入场日分钟K确认，减少假突破和不顺畅入场”，同时仍保持实时止损和有限重试。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage833_stage830_c4_forced_survival.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `enable_forced_margin_deleverage=True`
  - `forced_margin_deleverage_trigger_ratio=1.00`
  - `forced_margin_deleverage_target_ratio=1.00`
  - `forced_margin_deleverage_broker_multiplier=1.65`
  - `forced_margin_deleverage_priority=largest_margin`
  - `forced_margin_deleverage_max_reductions_per_day=100`
- 修改参数：无。C2 的 `1R/1R`、Stage830 的 broker10 entry cap 均冻结。
- 删除参数：无。

## 回测/归因参数

- 数据区间：压力起点独立跑到 `2026-05-29`。
- 账户规模：Stage819 候选口径 `300,000`。
- 成本口径：沿用 Stage819/Stage830 回测成本。
- 样本过滤：只跑 Stage832 压力起点 `2018-01, 2019-01, 2020-01, 2021-01`。
- 策略/归因口径：
  - A：Stage819 baseline。
  - C4：C2 日内实时止损 + broker10 `100%` flat-entry 入口 cap。
  - C5：C4 + 持仓后 broker10 实际保证金/权益 `>100%` 时，按最大保证金占用品种减仓到 `100%`。

## 结果

- 期末权益：
  - `2018-01` A `26,322,730`，C4 `30,523,910.8`，C5 `31,276,872.2`。
  - `2019-01` A `22,792,425`，C4 `35,491,021.8`，C5 `34,519,536.0`。
  - `2020-01` A `18,787,535`，C4 `25,947,231.6`，C5 `26,357,632.4`。
  - `2021-01` A `5,779,775`，C4 `13,705,900.0`，C5 `13,266,067.2`。
- 总收益：
  - `2018-01` A `8674.2433%`，C4 `10074.6369%`，C5 `10325.6241%`。
  - `2019-01` A `7497.4750%`，C4 `11730.3406%`，C5 `11406.5120%`。
  - `2020-01` A `6162.5117%`，C4 `8549.0772%`，C5 `8685.8775%`。
  - `2021-01` A `1826.5917%`，C4 `4468.6333%`，C5 `4322.0224%`。
- 最大回撤：
  - `2018-01` A `-54.7546%`，C4 `-50.7900%`，C5 `-50.5862%`。
  - `2019-01` A `-43.4335%`，C4 `-50.7898%`，C5 `-59.5303%`。
  - `2020-01` A `-44.6223%`，C4 `-50.8993%`，C5 `-50.6696%`。
  - `2021-01` A `-42.8163%`，C4 `-49.4595%`，C5 `-49.2605%`。
- Sharpe：
  - `2018-01` A `1.4363`，C4 `1.4519`，C5 `1.4292`。
  - `2019-01` A `1.5297`，C4 `1.5931`，C5 `1.5331`。
  - `2020-01` A `1.5941`，C4 `1.6220`，C5 `1.5947`。
  - `2021-01` A `1.3961`，C4 `1.6024`，C5 `1.5745`。
- 总滑点：
  - `2018-01` A `2,149,150`，C4 `2,079,430`，C5 `2,134,720`。
  - `2019-01` A `1,793,410`，C4 `2,348,680`，C5 `2,374,100`。
  - `2020-01` A `1,489,460`，C4 `1,779,890`，C5 `1,863,930`。
  - `2021-01` A `493,780`，C4 `954,740`，C5 `936,420`。
- 总交易次数：
  - `2018-01` A `666`，C4 `677`，C5 `667`。
  - `2019-01` A `621`，C4 `625`，C5 `617`。
  - `2020-01` A `529`，C4 `534`，C5 `530`。
  - `2021-01` A `387`，C4 `395`，C5 `391`。
- 胜率：
  - `2018-01` A `53.1069%`，C4 `53.6294%`，C5 `53.8002%`。
  - `2019-01` A `54.2778%`，C4 `53.9027%`，C5 `54.4373%`。
  - `2020-01` A `54.7544%`，C4 `54.4397%`，C5 `54.6512%`。
  - `2021-01` A `53.5475%`，C4 `54.0984%`，C5 `53.9617%`。
- 其他关键指标：
  - C5 对 A 收益胜出 `4/4`，但回撤只胜 `1/4`。
  - C5 对 C4 回撤胜出 `3/4`，但改善幅度很小，中位仅 `+0.2014pp`；`2019-01` 反而大幅恶化 `-8.7405pp`。
  - C5 DD50 失败 `3/4`，与 C4 相同，高于 A 的 `1/4`。
  - C5 broker100 失败 `4/4`，与 C4 相同，高于 A 的 `0/4`。
  - C5 max broker10 到 `125.5333%`，高于 C4 的最高 `115.4012%`。
  - forced 事件 `11` 次，合计关闭 `109` 手，主要集中 `CF.CZCE short`；未触达 Stage832 识别的 `2022-07` 黑色/燃油压力簇。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_report_stage833_stage830_c4_forced_survival_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_summary_stage833_stage830_c4_forced_survival_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_curves_stage833_stage830_c4_forced_survival_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_comparison_stage833_stage830_c4_forced_survival_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_aggregate_stage833_stage830_c4_forced_survival_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_trade_events_stage833_stage830_c4_forced_survival_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_intraday_events_stage833_stage830_c4_forced_survival_v1.csv`
- forced_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_forced_events_stage833_stage830_c4_forced_survival_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_chart_stage833_stage830_c4_forced_survival_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage833_stage830_c4_forced_survival_decision_stage833_stage830_c4_forced_survival_v1.json`

## 结论

- 本阶段结论：C5 不晋级，且不值得进入全年度起点验证。
- 原因：
  - C5 没有消除 broker100，反而使 exact broker10 峰值从 C4 的 `115.40%` 进一步恶化到 `125.53%`。
  - C5 没有修复 DD50，`2019-01` 最大回撤从 C4 的 `-50.7898%` 恶化到 `-59.5303%`。
  - forced 事件集中在 `CF.CZCE short`，没有命中 Stage832 的核心压力日簇；说明当前 runtime margin survival 与事后 exact broker10 风险口径不一致，且会改变路径后释放出新的风险。
- 是否进入下一步：不沿 C5 继续。
- 下一步：
  - 停止 C2/C4/C5 的保证金阈值、target ratio、broker multiplier 小数扫描。
  - 若继续本研究线，应回到用户原始目标的分钟级入场/出场：设计一个“入场日确认/假突破规避”只读候选，例如不抢日线信号后的首个成交，而是等待分钟级方向确认或回抽后再进；错则实时止损，有限重试。先做只读覆盖和逐笔图谱，不直接改策略。

## 过拟合反思

- 运行前判断：低到中。`100%` 是生存线语义，不是收益最优阈值；但样本只选已知压力起点。
- 运行后判断：继续调 forced target/trigger 会过拟合。
- 原因：当前问题不是 `100` 这个数不够精细，而是 runtime margin estimator 和 exact broker10 压力簇不一致，且强制减仓会改变后续路径，可能制造更高风险。

## 继续价值反思

- 运行前判断：有价值。Stage832 指向 full-path survival，必须验证一次固定形状。
- 运行后判断：C5 形状无继续价值；本研究线仍有价值，但必须换回分钟级入场质量方向。
- 原因：C5 反证了“C4 尾部靠简单持仓后强制减仓修复”；但 Stage827/830 仍证明日内实时止损能释放收益潜力，只是资金再利用纪律还没找到稳定形状。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为内部反证，不是正式候选、重要突破或跨线合并。
