# Stage068 独立审查063控制依赖与064首C2数据需求

2026-10-20 23:12；非重要突破版本，只读独立核验，不实施source v2，不修改063/064/core、旧receipt、LINE或registry。

实际16,665 checks、0失败，P0/P1/P2均0。覆盖原输入/输出前后SHA、全cohort及逐行集合、实际795个exact epoch×source_trade_date与当前clean日线OHLC只读SQL、固定12条064 trace实际held状态/新entry腿/episode R、固定12条063后管理状态。另用原管理函数运行7个合成管理边界，加旧roll close后新开未知、两branch中一个flat等挑战。审查脚本初跑私有_enter_state归属模块写错，改为034原函数后通过；未修改被审代码。

063全1036首missing窗与058日期/原因逐行相同。982在实际管理后flat且无pending，fresh仍必需；42首缺日不再依赖fresh；12仍因管理证据缺失未知。实际晨间全平后fresh必需，部分平仓仍held、Dclose排全平但未fill均不能误当flat。due roll缺target record只可排unknown_reopen；下一日old close完成后仍未知，不可因能跳fresh而抹除。42仅是一日隔离partial evaluation，不是恢复42个60日标签。39原观察合同明确要求held/pending也有fresh观察，正式目标AM门控又不同；跳过必须新版本合同。根暂不实施source v2是合理决定。

064全1931当前058成熟首C2未知窗、795个exact事件/795状态、34 held≠target、54 roll entry一致。1922窗仍为052原first C2，9窗推进到更晚事件；其中4窗复用旧已拒绝事件，5窗对应OI202301@2022-08-29及SH202605@2026-03-16两个新需求。候选身份仅metadata hint，未转授资格；067另统一审六CSV+SQLite后两新输入通过reference条件，这与064候选盘点边界一致。778事件仍在旧reference helper范围外；不将当前交易时段倒套历史，不把native或自然日当exact held/trade date。064最初旧无候选分类前缀已另存final纠正，精确状态与trace逐字节不变，旧历史未覆写。

旧4762已知矩阵与1366 robust矩阵完整文件SHA保持一致，因此旧值也未变；本次未运行新60日路径、未fit、未改标签/参数、未下载、未生产操作。权益/收益/回撤/Sharpe/滑点/交易次数/胜率N/A。

primary调研复用protocol内VeighNa维护者GitHub与Backtrader官方执行语义。判断：实际position、pending请求和成交时钟是不同控制输入；完整bar也不能证明tick先后。本审查可接纳063诊断及064数据需求作为研究证据，不接纳新source资格或完整窗恢复宣称。

开始与结束过拟合判断均否：全部候选规则预先固定，不看收益选事件/参数。继续价值是：补数据有实际覆盖价值，下一步仅合并独审通过输入、保留所有unknown，并重新验证新增source结果旧known单调一致；不为五窗增加learner复杂度或降低612 floor。

可执行复核：outputs/stage068_independent_dependency_event_review/review.py；逐项checks.json及绑定review.json。
