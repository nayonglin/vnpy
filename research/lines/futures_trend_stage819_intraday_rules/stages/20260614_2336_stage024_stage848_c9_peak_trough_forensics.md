# Stage024 Stage848 C9/C4 2022峰谷窗口只读归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 23:36 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因与视觉复盘；解释 Stage847 C9 相对 C4 在 `2022-03-09 -> 2022-06-29` 峰谷窗口为何回撤更深。
- 是否重要突破：否。确认 C9 弱点更接近“同方向更大持仓/权益分母压力”而非单纯 stop/retry 事件本身，但尚未形成可接入规则。
- 是否触发A/B：否。本阶段不产生新策略版本、不进入官方候选、不接正式版、不触发 A/B。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 外部资料只支持纪律原则：止损可以约束单笔执行风险，但不能自动解决组合层权益分母、保证金和集中度风险。
  - Stage848 不能直接生成 C10 参数变体；如果根据 `2022-03-09 -> 2022-06-29` 单窗口倒推品种/方向/阈值，就是过拟合。
  - 本阶段应该只回答“C9 回撤恶化来自哪里”，而不是回答“下一组参数是多少”。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage848_stage847_c9_peak_trough_forensics.py`
- 修改脚本：
  - 同上。运行后修正一次产品名规范化：closed-lot 产品统一由 `vt_symbol` 推导，避免 `sp`/`sp.SHFE`、`MA`/`MA.CZCE` 短名拆分影响产品方向归因；该修正不改变 C4/C9 曲线和交易结果。
- 删除脚本：无。
- 新增参数：
  - `WINDOW_START=2022-03-09`
  - `WINDOW_END=2022-06-29`
  - `MODEL_TAG=stage848_stage847_c9_peak_trough_forensics_v1`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage847 全周期 `2018-01-01` 到 `2026-05-29`，本阶段只截取 `2022-03-09 -> 2022-06-29` 峰谷窗口归因。
- 账户规模：沿用 Stage819 候选 `300,000` 口径。
- 成本口径：沿用 Stage830/Stage847 既有手续费、滑点、broker10 保证金代理；本阶段未新增成本压力。
- 样本过滤：
  - 日级曲线：Stage847 输出中的 C4 `stage830_stage819_c2_broker10_100_cap` 与 C9 `stage847_stage819_c4_05r_stop_retry_once`。
  - closed lots：窗口内 active overlap，且拆出 `entry_in_window`、`exit_in_window`。
  - stop/retry：只看 C9 在窗口内入场的 Stage847 stop/retry 事件。
  - 持仓压力：由成交逐日重建净持仓，使用 `last trade price * contract size * abs(position)` 作为产品方向敞口 proxy；这不是交易所精确保金。
- 策略/归因口径：
  - C4：C2 + broker10 `100%` flat-entry cap。
  - C9：C4 + 入场日 `0.5R` 先止损、重回原入场价允许一次重试。
  - Stage848 不重跑策略、不改变 C9 规则，只读取 Stage830/Stage847 输出做只读归因。

## 结果

- 期末权益：本阶段未新增策略回测；沿用 Stage847 C9 全周期 `37,395,131.2`，C4 全周期 `30,523,910.8`。
- 总收益：沿用 Stage847 C9 全周期 `12365.0437%`，C4 全周期 `10074.6369%`。
- 最大回撤：沿用 Stage847 C9 全周期 `-53.2418%`，C4 全周期 `-50.7900%`。
- Sharpe：沿用 Stage847 C9 全周期 `1.4910`，C4 全周期 `1.4519`。
- 总滑点：沿用 Stage847 C9 全周期 `2,610,040`，C4 全周期 `2,079,430`。
- 总交易次数：沿用 Stage847 C9 全周期 `730`，C4 全周期 `677`。
- 胜率：沿用 Stage847 C9 全周期 `53.3156%`，C4 全周期 `53.6294%`。
- 其他关键指标：
  - 决策标签：`stage848_c9_peak_trough_forensics_no_rule_yet`。
  - 峰谷窗口固定为 `2022-03-09 -> 2022-06-29`。
  - C4 窗口：peak equity `7,777,212.8`，trough equity `3,827,167.8`，窗口跌幅 `-50.7900%`，window cum net PnL `-3,494,105`，交易 `34`，滑点 `112,130`，窗口 max broker10 `96.9170%`。
  - C9 窗口：peak equity `10,205,981.8`，trough equity `4,772,131.8`，窗口跌幅 `-53.2418%`，window cum net PnL `-4,794,830`，交易 `38`，滑点 `162,200`，窗口 max broker10 `103.1305%`。
  - C9-C4 窗口差：峰值权益高 `+2,428,769`，谷底权益只高 `+944,964`，峰谷权益变化多亏 `-1,483,805`，窗口跌幅恶化 `-2.4518pp`，window cum net PnL 多亏 `-1,300,725`，多 `4` 次交易，多滑点 `50,070`，max broker10 高 `+6.2135pp`。
  - 窗口内 C9 stop/retry 事件只有 `3` 个：
    - `SM.CZCE long flat_no_reentry`：`1` 个，同入口总 PnL `-226,000`。
    - `MA.CZCE long flat_retry_failed`：`1` 个，同入口总 PnL `-155,000`。
    - `MA.CZCE short flat_retry_failed`：`1` 个，同入口总 PnL `-145,000`。
  - 这 `3` 个事件的同入口 PnL 合计约 `-526,000`，不足以单独解释 C9 相对 C4 的窗口日级净 PnL 差 `-1,300,725`。
  - 产品方向 closed-lot full-life/exit-in-window 归因显示，窗口内 active lots 均在窗口内退出：C4 `19` 笔、C9 `21` 笔；exit-in-window realized PnL 差合计 `-320,815`，负向合计 `-761,845`、正向合计 `+441,030`。
  - 主要负向产品方向：
    - `fu.SHFE long`：C9-C4 `-300,250`，入场风险金额差 `+224,616.8`。
    - `AP.CZCE long`：C9-C4 `-261,650`，入场风险金额差 `+249,082.2`。
    - `jm.DCE short`：C9-C4 `-80,940`，入场风险金额差 `+56,509.8`。
    - `SM.CZCE long`：C9-C4 `-47,710`，入场风险金额差 `+85,880`。
  - 主要正向抵消：
    - `sp.SHFE long`：C9-C4 `+244,020`。
    - `au.SHFE long`：C9-C4 `+124,960`。
    - `MA.CZCE long`：C9-C4 `+72,050`，但 C9 多 1 笔窗口退出。
  - 持仓压力 proxy：
    - 全窗口 `75` 个日级记录中，C9 平均权益差仍为 `+1,400,019`，但平均回撤差为 `-2.1573pp`，平均 broker10 差为 `+0.5176pp`。
    - C9 broker delta top quartile 的 `19` 天，平均 broker10 差 `+4.1910pp`，max 差 `+8.1973pp`，top3 产品方向 share 在 C4/C9 均接近 `100%`，说明不是集中度形状变了，而是同一压力簇里 C9 的名义敞口更大。
    - 压力日显示 `2022-05-27` `FG.CZCE short`：C4 broker10 `94.9333%`，C9 `103.1305%`，差 `+8.1973pp`；C9 exposure proxy `35,367,460` vs C4 `25,965,520`。
    - `2022-05-06` `fu.SHFE long`：C9 exposure proxy `38,887,960` vs C4 `28,701,570`，broker10 差 `+6.2481pp`。
    - `2022-06-28` `fu.SHFE short`：C9 exposure proxy `16,276,300` vs C4 `11,883,660`，broker10 差 `+4.9562pp`。
    - `2022-06-29` 当天 `fu2209.SHFE short` 平仓：C4 `303` 手，C9 `415` 手，同方向同合约但 C9 手数更大。
  - K线视觉：
    - path chart 显示 C9 全程权益高于 C4，但回撤曲线始终更深，说明“绝对多赚”掩盖了相对自身高水位的更大回撤。
    - broker10 图显示 C9 在关键压力段略高于 C4，`2022-05-27` 突破 `100%`，C4 未突破。
    - product-direction 图显示负向主要来自 `fu.SHFE long`、`AP.CZCE long`、`jm.DCE short`、`SM.CZCE long`，正向来自 `sp.SHFE long`、`au.SHFE long`、`MA.CZCE long`；不是单一品种补丁能解决。
    - cluster chart 显示多段风险集中在单一产品方向，C4 和 C9 top3 share 形状几乎相同，差异主要是 C9 的名义敞口更大。
    - stop/retry atlas 显示：SM 在下午才触发 `0.5R` 后无重入；MA 多空均在开盘 1 分钟先触发止损，随后重入但再失败，属于典型假收复。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_report_stage848_stage847_c9_peak_trough_forensics_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_window_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_product_direction_pnl_delta_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_stop_retry_window_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_position_pressure_summary_stage848_stage847_c9_peak_trough_forensics_v1.csv`
