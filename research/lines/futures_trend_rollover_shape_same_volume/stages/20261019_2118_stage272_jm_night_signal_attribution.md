# Stage272：jm2701 夜盘未交易的日线信号与执行链路归因

- 时间：2026-10-19 21:18 CST。
- 研究线：`futures_trend_rollover_shape_same_volume`。只读归因，未调参、未跑引擎回测、未更新行情、未连接CTP/SMTP、未下单或撤单。
- 用户确认所看为 jm2701 日K。以下价格判断明确截至已收盘的2026-10-19，不把今晚正在形成的后续日K当作收盘输入。
- 过拟合：否，逐点核对既有固定规则，不按本次行情放宽条件。继续价值：是，必须区分价格形态、AI资格与生产执行缺口。

## 原始数据及信号

主力映射10月19日为`jm2701.DCE`。stable与当前mail DB各读取截至10月19日的41日真实价格，逐字段完全一致，首日8月14日；`_generate_signal`、`_calculate_macd`两个函数AST亦一致。现stable仍在候选d558、CURRENT旧m0008，不能称本次归因为已资格生产指令。

10月19日OHLC：1450 / 1480 / 1393 / 1403。

| 指标 | 前日 | 10月19日 |
| --- | ---: | ---: |
| MA5 | 1526.7 | 1498.1 |
| MA10 | 1500.35 | 1494.9 |
| MA20 | 1525.05 | 1515.95 |
| MA40 | 1571.025 | 1568.2125 |
| DIF | -19.5630056541 | -27.2051529320 |
| DEA | -19.9253087329 | -21.3812775727 |
| MACD柱 | 0.7246061576 | -11.6477507186 |

MACD确实死叉且柱为负；三组均线当日交叉均false，因此进入MACD case3判断。该分支要求`macd_death and bearish_alignment and allow_short`，其中bearish_alignment定义为`MA5 < MA10 < MA20 < MA40`。当日MA5比MA10高3.2点，故bearish_alignment=false、原始signal为空，未进入影线、量仓、AI、仓位、保证金或真实执行过滤。本次不能说“AI首先过滤了已存在空头信号”。

作为独立的新开仓资格限制，活动m0008且m0012原字节继承的9月30日AI池11品种中没有jm；未修改池子去迎合单次K线。

## 生产侧

独立agent于21:15后直接查询全部7个gui/501生产服务：均不存在，disk上的7个生产plist也不存在；production manifest、最终qualification、activation audit、activation receipt和data-readiness均缺失，生产信号及执行目录无945/930记录。20:55 canonical night-session因此未启动，不能把未下单解释成账户风控已运行后拒绝。

19:20/19:23候选资格失败是当时正式前置连接/快照缺失；**本次读取既有20:55 mail只读快照，auth/login/settlement/account/positions均完成且send/cancel=0**，说明不能把19:20网络状态机械延续为21点的原因。本次没有新CTP连接，不推断当前逐秒连通性。旧mail服务是查询/通知，不能替代Stage948生产激活。

新候选m0012已经过61suite/1805tests失败0，但完整资格仍未通过/未激活，本记录不把这些测试包装成部署完成。

## 调研与判断

核对了本地冻结策略分支、既有Stage270独立全品种法证和上游vn.py ArrayManager源码（https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py）。决定开仓条件的是本地自定义规则；不能用“MACD已死叉”或其他软件图示代替严格均线排列，也不能用未部署来反证信号是否成立。未改任何策略参数，无新增回测收益指标。

证据：`../outputs/stage272_jm_night_attribution/jm_diagnostic.json`、`jm2701_41_daily_bars.csv`；执行独审见Stage271 outputs下`independent_2115_production_execution_status.json`。独立价格复核结果另存本输出目录。
