# Stage135 no-JD Stage208 真成交账本降级证伪预声明

- 时间：`2026-07-11 19:12 CST`
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 阶段：`Stage135`
- 性质：只读研究 A/B/C；不改正式策略、实盘、CTP、邮件、launchd 或订单路径。

## 外部调研与判断

- TqSdk 官方历史回测/下载接口支持以明确 datetime 边界获取和重放分钟数据；Stage134 已进一步用交易日集合与成交窗口严格验收全部本地分钟文件。
- 交易所历史保证金会随日期变化，下载完成或当前静态合约规格不能证明历史逐日保证金有效。`jd.DCE` 精确逐日保证金仍缺，禁止用默认 `0.12`、当前比例或旧代理补齐。
- 判断：只允许一次明确标注为 degraded 的 no-JD 证伪。它能回答“Stage208 结构在当前 C9/15w 上是否仍有价值”，不能回答“完整正式含 JD 版本是否可部署”。

参考：

- TqSdk DataDownloader：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html>
- TqSdk TqBacktest：<https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.backtest.html>

## 冻结输入

- A 基准：Stage167 当前 `Stage847-C9-15w` 多起点曲线，账户初始资金 `150,000`。
- xsmom 信号：Stage020 `mom_12m_skip1m`，月初使用上一交易日已经形成的横截面排名。
- 价格与主力映射：Stage020 `product_returns`。
- 分钟成交：Stage119/134 验收后的逐合约一分钟数据。
- 产品规格：`qmt_universe.py` 中非 JD 产品的显式 `size / margin_ratio / slippage`；任何缺值均 fail-close。
- 排除项：仅从冻结的 long/short 名单删除 `jd.DCE`，不递补、不重排、不按收益选择替代品种。
- 可交易性边界：若冻结名单在当日没有主力合约/价格行，沿用历史 Stage208 `_desired_contracts` 语义跳过该腿且不递补，并单列 phantom leg 审计。静态审计已在收益运行前识别 `lc.GFEX` 上市前 `20` 腿、`SH.CZCE` 上市前 `44` 腿；这是 Stage020 排名宇宙的已知可交易性 bug，因此 Stage135 即使通过也不能直接晋级。
- 区间：先跑 `2020-01` 起点至 `2026-06-30` canary；通过后才扩展 `2020-01` 至 `2026-01` 的逐半年 13 个起点。

## 冻结规则

1. 先按无 JD 全量目标篮子构造最低一手 frozen PnL 序列；合约换月日不把跨合约价差计作收益。
2. 用全历史可观察序列计算 Stage101 scale：`daily_pnl / 150,000` 的过去 63 个交易日年化波动，目标波动 `10%`，scale 截断到 `[0,1]`，并要求过去 63 日累计 PnL 为正；全部 `shift(1)`，当天信息不得进入当天 scale。
3. scale `>=0.5` 时执行当月无 JD 目标篮子每腿一手，否则空仓。不得扫描窗口、目标波动、阈值、top/bottomN、成本、品种或方向。
   冻结名单里当日尚无可交易主力合约的腿按既有执行语义跳过，不递补、不重排。
4. 成交优先取 `signal_date 21:00-21:05` 第一根 open；没有夜盘时取 `fill_date 09:00-09:05` 第一根 open；任何真实调仓 fallback 必须为 `0`。
5. C 组合的每个交易日先用当前 C9 exact margin 与卫星 proposed margin 做聚合闸门：`(c9_total_margin_exact + satellite_margin) * 1.10 <= previous_combined_equity`。不通过时卫星目标归零；C9 路径保持冻结，不反馈重算 C9 持仓。
6. A/B/C：A 为冻结 C9；B 为 `150,000 + no-JD xsmom true PnL`，但它使用的是 C 聚合保证金闸门实际承载的同一卫星成交路径，只作腿贡献诊断；C 为冻结 C9 equity 加同一起点卫星累计真实 PnL。
7. 本轮是“真实卫星成交与持仓账本 + 冻结 C9 路径”的单向 overlay，不是完整单体回测引擎，不得在记录或结论中简称正式真引擎。

## 统计与会计口径

- 日净 PnL：持仓从上一 mark 到当日真实成交/收盘的逐段盯市 PnL，减 `abs(delta_lots) * slippage * size`。
- C 账户权益：`150,000 + cumulative(c9_net_pnl + satellite_true_net_pnl)`，必须与 `c9_account_equity + cumulative(satellite_true_net_pnl)` 逐日一致。
- 收益保留：`C total_return_pct / A total_return_pct`；只在 A 收益为正时计算并作为闸门。
- 最大回撤：账户权益相对历史峰值的最小百分比。
- 水下时长：权益低于此前峰值的连续交易日数；起点第一天不计收益和调仓。
- 胜率：只统计组合 `net_pnl != 0` 的交易日。
- 成本压力：在已含 1x 滑点的净 PnL 上，再扣 `(multiplier-1) * (A slippage + B slippage)`；固定 `1x/2x/3x`。
- 严格目标审计：复用 Stage009 的所有 `>365` 天起终点窗口，另报 `2022-01` 启动路径。

## Canary 晋级闸门

`2020-01` 起点必须同时满足：

- 所有真实调仓 fallback `=0`；
- 会计重算最大绝对误差 `<=1e-6`；
- aggregate broker10 margin/equity 最大值 `<=100%`；
- C 相对 A 收益保留 `>=70%`；
- C 最大回撤严格优于 A；
- C 最长连续水下交易日严格短于 A；
- B/C 权益均未破产。

任一失败即停止扩展，并关闭当前 Stage208 no-JD 路线，不做小参数救援。

## 全量闸门

只有 canary 全通过才运行：

- 13 个逐半年起点全部 fallback `=0`、会计误差 `<=1e-6`、aggregate broker10 `<=100%`；
- 所有 A 正收益起点的收益保留均 `>=70%`；
- 跨起点最差最大回撤和最差最长水下时长都严格优于 A；
- `2022-01` 起点的最大回撤和最长水下时长都严格优于 A；
- `2x/3x` 成本压力下仍满足收益保留 `>=70%`，且跨起点最差最大回撤不劣于对应成本下 A；
- Stage009 严格 `>1年` 负窗口数和最差收益只作目标诊断，不允许据此回调参数。

全量通过也只允许决策为“值得继续获取 JD 精确逐日保证金并做完整含 JD 复验”，不得直接晋级正式版。

## 反思

- 运行前过拟合判断：否。规则、排除原因和晋级闸门均在看结果前冻结；排除 JD 是数据有效性约束，不是按历史收益选品。
- 运行前继续价值判断：有。分钟阻塞已经清零，这一次固定证伪能低成本决定是否值得继续投入 JD 历史保证金数据工程；若失败，路线必须关闭。