- orders：无，本阶段未生成订单。
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_daily_delta_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_position_pressure_daily_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_pressure_days_stage848_stage847_c9_peak_trough_forensics_v1.csv`
- quality：
  - `py_compile` 通过。
  - Stage848 脚本完整运行成功，`decision.json` 已生成。
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_decision_stage848_stage847_c9_peak_trough_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_stop_retry_window_events_stage848_stage847_c9_peak_trough_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_peak_trough_path_chart_stage848_stage847_c9_peak_trough_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_product_direction_pnl_delta_chart_stage848_stage847_c9_peak_trough_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_cluster_pressure_chart_stage848_stage847_c9_peak_trough_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage848_stage847_c9_peak_trough_forensics_stop_retry_window_atlas_page001_stage848_stage847_c9_peak_trough_forensics_v1.png`

## 结论

- 本阶段结论：
  - C9 弱窗口不是由窗口内 stop/retry 事件单独造成。窗口内 stop/retry 只有 `3` 个，同入口 PnL 约 `-526,000`，而 C9 相对 C4 的窗口日级净 PnL 差为 `-1,300,725`。
  - 更本质的机制是：C9 前期更高权益和 stop/retry 路径保留了更强进攻性，也让后续同一产品方向压力簇持有更大手数；当 `fu/AP/FG/jm/SM` 等方向进入不顺路径时，C9 的权益分母从更高水位回撤得更深，broker10 也略高。
  - closed-lot realized PnL 与日级净 PnL 不应混为一谈。前者按整笔生命周期归因，只解释窗口内退出交易；后者包含从 `2022-03-09` 高水位开始的盯市权益路径和结算波动。这个差异本身说明“持仓后生存线”比“入场日再加止损规则”更接近问题本质。
  - C4/C9 的 top3 产品方向集中度形状几乎一致，说明不是简单加一个“集中度阈值”就能解决；真正需要识别的是“单产品方向压力 + C9 更大名义敞口 + 权益高水位/分母脆弱”同时出现时的持仓后降风险语义。
