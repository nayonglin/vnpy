# Stage614：D日有效u.close条件限价现金实验独立审查

- line_id：`futures_full_market_long_signal_ai`；2026-10-21 08:40 CST。先读registry/610小结，随后完整读冻结611；方法来源继承610/612真实阅读的维护者日线撮合/队列规则，不重复网络/旧suite/原始行情。
- 当前仅协议收益前审查；非重要突破，未读新收益，0fit/cash/SQL/native/实际启动。累计551fit/286完成cash＋1旧partial暂不变。本614只写自身唯一stage和输出，不改LINE/registry/正式或其它agent文件。

冻结611 SHA `19c23d804c086a6d229cb2b96459e851549223916222646e1a3e354fac16992b`。**协议GO，无实质阻断，等待613source-ready做完整新机制源审后才由root唯一4C实际。** 对照是157四本OWN，不是旧baseline；原52/全98历史代码95family/原合同选择、u预算、.25N/费用/容量/K/退出与原A现金不重演。

限价L取所选实际epoch的原u.close；先原Q(Dopen)可承受时用原open，否则仅D有效等待原quote反解T。已知tick用精确Decimal合法raw网格；tick未知沿原A连续报价，不能为C新造tick或额外unknown-only过滤。触达比较始终Decimal Dlow<=semanticT；F为同T的保守最多1ULP编码，原Q(F)末端硬核actualfill<=L，不clip费用/滑点。qty/SL0/风险都用同rawF，SL0=F−.25N而非actualfill−.25N；原low20 stale/非正F等合法性保留。numeric_inverse_unknown单列并进入execution_unknown，不当作已知未触达。

u独占原allocation，D只减量/取消、不回流退出或取消额度、不重分、无winner-add/模型或合约重选；后续C按自身u状态形成预算。u新family与旧held不交叠，因此旧退出与新entry的跨epoch记账金额可交换；原131旧仓先记账可沿用，不能称旧Dlow退出真的早于Dopen BUY。新waiting root在连续首触模型内先触T再触较低boundary；协议没有增加跨品种高低路径工程。该一致性仅支持条件收盘账本，不证明实际排队/足量成交/跳价/盘中cash或margin安全，也不是终值/DD经济上下界；原A也是同层日线条件报价。

原门准确为2020stress收益严格更高且DD更浅，其他3本不差，四本自身正收益/正财富；主2020stress固定252原source-day/2000配对日log差CI下界>0，四CI均披露，不误换base。stale/entry/capacity/新增numeric unknown均保留；即使名义通过仍无真实/正式/加注资格。失败关闭本精确条件包，不改touch/tick/limit/等待天数/成本/风险救分。

后续614仅完整审新613kernel/runner和真实fixture收据，不重跑作者新测试或旧suite；根真实terminal后一次必要native110MB/signals/mothers小列/旧固定indices与全4C账独审，不A/C策略重演/旧模型或数据源重跑。当前权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A。开始/截至协议审按新结果过拟合：否，尚未新收益；长期同史择题风险高。继续价值：仅一个低优先级固定条件反证有价值，不预认优势，不铺微观数据工程。完整long目标仍active，历史研究不等今天日线。


## 2026-10-21 08:56 CST：收益前完整源审及真实actual后独审终态

613 source-ready收益前GO：完整实读kernel/runner/7个新synthetic定义及真实receipt；独立AST提取并剥离613 entry/audit/disjoint markers后，逐字恢复原131函数。源SHA `04e648ee00c750b96f896d2e801f0b4bd6d4cda208eceb15ebafe2874d18eac3`；runner SHA `b1762d036f8acd7cb6e603171bf38dc9cd33e0b57d0649317b075175f3bf2625`；7fixture SHA `1f0503f762349dd66aa963e886ddfb357b334c66926062fbeec2959ea0199d67`。作者RED7→GREEN7及其两次GREEN已经如实披露；本614未重跑新fixture、旧suite或历史rehearsal。`preactual_review.json`给GO后root才启动唯一actual_run1。

613唯一4C实际session68093经同handle退出0，4.523846083秒；4started/4completed，0fit/SQL/GET/A replay。原52、signals及mothers全98/95域不变；累计**551fit/290完成cash＋1旧partial**。本614独立逐笔记账/方程核验不是策略或账户重演，新增研究fit/cash均0。

**完整独审核算接受，critical=0、important=0；精确611条件限价包失败关闭。** 本614首进程15125通过四本core账/原报价/年家族诊断及全部8000固定CI抽样，8792条显式断言完成后，在新尾审第一u预算处因审查器误用原字符串book.daily产生TypeError并权威exit1；未称live或完整通过。原partial收据/脚本/日志保留。root明确授权一次最小尾审恢复，改用既有numeric DAILY，仅新进程94505执行未完成尾段，exit0、422988断言全过；不重算core/CI、不跑A/C资金或模型。

**IO偏差明确披露**：审查开始额外读取继承native110MB、signals及mothers必要列各一次；普通进程退出后RAM已丢，获root授权恢复又各读一次，合计各2次，不能写0或同handle续跑。没有为此制造通用持久缓存或重放账户；旧indices/core/CI只首遍核，不在恢复重算。Source/manifest精确绑定在两遍中均核对，不因经济失败换数据。

## 实际四本与原A对比

