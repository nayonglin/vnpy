# Stage249：固定全历史现货原件获取合同

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 22:06 CST；非重要突破；独立数据获取，不触发正式策略A/B。
- 用户完整目标继续，由用户授权自主补齐全市场数据。这里的现货来源只覆盖其实际刊载的商品，不能改称全98期货已有现金报价。
- 使用using-superpowers、brainstorming的范围设计原则；用户已明确要求按我们判断持续补数/研究，不重复要求确认。此项是246已有采集流程的有界扩展，不改产品、正式版本或生产，也不提交/切分支。

## 固定短设计/执行计划

1. 固定已接受原日历2011-01-01至2026-10-19，共3833日期；以各年ordinal交易日交错、同ordinal按年升序排列，完全不读标签/收益。已有9原页只继承binding，不重抓原件。
2. 250仅扩展246 stdlib urllib原件获取：每日期1次尝试、最大2并发、全局请求起始间隔0.75秒、15秒timeout、128KiB上限、无重试/无latest替代。每次调用最多250新请求；HTTP403/429或连续3失败停止新提交，保留在途结果。固定范围不是网站逐日有发布的证明。
3. 每date在联网前写request-start记录；崩溃pending保留unknown，之后自动跳过已尝试日期；只新建batch，已有日期不得自动覆盖或重复。原件与独立元信息、batch terminal和摘要持久化；锁防并发双跑。
4. 实现者做少量模拟传输行为检查，独立agent只核这份source合同。root一次启动首批；不自动启动剩余全部历史，也不因缺口重新运行已完成批次。
5. 原件完成后做一次有限内容清洗/覆盖统计；此阶段不统一grade/物理单位，不作F-close与source-settlement等价，不读取label/native价格/SQL，不训练、不现金回放。

机器合同：`outputs/stage249_full_raw_spot_archive_protocol/protocol.json`，75858B SHA `59a7622677e2d75ad989ff16db573a2d773d0c28616bf914c0cf7186514f8fea`。实际下载完成数量以后续250batch终态为准，不把3833计划量写成完成。

## 外部依据与判断

采用已实际取得的[生意社原始日报](https://www.100ppi.com/sf/day-2020-01-02.html)；[GitHub维护者代码](https://raw.githubusercontent.com/akfamily/akshare/main/akshare/futures/futures_basis.py)证明逐日报页路由，并提醒不能直接继承成品basis符号/单位变换及重试/latest替代。本轮不再次小探源，不安装依赖、不下载分钟。

策略参数/训练/现金/财务指标均无变化；新增0fit/0cash，累计439fit/234cash，期末权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A。前一记录生成中对241元信息误用body键，KeyError发生在任何249写入/网络之前；仅改为继承246已接受binding，并未重抓/重算金融数据。

开始过拟合：本次不看收益/标签、无新调参，因此新增拟合型过拟合否；同史择题风险是。继续价值：是，真实连续输入目前仍缺；若只是无限复核样本页则否。结束反思等实际批次终态，不提前声称来源完整或alpha成功。原goal active。
