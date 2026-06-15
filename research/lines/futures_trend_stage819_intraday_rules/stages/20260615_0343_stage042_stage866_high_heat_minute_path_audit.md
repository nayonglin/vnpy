# Stage042 Stage866 高热入场分钟路径只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 03:43 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读分钟路径审计与分钟K视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于强线索，但样本太窄，不能作为正式策略突破。
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Backtrader order creation/execution documentation：<https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/>
  - Backtrader stop trading example：<https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/>
- 我的判断：外部资料只作为逐 bar 订单语义和止损纪律的工程参照，不复制参数。Stage866 的核心不是继续扫阈值，而是验证 Stage865 的高热误伤是否能被分钟级实时路径拆开：顺势先确认的高热入场不能砍，只有先失败、回到入场附近、再失败的路径才可能有规则价值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage866_stage865_high_heat_minute_path_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无正式策略参数；只读路径分类固定使用 C9 已有 `0.5R` 语义和 Stage865 的 SBB0/SBB1 高热标记：
  - `progress_first`：入场日先触及有利 `+0.5R`。
  - `stop_no_reclaim`：先触及不利 `-0.5R`，且未回到入场价附近。
  - `stop_reclaim_no_second_stop`：先触及 `-0.5R`，随后回到入场价附近，但未再次失败。
  - `stop_reclaim_retry_failed`：先触及 `-0.5R`，随后回到入场价附近，再次触及不利 `-0.5R`。
  - `no_05r_event` / `same_bar_ambiguous` / `missing`：无 0.5R 事件、同 bar 歧义或分钟K缺失。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage863 C9 全周期 `2018-01-02 -> 2026-05-29` 输出。
- 账户规模：沿用 Stage863 C9 口径。
- 成本口径：本阶段不新增真实成交；代理 PnL 用 matched closed lots 与 `-0.5R` 退出假设做线性反事实估算。
- 样本过滤：读取 Stage865 `entry_audit` 中已匹配 closed lots 的 `327` 个 entry；其中 SBB0 高热 entry `23` 个，分钟K缺失 entry `8` 个。
- 策略/归因口径：只读路径审计，不接组合引擎；分钟K来自 Stage861 full minute bars，路径只能使用入场日逐分钟已知价格推进。

## 结果

- 期末权益：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `50,637,144.6`。
- 总收益：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `16,779.0482%`。
- 最大回撤：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `-42.6313%`。
- Sharpe：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `1.6312`。
- 总滑点：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `3,607,030`。
- 总交易次数：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `786`。
- 胜率：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `53.5299%`。
- 其他关键指标：
  - 全样本 `progress_first` 有 `168` 笔，matched PnL `47,890,100.8`，big winner `18` 笔，说明先走出有利 `0.5R` 的入场是右尾主来源，不能被高热或非低风险状态机械砍掉。
  - 全样本 `stop_no_reclaim` 有 `72` 笔，matched PnL `-7,017,764.0`，big winner `0` 笔，是明显左尾形状；但它不是 Stage865 高热误伤的全部答案，因为在高热子集中只贡献小额净亏。
  - SBB0 高热 entry 中，`progress_first` 有 `9` 笔，matched PnL `+482,660`，big winner `2` 笔，median MFE `2.0R`、median MAE `0.1069R`。这直接反证机械账户热度缩手。
  - SBB0 高热 entry 中，`stop_reclaim_retry_failed` 有 `4` 笔，matched PnL `-395,392.1`，big winner `0` 笔，median projected broker10 `99.8467%`，median MFE `0.4223R`，median MAE `1.8077R`。
  - 代理 `HH_NR1_retry_failed_only_no_retry` 只作用于 SBB0 高热且 stop/reclaim/retry failed 的 `4` 笔，affected PnL `-395,392.1`，proxy PnL delta `+153,334.8`，亏损修复 `+186,659.8`，赢家削减 `-33,325.0`，大赢家削减 `0`。
  - 代理 `HH_NR0_all_stop_first_no_retry` 作用于 `11` 笔，proxy PnL delta `+90,199.8`，但赢家削减 `-105,085.0`，不如 `HH_NR1` 干净。
  - 诊断项 `HH_DIAG_block_non_progress_first` 作用于 `14` 笔，proxy PnL delta `-414,566.8`，并削掉 `-799,800.0` 大赢家，证明不能把“没先到 +0.5R”扩大成通用屏蔽规则。
  - 视觉复盘确认：`jm2205.DCE long 2022-01-06` 与 `lh2205.DCE short 2022-02-17` 呈现先触及不利 `0.5R`、回到入场附近、再失败的结构；`AP101.CZCE short 2020-11-20`、`OI105.CZCE long 2021-02-23`、`ru2101.SHFE long 2020-12-01` 属于高热但先确认的右尾或正贡献结构。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_report_stage866_stage865_high_heat_minute_path_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_decision_stage866_stage865_high_heat_minute_path_audit_v1.json`
- orders：不适用，本阶段不生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_yearly_path_summary_stage866_stage865_high_heat_minute_path_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_entry_path_features_stage866_stage865_high_heat_minute_path_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_path_summary_stage866_stage865_high_heat_minute_path_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_proxy_summary_stage866_stage865_high_heat_minute_path_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_summary_chart_stage866_stage865_high_heat_minute_path_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_atlas_manifest_stage866_stage865_high_heat_minute_path_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_atlas_page001_stage866_stage865_high_heat_minute_path_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_atlas_page002_stage866_stage865_high_heat_minute_path_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage866_stage865_high_heat_minute_path_audit_atlas_page003_stage866_stage865_high_heat_minute_path_audit_v1.png`

## 结论

- 本阶段结论：决策为 `stage866_high_heat_minute_path_no_engine_yet`。高热入场不是问题本身，`progress_first` 仍是右尾来源；可继续的唯一线索是 `高热 + 先0.5R止损 + 回到入场附近 + 再次0.5R失败`，但只有 `4` 笔，不能直接接真实引擎或 A/B。
- 是否进入下一步：是，但只允许一次冻结规则草案或真实引擎验证，不允许扩展为热度阈值、R 小数、时间窗、品种、方向或年份扫描。
- 下一步：设计 `HH_NR1` 的可实时成交语义，核心是第一次 `-0.5R` 后允许观察重回入场，若重回后再次失败则不再重试或强制退出；必须保留 `progress_first` 右尾，不做广义 `non-progress` 屏蔽。

## 过拟合反思

- 运行前判断：不是正式策略过拟合。本阶段固定使用 C9 已有 `0.5R` stop/retry 语义和 Stage865 高热标记，只做路径归因。
- 运行后判断：仍不是正式策略过拟合，但 `HH_NR1` 样本太小，存在很高的规则推广风险。
- 原因：没有扫分钟窗、R 倍数、品种、方向、年份或账户热度阈值；但 `4` 笔正代理不足以证明稳健性，下一步若做引擎必须一次冻结，不能根据结果再调。

## 继续价值反思

- 运行前判断：有继续价值。Stage865 已反证机械账户热度缩手，但仍需要解释高热下哪些分钟价格路径是真的错误。
- 运行后判断：有继续价值，但只剩窄路径。
- 原因：Stage866 把“危险热度”和“趋势右尾热度”拆开了。继续价值在二次失败纪律，而不是账户热度阈值本身；如果下一步冻结引擎无法改善真实组合路径，就应停止这个分支。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage042 当前状态和下一步。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、跨线合并或重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段只读线索，不属于重要突破、路线废弃、正式候选或跨线合并。
