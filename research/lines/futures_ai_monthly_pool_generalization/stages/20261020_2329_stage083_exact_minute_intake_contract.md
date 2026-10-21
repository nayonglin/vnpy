# Stage083 剩余首C2缺口的精确数据接收合同

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 23:27—23:29 CST。
- 只派生需求清单，不运行source、不取外部行情、不拟合；非重要突破、不触发正式A/B。

## 调研与判断

延续本轮交易所原始时段和GitHub时钟源码的调研：native文件名、自然日和逐日代表不等同actual held×source_trade_date的完整会话。071/076已证明35历史CZCE缓存无合格输入；079/080/081说明剩余doc7的11provider链接被必要条件排除。继续反复使用同一缓存不会增加可靠标签，须把新的资料需求明确到精确合约和交易日，并把历史规则缺口与原始分钟缺口分开。

## 实际派生

073仍有3398成熟未知。其中1926首C2未知窗，对应793个精确epoch×source_day、793已有状态、83历史产品域。其余1472成熟未知不被笼统称为缺分钟，包括缺会话/信号、错侧R、tick、anchor/held等。

派生过程只从064原1931状态映射扣除073新增known五窗；所有剩余窗口的first_unknown_day/reason与073逐行一致，原exact state未重建/猜测/声称又回放。3CSV保留原源OHLC、首open、stop、guard、tick、metadata hint、源状态和1926月窗映射；每请求当前windowcount总和1926。原064/073 SHA及输出SHA均绑定。

新增数据请求/说明，不修改任何标签、模型参数、策略参数；删除参数/结果0。下载/API/source replay/fit/生产/订单均0，清单不会自动生成训练标签，793请求尚未统一历史session资格认证。即使全取得资料，也可能遇到后续新C2/换月/缺日，不能保证整窗可知。

期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。输出`outputs/stage083_next_exact_minute_intake/`；独审Stage084。

## 反思

开始/结束新增按成绩选参过拟合：否，只按实际缺口逐项列需求，不按净R或模型分数挑来源；历史开发与缺失非随机风险仍在。继续补精确数据价值是；继续用当前不足缓存反复重训价值否。既有正式策略、AI池和正式半R设置未改，训练源halfR/retry=False、C2=True维持。
