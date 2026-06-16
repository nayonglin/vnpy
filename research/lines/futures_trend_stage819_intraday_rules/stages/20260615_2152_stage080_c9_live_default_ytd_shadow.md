# Stage080 C9 切为当前实盘默认并跑 2026 年初至今影子盘

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 21:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式默认切换、只读影子盘、执行治理记录
- 是否重要突破：是。`OFFICIAL_LIVE_VERSION` 已按用户 operator override 从 Stage372/20w 切为 C9/30w。
- 是否触发A/B：是，C9 已进入正式默认口径；本阶段没有新增 A/B 策略参数，只做 live default 注册和 shadow。

## 外部调研与判断

- 参考资料：
  - vn.py 官方仓库 README：确认 vn.py 支持多合约组合回测与实盘自动交易框架，本次仍必须以本仓库官方配置为准。
  - FCA algorithmic trading controls 高层观察：强调算法交易上线前的治理、控制、监控和变更管理。
  - FIA algorithmic trading providers guidance：强调 pre-trade controls、风险限制、监控、记录与变更审批。
- 我的判断：外部资料不提供可直接复制的策略 alpha，但支持“正式默认切换必须记录、可回滚、可监控、执行 fail-closed”的工程纪律。用户已明确接受 C9 回撤并要求切默认，因此允许 operator override；但真实报单仍不能跳过 read-only、dry-run、broker-state reconciliation 和显式下单确认。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
- 修改脚本：
  - `examples/portfolio_backtesting/qmt_roll_official_live_config.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py`
- 删除脚本：无
- 新增参数：
  - `OFFICIAL_LIVE_PREVIOUS_VERSION=official_live_stage372_20w_recovery_sleeve`
  - `OFFICIAL_LIVE_PREVIOUS_PROFILE_NAME=stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - `OFFICIAL_LIVE_ROLE=official_live_deployment_profile_operator_override_high_risk`
  - C9 shadow 输出前缀 `qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow`
- 修改参数：
  - `OFFICIAL_LIVE_VERSION`：从 `official_live_stage372_20w_recovery_sleeve` 改为 `official_live_stage847_c9_30w_stage819_05r_stop_retry_once`
  - `OFFICIAL_LIVE_ALIAS`：从 Stage372/20w 改为 `Stage847-C9-30w`
  - `OFFICIAL_LIVE_CAPITAL`：从 `200000` 改为 `300000`
  - `OFFICIAL_LIVE_STRATEGY_OVERRIDES`：改为 C9 官方候选冻结覆盖项，继承 Stage819 30w、C2 intraday stop、broker10 cap、`0.5R` stop/retry once
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-01-01` 至 `2026-06-12`
- 最新完成交易日：`2026-06-12`
- 账户规模：`300000`
- 成本口径：基础滑点 `1x`，另输出 `2x/3x` 成本压力
- 样本过滤：当前 C9 正式默认 profile，按本地最新主力映射与日线数据；本阶段先补到 `2026-06-12`
- 策略/归因口径：只读历史 shadow，不连接 CTP，不读取真实账户，不调用下单或撤单 API

## 结果

- 期末权益：`265,860`
- 总收益：`-11.38%`
- 最大回撤：`-14.8955%`
- Sharpe：`-1.1331`
- 总滑点：`3,860`
- 总交易次数：`27`
- 胜率：`45.7143%`（非零日胜率）
- 其他关键指标：
  - CAGR：`-24.3675%`
  - max broker10 margin/equity：`54.8506%`
  - p95 broker10 margin/equity：`31.8104%`
  - `days_over_100pct=0`
  - `days_over_90pct=0`
  - `days_equity_below_zero=0`
  - `deployable_pass=1`
  - 风险层级：`normal`
  - `allow_shadow_record=1`
  - `allow_real_new_orders=1`
  - `order_api_called=false`
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
  - target-date 后 pending order 数：`1`

## 目标日持仓与信号