100万起始、原0.25N/费用/u风险/保证金/容量/K不变，D开始到收盘有效的唯一L=u.close条件模型：

|C窗口/成本|期末权益|总收益|最大回撤|Sharpe|总滑点金额|成交fill/闭合root|闭合净胜率|
|---|---:|---:|---:|---:|---:|---:|---:|
|2020主/base|1,534,341.0275|53.434103%|−16.930978%|0.617020|100,878.024606|2239/1119|12.0643%|
|2020主/stress|1,447,213.0830|44.721308%|−14.928032%|0.689256|148,084.714149|1729/864|11.4583%|
|2023冷启/base|1,558,604.2050|55.860420%|−10.466197%|1.130824|44,410.523488|879/439|12.0729%|
|2023冷启/stress|1,477,448.2025|47.744820%|−9.859690%|1.129827|74,046.677311|762/379|11.6095%|

相对157 OWN，四组收益百分点差−69.4929191/−8.1206627/−26.68323495/−4.9197621，DD百分点差−1.30355769/−3.56873175/−0.56404832/−3.43692882，负数均表示候选更差。主stress原52.841971%降到44.7213083%，DD由−11.35930055%变为−14.92803230%。不能用某个成交子集更便宜/胜率变化替代完整自身账户结果。

四组原252 source-day循环、2000固定配对日log差区间：主base[−0.000409899209,−0.000069851927]；主stress[−0.000136066914,+0.000072149577]；冷base[−0.000294953663,−0.000037675031]；冷stress[−0.000158148340,+0.000065318826]。主STRESS下界门未过；所有C自身正收益/正财富，但return/DD/主CI门均false，gate nominal=false/financial_unknown=true。没有新seed、block、epsilon修复或CI重新生成。

## 全部新机制、路径及未知复核

逐账独立重构全部u潜在请求、family选择及占用/生命周期/风险拒绝、预floor共同scale/cap、专属风险/保证金/fee reserve与原F0减少；每个D pending的原native O/low、精确Decimal T、原tick/连续fallback、唯一ULP编码F、原Q/费用/滑点、rawF−.25N/low20、own D量、全部成交与取消/未知，均匹配。首个非marketable D前的原A/C现金/权益/风险/费用路径相等；主为2020-03-19、冷启为2023-01-03，不把此后A未来预算借给C。

|C窗口/成本|正cap限价pending|实际进入root|known未触达到期|rawF stale取消|缺D entry unknown|numeric unknown|capacity unknown roots|
|---|---:|---:|---:|---:|---:|---:|---:|
|2020主/base|1337|1120|182|32|3|0|33|
|2020主/stress|1049|865|154|28|2|0|16|
|2023冷/base|541|440|87|14|0|0|10|
|2023冷/stress|477|380|83|14|0|0|4|

原u新entry预算行2738/3149/1099/1198与C own轨迹一致。所有正cap pending审计闭合、所有取消无BUY、每个实际BUY限价硬核且未clip成本。全部旧force/reduce/gap/stop原价、等待root自身先入后更低stop、close mark/low20/canonical anchor/K/stale一次递增、全部逐fill gross容量/未知root和明细拒绝表，已核；不存在D取消/退出额度再分。恢复尾审使用已经首遍核过的core账/报价/CI，未伪装再跑旧策略。

年切片、全95family含零行成本及权益归因由独立core重构；导出年表/全8行A/C指标、完整BUY身份/数量重叠、entry-kind账内PnL恒等、sector分组权益/费/slip总计与最大盈亏root字段均匹配。开盘/盘中root贡献仅记账分组，不是无等待因果反事实；没有静态删除A逐笔盈亏冒充C。stale/entry/capacity未知保留，numeric未知本次恰0不代表真实队列已知。

## 最终收据、停止边界与反思

最终小收据：`outputs/stage614_conditional_limit_cash_review/actual_review2/review_receipt.json`（1973B，SHA `620c8c98f40a7460c56ef75f25d6ada849cfef73bc9b534dd342174b4c6c3288`）；acceptance_summary.json（24142B，SHA `20836ce6e016f0bb21dec708529a6859b5493a5a82d392861fc574544f25c06f`）；完整review.json（34883894B，SHA `1e7c152c84aebf6186f9b51e0534c212b2d3a3275073c6e1339dd7a890bf1329`）。原15125 partial在actual_review1，恢复脚本/尾段/正常日志在actual_review2。断言数用于覆盖说明，不是新增独立样本N。

新增策略数值搜索0；新机制参数仅611预冻的u.close/Donly/原cost反解理想触达约定，本614未增改删任何策略参数或旧结果。新增金融结果是唯一613四C，不因失败重启。结束按新结果过拟合：否，未调整任何limit/tick/touch/成本/等待日/stop/risk/样本窗口；长期同史择题风险仍高。继续价值：**本精确条件模型已充分反证，不值得救分或再跑cash**；完整全市场long目标仍active。

原A同样为日线条件报价；本模型更不保证接单/排队/冲击/足量成交、跳价/实际盘中cash或margin安全。四条确定账本不是经济上下界，.25N也不是实际最大亏损保证。失败关闭611精确条件包，不推断所有限价策略无效、不铺盘口/分钟工程。未授正式C9、生产或加注资格；由root615归档，本614不改LINE/registry、不再加测试/数据或新提案。历史研究不等今天日线。
