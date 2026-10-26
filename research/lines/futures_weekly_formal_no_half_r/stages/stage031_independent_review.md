# Stage031 独立只读复核

- 研究线：`futures_weekly_formal_no_half_r`；复核者不是A/B/C实现作者。
- 状态：`PASS_READONLY_ATTRIBUTION_AND_CANONICAL_RECAP_WITH_MATERIAL_LIMITATIONS_NO_PROMOTION`。最终关闭时间：2026-10-26T22:27:11.709446+08:00。冻结账本、全量图表、父综合记录与父浏览器验收记录复核完成。
- 新增策略参数/修改参数/删除参数：全部无。新增回测0，旧回测结果修改/删除0；不属于重要突破，不晋级。
- 本次未导入策略、未回放、未下载、未触及生产/CTP/邮件/定时任务。

## 独立计算的方法与结果

A采用原daily、全部有效positions、原trades与effective parameters重新从有符号成交计算持仓/成交价差、费滑点及每日权益。127项独立检查通过；源A清单及输出SHA全部匹配。B峰2017-09-05/367425，谷2020-04-09/160520，DD−56.3121725522%，首次恢复2020-12-10；W峰2018-02-27/290665，同谷114515，DD−60.6024117111%，首次恢复2021-02-25。W同窗515日中B亏195365、W亏176150，W少亏19215但起点少65220。812个有效日合约并集/49合约完整保留；持仓项+55115、成交项−39435、成本项+3535合为+19215。五案例DB/账本价及昨收核对通过。配置1.65倍保证金W占比高于B为164/515天，双方该窗超100%为0。

B直接以physical_epoch_daily的实际入场日期赋物理epoch，独立于作者prior-week lookup，从真实fill cash flow重建所有B359/W353轮、完整峰谷快照、712笔实际初始订单与risk snapshot，再逐值核完整配对与触发。339同入口匹配，B独有20/W独有14，不强拼缺失轮。峰前−65220、峰谷窗+19215逐轮守恒。74条>5%严格周信号、同步实际入场成本、next-trading-day真实成交全部对上，半仓393手=净成交393，附加forced量0。74轮单位项40正34负；DD窗50个同入口新开中20个W相对初始风险更高。

C逐值核全部704已平图（W349/B355）、各4末仓与81/9真实部分平仓markers。所有入场/最终出场日期和执行时间、价格/加权价、数量/费用后PnL、原始标的涨跌/方向、物理epoch，与独立真实成交轮一致。每个显示日线的OHLC/成交量、MA5/10/20/40、周/月/10日/30日OHLC与量全部对上同一物理epoch冻结真实bar；无跨十年native同名合约混合、无代理bar。R保持null；15分钟为空并披露。canonical源码SHA=`613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a`未改。B/C共458622个逐值断言通过，详情在本独审输出JSON。

## 问题与置信界限

当前P0=0、P1=0、需修复P2=0。非阻断观察：6条源fill最终reason标签与profit-half trigger原因不同（如hc1605），真实anchor/order/quantity都一致。tooltip应保留源标签，解释动作原因应同时引用trigger/events，root最终交付需披露这项标签边界。

源/派生SHA闭合证明本地冻结输入未变和计算可复验，不能证明独立历史行情真值、PIT或OOS。分母桥及手数/单位收益桥均为会计恒等式、依赖替换顺序和实际路径，不是只移除一次半仓的因果反事实；不得将规模项全称卖飞。保证金是冻结名义值乘配置1.65，非真实历史券商逐日保证金序列。零手续费、固定滑点、静态规格、日开盘执行及真实自然周覆盖局限继续保留；日末回撤不是盘中回撤。

## 调研与反思

独立查看QuantConnect官方drawdown定义和vn.py官方GitHub的ContractDailyResult。判断：历史峰到随后谷的百分比与持仓/交易/成本守恒用于核算是合理的；外部定义不能替代本地源，也不能把会计桥变成单因果。
- https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary#Drawdown
- https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py

开始/结束是否新增过拟合：均否，仅审固定账本，没有选择新的参数或交易规则。开始/结束是否有价值：均是，解释现有损益与分母路径、避免因果误读；不据此救参。后续TODO：本次已闭合，无剩余修复；不新增策略研究。

详细输出：`outputs/stage031_independent_review/A_independent_review.json`、`BC_independent_review.json`、`summary.json`。完整SHA见同名stage JSON；不修改LINE/registry/root总账或其他agent文件，不commit。

## 最终综合记录、图与浏览器收口

根综合记录`20261026_2224_stage031_weekly_half_drawdown_forensics.md`最终SHA=`a3249685ad845e8ad7171f281f02f8cbb4246af1de3671b54e004bca3eb1af85`。叙述与全量账本/配对证据一致，6条源reason标签、日末/静态保证金/零费/PIT/OOS等局限均明确。一个末位舍入笔误已修为各自最大DD差4.290239pp，不改变源数值或结论。当前无未解决P0/P1/需修复P2。

补充FIFO/anchor独立检查4990项通过：B364/W432个FIFO段完整覆盖所有close fill且各一次，按原入场/出场价量与effective参数逐笔重建成本与净损益；712轮已实现PnL及74个原始signal/native/order/day/open锚全部一致。完整检查JSON另存独审输出。

已实际查看同窗说明PNG：起点/终点、绝对亏损、固定同日起点百分比与说明一致；516行含峰日。图脚本仅从冻结daily直接画数学变化；receipt的输入/脚本/PNG SHA均一致，没有新金融曲线或策略回放。

父浏览器记录8项通过、无未解决项，覆盖两页hc1605深链、默认30日+日K、2016/hc/loss组合筛选、前后导航、周图切换、Zoomin联动响应、真实截图视觉检查；canonical matches另有静态和数据证据。UI操作是父任务验收，本独审读取该记录并核其与冻结数据的一致性；截图保留在父任务tool transcript，无独立导出bitmap，不虚构截图文件。

C最终build stage及日MA验收receipt SHA已刷新，原recap bundle未变；本线336项回归8.851秒OK日志已查看，继承的Tq免责声明与pandas dtype FutureWarning保留，不声称全仓库CI或真实引擎回放通过。最终源、图、父验收、回归日志与本独审详情SHA全部列入同名stage JSON。原3499文件保全及统一Git清单由root收口，本独审不再扩核验、不改其他文件、不提交Git。