- 当前持仓：`MA609.CZCE` 多单 `12` 手，2026-06-12 收盘价 `3010`，估算保证金 `43,344`
- 目标日信号计划：`MA609.CZCE` `Long Open` `12` 手，理论价 `3029`
- 信号计划性质：`historical_shadow_trade_price_no_broker_submit`，代表历史回放中的成交记录，不等同于下一交易时段待执行指令。
- target-date 后 pending order：`BACKTESTING.28`，`MA609.CZCE` `Short Close` `12` 手，理论价 `3010`，状态 `Submitting`。
- target-date trade event：`MA609.CZCE` 多头因 `long_risk_cluster_heat_deleverage` 触发平仓。
- target-date entry candidates：`0`，没有新的开仓候选。
- 真实执行备注：pending close 只是影子盘理论平仓指令；若要真实处理，必须重新进入 CTP/SimNow/券商 SOP 的 read-only、dry-run、账户持仓对账和显式报单确认。若真实账户没有匹配的 `MA609.CZCE` 多头持仓，必须 fail-closed，不得发送平仓单。

## 月度结果

| 月份 | 期初权益 | 期末权益 | 收益 | 最大回撤 | 交易数 | 滑点 | max broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-01 | 300,000 | 299,260 | -0.2467% | -6.5206% | 8 | 1,640 | 54.8506% |
| 2026-02 | 299,260 | 289,420 | -3.2881% | -6.5963% | 5 | 590 | 31.9566% |
| 2026-03 | 289,420 | 277,560 | -4.0979% | -7.9636% | 9 | 1,210 | 38.4084% |
| 2026-04 | 277,560 | 275,520 | -0.7350% | -0.7350% | 1 | 120 | 11.6477% |
| 2026-05 | 275,520 | 265,800 | -3.5279% | -3.6150% | 1 | 120 | 12.5797% |
| 2026-06 | 265,800 | 265,860 | 0.0226% | -4.6687% | 3 | 180 | 17.9336% |

## 成本压力

| 成本倍数 | 期末权益 | 总收益 | 最大回撤 | Sharpe | max broker10 | deployable |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1x | 265,860 | -11.3800% | -14.8955% | -1.1331 | 54.8506% | 1 |
| 2x | 262,000 | -12.6667% | -15.5928% | -1.2708 | 54.9447% | 1 |
| 3x | 258,140 | -13.9533% | -16.6457% | -1.4073 | 55.0392% | 1 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_report_stage901_stage847_c9_2026_ytd_live_shadow_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_summary_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_decision_stage901_stage847_c9_2026_ytd_live_shadow_v1.json`
- current positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_current_positions_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- signal plan：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_signal_plan_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- pending orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_pending_orders_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_daily_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- monthly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_monthly_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow_trades_stage901_stage847_c9_2026_ytd_live_shadow_v1.csv`

## 结论

- 本阶段结论：C9 已按用户要求切为当前实盘默认配置；2026 年初至最新完成交易日的影子盘为负收益，但风险闸门未触发硬失败。目标日信号计划里有 `MA609.CZCE` 多开 `12` 手的历史回放成交记录；更关键的是 target-date 后 active pending order 为 `MA609.CZCE` `Short Close` `12` 手，理论价 `3010`，对应多头 heat deleverage 平仓。
- 是否进入下一步：进入执行治理下一步，但不是直接真实报单。
- 下一步：
  1. 若用户要求真实处理 `MA609.CZCE` pending close，先按 CTP/SimNow SOP 做 read-only 账户/持仓/前置 runtime gate。
  2. 再做 dry-run，核对 pending、最终交易日信号、账户持仓差异和保证金。
  3. 只有真实账户存在匹配多头且用户再次明确下单确认后，才允许进入报单草案或真实报单路径。

## 过拟合反思

- 运行前判断：不是新增过拟合，但有风险接受问题。
- 运行后判断：不是过拟合。
- 原因：本阶段没有新增策略参数、没有按 2026 年负收益救参，也没有按目标日信号改规则；只是按用户明确要求把已冻结 C9 切为 live default，并跑固定区间 shadow。真正的风险不是参数过拟合，而是 operator override 选择性接受 C9 的历史大回撤尾部。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值在执行治理而非继续优化 C9。
- 原因：正式默认已经切换，必须用最新 shadow、dry-run、账户对账和 fail-closed 监控保护真实执行；继续扫 R 倍数、重试次数、月份、品种、方向或窗口没有价值，且会抬高过拟合风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 C9 已切为当前实盘默认和 Stage901 shadow 结果。
- 是否更新 `research/registry.md`：建议由合入者统一更新；因这是正式默认变更，后续合入时必须把 Stage372 从当前默认改为 previous default。
- 是否追加根目录 `memory.md/back_log.md`：是，属于正式默认切换与重要执行里程碑。
