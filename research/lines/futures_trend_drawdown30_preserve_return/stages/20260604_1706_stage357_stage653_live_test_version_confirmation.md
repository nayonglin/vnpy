# Stage357：Stage653 夜盘测试准实盘版本确认

- 时间：2026-06-04 17:06 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 决策：`stage653_force95_to80_confirmed_as_live_test_candidate_not_full_live_approved`
- 版本状态：夜盘测试准实盘版本 / `live_test_candidate`
- 是否正常手数实盘批准：否
- 是否允许今晚测试：是，仅限测试环境、只读快照、dry-run、1 手 smoke order 闸门
- 是否改策略代码：否
- 是否新增回测：否
- 是否调用下单 API：否

## 确认版本

本阶段把用户偏好的高收益 all-in 路线固定为今晚夜盘测试对象：

`stage526_200k_force95_to80_largest_margin_r080_pc25_maxpos4`

简称：`Stage653 force95->80`

该版本含义：

- 基础策略：Stage526 `r080_pc25_maxpos4`
- 账户资金：`200,000`
- 风险倍率：`0.80`
- 单产品保证金 cap：`25%`
- 最大同时活跃产品：`4`
- 保证金强制减仓：超过 `95%` 后，按最大保证金占用品种逐手减仓，目标降到 `80%`
- 成交语义：完整日K确认后，订单在下一真实窗口成交；不是同日收盘价成交

## 指标摘要

Stage353 固定结果：

- 期末权益：`10,415,070`
- 总收益：`5107.5350%`
- 年化收益率：`86.8222%`
- 最大回撤：`-38.8730%`
- Sharpe：`1.6384`
- 总滑点：`597,710`
- 总交易次数：`655`
- 胜率：`52.3156%`
- 相对 20 万 all-in 原版收益保留：`89.9664%`
- broker10 最大保证金/权益：`83.3212%`
- 超过 100% 保证金天数：`0`
- 强制减仓：`6` 次 / `317` 手
- 2x 成本最大回撤：`-41.3142%`
- 3x 成本最大回撤：`-43.9072%`
- hard_pass：`0`

## 为什么只能确认为测试准实盘，而不是正常实盘批准

正向证据：

1. 已修正旧同日收盘成交理想化，当前 Stage653 使用 `ConfirmedDailyNextRealOpenEngine`。
2. 20万 all-in 原版保证金峰值 `120.0983%`、超100% `2` 天；`force95->80` 把 broker10 峰值降到 `83.3212%` 且超100%为 `0`。
3. 收益仍保留 all-in 原版约 `90%`，符合用户偏好的高收益进攻路线。
4. Stage354/355 已确认实盘保证金触发不能用 vn.py `AccountData.frozen`，必须使用显式当前保证金或 CTP raw `CurrMargin`；Stage656 曾成功拿到 native CP `CurrMargin`。

未关账风险：

1. 2x/3x 成本最大回撤仍打穿 `-40%`。
2. 券商 CP 前置最新 Stage356 TCP 不可达，`41407/41415/41207/41215` 均 timeout。
3. 1 手 smoke order 尚未完成本轮官方采集库路线下的 submit-cancel。
4. 精确 `bridge_signal_id -> vt_orderid -> EVENT_ORDER/EVENT_TRADE/EVENT_TICK -> TCA` 样本仍缺。
5. 真实成交质量、排队、部分成交、拒单、撤单延迟仍未用当前版本关账。

因此，本阶段确认的是：

> `Stage653 force95->80` 是今晚夜盘测试准实盘版本；不是正常策略手数实盘批准。

## 今晚夜盘测试闸门

按顺序执行，任一步失败即停止：

1. 刷新 TCP/只读快照：
   - 要求 `front_connected/auth_ok/login_ok/settlement_ok=true`
   - 要求 `account_rows>=1`
   - 要求 `explicit_margin_rows>=1`
   - 要求 `send_order_api_called_count=0`
2. 运行 smoke order dry-run：
   - 要求 request ready
   - 要求 `send_order_api_called_count=0`
3. 用户再次确认测试环境和 submit 动作后，才允许 1 手 submit-cancel：
   - `volume=1`
   - 明确确认 token
   - 被动或刻意选择的价格
   - 记录 `OrderRef/FrontID/SessionID/OrderSysID`
   - 记录 `OnRspOrderInsert/OnErrRtnOrderInsert/OnRtnOrder/OnRtnTrade`
4. 若 1 手测试成交：
   - 立即记录成交
   - 检查残余持仓
   - 必要时只做平仓/撤单/对账，不进入正常手数
5. 只有 1 手链路、撤单/成交回报、残余持仓检查、TCA bridge 均通过后，才讨论正常策略委托。

## 外部调研与判断

本阶段没有新增联网调研，不新增策略逻辑。判断沿用既有执行证据：

- 事件驱动回测底线：完整日K确认后的订单不能按同日收盘价成交，当前 Stage653 已沿用下一真实窗口成交。
- CTP 下单链路底线：真实 submit 前必须有 fresh read-only 账户快照、dry-run 和显式 1 手测试确认。
- 实盘保证金触发底线：使用 CTP raw `CurrMargin` 或等价显式当前保证金字段，不能使用 vn.py `AccountData.frozen`。

## 反过拟合反思

否。本阶段没有调参数、没有新增回测、没有按历史收益筛选品种或日期；只是把既有固定候选登记为今晚测试对象，减少临时决策漂移。

## 继续价值反思

有价值。现在继续优化历史回测价值低，真正价值在夜盘测试链路：前置可达性、1 手 submit-cancel、订单回报、成交/TCA、残余持仓检查。

## 进一步规划

1. 夜盘开始后先重跑 Stage656 native CP read-only。
2. 若 Stage656 通过，再运行 Stage281 dry-run。
3. 若 dry-run 通过，并且用户再次确认 submit 动作，再发 1 手 submit-cancel。
4. 记录 Stage358 夜盘测试结果；若成功，再补 live TCA bridge，不直接放开正常手数。
