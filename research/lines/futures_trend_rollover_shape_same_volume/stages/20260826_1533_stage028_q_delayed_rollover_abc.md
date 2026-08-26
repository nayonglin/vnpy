# Stage028 新主力自身K线延迟5交易日换月 A/B/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-26 15:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/fix-rollover-new-contract-history` / `codex/stage028-rollover-delay-5d`
- 阶段性质：基于 Stage027 的单变量延迟换月研究
- 是否重要突破：否；全周期收益改善明显，但正式 Sharpe 与 broker100 硬闸失败
- 是否触发A/B/C：是；`A=正式Q`、`B=Stage027新主力自身K线立即换月`、`C=B+延迟5个交易日`

## 外部调研与判断

- CME 的换月说明指出，实际换月通常观察旧、新合约成交量迁移；延期持有旧合约会同时承受流动性下降与到期风险。
- Ma、Mercer、Walker（1992）说明换月日期和连续序列构造会改变交易规则的风险收益测量。
- 本阶段判断：固定5个交易日是低自由度、可证伪的执行时点假设，但不是交易所通用最优规则；不能在结果出来后继续扫描3/4/6/7天。

## 本次版本变更

- 新增配置：`examples/portfolio_backtesting/qmt_roll_candidate_stage028_delayed_rollover_config.py`。
- 新增回测器：`research/lines/futures_trend_rollover_shape_same_volume/tools/stage028_q_delayed_rollover_abc.py`。
- 新增测试：`tests/test_stage028_delayed_rollover.py`。
- 修改策略：增加可选延迟换月状态；默认值为0，因此正式Q和Stage027立即换月路径不变。
- 修改回测采集器：只新增 `rollover_delay` 诊断帧，不改变交易规则。
- 新增参数：`rollover_delay_trading_days=5`；候选版本 `stage028_q_target_contract_history_delay_5td_v1`。
- 修改参数：无；Stage027 的 `target_contract_only`、MA/MACD、成交量风险、ATR拦截、缩手和正式Q其余参数全部不变。
- 删除参数：无。
- 状态机：D0登记；D1-D4继续管理旧合约但禁止加仓/反向新开；D5若旧仓仍在则平旧，并以D5当时新合约自身K线重新判断。等待期止损/退出会取消任务；目标再次变化则重置计时。

## 身份与回测参数

- Stage028 基线提交：`d4b54531dee806321c4dd4ec6c921629fda04593`（Stage027）。
- 远端 master：`09aa96a03fb91124be90bd69861be3f834ab6299`。
- 正式/生产六身份一致：ruleset `stage021_q_rollover_volume_atr_v1`，活动物料 `m0015_20260825T205121+0800_c097d7836dd4`。
- 区间：`2018-01-01 -> 2026-08-25`；账户：`150,000`；真实引擎、正式AI池/产品池、正式成本和broker10口径。
- C相对B唯一覆盖差异：`rollover_delay_trading_days: 未设置(默认0) -> 5`。

## 回测结果

| 指标 | A 正式Q | B Stage027 | C Stage028 |
| --- | ---: | ---: | ---: |
| 期末权益 | 14,989,515.10 | 13,868,439.90 | 15,889,543.30 |
| 总收益 | 9893.0101% | 9145.6266% | 10493.0289% |
| 最大回撤 | -44.9033% | -47.9843% | -46.4506% |
| Sharpe | 1.468555 | 1.418929 | 1.437784 |
| 总滑点 | 1,741,690 | 1,685,830 | 1,654,705 |
| 总交易次数 | 846 | 834 | 810 |
| 胜率 | 52.6728% | 52.6274% | 52.8229% |
| broker10峰值 | 99.6724% | 87.7838% | 100.3426% |
| broker10超过100%天数 | 0 | 0 | 1 |

### 新增/修改/删除的回测结果

- 新增结果：C-B期末权益 `+2,021,103.40`、收益 `+1347.4023pp`、回撤改善 `1.5337pp`、Sharpe `+0.018855`、滑点 `-31,125`、交易 `-24`。
- 新增结果：C-A期末权益 `+900,028.20`、收益 `+600.0188pp`，但回撤恶化 `1.5473pp`、Sharpe `-0.030771`；滑点 `-86,985`、交易 `-36`。
- 修改结果：无，A/B与Stage027独立回测逐值一致。
- 删除结果：删除“延迟5天能够让原来只有1根新合约K线的事件满足40根”的假设；5次均只增长到6根，仍因历史不足跳过。

## 换月合同与归因

- C共登记24次延迟任务：14次坚持到D5，10次等待期被旧仓原生风控提前关闭。
- 14次D5事件全部严格 `elapsed_trading_days=5`；所有C换月诊断都与D5 due记录一一对应。
- 14次D5事件中8次续开、6次跳过；5次因新合约只有6根K线不足40根，1次因形态/MACD不一致。
- 10次等待期退出：多头前2日止损4次、多头基础止损2次、空头前2日止损2次、风险簇降杠杆1次、空头基础止损1次。
- 等待期间没有加仓或反向新开；退出后任务清空，不会在D5凭旧信号重新开仓。

## 验证与闸门

- 状态机/配置/正式身份聚焦测试：`20 passed + 14 subtests`；`py_compile`通过。
- 真引擎小样本验证：`si2501→si2502` 于2024-12-16登记，12月23日第五个后续交易日执行。
- 通过：单变量范围、target-only合同、5日计数合同、账户生存、C相对B收益/回撤/Sharpe/成本门、C相对A回撤门。
- 失败：C相对A Sharpe差 `-0.030771 < -0.02`；C在2020-10-15出现broker10 `100.3426%`，超过100%一天。
- 首轮决策器遗漏broker100字段；发现结果后补回既有正式硬闸并透明记录。该修正不改变策略参数，且首轮本已因Sharpe失败，最终决策不变。
- 决策：`stage028_delay_5td_fail_full_period_keep_research_only`；不自动多周期、不晋升、不修改master/正式物料/生产/CTP。

## 输出

- decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage028/stage028_decision.json`
- summary/comparison：`stage028_abc_summary.csv` / `stage028_abc_comparison.csv`
- curve/chart：`stage028_abc_curve.csv` / `stage028_full_period_equity_abc.png`
- rollover/delay：`stage028_rollover_diagnostics.csv` / `stage028_delay_diagnostics.csv`
- trades/events：`stage028_trades.csv` / `stage028_trade_events.csv`

## 过拟合反思

- 运行前判断：否；用户预先固定5个交易日，只有一个自由度，没有按品种、年份或输赢窗口调参。
- 运行后判断：本轮本身仍不是结果后拟合，但14个真正执行样本很小，单次完整周期的复利优势可能由少数路径驱动；继续扫描延迟天数、品种或退出例外将构成明显过拟合。

## 继续价值反思与TODO

- 运行前判断：有价值；检验新合约价格发现与旧仓继续管理能否改善立即换月路径。
- 运行后判断：有继续验证价值，但没有立即晋升价值。
- 原因：C同时改善A/B期末权益且改善B回撤/Sharpe，机制真实；但正式Sharpe和broker100硬闸失败，不能用收益覆盖风险反证。
- TODO：等待用户决定是否保持5天完全冻结，运行固定多周期；不扫描2-10天，不增加品种/年份/方向例外，不为2020-10-15单日超限修改alpha。

