# Stage003 被拦候选复盘HTML独立审查

- line_id：futures_weekly_short_ma_slope_gate；审查日期：2026-10-29，精确时间见同名JSON。
- 独立审查员 independent_review；本次只审显示适配、冻结来源和页面语义，不执行金融策略、不下载行情、不访问生产。
- 结论：**PASS_WITH_LIMITATIONS，P0/P1/P2=0/0/0**。签署最终index.html SHA为 `b2331ba0e88c04b70c3335a603b0066be1c60a9ba28dba54e13f91c89df5c249`，不是文案修正前旧生成件。

## 唯一来源与事件全集

- 唯一源为Stage002 C attempt001中applied_block=True且父级原计划量>0、过滤后=0的35个唯一候选：20个多头（14个long_case1a、6个long_case2）、15个空头short_case1a。原规则已归零或仅would_block但未实际归零的候选均未混入。
- 每个signal_date/contract/direction/signal四键、源MA当前/前值/delta、最新11个接受周收盘和physical epoch逐值匹配。标记值是信号日同物理合约真实日K close，不是成交价。
- 原Stage001 3,105个绑定与Stage002 3,141个绑定全部未变；canonical renderer和Stage031 AST纯函数加载器的完整文件与来源HEAD4be2e9389 Git内容相等。新输出/审查只在本线，不改44池或其他研究线。

## 无虚构交易语义

- records/meta和chart_manifest删除了临时canonical适配所用entry/exit日期、价格、trade_id、lot_id和holding字段。volume、realized_pnl、r_multiple、lot_count和price_change_pct均为null，页面明确N/A，状态为“被拦候选，未成交”。行情图中的成交量柱是原生市场日K/聚合量，不是候选成交手数。
- canonical内部临时同日entry=exit只用于选视窗和公共坐标，没有变成交易。独立JS语义运行器实际执行35个页面渲染：每个最终仅一个信号close叉形标记，0个真实成交标记、0个持仓矩形，只有“被拦信号，未成交”注释，最终有效指标无净利润/平仓lot，PnL/R为N/A。
- 两条加粗点线和指标卡展示策略实际接受观察周的前/本周MA5/10；自然周图的MA只是参考，可能与策略接受周序列不同，页面有明确说明。MA40未参与策略。

## 上一版本事实匹配

- 多头对照Stage001 C仅空头门，空头对照Stage001 A原版；四键候选匹配后，以订单anchor和实际fills核对开仓，不用candidate_status=opened替代真实成交。
- 35个中34个有旧路径实际开仓证据，1个旧路径候选本来未开：2020-07-10 ru2009.SHFE long_case2。该条不是“没找到”，页面诚实显示candidate_not_opened。
- 每个旧路径实际开仓的trade IDs、日期、合约、价格和手数与冻结fills一致。旧路径证据仅用于定位，不被标为Stage002新交易，也不提供虚构的被拦盈亏或反事实利润。

## 行情、MA、缺口与周期

- 最终全量输出116,677项检查通过，覆盖35记录、全部可见日K原生OHLCV/日MA5/10/20/40、同epoch身份、策略实际MA和基准匹配。
- 另核对所有3,347条非日线聚合bar（周1,711、月448、10日874、30日314）的OHLCV来源及隐藏真实历史的MA预热；这是各候选页面bar合计，不是独立市场样本数。
- 精确合约、同physical epoch、0主力价格代理。每日/周期MA预热缺值与可用历史一致，无可避免的前导空值或伪造补值。真实上市前/冻结截止后的视窗不足保留，coverage日期、前后可用bar数和截断披露均匹配。
- 默认30日K+日K，月/周/10日选项沿canonical保留。35个均无15m缓存，未下载、未制造分钟bar；最终勾选缺失15m提示明确“无缓存、未下载”，不再暗示本页另有已补数交易。
- 9项适配测试独立重跑通过，全部3段嵌入JS独立解析通过。JS语义运行器验证35初始/20多/15空筛选、上一/下一、周+日选项和共享matches轴配置；真实浏览器的视觉及Plotly实际缩放由root另行验收，不能把语义运行器称为浏览器测试。

## canonical复用、哈希与文案修正

- 使用Stage031 AST纯函数加载器调用canonical _records/_html；聚合、蜡烛、MA、轴、周期selector和linked zoom无复制新实现。Stage003只进行数据适配和候选状态/标记/指标的窄语义变换，未改canonical源文件。
- 25个直接source_hashes绑定、delivery所有产物SHA、源旧交付均通过；审查中最终产物原字节未变。summary保留的原回测metrics与冻结Stage002 metrics完全相同，未由可视化改写。
- 首版分钟提示“切到已补数交易时恢复”文案不适用于本页全缺分钟候选。已补回归测试并修正，旧生成目录保留；新旧records、summary、chart_manifest、coverage及旧路径匹配表逐字节相等，仅显示文案/对应JS及其哈希改变。不涉及策略/数据/回测修改。

## 边界和反思

本页35项是未成交候选，不能称35笔交易。34个旧版实际开仓也不能形成固定底仓、固定资金路径的因果反事实，更不能据后续价格图虚构拦截直接PnL。既有数据PIT、生命周期、容量、成本和泛化限制不因页面完成而消失。

开始/结束过拟合判断：否，本阶段只读展示冻结事件，无参数选择、策略重跑或行情补数。继续价值：有，能逐条定位规则触发与后续行情；可视化不新增alpha/OOS或晋级证据。

金融回放0、行情下载0、生产访问0、策略改动0。机器证据为stage003_independent_review.json、stage003_independent_output.json、stage003_independent_expected.json、stage003_independent_semantics.json、stage003_independent_jsparse.json及对应独立工具。

## root真实浏览器验收补充

已读取stage003_browser_qa.json，status=PASS且index SHA与本签审精确相同。root实际验证35/20/15筛选、2026/rb/空头=2、上一下一恢复、默认30日+日、周日两轴真实Zoom in由[0,242]同步变为[60.5,181.5]、matches=x、console error0，以及最终缺分钟提示。两张root截图与receipt已加入独立JSON哈希；这是root真实浏览器证据，与本agent的JS语义运行器证据分开陈述。
