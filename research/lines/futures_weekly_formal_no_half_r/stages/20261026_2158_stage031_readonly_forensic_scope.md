# Stage031 周K5%半仓回撤增大：只读逐笔归因范围

- line_id=futures_weekly_formal_no_half_r；记录时间2026-10-26T21:58:55+08:00；来源HEAD59e58f271df58451869c9da3d66f0de750f3b013。当前day模式，继续已有研究工作树，仅新增本线文件。用户要求解释W最大回撤反变大并逐笔复盘。
- 来源固定：B=outputs/R_attempt003，W=outputs/stage030_weekly_attempt001；区间2015-01-05—2026-10-26，15万元、原19、原MA和技术止损周频。只读已独审Stage029/030的源、真实fills/每日账本和冻结SQLite；本轮不改策略参数、不金融回放、不市场下载、不生产/CTP/邮件/定时任务。
- 这是一份当前归因范围记录，并非新的盲预注册；初步峰谷已可见。先按各自峰谷核百分比，再做相同日期窗口比较，分别列绝对亏损、峰值基数、净损益差和风险曝险，避免将不同起点最大DD混作同窗亏损。
- 三路独立分析：A全日逐合约净损益守恒桥；B全部W353/B359真实native轮与74半仓逐项源匹配、缺失/新增及静态规模/单位收益分解；C复用canonical Stage038的多周期HTML（完整W349/B355已平轮、各4末仓单列），保留selector/真实K线/linkedzoom并只读本地精确epoch，缺分钟/上市/末期背景如实披露。
- 归因不是因果重跑。配对日期/合约/方向/实际成本必须明确，未配对不可强拼；数量分解与每日Pnl桥为可核算会计恒等式，不声称它们等于只改该笔止盈的策略反事实。所有已平和末仓都保留，不选赢家画图。
- 外部调研：QuantConnect官方Glossary的drawdown定义为历史峰至后续谷的比例下降，https://www.quantconnect.com/docs/v2/writing-algorithms/key-concepts/glossary#Drawdown 。采用该定义核对指标与峰值分母；具体原因必须由本账本/源证据支持。不因图形直觉新增阈值。
- HTML使用skills/futures-recap-html及recap-contract的canonical renderer；用户要求只修改自身研究线优先，因此窄adapter与输出放本line，旧canonical源码不修改，只绑定完整SHA。MA40仅图表参考且策略off；图表自然周与策略有效观察周可能不同，明确披露。没有准确R时null，不虚造末仓finalexit。
- 开始反思：本轮是否在新增拟合，否；是否有继续价值，是，解释已发生的风险路径。仍保留原重复历史选择/源真值/PIT/零费/静态规格及容量局限，不新增策略有效性或晋级证据。不是重要突破。
- 交付：中文结果stage、全量配对与74次触发CSV、DD区间全日/全合约明细、HTML/summary/chart_manifest及浏览器验收、独立复核与SHA闭包；旧3499绑定证据保全，保留原失败/负结果。只本地研究提交，不push、不改LINE/registry/rootmemory或个人memory。
