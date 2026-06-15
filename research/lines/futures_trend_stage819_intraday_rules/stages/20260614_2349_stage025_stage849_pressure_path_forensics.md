# Stage025 Stage849 C9/C4压力段逐日与分钟K只读复盘

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 23:49 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读压力段路径归因；沿 Stage024 指出的 `fu/AP/FG` 产品方向压力段，拆 C4/C9 是否同路径但 C9 更大仓。
- 是否重要突破：否。确认 C9 的压力段弱点主要是同路径更大名义敞口，而不是新的入场/退出时点错误；但分钟K覆盖不足，不能直接晋级规则。
- 是否触发A/B：否。本阶段不产生新策略版本、不进入官方候选、不接正式版、不触发 A/B。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 外部资料继续支持同一个原则：止损只是单笔执行纪律；组合层风险还需要仓位规模、保证金、集中度和权益分母一起控制。
  - Stage849 不能寻找新品种过滤或年份补丁；只允许验证 Stage024 的机制判断：C9 是不是在相同交易路径上放大了手数和风险金额。
  - 如果同合约、同入场/退出日期、同价格、同退出原因都一致，而 C9 只是手数更大，那么下一步应该讨论持仓状态/账户状态，而不是继续改入场日分钟K规则。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage849_stage848_pressure_path_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage849_stage848_pressure_path_forensics_v1`
  - 预声明压力段：
    - `fu_long_20220325_0401`
    - `fu_long_20220418_0419`
    - `ap_long_20220428_0510`
    - `fu_long_20220506_0509`
    - `fg_short_20220524_0602`
    - `fu_long_20220527_0531`
    - `fu_short_20220622_0629`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage848 峰谷窗口内相关压力段；全周期曲线仍沿用 Stage847 结果。
- 账户规模：沿用 Stage819 候选 `300,000` 口径。
- 成本口径：沿用 Stage830/Stage847 既有手续费、滑点、broker10 保证金代理；本阶段未新增成本压力。
- 样本过滤：
  - 压力段来自 Stage024/Stage848 已识别的产品方向：`fu.SHFE long`、`AP.CZCE long`、`FG.CZCE short`、`fu.SHFE short`。
  - 只做 read-only paired-lot 归因；不按新阈值、收益排序、品种过滤或年份过滤挑样本。
  - 分钟K读取沿用 Stage825 的分钟源；缺分钟必须如实记录。
- 策略/归因口径：
  - C4：`stage830_stage819_c2_broker10_100_cap`。
  - C9：`stage847_stage819_c4_05r_stop_retry_once`。
  - 配对口径：同 `episode_id/vt_symbol/direction/entry_date/exit_date/entry_price/exit_price/exit_reason` 视为同路径交易，再比较手数、风险金额和 PnL。

## 结果

- 期末权益：本阶段未新增策略回测；沿用 Stage847 C9 全周期 `37,395,131.2`，C4 全周期 `30,523,910.8`。
- 总收益：沿用 Stage847 C9 全周期 `12365.0437%`，C4 全周期 `10074.6369%`。
- 最大回撤：沿用 Stage847 C9 全周期 `-53.2418%`，C4 全周期 `-50.7900%`。
- Sharpe：沿用 Stage847 C9 全周期 `1.4910`，C4 全周期 `1.4519`。
- 总滑点：沿用 Stage847 C9 全周期 `2,610,040`，C4 全周期 `2,079,430`。
- 总交易次数：沿用 Stage847 C9 全周期 `730`，C4 全周期 `677`。
- 胜率：沿用 Stage847 C9 全周期 `53.3156%`，C4 全周期 `53.6294%`。
- 其他关键指标：
  - 决策标签：`stage849_pressure_path_forensics_no_rule_yet`。
  - 压力 episode 数：`7`。
  - paired lots：`8` 对。
  - `8/8` paired lots 都是 C4/C9 同合约、同入场/退出日期、同价格、同退出原因，但 C9 手数更大。
  - C9-C4 paired 合计：手数 `+817`，风险金额 `+449,837.4`，PnL `-386,960`。
  - C9/C4 手数比：中位数 `1.3549`，最小 `1.2920`，最大 `1.3696`。这说明 C9 压力段的核心不是时点变化，而是约 `1.3x-1.37x` 的规模放大。
  - paired PnL：正向 `+215,940`，负向 `-602,900`，净 `-386,960`。
  - episode 级别：
    - `fu_long_20220325_0401`：C9 多 `235` 手，多风险 `63,760`，PnL 反而 `+37,400`；说明更大仓不必然错，但会放大路径。
    - `fu_long_20220418_0419`：C9 多 `123` 手，多风险 `103,516.8`，PnL `-89,790`。
    - `ap_long_20220428_0510`：C9 多 `53` 手，多风险 `98,293.8`，PnL `-54,590`，episode equity change delta `-253,020`。
    - `fu_long_20220506_0509`：C9 多 `119` 手，多风险 `30,940`，PnL `-149,940`，episode equity change delta `-136,810`。
    - `fg_short_20220524_0602`：C9 多 `127` 手，多风险 `89,966.8`，PnL `-25,400`，max broker10 C9 `103.1305%` vs C4 `94.9333%`，max broker10 delta `+8.1973pp`。
    - `fu_long_20220527_0531`：C9 多 `48` 手，多风险 `26,400`，PnL `-97,920`，max broker10 delta `+8.1973pp`。
    - `fu_short_20220622_0629`：C9 多 `112` 手，多风险 `36,960`，PnL `-6,720`，episode equity change delta `-236,320`。
  - 逐日压力：
    - path chart 显示各 episode 中 C9 equity 绝对值通常仍高于 C4，但 broker10 和 product-direction exposure proxy 也系统性高于 C4。
    - `FG.CZCE short` episode 是 broker10 压力最典型段：同一路径下 C9 exposure proxy `16,921,200` vs C4 `12,425,400`，broker10 峰值突破 `100%`。
    - `fu.SHFE long/short` episode 多数是同价格同退出但 C9 更大手数造成相同方向的损益放大。
  - 分钟K视觉覆盖：
    - 关键日期 `19` 个，分钟K覆盖 `7` 个，覆盖率 `36.84%`。
    - `AP.CZCE long`：`3/3` 覆盖，`2022-05-09` 当天从开盘到收盘方向收益 `-2.3406%`，盘中不利从开盘到最低 `-2.9867%`，显示日内连续下行，C4/C9 入场/退出线一致，差异来自手数。
    - `fu.SHFE short`：`3/3` 覆盖。`2022-06-22` 对 short 有利，`2022-06-28/29` 逐步反向，`2022-06-29` 日内不利约 `-1.2843%`，退出线一致；C9 仍只是更大手数。
    - `fu.SHFE long` 和 `FG.CZCE short` 多数关键日期缺分钟K，不能宣称这些压力段已经完成分钟级视觉证明。
    - `fu2205.SHFE 2022-03-29` 仅 `16` 根分钟K，证据弱，只能作为局部图示。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_report_stage849_stage848_pressure_path_forensics_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_summary_stage849_stage848_pressure_path_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_lot_pairs_stage849_stage848_pressure_path_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_lots_stage849_stage848_pressure_path_forensics_v1.csv`
