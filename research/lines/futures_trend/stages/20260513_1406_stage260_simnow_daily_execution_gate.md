# Stage260 Stage78-1 SimNow每日执行闸门

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-13 14:06
- 阶段性质：每日虚拟盘SOP / 理论信号与SimNow实际持仓对账
- 是否重要突破：是
- 是否触发A/B：否，本阶段不修改策略、不比较收益、不引入新alpha

## 外部调研与判断

- 本阶段没有新增外部调研，沿用Stage257-259的SimNow/vn.py执行SOP和本地源码审计结论。
- 判断：进入虚拟盘后，不能直接把历史影子盘持仓当作账户持仓；必须以SimNow只读快照为准。

## 本次变更

- 新增 `examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py`
  - 读取Stage188最新AI池影子信号。
  - 读取Stage174 SimNow只读账户/持仓/订单快照。
  - 逐笔判断信号是否可进入SimNow执行。
  - 本脚本只做闸门判断，不调用发单API。
- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage244_phaseb_pre_submit_check.py`
  - 活跃委托判断改为按同一 `orderid/vt_orderid` 的最新状态判断。
  - 补充 `Not Traded`、中文状态等状态归一。

## 新增参数

- `--max-snapshot-age-seconds`

## 修改参数

- 无策略参数修改。

## 删除参数

- 无。

## 本次运行

### SimNow只读快照

- 命令：`env SIMNOW_FRONT=trading bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 120`
- 时间：2026-05-13 14:03
- 状态：`readonly_snapshots_received`
- 持仓语义：`confirmed_flat`
- 持仓行：`5`
- 非零持仓行：`0`
- 账户实际状态：空仓

### 每日执行闸门

- 命令：`.py311/bin/python examples/portfolio_backtesting/run_qmt_roll_stage260_stage78_1_simnow_daily_execution_gate.py --max-snapshot-age-seconds 300`
- 目标交易日：`2026-05-12`
- Stage188生成时间：`2026-05-12 20:13`
- AI池最新eval_date：`2026-04-21`
- 风险级别：`review`
- 只读快照年龄：`175.9`秒
- 理论信号数：`1`
- 可执行信号数：`0`
- 因账户空仓跳过平仓数：`1`
- 阻断数：`0`
- 委托API调用次数：`0`

## 信号执行判断

| vt_symbol | direction | offset | volume | risk_level | broker_position | action | reason |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `si2609.GFEX` | `short` | `close` | 1 | `review` | 0 | `skip_broker_flat_for_close` | `no_matching_long_position_to_close` |

## 输出文件

- Decision CSV：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_stage78_1_simnow_daily_execution_gate_decisions_20260512_stage260_stage78_1_simnow_daily_execution_gate_v1.csv`
- Summary JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_stage78_1_simnow_daily_execution_gate_summary_20260512_stage260_stage78_1_simnow_daily_execution_gate_v1.json`
- Report MD：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage260_stage78_1_simnow_daily_execution_gate_report_20260512_stage260_stage78_1_simnow_daily_execution_gate_v1.md`

## 新增回测结果

- 无。本阶段没有运行回测。

## 修改回测结果

- 无。

## 删除回测结果

- 无。

## 固定指标占位

- 期末权益：无，本阶段无回测。
- 总收益：无，本阶段无回测。
- 最大回撤：无，本阶段无回测。
- Sharpe：无，本阶段无回测。
- 总滑点：无，本阶段无回测。
- 总交易次数：无，本阶段无回测。
- 胜率：无，本阶段无回测。

## 结论

- 当前Stage78-1最新信号是平 `si2609.GFEX` 多头1手。
- SimNow账户实际没有 `si2609.GFEX` 多头持仓。
- 因此今天不应发送任何策略委托。
- `review`风险状态下本来只允许平仓/降风险；但账户为空仓时，对空仓发平仓单是错误动作。
- 虚拟盘从真实SimNow空仓状态冷启动，历史影子盘持仓差异只记录，不回填。

## 过拟合反思

- 运行前判断：否。每日执行闸门只比较既有信号和SimNow持仓，不改策略参数。
- 运行后判断：否。本阶段没有根据结果调整策略，也没有生成新alpha规则。

## 继续价值反思

- 运行前判断：有价值。虚拟盘必须从账户状态对账开始，不能直接执行理论信号。
- 运行后判断：有价值。今天明确没有可执行委托，下一步应等5月13日收盘数据完整后生成5月13日报，再决定下一交易时段是否执行。

## TODO

- 5月13日收盘数据完整后，运行Stage173更新主力和日线。
- 复跑Stage188最新AI池日报，生成目标交易日为 `2026-05-13` 的信号。
- 再运行Stage260执行闸门；若出现可执行开仓信号，`review`状态仍应阻断开仓，若出现可执行平仓信号则需SimNow有对应持仓。
