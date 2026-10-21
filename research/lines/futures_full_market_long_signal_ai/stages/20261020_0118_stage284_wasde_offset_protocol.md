# Stage284：冻结COMMON52＋WASDE发布当月单项offset实验

- line_id=`futures_full_market_long_signal_ai`；2026-10-20 01:18 CST；金融前冻结，非突破/正式A/B；沿用现分支，不改正式/生产。
- 复用271—277 USDA官方/NBER库存机制及GitHub parser调研、272与279Ridge/接口判断。283静态审查认为发布当月有限使用不依赖未来报告，无确定性时间泄漏；仍非首发PIT，公告期/覆盖年份和库存数值可能混杂。
- 原130 COMMON52权重、截距、缩放、训练身份/成熟与权重全冻；只给DCE.C每个真实月份相同新项。仅main两cutoff各解一次无截距Ridge1残差scalar，不重训旧52、不借held系数。单一产品源无法通过现有family留出；不做四个无用held fit。
- 新增参数：唯一库存比值Ending Stocks/Domestic Total、release+2自然日NY00、发布当月内有效、训练内原权重标准化、alpha1无截距。跨月主动offset0，缺失/更正不明/未映射均0；不靠未来报告或缺文件决定当日状态。此项有限使用假设明确替代271持续carry提议，是缺时钟下的收益前简化，不声称连续库存状态或纯数值因果。
- 全966740 main children及161014母行重选，允许新增和取消参与；D<K/优先级保持。完整98母体不删，未映射继续旧分数。信号按所有新selectedID从129一次取得，复用接受现金核与native缓存，0SQL。
- 恰2新fit＋4新候选账户：2020连续/2023空仓冷启动×base/stress；100万/0.25N/单family0.25%/总2%/margin25%/buffer1.1等不变，157四控制只引用不重放。两stress各权益更高且DD更浅是唯一名义经济门；失败停止本包，不救符号/有效期/模型/止损/风险。
- 逐年与旧固定2000bootstrap配对CI只作诊断；日行/合约不是独立USDA经验。2026 partial；档案修订/缺源/单Corn/历史多次研究均限制置信度，名义门通过亦不自动alpha或晋级。
- 当前0实际新fit/cash，累计439/238；权益/收益/DD/Sharpe/滑点/交易数/胜率N/A，旧结果不修改删除。完整协议与小绑定见outputs/stage284_wasde_offset_protocol/，source282完成物料将在actual前单独绑定，不改科学规则。
- 开始新增按收益调参过拟合：否，但长期择题风险是。继续价值：是，只限一次有限增量证伪，之后按固定门决定停止；完整用户目标未达，goal active。