- orders：无，本阶段未生成订单。
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_daily_stage849_stage848_pressure_path_forensics_v1.csv`
- quality：
  - `py_compile` 通过。
  - Stage849 脚本完整运行成功，`decision.json` 已生成。
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_decision_stage849_stage848_pressure_path_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_minute_features_stage849_stage848_pressure_path_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_path_chart_stage849_stage848_pressure_path_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_atlas_ap_long_20220428_0510_stage849_stage848_pressure_path_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage849_stage848_pressure_path_forensics_episode_atlas_fu_short_20220622_0629_stage849_stage848_pressure_path_forensics_v1.png`
  - 其余 episode atlas 已生成，但多为缺分钟提示，不作为强视觉证据。

## 结论

- 本阶段结论：
  - Stage849 强化了 Stage024 判断：C9 在压力段的失败不是新的入场/出场时点错误，而是同路径下更大手数、更大风险预算导致的损益、broker10 和回撤放大。
  - `8/8` paired lots 同合约、同入场/退出日期、同价格、同退出原因，但 C9 手数更大；这已经把问题从“分钟级入场形状”推向“持仓后账户状态/规模状态”。
  - 分钟K视觉上，`AP long` 与 `fu short` 支持“同路径、同价位、C9 更大仓”的判断；但 `fu long` 与 `FG short` 缺分钟，不能把 Stage849 当作完整分钟级生存线证据。
  - 目前不应该直接写规则。任何下一步规则如果存在，应是“在持仓后，当 product-direction exposure/broker10/权益高水位回撤同时恶化时，对单产品方向做低自由度降风险”的账户状态规则，而不是 `0.5R`、开盘分钟窗、重试次数或品种名过滤。
- 是否进入下一步：可以继续，但只能先形成一个预声明、低自由度的规则候选设计说明，不立即接入引擎。
- 下一步：
  - Stage026 若继续，先写规则设计草案而非代码：定义一个不含品种名、不含年份、不扫小数阈值的 product-direction exposure guard 形状。
  - 候选形状必须只用实时可见状态：当前持仓产品方向、broker10/equity、账户回撤状态、当前产品方向名义敞口相对权益或保证金压力。
  - 若规则形状无法做到低自由度，就停止持仓后生存线分支，不再用压力段补丁救 C9。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否；但继续到规则阶段风险升高。
- 原因：
  - 本阶段 episode 来自 Stage024/Stage848 已记录的压力段，没有新增阈值筛选、品种过滤或参数扫描。
  - 结论没有使用 `fu/AP/FG` 作为未来过滤名单，而是抽象为“同路径更大手数/风险预算”。
  - 但如果下一步直接按这些品种、这些日期或 `1.35x` 手数比写规则，就是过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但必须更谨慎。
- 原因：
  - Stage849 把失败机制进一步收敛为规模/持仓状态问题，排除了继续救入场日 stop/retry 小参数的必要性。
  - 由于分钟K覆盖只有 `36.84%`，下一步不能声称分钟级持仓后规则已经被证明；最多先做低自由度规则设计，然后再用真实引擎和更广窗口反证。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage025 结论和 Stage026 下一步方向。
- 是否更新 `research/registry.md`：否，本阶段未产生正式候选、重要突破、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是研究线内部只读归因，不是正式候选或重要突破。
