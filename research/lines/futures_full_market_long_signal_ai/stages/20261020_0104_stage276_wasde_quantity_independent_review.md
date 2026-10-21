# Stage276：WASDE 世界玉米 quantity 有限独审

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 01:04 CST。非重要突破，只接受来源提取与量计算；不授予alpha、首发PIT、DCE.C交易映射或全98覆盖资格。
- 先读274冻结协议（SHA `023ffe7d172c93534adc80c718a7cd7c8b6cbfbc0992df9a4d0c68d4e2d7975d`），与275作者协调实际ready，root确认273真实exit0及handle completed后才审数据。273 acquisition实为stopped_early，不把进程exit0误写成全部采集成功。
- 仅新增本唯一stage及[独审收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage276_wasde_projection_review/receipt.json)，不改LINE、registry或作者代码。收据22399B，SHA `0d33f61f820630a8795ad07b39bfa7e7c24a049fd2b4e880a62ebbdfd0ef3064`。

## 裁决与数量

**核心阻断0，接受本批冻结quantity算术。** 独审唯一执行exit0，未import或执行作者计算；一次读取完整3612条Corn/World literal子集、全部172条报告投影及小inventory/receipt/manifest，独立使用stdlib Decimal50、显式日期与zoneinfo复算。

- 172个观测报告身份完整，163个符合冻结条件，范围为2011-01-12至2024-10-11。2010-04至12的9报告因最高当前marketing year未满足精确`Proj.`合同，保持`latest_marketing_year_not_unique_Proj` unknown；不改literal、不退回旧年、不补0比例。
- 逐报告独立筛当前Forecast年月，保留重印行但不混作本期；先选最高合规`YYYY/YY`，再要求Proj；Ending Stocks、Domestic Total各唯一、同release/WasdeNumber/marketing year与Forecast年月、同Million Metric Tons，S≥0、U>0。所有S/U原literal、来源行及Decimal50比值一致，最大比值绝对误差`0E-50`。
- 172个显式ReleaseDate、ReportDate月份及源目标月一致；ReleaseTime原literal保留，known_at为空、historical_first_seen_proven=false。`r+2 calendar days、America/New_York 00:00→UTC`逐条一致，包括夏冬时差；它只是主动延迟假设，不是实际HTTP首见或历史首发证明。
- 本批实际V2报告0。最终源码与3个synthetic定义静读符合“保留raw ratio、correction known_at unknown、feature_eligible=false”；绑定作者fixture终态，独审没有重跑fixture，也不把静态分支审查冒充实际V2样本验证。

## 原件预算及来源缺口

273为71目标、51次请求、47成功原件、4失败、20未尝试。275为47个新CSV/member流；各header/完成状态、Corn子集计数与库存记录闭合。843079全源行仅核各流元数据求和一致，**未再次解析843079全源行**，不冒称全raw独立重建。

| 事前固定样本 | 有限原件读取 | 结论 |
|---|---|---|
| 2010-04，两ZIP中第一个 | 对应ZIP/member一次，访问4759条数据记录，遇下一Wasde身份即停止；21条Corn/World | 16原字段、记录号及physical endline全同；quantity仍unknown |
| 2016-01，第二个ZIP | 对应ZIP/member一次，访问4845条即遇下一报告停止；21条Corn/World | 原literal/出处全同；投影一致 |
| 2021-01，原CSV | 单CSV一次，4969条数据记录；21条Corn/World | 原literal/出处全同；投影一致 |
| 2026-10，原CSV | 0次，未采得 | 保留unattempted unknown，不替换其他月 |

两个ZIP均只读固定首报告连续块，没有extractall或全ZIP内容重解析；原件SHA继承273采集时绑定，仅查成功原件尺寸，不再完整重hash。原件样本与全Corn子集核算的关系明确，不把三个样本扩大成全部原始行完整性证明。

24个失败/未尝试源月完整保留且release_date=null：2023-01、2024-11/12、2025-01至09及11/12、2026-01至10。另目录未列2025-10；两个ZIP名义跨度中未见2013-10、2019-01报告，只描述未见，不推断停发原因。合计27个未观测月份槽，与2010-04至2026-10完整月历减去172观测月份一致；它们没有被伪造为带日期的release，也没有carry旧quantity跨缺源月。9个2010 quantity未知是“有报告但不合格”，与这27个“未观测月份槽”分开。

## 绑定、边界与停止点

- 275 manifest SHA `96100663bbd66be4097e0638e28b477ef72b5f7d0dbadaca8fa7c15d08fe9ed8`；完整新子集/报告/inventory/receipt/terminal与manifest逐一绑定一致。275源SHA `4467590ea3f5f8d1bfbccc051698e4075d650e632c46e1dbb951d8802b6a9fda`，3fixture源SHA `dfb507808bc4ccdfb99db34af6ff690e05574b226019242b5ff21fcd26e2e0d6`。完整绑定及读取计数在276收据，不再二次读取新子集或原件。
- 不重做270/271经济理论审，也不新增网络。调研判断沿274已冻结的官方vintage/字段定义：物理库存缓冲与价格中已含的库存信息是否仍有增量，尚未受测；数据可构造不等于增量、可执行性或收益。此次只核“按冻结合同实际算的是什么”。
- 独审新增network/SQL/native/金融labels/fit/cash、旧suite、原件完整hash均0；新增/修改/删除策略参数、模型与回测结果均0；累计439fit/238cash不变。权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率及金融CI全部N/A。
- 开始/结束按本批收益调参过拟合：**否**，没有金融结果、拟合或放宽source合同；长期同史适应性选题风险仍为**是**。继续这一轮有限quantity核验：**有价值且已完成**；为漂亮覆盖补抓、改Proj literal、另换样本或启动金融实验：**本次未授权且不继续**。止步于source/quantity接受，完整目标仍未完成。