- 是否进入下一步：可以继续本研究线，但不沿 C9 stop/retry 小参数救参。
- 下一步：
  - 不生成 C10 参数变体，不扫 `0.4/0.6R`、重试次数、开盘分钟窗、单品种/方向过滤。
  - 若继续，优先做 Stage849 只读归因：对 C4/C9 的 `fu.SHFE long`、`AP.CZCE long`、`FG.CZCE short`、`fu.SHFE short` 压力段做逐日/分钟级持仓后路径复盘，判断是否存在低自由度、可实时执行的“单产品方向压力降风险/跟踪止损”规则形状。
  - 任何候选规则必须先证明不是按 `2022` 或单品种补丁化；应使用产品方向簇/保证金压力/权益高水位回撤这些账户状态，而不是品种名本身。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但继续救参会过拟合。
- 原因：
  - 本阶段窗口由 Stage847 最大回撤峰谷预先给定，只做失败归因，没有选择新阈值、年份、品种、方向或 retry 参数。
  - 输出结论没有把 `fu/AP/FG` 当成过滤名单，而是把它们作为同一机制的证据：单产品方向压力下 C9 的名义敞口更大。
  - 若下一步直接针对这些品种做过滤，就是过拟合；只有抽象成账户状态/持仓状态才有继续价值。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值方向已经收窄。
- 原因：
  - Stage848 证明 C9 不是简单“stop/retry 事件太差”，而是进攻增强后在持仓压力段放大了波动，这能指导下一步从更本质的持仓后风控入手。
  - 继续扫入场日规则价值低；继续研究“单产品方向压力 + 名义敞口 + 权益分母”的低自由度实时生存线仍有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage024 结论和 Stage025/Stage849 下一步方向。
- 是否更新 `research/registry.md`：否，本阶段未产生正式候选、重要突破、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是研究线内部只读归因，不是正式候选或重要突破。
