# Stage544：官方PMI五页源小试冻结

- line_id：futures_full_market_long_signal_ai；时间：2026-10-21 04:36 CST；day；非突破。
- 前一goal轮为进展：540完成12fit和独审、关闭行业截距。541已证当前OI提议不足以重开旧包，不把未测全市场OI聚合误称已失败。542/543确认PMI未actual，但只支持有界源核，不授权金融。

## 调研与判断

实际核国家统计局、CFLP网页入口、[S&P原始解释](https://www.spglobal.com/market-intelligence/en/news-insights/research/2024/12/how-to-interpret-and-use-the-pmi-orders-to-inventories-ratio-dec24)与AKShare原GitHub：orders/inventories反映调查生产调整，并非实物库存缺口/订单surprise，更不是发布后short-stop long alpha。AKShare headline接口不足这两个子项。旧页面有09:00、新页面09:30，不能硬编码月末或把当日开盘设为已知。

冻结protocol `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage544_pmi_source_pilot_protocol/protocol.json`，仅5个指定官方HTML URL各一次GET、12秒超时、不重试/重定向/换源；保存body/headers/SHA/实际请求时刻与失败。2010旧格式用于查缺字段，2019 NBS/CFLP原月及2020滚动重印用于有限字段/版本对照，2026新表用于格式和时钟。取样按来源/年代而非交易收益。页面声明发布时刻不冒充当年first-vintage字节。

新增源小试约束；原策略参数修改/删除0，fit/cash/SQL/label读取0，累计523fit/278完成cash+1partial不变；期末权益/总收益/DD/Sharpe/滑点/交易次数/胜率N/A。先545实际存源，再546独立检查原文/字段与未知，root有限裁决，不能直接写可训练全历史或稳定优势。

开始/结束同史择题过拟合风险是；本轮不看收益救参。继续价值仅这次源证伪是，继续旧OI模糊提案否。完整目标未完成，不改正式/生产/Git。
