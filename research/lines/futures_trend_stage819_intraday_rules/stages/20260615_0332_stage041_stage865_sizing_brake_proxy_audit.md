# Stage041 Stage865 账户层 sizing brake 只读代理审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 03:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读代理审计与分钟K视觉复盘；不写新规则、不改正式版、不改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：<https://github.com/vnpy/vnpy>
  - backtesting.py 逐 bar 回放文档：<https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html>
- 我的判断：外部资料继续只作为工程纪律参照。仓位 brake 必须只使用下单时已知的账户状态，且要同时审计“降低保证金峰值”和“误杀趋势右尾”；不能用峰值日期、品种、方向或事后亏损标签写规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage865_stage864_sizing_brake_proxy_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无正式策略参数；只读代理中固定审计 `SBB0/SBB1/SBB2/WATCH` 四个形状：
  - `SBB0_projected90_heat_buffer`：投影 broker10 after-entry `>=90%` 时，按 `90%` 目标等比例缩手。
  - `SBB1_nearcap90_largeadd20`：投影 broker10 `>=90%` 且单笔新增 broker10 `>=20%`。
  - `SBB2_stacked50_largeadd20`：下单前 broker10 `>=50%` 且单笔新增 broker10 `>=20%`；若投影超过 `90%` 才实际缩手。
  - `WATCH_single_add20`：只读观察单笔新增 broker10 `>=20%` 的覆盖面，不作为可执行 brake。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage863 C9 全周期 `2018-01-02 -> 2026-05-29` 输出。
- 账户规模：沿用 Stage863 C9 口径。
- 成本口径：本阶段不新增真实成交；代理 PnL 只按匹配 closed lots 线性缩放估算。
- 样本过滤：C9 `entry_risk` 中 `selected_volume > 0` 的 `334` 个下单上下文；同合约、同方向、决策日后 `0-4` 天实际入场日聚合 closed lots，匹配 `327/334` 个。
- 策略/归因口径：只读代理，不接组合引擎；C4/Stage864 只用于峰值前 active lot 覆盖对照，不作为实时输入。

## 结果

- 期末权益：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `50,637,144.6`。
- 总收益：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `16,779.0482%`。
- 最大回撤：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `-42.6313%`。
- Sharpe：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `1.6312`。
- 总滑点：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `3,607,030`。
- 总交易次数：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `786`。
- 胜率：本阶段不新增真实回测；引用 Stage863 C9 固定结果 `53.5299%`。
- 其他关键指标：
  - `SBB0_projected90_heat_buffer` 标记 `24/334 = 7.1856%` 个 entry，全部会缩手，平均缩手 `30.9046%`；峰值前 `7` 个唯一 entry 中命中 `3` 个。但代理 PnL delta 为 `-152,059.1`，其中亏损修复 `+205,705.6`，赢家削减 `-357,764.7`，大赢家削减 `-272,008.6`，净负。
  - `SBB1_nearcap90_largeadd20` 标记 `19/334 = 5.6886%` 个 entry，平均缩手 `29.8242%`；峰值前 `7` 个唯一 entry 中命中 `2` 个。代理 PnL delta 为 `-115,974.1`，亏损修复 `+201,330.6`，赢家削减 `-317,304.7`，大赢家削减 `-242,108.6`，净负。
  - `SBB2_stacked50_largeadd20` 标记 `25/334 = 7.4850%` 个 entry，实际缩手 `19` 个；代理 PnL delta 同为 `-115,974.1`，说明下单前热度叠加条件没有带来更干净区分。
  - `WATCH_single_add20` 标记 `183/334 = 54.7904%` 个 entry，覆盖过宽，flagged matched PnL `23,026,228.4`，含 `11` 个大赢家，不能直接规则化。
  - 峰值前覆盖显示：`AP101.CZCE short` 在 `2020-11-19` 决策时投影 broker10 `91.6485%`、新增 broker10 `40.6636%`，SBB0 只会缩 `4.0816%`，但该上下文 matched PnL `+235,410`，属于明确右尾；`jm2101.DCE long` 在 `2020-11-25` 决策时投影 broker10 `100.2799%`，SBB0 会缩 `53.8462%`，matched PnL 聚合后为 `+60,648.9`，也不是干净左尾。
  - 视觉图册显示，AP101 入场日和峰值日价格路径本身是顺势盈利结构，简单热度缩手会削右尾；rb2101 峰值日缺分钟K，已在 atlas manifest 记录为覆盖边界。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_report_stage865_stage864_sizing_brake_proxy_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_decision_stage865_stage864_sizing_brake_proxy_audit_v1.json`
- orders：不适用，本阶段不生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_yearly_proxy_impact_stage865_stage864_sizing_brake_proxy_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_entry_audit_stage865_stage864_sizing_brake_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_brake_summary_stage865_stage864_sizing_brake_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_peak_precursor_coverage_stage865_stage864_sizing_brake_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_summary_chart_stage865_stage864_sizing_brake_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_atlas_manifest_stage865_stage864_sizing_brake_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_atlas_page001_stage865_stage864_sizing_brake_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_atlas_page002_stage865_stage864_sizing_brake_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_atlas_page003_stage865_stage864_sizing_brake_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage865_stage864_sizing_brake_proxy_audit_atlas_page004_stage865_stage864_sizing_brake_proxy_audit_v1.png`

## 结论

- 本阶段结论：决策为 `stage865_sizing_brake_proxy_too_blunt_no_engine`。账户层 heat brake 能碰到一部分 broker10 峰值前风险单，但当前形状太钝：修复亏损不够，削掉赢家和大赢家更多，不能进入真实引擎，也不能触发 A/B。
- 是否进入下一步：是，但不是继续扫 `90/20/50` 阈值。
- 下一步：回到分钟级路径，寻找“高热入场后分钟内价格确认失败/二次失败”这类更本质的实时触发，或只对已经发生 stop/retry 二次失败的路径做纪律约束；不得沿账户热度阈值、峰值品种、峰值日期或方向继续补丁化。

## 过拟合反思

- 运行前判断：不是正式策略过拟合。本阶段只是审计 Stage864 提出的账户层 sizing brake 方向，不把代理写入引擎。
- 运行后判断：仍不是正式策略过拟合，但这些代理本身显示出明显过拟合风险。
- 原因：输入只来自 C9 下单时已知账户字段，没有使用未来收益标签、峰值日期、品种或方向生成规则；但结果显示 `90/20/50` 这类账户热度条件区分不了“危险热度”和“趋势右尾热度”，继续扫阈值会变成事后救参。

## 继续价值反思

- 运行前判断：有继续价值。Stage864 已证明 C9 broker10 峰值来自组合级 sizing 放大，必须审计账户层 brake 是否有可能。
- 运行后判断：仍有继续价值，但价值不在账户热度阈值本身。
- 原因：Stage865 反证了机械热度缩手，逼迫下一步回到更贴近原目标的分钟级实时路径：高热入场后若分钟K快速证明错误，可以实时止损/缩手；如果价格顺势走出来，不能因为账户热度高就机械砍掉。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage041 当前状态和下一步。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、跨线合并或重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段只读反证，不属于重要突破、路线废弃、正式候选或跨线合并。
