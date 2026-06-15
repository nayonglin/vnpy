# Stage023 Stage847 C9 0.5R实时止损重试真实引擎

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 23:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结真实组合引擎 A/C；验证 Stage846 P2 `0.5R 实时止损 + 重回原入场价允许一次重试` 是否能穿过资金联动。
- 是否重要突破：否。C9 显著提高收益和 Sharpe，但相对 C4 最大回撤恶化，未达到晋级闸门。
- 是否触发A/B：否。C9 不进入官方候选、不接正式版、不触发 A/B。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
  - Walk-forward / rolling-window 资料用于约束验证纪律，而不是复制参数。
- 我的判断：
  - 外部资料只能支持“止损、再入场和仓位风险必须预先定义并真实执行验证”的原则，不能给出可复制的 `0.5R` 或重试次数。
  - Stage847 的价值在于把 Stage846 的 lot-level proxy 落到成交序列、滑点、资金复用和 broker10 路径；不允许因收益漂亮继续扫 `0.4/0.6R`、分钟窗或重试次数。
  - 从结果看，C9 是“进攻增强但回撤不稳”的规则，不是能替代 C4 的生存线。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage847_stage830_c4_stop_retry_engine.py`
- 修改脚本：
  - 同上。运行中修复两处报告/视觉问题：`_events_by_year` 兼容 C2 事件缺少 retry 字段；atlas 日期去时区后再和分钟K `bar_date` 对齐。二者不改变 C9 交易语义或参数。
- 删除脚本：无。
- 新增参数：
  - `STOP_RETRY_R=0.5`
  - `MAX_RETRIES=1`
  - `C9_ARM=stage847_stage819_c4_05r_stop_retry_once`
- 修改参数：无。C4 的 C2 逻辑与 broker10 `100%` 入口 cap 保持不变。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`。
- 账户规模：Stage819 候选 `300,000` 口径。
- 成本口径：沿用 Stage819/Stage830 默认手续费、滑点和 broker10 保证金代理；本阶段未做 2x/3x 成本压力。
- 样本过滤：以 Stage830 C4 为基础，只对有入场日分钟K且先触发 `0.5R` 逆向、未先触发 `0.5R` 顺向进展的开仓事件生成 C9 stop/retry。
- 策略/归因口径：
  - A：Stage827 baseline，即 Stage819 原始候选复现。
  - C2：入场日分钟K先触发 `1R` 逆向止损而非 `1R` 顺向确认时，同日止损。
  - C4：C2 + flat-entry 开仓前 projected broker10 margin/equity 超过 `100%` 时降手数。
  - C9：C4 不变；若入场日先触发 `0.5R` 逆向，则按 `-0.5R` 合成平仓；若同日后续重新穿越原入场价，则只允许一次按原入场价合成重开；若重开后再次触发同一个 `0.5R` 逆向止损，则再次平仓且不再重试。
  - 同一根分钟K同时触发顺向进展和逆向止损，按保守口径记为止损先发生。

## 结果

