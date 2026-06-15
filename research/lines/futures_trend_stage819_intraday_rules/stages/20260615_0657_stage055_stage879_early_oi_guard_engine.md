# Stage055 Stage879 早段 OI 参与度真实引擎审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 06:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎审计；不改官方正式版、不改官方候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否；Stage879 反证早段 OI-down no-progress 直接退出。
- 是否触发A/B：否；C15 未达到可接正式候选或正式 A/B 的标准。

## 外部调研与判断

- CME open interest / volume-open-interest 资料说明 OI 是价格之外的参与度信息，但不是单独交易信号。
- CME futures order type 与 CFTC stop order 教育资料说明 stop 可以用于保护风险，也可能在电子市场中触发级联或误伤；因此必须用真实执行语义验证。
- vn.py/组合回测框架适合把规则落成可复现引擎，而不是只看 lot-level 代理。
- 我的判断：Stage878 已证明 `favorable_price_oi_up` 是右尾核心，因此 Stage879 不能直接做“早段逆向就退出”。本阶段只测试最窄冻结语义：`adverse_price_oi_down + no +0.5R progress`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage879_stage878_early_oi_guard_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE = "Stage879"`
  - `MODEL_TAG = "stage879_stage878_early_oi_guard_engine_v1"`
  - `C15_ARM = "stage879_stage819_c9_early_oi_down_no_progress_guard"`
  - `EARLY_BARS = 60`
  - `MIN_EARLY_BARS = 60`
  - `EARLY_GUARD_R = 0.5`
- 修改参数：无
- 删除参数：无

## 规则语义

- A：C4，即 Stage830 broker10 入口 cap。
- B：C9，即 Stage847 C4 + `0.5R` stop/retry once。
- C：C15，即 C9 保持不变；若入场日最早 `60` 根1分钟K没有触达 `+0.5R` progress，且第 `60` 根时信号方向价格收益为负、OI变化为负，则按第 `60` 根收盘价退出，当天不重试。
- 固定约束：不扫描分钟窗口、OI阈值、成交量阈值、品种、方向或年份。

## 回测参数

- 数据区间：`2018-01-02` 至 `2026-05-29`
- 账户规模：Stage819 候选 `300,000`
- 分钟K来源：Stage861 full minute bars，加载 `1,479,592` 根、`216` symbols。
- 组合路径：复用 Stage863 已落盘 C4/C9 同口径基准，只新增 C15 真实引擎回测。
- 成本口径：沿用现有 Stage819/C4/C9 默认手续费/滑点；本阶段不做 2x/3x 成本压力。

## 结果

| arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C4 `stage830_stage819_c2_broker10_100_cap` | `46,015,805.0` | `15,238.6017%` | `-47.1915%` | `1.5996` | `3,023,410` | `678` | `53.0630%` | `111.4255%` |
| C9 `stage847_stage819_c4_05r_stop_retry_once` | `50,637,144.6` | `16,779.0482%` | `-42.6313%` | `1.6312` | `3,607,030` | `786` | `53.5299%` | `114.3987%` |
| C15 `stage879_stage819_c9_early_oi_down_no_progress_guard` | `41,990,763.2` | `13,896.9211%` | `-35.4692%` | `1.5681` | `3,464,580` | `796` | `52.8545%` | `119.3842%` |

### C15 相对变化

- 相对 C9：期末权益 `-8,646,381.4`，最大回撤改善 `+7.1620pp`，Sharpe `-0.0631`，max broker10 恶化 `+4.9854pp`。
- 相对 C4：期末权益 `-4,025,041.8`，最大回撤改善 `+11.7222pp`，Sharpe `-0.0315`，max broker10 恶化 `+7.9587pp`。
- 事件数：C15 stop/retry/guard events `137`；其中早段 OI guard events `14`，volume `2,551`。
- 早段 OI guard 分布：median early price directional return `-0.2976%`，median OI change `-1.4283%`。

## 视觉复核

- path chart 显示 C15 明显压低后期权益曲线，最大回撤更浅，但权益分母降低导致 broker10 峰值更高。
- atlas page001 显示规则确实在第 `60` 根附近按 early OI guard 退出，图上 K线、entry、`+0.5R progress`、early OI exit 与 vertical exit marker 均正常显示。
- 事件图谱说明该规则能救部分早段弱势左尾，但也会使账户长期右尾复利变薄；最终不是更好的策略。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_report_stage879_stage878_early_oi_guard_engine_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_summary_stage879_stage878_early_oi_guard_engine_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_comparison_stage879_stage878_early_oi_guard_engine_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_curve_stage879_stage878_early_oi_guard_engine_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_trades_stage879_stage878_early_oi_guard_engine_v1.csv`
- entry_risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_entry_risk_stage879_stage878_early_oi_guard_engine_v1.csv`
- entry_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_entry_candidates_stage879_stage878_early_oi_guard_engine_v1.csv`
- trade_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_trade_events_stage879_stage878_early_oi_guard_engine_v1.csv`
- intraday_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_intraday_events_stage879_stage878_early_oi_guard_engine_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_stop_retry_events_stage879_stage878_early_oi_guard_engine_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_closed_lots_stage879_stage878_early_oi_guard_engine_v1.csv`
- event_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_event_summary_stage879_stage878_early_oi_guard_engine_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_decision_stage879_stage878_early_oi_guard_engine_v1.json`
- path chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_path_chart_stage879_stage878_early_oi_guard_engine_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage879_stage878_early_oi_guard_engine_atlas_page001_stage879_stage878_early_oi_guard_engine_v1.png` 至 `page004`

## 结论

- 本阶段结论：`stage879_early_oi_guard_not_promoted`
- 是否进入下一步：不沿早段 OI-down 退出继续推进；不做滚动起点、不做成本压力、不触发 A/B。
- 下一步：Stage878 的 OI/参与度只能保留为复盘/解释标签，不能直接写成分钟级退出规则。若继续本线，应转向账户/持仓层生存问题，或寻找新的低自由度外生信息源；不得继续扫早段分钟窗口、OI阈值、成交量阈值、品种、方向或年份。

## 过拟合反思

- 运行前判断：否。Stage879 不是扫参，只是把 Stage878 的参与度线索按固定 60 根、0轴 OI、0轴价格方向、C9 既有 `+0.5R` progress 保护落成一次真实引擎。
- 运行后判断：本次验证本身不是过拟合；但继续救该分支会变成过拟合。
- 原因：C15 的回撤改善来自更早砍仓，但收益、Sharpe 和 broker10 都变差。若继续调 `45/75/90` 分钟、OI阈值或按品种/年份排除，就是在用右尾误伤结果反向补丁。

## 继续价值反思

- 运行前判断：有有限价值。Stage878 找到新信息维度，值得一次冻结真实引擎审计。
- 运行后判断：早段 OI 直接退出路线没有继续价值；本线整体仍有有限价值，但方向必须改变。
- 原因：C15 触发 `14` 次后把期末权益比 C9 打低 `8,646,381.4`，且 broker10 更高，说明“参与度弱就退出”仍然在削右尾复利。后续若继续，价值在账户/持仓生存或外生信息，而不是早段 OI 退出。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage879 反证和路线收束。
- 是否更新 `research/registry.md`：否，未形成正式候选或重大突破。
- 是否追加根目录 `memory.md/back_log.md`：否，未形成正式候选、跨线合并或重要突破。
