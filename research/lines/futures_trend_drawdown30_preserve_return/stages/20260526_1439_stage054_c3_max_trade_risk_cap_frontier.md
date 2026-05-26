# Stage054 C3 单笔风险上限真实引擎筛查

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：`2026-05-26 14:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：C3 真实引擎既有风控参数粗筛；路线反证。
- 是否重要突破：否，但属于重要排除。
- 是否触发A/B：否；没有出现可与正式78-1结合的候选。

## 外部调研与判断

- 参考资料：AQR/Hurst-Ooi-Pedersen 的趋势跟随长期证据；Moskowitz-Ooi-Pedersen 的时间序列动量；Kim-Tse-Wald 对波动缩放贡献的讨论。
- 我的判断：外部研究支持趋势策略里的风险预算、波动缩放和多市场分散，但本线已经反证多个账户层波动预算形状。本阶段只验证更窄的“单笔风险集中度”是否能解释 C3 剩余 `-31%` 回撤，而不是继续调全局波动阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage354_c3_max_trade_risk_cap_frontier.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`max_risk_per_trade` 粗档位 `22500/30000/37500/45000/60000`。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`。
- 账户规模：50万 78-1/C3 口径。
- 成本口径：沿用 C3 正常成本与真实引擎口径。
- 样本过滤：先全周期粗筛；只有同时满足最大回撤30以内和收益保留80%以上才进入多周期。
- 策略/归因口径：固定 C3 的入场、AI池、品种池、出场逻辑和供需强逆风处理，只改变已有 `max_risk_per_trade`。

## 结果

- C3基准：期末权益 `30,925,650`，总收益 `6085.1300%`，最大回撤 `-31.0767%`，Sharpe `1.3663`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。
- `cap_22500`：期末权益 `3,156,000`，总收益 `531.2000%`，最大回撤 `-28.3411%`，Sharpe `0.8497`，总滑点 `248,110`，总交易次数 `688`，胜率 `44.4767%`，收益保留 `8.7295%`。
- `cap_30000`：期末权益 `4,059,080`，总收益 `711.8160%`，最大回撤 `-34.5233%`，收益保留 `11.6976%`。
- `cap_37500`：期末权益 `5,485,980`，总收益 `997.1960%`，最大回撤 `-32.0398%`，收益保留 `16.3874%`。
- `cap_45000`：期末权益 `5,440,665`，总收益 `988.1330%`，最大回撤 `-32.8921%`，收益保留 `16.2385%`。
- `cap_60000`：期末权益 `6,733,345`，总收益 `1246.6690%`，最大回撤 `-31.0767%`，收益保留 `20.4871%`。
- 其他关键指标：只有 `cap_22500` 把全周期回撤压进30以内，但收益保留只有 `8.7295%`；其他档位既没有压进30以内，也大幅牺牲收益。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage354_c3_max_trade_risk_cap_frontier_report_stage354_c3_max_trade_risk_cap_frontier_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage354_c3_max_trade_risk_cap_frontier_summary_stage354_c3_max_trade_risk_cap_frontier_v1.csv`
- full_screen：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage354_c3_max_trade_risk_cap_frontier_full_screen_stage354_c3_max_trade_risk_cap_frontier_v1.csv`
- window_results：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage354_c3_max_trade_risk_cap_frontier_window_results_stage354_c3_max_trade_risk_cap_frontier_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage354_c3_max_trade_risk_cap_frontier_decision_stage354_c3_max_trade_risk_cap_frontier_v1.json`

## 结论

- 本阶段结论：`no_candidate_stop_max_trade_risk_cap`。
- 是否进入下一步：否。
- 下一步：停止围绕 `max_risk_per_trade` 相邻小数或档位救结果。若继续本线，应换真正独立收益源、不同承载结构，或回到 `11.5万外部现金` 正常成本部署边界。

## 过拟合反思

- 运行前判断：不是过拟合；这是已有风控参数的粗档位经济含义验证，不改 alpha、不改品种池、不看未来收益。
- 运行后判断：本阶段不是过拟合；失败后继续把 `22500/30000/37500` 附近改成小数救收益或回撤会过拟合。
- 原因：单笔风险上限本质是在复利放大后切断单笔风险预算，但真实结果显示它主要切掉趋势盈利腿，而不是精准切掉尾部亏损。

## 继续价值反思

- 运行前判断：有价值；若成功，可直接落到真实引擎已有参数。
- 运行后判断：本具体路线继续价值低；总研究线仍有价值。
- 原因：`cap_22500` 证明绝对单笔风险上限确实能压回撤，但收益损失极端；这说明 C3 的收益来自允许大趋势仓复利扩张，粗暴单笔封顶会破坏策略本体。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录该路线停止。
- 是否更新 `research/registry.md`：是，更新当前研究线状态。
- 是否追加根目录 `memory.md/back_log.md`：是，作为路线反证摘要追加。
