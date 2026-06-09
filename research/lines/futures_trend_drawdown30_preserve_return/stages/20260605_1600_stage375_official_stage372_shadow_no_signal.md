# Stage375 - 正式版 Stage372 影子盘日内信号检查

- 时间：2026-06-05 16:00 CST
- line_id：`futures_trend_drawdown30_preserve_return`
- 阶段：Stage375
- 触发原因：用户要求“正式版本跑一下影子盘，看看今天有没有交易信号”。
- 当前工作模式：`day`
- 当前正式版本：`official_live_stage372_20w_recovery_sleeve`
- 当前策略体：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
- 当前资金口径：20万，仅用于正式/影子盘执行口径；未切换到 30万实验口径。

## 执行命令

1. 更新 2026-06 主力映射和日线：

```bash
.py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py --mapping-start 2026-06-01 --bar-start 2026-06-01 --end 2026-06-05
```

2. 运行正式版最新 AI 池影子盘：

```bash
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage659_stage653_2026_ytd_latest_ai_shadow.py --target-date 2026-06-05
```

## 数据与 AI 池

- 最新可用行情日期：`2026-06-05`
- Stage173 更新结果：21 个合约保存成功，失败 0，空数据 0。
- AI 池文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- AI 池最新 eval_date：`2026-05-29`
- 最新 AI 池品种：`SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE`

## 影子盘结果

- 决策：`stage372_2026_ytd_latest_ai_shadow_measured_no_order_api`
- 统计区间：`2026-01-01` 至 `2026-06-05`
- 期末权益：`216,080`
- 总收益：`8.04%`
- 最大回撤：`-16.3027%`
- Sharpe：`0.7780`
- 总滑点：`1,550`
- 总交易次数：`22`
- 胜率：`47.6190%`
- broker10 保证金峰值：`55.1058%`
- 超 90% / 100% 保证金天数：`0 / 0`
- deployable_pass：`1`
- 强制减仓次数/手数：`0 / 0`
- 今日 target_signal_count：`0`

## 今日信号与持仓解释

- 今日信号计划文件只有表头，没有新增开仓、平仓或换仓信号。
- 影子盘理论当前持仓：
  - `OI609.CZCE` 多 3 手，收盘价 `9990`
  - `jm2609.DCE` 多 2 手，收盘价 `1459`
- 这些是“从 2026 年初连续运行”的影子盘理论持仓，不代表真实账户必须追补。真实/虚拟执行必须以 CTP 账户快照为准；如果真实账户为空仓，不应因为影子盘有历史持仓而补开历史仓。

## 执行边界

- 本次为只读影子盘，不连接 CTP，不读取账户，不调用下单 API。
- order API 调用次数：`0`
- 因今日 target_signal_count 为 `0`，不需要进入今日下单 dry-run。
- 如后续要判断真实账户是否与影子盘理论仓位对齐，应单独跑 fresh read-only 账户快照和每日执行 gate；无新信号时仍不得追补历史影子仓位。

## 输出文件

- 日报：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_report_stage659_stage372_2026_ytd_latest_ai_shadow_v1.md`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_decision_stage659_stage372_2026_ytd_latest_ai_shadow_v1.json`
- 信号计划：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_signal_plan_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- 当前理论持仓：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage659_stage372_2026_ytd_latest_ai_shadow_current_positions_stage659_stage372_2026_ytd_latest_ai_shadow_v1.csv`
- 数据更新摘要：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`

## 过拟合与继续价值

- 运行前过拟合判断：否。本次只更新行情并按已锁定正式版本跑日常影子盘，不修改 alpha、参数、AI 排名或资金规则。
- 运行后过拟合判断：否。结果用于执行检查，不参与挑参。
- 运行前继续价值判断：是。正式版日常影子盘直接回答今天是否有交易信号。
- 运行后继续价值判断：是。今日无新增交易信号，但影子盘理论持仓和真实账户是否一致仍需要在进入真实执行前由 CTP fresh snapshot 约束。

## 后续 TODO

- 若用户只关心今日是否交易：结论为今日无新增交易信号，不下单。
- 若用户要做账户对齐：下一步跑 CTP fresh read-only，再跑每日执行 gate；不得用影子盘历史持仓直接补仓。
