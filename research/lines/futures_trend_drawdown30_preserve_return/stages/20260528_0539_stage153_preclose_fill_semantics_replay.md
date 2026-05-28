# Stage153 Stage079 预收盘成交语义真实路径回放审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 05:39 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行模型敏感性审计；不新增策略，不修改 Stage079/C3 交易规则。
- 是否重要突破：是，确认 14:55 VWAP 失败不是单一成交价定义造成。
- 是否触发A/B：否。本阶段没有产生可晋级策略版本。

## 外部调研与判断

- 参考资料：
  - Backtrader order execution: https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - ML4T execution semantics: https://ml4trading.io/docs/backtest/user-guide/execution-semantics/
  - NautilusTrader backtesting: https://nautilustrader.io/docs/latest/concepts/backtesting
  - TqSdk docs: https://tqsdk-python.readthedocs.io/
  - TqSdk disclaimer: https://www.shinnytech.com/blog/disclaimer/
- 我的判断：
  - 日线 same close、盘中预收盘窗口、next open 都是不同成交语义，不能混用。
  - 只有在信号能收盘前冻结时，`14:55/14:59` 这类窗口才可能成为部署口径；否则只能作为执行敏感性审计。
  - 本阶段预先固定三种收盘前成交语义，不按收益事后挑选，因此不是过拟合；但若只选 14:59 好看的收益曲线晋级，则会变成过拟合或执行假设泄漏。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage453_preclose_fill_semantics_replay.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `MODEL_TAG=stage453_preclose_fill_semantics_replay_v1`
  - `MAX_ITERATIONS=4`
  - 固定审计三种成交语义：
    - `stage079_true_path_1455_vwap_backfilled_rerun`
    - `stage079_true_path_1455_first_open`
    - `stage079_true_path_1459_last_close`
  - 统一使用 `14:55-14:59` 1分钟K窗口。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：Stage079 账户口径 `615,000`，即 `50万C3下单 + 11.5万外部现金`。
- 成本口径：沿用 Stage079/C3 原滑点；另做 `1x/2x/3x/5x` 成本压力。
- 样本过滤：无。
- 策略/归因口径：
  - baseline：Stage079 Stage403 冻结日权益。
  - rerun：同日收盘口径真实引擎重跑，用于确认入口可复现。
  - true path：同日收盘撮合产生订单后，把成交价替换为固定分钟代理价，并进入后续仓位路径。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252日破30率 | 504日破30率 | 年度/季度冷启动回撤30内 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |
| Stage079 same-day rerun | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |
| 14:55 first open | 24,487,495 | 3881.7065% | -28.8199% | 1.2712 | 14.1511 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |
| 14:55-14:59 VWAP rerun | 35,470,684 | 5667.5909% | -30.1914% | 1.3504 | 14.8757 | 5.2913% | 19.9668% | 60.0000% / 54.5455% |
| 14:59 last close | 36,225,405 | 5790.3098% | -29.7606% | 1.3651 | 14.8399 | 0.0000% | 0.0000% | 100.0000% / 100.0000% |

交易覆盖：

- 三个 true path 版本最终 fallback 均为 `0`。
- `14:55 first open` 真实路径交易次数 `749`，代理键 `803`，补齐 `5` 个新键。
- `14:55-14:59 VWAP` 真实路径交易次数 `774`，代理键 `797`。
- `14:59 last close` 真实路径交易次数 `774`，代理键 `797`。

3个月/6个月体验：

| 版本 | 周期 | 5%分位收益 | 中位收益 | 正收益率 | 年化低于5%概率 | 最差期内回撤 | 破20回撤率 | 破30回撤率 | Ulcer P95 | P95最长水下 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 3个月 | -11.4702% | 13.5434% | 73.4804% | 29.4012% | -29.1988% | 18.5052% | 0.0000% | 17.7786 | 88.0 |
| 14:55 first open | 3个月 | -15.4307% | 11.6206% | 75.8667% | 27.9154% | -26.7737% | 18.6403% | 0.0000% | 16.6116 | 87.0 |
| 14:55-14:59 VWAP | 3个月 | -11.5925% | 16.4426% | 75.9568% | 26.5196% | -29.3748% | 18.1450% | 0.0000% | 18.5661 | 87.0 |
| 14:59 last close | 3个月 | -12.4403% | 15.9605% | 75.6416% | 26.9248% | -29.1215% | 16.5241% | 0.0000% | 18.6307 | 88.0 |
| Stage079 baseline | 6个月 | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 35.7109% | 0.0000% | 19.9011 | 167.0 |
| 14:55 first open | 6个月 | -3.1721% | 29.2518% | 92.5387% | 9.7137% | -28.8199% | 39.3243% | 0.0000% | 18.8269 | 164.0 |
| 14:55-14:59 VWAP | 6个月 | -0.2969% | 33.6513% | 94.4158% | 7.0389% | -30.1914% | 30.5960% | 1.7832% | 20.5756 | 162.5 |
| 14:59 last close | 6个月 | -2.5067% | 33.7380% | 93.8057% | 7.4144% | -29.7606% | 28.9535% | 0.0000% | 19.9692 | 162.5 |

