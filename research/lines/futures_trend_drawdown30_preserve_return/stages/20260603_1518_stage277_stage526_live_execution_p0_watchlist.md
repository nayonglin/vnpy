# Stage277 Stage526 实盘P0执行证据清单

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 15:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行证据工程；只读生成 P0 watchlist 和 live TCA 模板，不改策略、不改参数、不重算收益
- 是否重要突破：否
- 是否触发A/B：否。本阶段不是新策略版本，只补真实成交偏差证据链。

## 外部调研与判断

- 参考资料：
  - CFA Institute Trading Costs and Electronic Markets：`https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2025/trading-costs-and-electronic-markets`
  - Interactive Brokers Order Types and Algos：`https://www.interactivebrokers.com/en/trading/ordertypes.php`
  - Interactive Brokers VWAP notes：`https://www.interactivebrokers.co.uk/en/software/tws.bak/usersguidebook/ordertypes/vwap.htm`
- 我的判断：VWAP 适合做日常成交质量基准，但 implementation shortfall 更完整，因为它覆盖冲击、延迟、未成交和显性费用。Stage526 要声明“真实交易不存在偏差”，必须记录 `signal/submit/fill/cancel/unfilled/VWAP/participation/shortfall`，不能只用回测成交价或历史分钟代理。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage575_stage526_live_execution_p0_watchlist.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增 P0/P1 watchlist 分类和 live evidence close condition。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：读取 Stage573 硬容量事件和 Stage568 live execution template。
- 账户规模：Stage526 `50万` 真实执行候选口径。
- 成本口径：本阶段不重算成本；只定义 live TCA 记录字段。
- 样本过滤：Stage573 的 `5` 个 hard capacity events。
- 策略/归因口径：执行证据 watchlist，不改变 Stage526 策略本体。

## 结果

- 期末权益：不适用，本阶段不重算收益；Stage526 参考为 `23,369,505`
- 总收益：不适用；Stage526 参考为 `3699.9195%`
- 最大回撤：不适用；Stage526 参考为 `-36.2670%`
- Sharpe：不适用；Stage526 参考为 `1.6385`
- 总滑点：不适用；Stage526 参考为 `1,342,190`
- 总交易次数：不适用；Stage526 参考为 `905`
- 胜率：不适用；Stage526 非零日胜率参考为 `53.6330%`
- 其他关键指标：
  - 决策：`p0_execution_watchlist_ready_bias_not_closed`
  - 执行证据闸门：`2/6` 通过。
  - P0：`3` 个，分别为 `fu2509.SHFE`、`lc2505.GFEX`、`AP505.CZCE`。
  - P1：`2` 个，分别为 `SM501.CZCE`、`SM505.CZCE`。
  - 残余收盘窗口缺口：`3` 个，均已列入 P0。
  - 日成交量占比超过 `1%`：`1` 个，即 `fu2509.SHFE`，最大 `1.0381%`。
  - 目标收盘窗口最大订单占比：`5.1261%`，来自 `SM501.CZCE`，作为 P1 高窗口参与率参考样本。
  - live 模板字段完整度：`12/12`，已包含 signal、submit、fill、unfilled、implementation shortfall、VWAP bps 等字段。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_report_stage575_stage526_live_execution_p0_watchlist_v1.md`
- watchlist：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_watchlist_stage575_stage526_live_execution_p0_watchlist_v1.csv`
- live evidence template：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_live_p0_evidence_template_stage575_stage526_live_execution_p0_watchlist_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_gates_stage575_stage526_live_execution_p0_watchlist_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_decision_stage575_stage526_live_execution_p0_watchlist_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage575_stage526_live_execution_p0_watchlist_chart_stage575_stage526_live_execution_p0_watchlist_v1.png`

## 图表视觉复盘

- 左上日成交量图：`fu2509.SHFE` 唯一超过 `1%` 硬线，`lc2505/AP505` 虽未超过 `1%`，但都高于 `0.5%` 提醒线，均应保留 P0 监控。
- 右上收盘窗口图：`fu2509/lc2505/AP505` 三个目标日 `14:30-15:00` 窗口成交量缺失，历史代理无法证明 close-window 可成交。
- 左下配对合约图：`fu2510/lc2507` 同日成交量明显高于旧合约，支持实盘加入旧合约流动性衰减、提前换月、拆单和配对合约证据记录；这不是 `fu/lc` 产品黑名单。
- 右下闸门图：P0 watchlist 和 live TCA template 已就绪，但历史窗口证据、`fu` 日成交量占比、P0 live fills、零偏差声明均失败。

## 结论

- 本阶段结论：Stage526 的 P0 实盘执行证据清单已准备好，但 Stage526 仍不能宣称“真实交易不存在偏差”。剩余关账项不是普通事件，而是 `AP505/lc2505/fu2509` 三个硬容量残余事件。
- 是否进入下一步：进入，但下一步必须来自真实 SimNow/CTP/券商成交回报、成交明细或独立全日分钟源，不再靠历史代理推断。
- 下一步：将 P0 模板接入日常 shadow/live execution ledger；每个 P0 类别至少累计 `3` 个可比 live fills 或独立全日分钟证据，满足 `filled=100%`、`unfilled=0`、`actual_vs_window_vwap_bps<=50`、`actual_implementation_shortfall_bps<=75`、`participation<=25%`、无 broker reject/filter 后再关闭。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：本阶段只把已知执行硬缺口转成固定证据采集模板，没有改变品种、信号、开平仓、仓位、收益或回撤。

## 继续价值反思

- 运行前判断：有继续价值。
- 运行后判断：有继续价值，但必须换成真实成交证据。
- 原因：这一步是证明或证伪 Stage526 可成交性的最短路径；没有 P0 live/independent evidence，就不能把 Stage526 作为“无实盘偏差”版本关账。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage277 摘要。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选、重要突破或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段为执行证据清单，不是重要合入事件。
