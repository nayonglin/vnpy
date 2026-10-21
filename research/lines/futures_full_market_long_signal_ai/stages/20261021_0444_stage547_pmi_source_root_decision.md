# Stage547：排除重复OI提议，接受有限PMI原页样本

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-21 04:44 CST；day模式；非重要突破。
- 工作区 `/Users/mac/Desktop/fian` / 分支 `codex/ai-training-data-expansion`。本轮是来源验证，不是策略回测。
- 前一goal轮分类：进展（540已有真实12fit与539独审）；本轮亦为进展（545实际取得原响应并形成可反驳的来源/缺失结论），不是状态复述或等今日日线。

**裁决：当前模糊OI提议不继续；PMI两分项的官方来源小试通过有限验收，可以继续原月公告覆盖盘点。尚不进入训练/回测，也没有新增收益或稳定优势结论。** 五个样本响应不能代替全历史，原高收益、低回撤、全市场高质量long、极窄损加注目标保持完整且尚未完成。

## 调研与判断

541精确排重：代表合约ΔOI/V与同产品候选月份lag1 OI份额已实测失败；跨产品总OI增长不是这两者完整实测，不能笼统说所有OI无效。但当前price×OI/随意聚合缺稳定经济定义，手数跨品种不可比、普通/F重复与正V观察池不等于全部上市OI，不能以尚未测为理由无限重开。

PMI是不同的企业调查对象，不是旧52的同一价量公式。[国家统计局2019Jan原页](https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900229.html)与[2026Sep原页](https://www.stats.gov.cn/sj/zxfbhjd/202609/t20260930_1965449.html)已真实保存并独立核值。[S&P原始解释](https://www.spglobal.com/market-intelligence/en/news-insights/research/2024/12/how-to-interpret-and-use-the-pmi-orders-to-inventories-ratio-dec24)谈订单/库存比与生产调整，不证明本线差值、发布后期货long、0.25N先碰损结果或加注alpha。[AKShare维护者源码](https://github.com/akfamily/akshare/blob/main/akshare/economic/macro_china.py)的headline函数不能替代所需分项/原发布版本。我的判断：这项调查值得一次有界源核，盈利价值必须后验于合格历史和固定经济问题；不默认q正即全98/95利多。

NO−FG是两个季调diffusion广度的差，不是物理stock-flow缺口、补库吨数或公告surprise。同样的差可出现在扩张或收缩，两变量的水平与公告后市场反应仍不相同。共同月状态可能改变给定52后的平均参与质量，但不会凭自身识别同日某个family/合约月；月频独立单位是公告，不能把每天×98制造成百万宏观经历。

## 实际源、核对结果与缺口

544收益前冻结5URL各1GET、12秒、无redirect/retry/fallback；545唯一actual exit0，23.940511秒，5GET、4HTTP200和1个CFLP404（错误body600B也保留），原body共1,382,131B。无源请求重跑、0新fit/cash/SQL/行情/label大表。完整raw/headers/SHA与当前claim时钟留存，本地归一只从已存内容做，不重新网络探测。

| 报告月 | 制造业新订单 | 产成品库存 | 原页声明日期时刻（CST约定） | 制造业样本 | 边界 |
| --- | ---: | ---: | --- | ---: | --- |
| 2010-08 | 53.1 | 未报告数值 | 2010-09-01 09:31 | 820 | 缺值保持null |
| 2019-01 | 49.6 | 47.1 | 2019-01-31 09:00 | 3000 | 两分项完整 |
| 2020-01 | 51.4 | 46.0 | 只有成文日2020-01-31 | 3000 | 发布时分null |
| 2026-09 | 50.5 | 47.6 | 2026-09-30 09:30 | 3200 | 两分项完整 |

2019NBS原页已有NO/FG，不必用CFLP404补值；与2020NBS滚动表重印的2019Jan二值恰好一致。这是一项小范围版本对照，非全史从不修订证明，也不增加独立月数。2010/2019/2026的桌面手机完整副本各两套，归一仍每源每月一条。制造业与非制造业的同名新订单分开，不能只按7列猜表类。

2019实际原页附注是GB/T4754-2017/3000，纠正542检索阶段把CFLP的GB2011描述误推NBS的暂定说法；保留原发现并追加更正，没有篡改当时核验状态。2010为GB2002/820，2026为GB2017/3200；仍未查齐具体变更月，不把口径变化抹平为完美同质序列。

09:00/09:30/09:31差异真实存在。URL的2023目录迁移年份、HTTPDate、取回时刻和404body服务器2026时间都不能当原发布日期。2020仅成文日无时分不自动补09:30；页面未打印时区后缀，Asia/Shanghai来自国家发布者约定。当前历史页面所声称的旧署时，不等于已经取得当年首发字节；4报告例、3完整pair、2完整pair+分钟署时，不足以认证2010—2026全史、首发PIT或可交易执行。

## 独立源审查

546仅读五raw各一次，校原bytes/SHA、原文表格/字段/文章日期时刻/行业口径/样本/重复/缺值/一个重印对照及作者小normalized；0额外GET、fit、cash、SQL。有限scope C/I/M=0/0/0，全部列出的核对一致。

其首次新审查器将7列非制造表误当制造表的选择器断言停下；从既有RAM缓存限定制造表1在产成品表2之前后恢复，未重读raw、未改作者数据/数值、未触发新下载。这是审查器技术修复，不是新金融实验或原始数据冲突。审查明确不认证全史、首发版本、2020发布小时或alpha。

## 参数、财务指标与后续

新增来源小试脚本、协议/原HTML/headers/小归一样本及独审/决策记录；修改/删除原策略参数0，无新策略模型或正式材料。新增/修改/删除回测结果0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率**全部N/A**（本轮无资金回测）。累计仍**523fit/278完成cash及1旧partial**，不把独立源核计作策略fit或把一次原页写成数据已补齐。

下一步只盘点国家统计局**原月公告**2010-01—2026-09的URL、原月两字段、声明发布精度及口径/样本覆盖；先确认2020/2023截点前是否有可用训练支持，再决定是否冻结一个低容量、纯参与时机问题。后续新的批量下载另冻范围，当前没有再试545链接或扩GET。不能以2020重印冒充2019首发、按所属月份回填月初/当日开盘，也不先写PMI模型再找数据。具体后继在`next_scope.json`，不是金融授权。

开始/结束同史择题过拟合风险均**是且高**；本轮没有看新收益选字段/符号/阈值。继续旧模糊OI提议价值**否**；继续PMI原月来源覆盖盘点价值**是**（真实新增调查对象已有可用原页和可见缺项），直接训练价值仍未决定。完整目标保持，不因小样本验源缩为下载任务，不加注/晋级/改生产；root只更新本线LINE/registry，不追加根总账或提交推送。

Polanyi式经验判断仅压成“企业需求与库存调整是否提供价格之外的参与状态”，并接受月频、口径与可得时刻反证；不把宏观经验当赢利证明。

证据：

- [五页实际manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage545_pmi_source_pilot/actual_run1/manifest.json)
- [四条规范样本和重印对照](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage545_pmi_source_pilot/actual_run1/normalized_samples.json)
- [独立审查](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage546_pmi_source_independent_review/review.json)
- [机器决策](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage547_pmi_source_root_decision/decision.json)
- [后继范围](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage547_pmi_source_root_decision/next_scope.json)
