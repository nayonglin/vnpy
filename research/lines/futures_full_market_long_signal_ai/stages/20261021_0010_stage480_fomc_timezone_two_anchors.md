# Stage480：固定夏冬两锚支持纽约当地时钟，未认证全385行

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-21 00:10 CST。
- 性质：一次有限时区核证，非重要突破；只新增本stage及一个小JSON，不改LINE、registry、模型、原四前瞻账户或生产。
- 开始判断：新增按收益调参过拟合否；本步没有金融结果或可调策略参数。继续价值是，用事先固定的一夏一冬检验时区解释，避免固定UTC差造成一小时错位；完成后停止。

## 固定输入与外部原文

只读一次本地`outputs/stage477_fomc_original_source/actual_run1/fomc_raw.body`，实际69,885B，SHA256核得`785cb0ac6e50df1779820dffdaf399c312510e44d2b547fabb3925ed9a443300`，与root绑定相同。仅提取固定2025-06-18、2025-12-10两行；各恰一行、均`FOMC Rate Decision (Scheduled)`，`start`分别为两日14:00:00。不存在换锚、读取市场价格、源重取或重新完整coverage认证；完整385行源coverage由478负责。

root提供源commit为`f788aef7d573f87f28b70ffc3763e73c4886a53f`；本阶段不再次请求GitHub核commit。作者原文没有已核的timezone明文，本步不扩大搜索或联系作者。

一次定域搜索（同次两query）仅用于定位固定URL；随后只打开下列两份Fed官方正文，未打开其他年月/附件：

- [2025-06-18 Fed官方FOMC新闻稿](https://www.federalreserve.gov/newsevents/pressreleases/monetary20250618a.htm)：正文日期为June18，时间原文为“For release at 2:00 p.m. EDT”（web正文日期L8、时间L11）。
- [2025-12-10 Fed官方FOMC新闻稿](https://www.federalreserve.gov/newsevents/pressreleases/monetary20251210a.htm)：正文日期为December10，时间原文为“For release at 2:00 p.m. EST”（同为L8、L11）。

## ZoneInfo数值结果

使用仓库`.py311/bin/python`标准库`zoneinfo.ZoneInfo('America/New_York')`及`ZoneInfo('Asia/Shanghai')`。将raw naive时钟解释为纽约当地时间，先转UTC，再在UTC上加90,000秒（25小时），最后转上海；不是把naive时间当UTC，也不是全年固定差13小时。

| 固定锚 | raw start/纽约解释 | Fed明确时区/UTC偏移 | 公告UTC | 公告上海时间 | ＋25h UTC | ＋25h 上海时间 |
| --- | --- | --- | --- | --- | --- | --- |
| 夏季 | 2025-06-18 14:00:00 | EDT / −04:00 | 2025-06-18 18:00 | **2025-06-19 02:00 +08:00** | 2025-06-19 19:00 | **2025-06-20 03:00 +08:00** |
| 冬季 | 2025-12-10 14:00:00 | EST / −05:00 | 2025-12-10 19:00 | **2025-12-11 03:00 +08:00** | 2025-12-11 20:00 | **2025-12-12 04:00 +08:00** |

两个锚点的纽约本地日期/14:00和EDT/EST均吻合。上海相对纽约的时差分别是12/13小时；全年固定EST会使夏锚晚一小时，全年固定EDT会使冬锚早一小时。

**我的判断：两场固定预定公告支持raw `start`采用America/New_York当地时钟、随DST变化的解释。** 这是基于两个锚的有限推断，不是385行的普遍明文证明；不能据此认证早期、非预定或其他类别事件的时区。

## 本步边界与停止

25小时只是沿474/476已声明的计算窗口保守假设所作算术；本步没有读取作者底层行情或逐事件endpoint，不能证明实际窗口到点、作者当年已发表该数据、firstseen或strict PIT。Fed明确的公告时间认证的是Fed新闻稿，不是作者CSV的发表时间。实际历史研究若使用纽约解释仍须标注该推断及源修订限制。

本步没有映射国内u/D日历，没有建立可交易时点、下单或收益资格；也不据两个锚替代478的完整源检查。0行情/API/SQL、0预测fit/cash、0新标签、0作者源重抓、0生产/CTP/邮件/launchd操作。权益、收益、DD、Sharpe、总滑点、交易数与胜率均N/A。

输出：[anchor_check.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage480_fomc_timezone_two_anchors/anchor_check.json)，3,427B，SHA256 `52a0527cddbb1086902281041375c39454556f1640697711ec627fef4937663e`；含原源绑定、两主源URL/短引、纽约/UTC/上海与＋25h三地完整ISO时间、操作计数及明确false的全385行/PIT/alpha声明。

结束新增按结果调参过拟合：否；整条线长期同史择题风险仍高。本次核证价值已实现，继续泛搜时区/增加锚点无当前授权或必要性。**完成即停，不授权模型、回测、生产或加注。**
