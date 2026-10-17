# Stage005 零账户枚举潜在初始信号及首日分钟需求

- line_id：futures_trend_triple_screen；冻结时间2026-10-17 23:26 CST。
- 性质：数据需求生成，不是新alpha或金融回放；不读取收益、不下载、不修改Stage001/002/004或正式策略。

## 来源与固定语义

沿用Elder/LEAN/Backtrader多周期调研，另核对[Backtrader次bar开盘成交说明](https://backtrader.com/blog/posts/2017-05-01-cheat-on-open/cheat-on-open/)与[GitHub broker源码](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)。本阶段核心依据是当前已接受C9实际源码与A0 settings，而不是实现另一份近似指标公式。

1. 复用实际`_generate_signal(am, history)`、`_build_history_df(am)`及真实`ArrayManager(41)`，按A0实际settings设置对象。禁止调用账户规划/手数/权益/连败/持仓/组合排序接口；不能为枚举信号实际运行空仓账户。
2. 原加载起点2019-06-01（DB首bar2019-06-03）、实际warmup_days=90、trade_start_date=2020-01-01、截止2026-10-14。AM初始为原实现零数组，所有metadata真实合约均按每日真实bar连续更新，包括成为主力前的行情；缺日不填carry，不在2020重新清空，不用整段历史EMA代替AM41滚动历史。
3. 每日先更新全部真实bar对应AM，再按当日mapping的真实目标合约计算信号。目标bar缺失或AM未暖机则记录原因，不生成初始信号。实施前再次确认flat分支不会在carry目标上开仓；已有持仓引起的延迟换月不属于本阶段的flat事件。
4. 不按旧A成交、持仓、资金、保证金、maxpos、风险手数和胜负筛掉信号。保留全部19基础品种raw alpha事件。固定AI许可可单独注释，不能为简化改变资格语义或把未知当拒绝；本阶段允许不按AI删事件，保留可解释的上界。
5. C0周许可可单独记录/派生子集：继续读取同SHA完成周状态，ready反向/零方向为不能产生新flat开仓，unknown保留原始信号。不得扫MACD或其他参数。

## 订单时间及分钟需求

信号日u的订单仍属于u日指定真实合约；生效日是下一全局engine日线批次日期，不是自然日加一天，也不能换成u+1的新主力。原Stage502先撮合旧单再计算当天信号。首分钟时间使用该生效交易日和原session helper/完整源日历；末日无下一批次记terminal_pending。

对每个潜在初始信号，生成首日完整session需求（覆盖可能的0.5R、retry和C2先后顺序），并与已验base＋overlay索引比较。输出逐事件、去重session、按年/产品的覆盖/缺口及与现有本机候选路径关联。拒绝重复输入键；本阶段不接入未验来源。

该表可以准确枚举固定纯信号接口的潜在初始事件，但**不是实际成交集合，也不是完整策略分钟需求证明**。加仓/换月重开也为OPEN、普通CLOSE也需anchor，均需另列闭包；未来独立B的新信号不能用该C9事件集替代。此阶段不授权C0_attempt3，即使全部初始事件已有分钟也不能声称全账户路径已齐。

## 验证与产物

- 有意义验证：AM41暖机边界/非主力历史连续更新；只用当日及以前历史；目标缺bar不产生flat；下一全局日及跨周末夜盘映射；末日pending；周unknown回退；向量分钟计数与已有已验helper一致。
- 将原A0 `entry_candidates`中只读的date/product/contract/signal字段与事件集做已知子集检查，不读PnL或candidate胜负；匹配不是充分证明全部路径，但漏任何已知初始信号都不接受。
- 冻结源码、实际settings、DB/mapping/周状态/覆盖源指纹和运行runtime。只运行一次指标流枚举；失败留receipt，不循环修正得到期待信号数。
- 输出金融指标N/A、金融attempt=0、训练/下载=0；独立agent仅复核信号接口/时序和少量哨点，不重复旧全量账户/周表QA。

过拟合判断：否，不以收益选择事件或参数；原策略历史选择风险仍在。继续价值：是，先定位可交易初始机会对应的真实数据缺口，能把数十万理论session上界收敛成有意义的事件需求，减少后续无效金融重跑。