- 期末权益：`37,395,131.2`
- 总收益：`12365.0437%`
- 最大回撤：`-53.2418%`
- Sharpe：`1.4910`
- 总滑点：`2,610,040`
- 总交易次数：`730`
- 胜率：`53.3156%`
- 其他关键指标：
  - 决策标签：`stage847_c9_not_promoted_stop_retry_fullpath_failed`。
  - A baseline：`26,322,730 / 8674.2433% / -54.7546% / Sharpe 1.4363 / 滑点 2,149,150 / 交易 666 / 胜率 53.1069% / broker10峰值 90.6200%`。
  - C2 naked：`37,022,638.4 / 12240.8795% / -62.7688% / Sharpe 1.4583 / 滑点 2,512,570 / 交易 672 / 胜率 53.1463% / broker10峰值 119.6624%`。
  - C4 broker10 cap：`30,523,910.8 / 10074.6369% / -50.7900% / Sharpe 1.4519 / 滑点 2,079,430 / 交易 677 / 胜率 53.6294% / broker10峰值 115.4012%`。
  - C9 相对 A：期末权益 `+11,072,401.2`，最大回撤改善 `+1.5128pp`，Sharpe `+0.0547`。
  - C9 相对 C4：期末权益 `+6,871,220.4`，Sharpe `+0.0392`，broker10峰值从 `115.4012%` 降到 `109.9858%`，但最大回撤从 `-50.7900%` 恶化到 `-53.2418%`，恶化 `2.4518pp`；因此未过 C4 晋级闸门。
  - stop/retry 事件：`72` 个；其中 `flat_no_reentry=44`、`open_after_reentry=12`、`flat_retry_failed=16`。
  - stop/retry 重回入场价：`28` 个；重试后再次失败：`16` 个。
  - C2 事件在 C9 里剩余 `11` 个；cap 事件 `28` 个，全部为 reduce，blocked `0`，reduced volume `803`。
  - 路径诊断：四个版本最大回撤峰谷都集中在 `2022-03-09 -> 2022-06-29`。C9 同窗口 peak equity `10,205,981.8`、trough equity `4,772,131.8`、DD `-53.2418%`，低于 C4 的生存质量。
  - K线视觉：
    - path chart 显示 C9 后半段权益明显高于 C4，broker10 峰值低于 C4，但 2022 峰谷回撤仍深于 C4。
    - atlas page001 的 `flat_no_reentry` 多数是在入场附近快速打穿 `0.5R` 后未能有效收复，符合“错误先退”的实时止损直觉。
    - atlas page003 的 `open_after_reentry` 显示重回原入场价经常发生在午后或夜盘，恢复不一定顺畅；它能保留部分右尾，但并不天然降低路径波动。
    - atlas page004 的 `flat_retry_failed` 显示假收复后再次打止损不少发生在宽幅震荡里，说明“只重试一次”有必要，但该形状仍会制造额外成交和路径噪音。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_report_stage847_stage830_c4_stop_retry_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_summary_stage847_stage830_c4_stop_retry_engine_v1.csv`
- orders：无，本阶段未生成订单。
- daily：无新增日度执行文件；输出资金曲线为 `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_curve_stage847_stage830_c4_stop_retry_engine_v1.csv`
- quality：
  - `py_compile` 通过。
  - 完整脚本运行成功，`decision.json` 已生成。
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_decision_stage847_stage830_c4_stop_retry_engine_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_comparison_stage847_stage830_c4_stop_retry_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_stop_retry_events_stage847_stage830_c4_stop_retry_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_stop_retry_event_summary_stage847_stage830_c4_stop_retry_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_path_chart_stage847_stage830_c4_stop_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_stop_retry_atlas_page001_stage847_stage830_c4_stop_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_stop_retry_atlas_page003_stage847_stage830_c4_stop_retry_engine_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_stop_retry_atlas_page004_stage847_stage830_c4_stop_retry_engine_v1.png`

## 结论

- 本阶段结论：
  - C9 证明“实时止损 + 一次重试”确实有进攻价值：它比 C4 多赚 `6,871,220.4`，Sharpe 更高，broker10 峰值也更低。
  - 但 C9 没能成为更好的候选规则，因为它相对 C4 最大回撤恶化 `2.4518pp`，且交易从 `677` 增至 `730`、滑点从 `2,079,430` 增至 `2,610,040`。
  - 这说明 Stage846 P2 的 lot-level proxy 方向没有错，但真实组合路径里，止损释放资金、重试成交和后续持仓路径仍会把 2022 峰谷回撤拉深。
  - C9 不进入官方候选，不触发 A/B，不做年度/成本压力扩展。
- 是否进入下一步：不继续 C9 stop/retry 分支救参；整个 Stage819 日内规则研究仍可继续，但需要换机制。
- 下一步：
  - 停止 `0.5R/重试一次` 及其小数救援，不扫 `0.4/0.6R`、不扫时间窗、不扫重试次数。
  - 下一阶段若继续，应回到更上层的“持仓后权益分母脆弱 + 产品方向簇集中 + broker10压力”的实时生存线，或做 C9 事件只读归因解释为何 2022 峰谷被拉深；不要直接生成 C10 参数变体。

## 过拟合反思

- 运行前判断：否，但风险中等。
- 运行后判断：本阶段本身不是过拟合；若继续救参则会过拟合。
- 原因：
  - 本阶段只执行 Stage846 预先冻结的 P2 语义，没有按年份、品种、方向、R 倍数、OR 长度、确认分钟或重试次数扫描。
  - 结果虽然收益漂亮，但 C4 回撤闸门失败；如果继续用 `0.4/0.6R`、重试 `2` 次或加时段条件救 C9，就是根据失败路径补丁化。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：C9 分支继续价值低；Stage819 日内规则总目标仍有价值。
- 原因：
  - C9 已回答 P2 proxy 能否穿过真实资金联动：答案是“能增收，但不能稳健降回撤”。
  - 继续围绕同一形状扫参的边际价值低，且容易过拟合。
  - 但用户目标仍未完全完成：规则类日内机制还可以转向更本质的组合状态生存线，尤其是 2022 峰谷期间的权益分母和产品方向簇压力。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage023 结论和下一步方向。
- 是否更新 `research/registry.md`：否，本阶段未产生正式候选或跨线状态变化。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是研究线内部反证，不是正式候选、重要突破或路线迁移。
