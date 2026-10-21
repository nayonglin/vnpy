# Stage113 NFC同表类别比例：现金包装实现冻结

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 19:43 CST；重要突破否。
- 已读registry/LINE和110固定协议（SHA80b9eb2f8e959fb61218b92c3c35049a3f5084817d784c211ece2fc5970a81bc）；本阶段只实现，actual0。当前361fit/94cash，109真实来源获取尚由root维护，不假称已完成。
- 延续107—110官方类别原表与收益前科学收敛判断：仅NFC净量除同表四边gross的唯一比例，类别组成是COMMON/总OI之外的新观测；官方历史归档加一完整source日lag只是有限研究假设，不是当年首发PIT或盈利证据。

## 改动与冻结

只新增113脚本与少量新合成fixture。以095已接受包装最小适配CONTROL/NFC，shared external_missing只作诊断，不删完整母体、不作交易门。112 main每臂161014进入现金；held两组只诊断，绝不拼入主资金。112必须completed actual12fit/644056预测、cash_eligible true、0native/0cash，terminal attempted=completed12；不接受unsupported_scalar_support或partial结果。

110使用stage/cash/bound_inputs结构，113显式绑定已接受052 market protocol、070 narrow labels/manifest和两既有bootstrap indices精确引用，root已确认该适配；不改110冻结字节。root现金授权仍精确六输入roles，沿112 manifest保留109/111来源闭包供114全核。

交易参数新增/修改/删除0：100w、单family.0025/总.02、bufferedmargin.25/1.1、.25Wilder20N/20low、原u联合预留D只减、不回收当u卖出预算、gap/roll/lifecycle/stale/insolvency不变，绝不叠080一手预过滤。slip已在fill价，仅归因统计，不重复扣费。无新目标/模型/分钟/下载/旧金融回放。

## 冻结门与新测试

唯一严格增量>0为主2020stress NFC−CONTROL，另三组收益差>=0；四DD均不更深，主stress同旧252源日块2000次indices CI低端>0，NFC自身四收益严格>0、全8账本实际wealth正且无ever_insolvent。两个held已识别u等权增量均非负；未知足以翻转而无界时不给支持。空CONTROL DD N/A；名义失败优先unsupported，不能借unknown遮掩；真实历史stale与未成交潜在label未知分离。

6项必要新wrapper行为fixtures先RED（脚本缺失）后GREEN，0.033秒：missing且未来unknown仍按当时score交易、held不能入cash、两臂external missing共享、primary base恰好等收益可通过而主stress为0不通过、NFC自身不盈利/破产不通过、未知不遮盖名义失败或虚构未成交现金敞口、空DD保持NA且无held不编通过。没有旧suite/模型/行情/标签数据的实际运行，导入native计数0。

- source 27190B SHA `35c365e16c7c5853aedefeb493211c1af65879db593c9755132f91c394308131`。
- tests 4679B SHA `8c725e0ea26e2b1255c27eb7d9bec9f92b114600a4cd1f3bb50ba3b63a98e77c`。
- `outputs/stage113_member_category_cash/implementation_freeze.json` 5041B SHA `44afffe999ac83b91e18be8af94a174fe2313db8ad509a62648cac89c8f046d3`。

## 产物与后续

root唯一actual runner，精确源/112终态绑定后fresh `outputs/stage113_member_category_cash/cash`一次8cash/一次共享nativeSELECT，stat-bind原库，不hash大库。保留全部fills/reservations/rejections/daily/positions/closed/open、8指标、费滑/年度/全95family含零/贡献集中、gap及>1Rloss、四paired CI/unknown/风险/门/有限native案例、显式asset roles。114一次全面独立核验来源/分数/资金/置信度/bug，失败保存不自动重跑。

本阶段新增/修改/删除回测结果均0；期末权益/总收益/最大回撤/Sharpe/总滑点/交易次数/胜率N/A，fixture不是金融成绩。

开始与结束反思：本阶段按本包成绩选参过拟合否（无actual且实现110单点）；累计多轮历史选择风险是，不能称真正未见OOS。继续价值有，限真实新增类别信息的一次有对照检验；不支持即停该scalar/lag/Ridge/NARROW包，不扫分母/方向/窗口/止损/风险，不加注、不动正式版。TODO为114有限预审、等待source/112终态和root精确授权、root唯一次现金、114实际全核。
