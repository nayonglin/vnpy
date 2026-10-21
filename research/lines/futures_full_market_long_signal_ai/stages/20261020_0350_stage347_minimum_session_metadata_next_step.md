# Stage347：一次时段元数据补齐建议

2026-10-20 03:50 CST；line_id=`futures_full_market_long_signal_ai`。只读；0网络/raw/经济大表/SQL/实现/测试/fit/cash，T0None；不改旧源/LINE/registry。

**一次quote metadata批次可补周期模板，不能单独证明具体日期session。** 复用335已核[官方API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)及[维护者源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/datetime.py)，未重复联网。本机3.10.2 `get_quote_list`支持列表；`TradingTime.day/night`为时段数组，交割年月与expiry分列。

已有：338calendar确认19/20/21交易日；874-symbol并集、794身份、321receipt；342日期不证明session。317经济投影可沿用经济/lifecycle，**不能由绑定推导session**；未读8MB文件。真正缺逐symbol模板、日期适用/例外及首个可成交时刻。

建议仅授权一次连接、一次`get_quote_list(338既存874并集)`，固定总超时、无重试/新目录/serial。仅存symbol、exchange/ins_class、`trading_time.day/night`、交割年/月、expiry、tick/乘数、SDK版本及实际UTC receipt；后两经济字段仅交叉核对，不自动替换旧单位。保留4新及76旧unknown；metadata缺失逐项unknown，不拆成多轮probe。身份未知不妨碍按原symbol保存模板；交割年月可辅助显式身份，expiry年月不能替代名义月份。未知身份仍不能进入模型。

形成日期区间时只补19—21日及其相关前夜的日程适用证据：沿335已核交易所通知；未覆盖交易所/临时例外明确unknown。quote周期模板和交易日calendar均不是节假日夜盘证明，无证据不能签全98已完成。普通夜盘锚到前一实际开市自然日，25:00按锚日+25小时，周末/长假不得用18点helper盲补。CFFEX债09:15与股09:30须分开确认，不能全市场套09:00；集合竞价起点另列，不替换实际可成交open。

最小输出每symbol/date：具体区间及证据、`session_end_at`、`D_date/D_open_at/state`、override状态。u19取已确认最后session末端；D20取所属交易日全部实际时段的最早可成交open（有夜盘可能在19日晚）。`source_completed_at=session_end_at`；实际fresh-ready接收是`completion_observed_at/received_at`，不是完成或首次发布。当前quote也不能倒证历史首发。

以后采u20：在20日实际依赖产品最晚已确认session_end之后、D21最早已确认open之前，一次fresh-ready快照；不等21日日K或加稳定等待。影响者时段未知则观察，不选赢家后放宽deadline。迟到不补决定；T0未签不称forward。保留98域/unsupported，337/root canonical overlay决定模型可用行，无需生产资格。

开始/结束：无收益调参；补时钟有价值，旧资格/训练无必要。金融指标N/A、累计不变；不授权查询/T0/资金state。
