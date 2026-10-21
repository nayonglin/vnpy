# Stage029 两个真实来源见证连接独立复核

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:08 CST；day。
- 独立reviewer；研究源halfR/retry=False，C2保留，正式未改。非重要收益突破。

Stage028单次probe运行时间为2026-10-20 21:06:34。对84精确epoch/date键逐键只读SQL，OHLC/source_id与bound CSV一致、无重复；DB stat、源码/输入/输出/calender及两个既有minute projection SHA一致。每例41bars止于execution day，signal为前一source day，nextday只proxy不进features。独立Decimal Wilder RSI6与previousMA20一致。

AU手算ATR14=3.76，日close变动4.66<7.52，不更新ATR mid stop；maxprofit0无锁盈、age1无prev2day，close377.84<=base stop381.22，故long_base_stop request、signal_reference377.84一致。nextopen377.44不是fill。JM已有条件C2stop3224.5后flat不再调用日级adapter，nextproxy3145未用。

1086独立断言0失败、3窗口测试通过，未解决P0/P1/P2=0/0/0。产物只新增outputs/stage029_independent_real_link_review/及本stage，不改root代码/LINE/registry。

边界：两个预选条件见证不能代表总体；qty2、signal-date age1、单层、无账户退出/roll是条件；source calendar非会话资格；分钟参考policy非逐笔真值。没有actual-fill账本连接、PNL或净标签。金融回放/fit/净60日标签/订单/下载/生产修改0；所有权益、收益、回撤、Sharpe、滑点、交易次数、胜率N/A；模型和策略参数新增修改删除0。

开始/结束新增收益选参过拟合：否，只有绑定和因果检查；继续价值：是，真实来源上首次核清C2→日终请求连接，但完整源/历史经济及未知分支门槛未移除。后续由root决定，不据2例放宽标签。