短持有体验分：

- Stage079 baseline：3个月 `100.0000`，6个月 `100.0000`，综合 `100.0000`
- `14:55 first open`：3个月 `86.8344`，6个月 `69.0003`，综合 `77.0256`
- `14:55-14:59 VWAP`：3个月 `112.0785`，6个月 `153.3823`，综合 `134.7956`
- `14:59 last close`：3个月 `107.6842`，6个月 `121.5671`，综合 `115.3198`

硬约束失败项：

- `14:55 first open`：`total_return_not_lower,sharpe_not_lower`
- `14:55-14:59 VWAP`：`max_dd_not_worse,max_dd_below_30,rolling252_dd30_zero,rolling504_dd30_zero,annual_dd30_pass_100,quarter_dd30_pass_100,cost_stress_not_worse`
- `14:59 last close`：`max_dd_not_worse,cost_stress_not_worse`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_report_stage453_preclose_fill_semantics_replay_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_chart_stage453_preclose_fill_semantics_replay_v1.png`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_daily_stage453_preclose_fill_semantics_replay_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_summary_stage453_preclose_fill_semantics_replay_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_horizon_stage453_preclose_fill_semantics_replay_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_score_stage453_preclose_fill_semantics_replay_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_gate_stage453_preclose_fill_semantics_replay_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_cost_stress_stage453_preclose_fill_semantics_replay_v1.csv`
- trade_usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_trade_usage_stage453_preclose_fill_semantics_replay_v1.csv`
- backfill_status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_backfill_status_stage453_preclose_fill_semantics_replay_v1.csv`
- proxy_map：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_proxy_map_stage453_preclose_fill_semantics_replay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage453_preclose_fill_semantics_replay_decision_stage453_preclose_fill_semantics_replay_v1.json`

## 结论

- 决策标签：`preclose_semantics_all_hard_fail_keep_execution_pause`
- 本阶段结论：三种预收盘成交语义全部不晋级。
- 是否进入下一步：不进入 Stage079 优化候选；Stage103/xsmom 真实 paper 晋级继续暂停。
- 下一步：
  - 不继续在同日收盘口径上做 3个月/6个月 alpha 补丁。
  - 先研究“信号能否收盘前冻结/实时化”的工程可行性；如果不能冻结，`14:59 last close` 不具备部署含义。
  - 同时可以固定少数真实可部署开盘/夜盘执行口径做风险缓冲边界审计，但不得按收益挑成交价。

## 独立判断

- `14:59 last close` 最接近看起来可惜：收益最高、rolling破30为0、年度/季度通过100%，但最大回撤 `-29.7606%` 已比 Stage079 深，且 1x/2x/3x 成本压力也更差；3个月体验分只提升 `7.6842%`，没有达到 `10%`。
- `14:55 first open` 风险更干净，但总收益和 Sharpe 明显劣化，不能用“更稳”换掉长期收益。
- `14:55 VWAP` 分数最好，但风险硬失败最严重。
- 因此不按目标独立判断也没有值得晋级的版本。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但存在误用风险。
- 原因：本阶段三种语义运行前固定，没有按坏窗口或收益筛选；但如果事后只挑 `14:59 last close` 的高收益而忽略执行时点和硬约束，那就是过拟合/执行假设泄漏。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，但重点应从 alpha 优化转向执行语义工程。
- 原因：Stage153 证明预收盘分钟语义没有干净候选；继续救同日收盘口径参数价值低，但验证能否收盘前冻结信号、以及真实部署应配置多少风险缓冲仍有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录三种预收盘成交语义全部硬失败。
- 是否更新 `research/registry.md`：是，本阶段改变下一步优先级。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要执行口径长期记忆。
