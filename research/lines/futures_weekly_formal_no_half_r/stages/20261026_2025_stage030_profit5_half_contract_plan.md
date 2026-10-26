# Stage030 盈利超过5%半仓止盈：日收与周收固定对照计划

> 执行方式：已授权在当前隔离研究分支继续迭代；只新增本研究线唯一文件，不改旧代码、数据、LINE/registry、正式/生产。使用writing-plans、TDD和独立审查；不另行要求实施许可。

- line_id=futures_weekly_formal_no_half_r；记录时间2026-10-26T20:25:34+08:00；来源HEAD9eacc5443c724edc821a8522e1a498aeac84e59a。用户确认“5%按合约价格涨跌幅”，最初选择周收后补充“日K和周K同时跑”。解释为仅新增半仓止盈频率分daily/weekly两臂，其它指标及技术止损继续周线。不是全策略改日线。
- 结构假设：以固定阈值分段兑现减小利润回吐，但可能削弱趋势右尾与复利；结果不预设为优化。无新增拟合，重复历史及本线多次迭代有过拟合/选择风险；只固定5%/50%，不按结果救参、删品种、换源或扫阈值。继续有价值：辨明兑现频率与持有收益/风险的交换。不是重要突破，NO_PROMOTION。
- 最小对照：B=冻结Stage029 R_attempt003（无本条止盈，复用独审通过账本）；D=同版+daily close盈利>5%半仓；W=同版+fresh completed weekly close盈利>5%半仓。旧正式版不参与本次优化晋级；退出模块无法独立交易，无独立B策略，不展开正式A/B/C及生产资格。D/W作为同等预声明候选并排，不事后只保留好结果。
- 区间2015-01-01—2026-10-26，实际2015-01-05起2868日；本金150000，原19品种。直接复用stage029_latest_data/data_approved冻结日库，SHA8483435b49605691c91380beea999f49ec7fd08b3ea81b981fdf9953f61989d9；无新下载/行情改写。MA5/10/20周，MA40/MACD/全AI/HalfR/C2/RSI退出off，21接受周就绪/41容量，max19无额外4仓；其它资金、保证金1.65、安全、热度、5日换月、无加仓反手等沿用Stage029 v2。
- 盈利口径：每个真实合约原生持仓轮（0→持仓→0）以已实际成交并同步entry_price的层、数量加权开仓价为成本。长仓close>cost*1.05，短仓close<cost*.95，严格超过；等于不触发。按价格毛涨跌判断，不按保证金/账户/含已实现收益口径，不用计划信号close或周high/low代替，不以最高浮盈已达标而当前close未达标触发。费用照原账本单独扣。
- D使用本日实际日K close，W使用本约本日fresh有效完成周close；10/26未完周不得用于W。合约与epoch有效、价格有限正值、全部层entry_price_synced且层数量=实际仓位绝对值才可判断；缺失或矛盾硬失败，不悄悄以计划价回退。
- 半仓数量=floor(当前实际持仓手数/2)，至少留1手；3手平1留2，2手平1留1，1手不减且不伪记done。每原生合约轮最多一次；成功生成减仓目标即置done防重复，下一日实际fill另勾稽。换月旧轮结束、新约以自己的实际成交成本开新轮，done重新计一次；不做跨合约拼接的连续趋势成本/累计收益。本轮层无加仓，部分退出保留余层原成本、stop和极值，不能以现价或已实现收益重置余仓成本。
- 退出优先级：原prev2/layer全平与每日账户安全/热度减仓优先；借现有partial-exit调用槽接入独立profit5 helper，RSI flag仍False且不得调用RSI/复用RSI done。该槽在内联MA全平之前，因此helper须用同observed weekly history的MA20_prev做无副作用defer：同fresh周MA全平已成立时不半仓，返回原流程让MA全平继续。不修改_stop_triggered全局语义，不让半仓提前continue抢占原全平。
- 状态：Stage030自有episode字典/递增ID，由成功_open_position创建，标注product/native/direction/entry signal date与actual synced cost；不依赖ProductState.reset删除动态属性。换月拒开/旧空仓不能遗留done影响下一新开；未匹配episode/未知方向/未同步成本等显式失败。
- 执行：信号后下一全市场交易日、同真实合约正量日Kopen，使用原严格时钟/日开盘适配。没有分钟、代理、顺延、同close成交或5%限价保证；次日跳空可使实际兑现涨幅低于5%。末期pending保留，不借10/27行情执行/期末强平；已生成而未成交止盈目标需独立报告。
- 记录：新decision/trigger/episode/guard CSV逐日保留basis、direction、frequency、date/week_end、close、cost、pre/close/remaining数量、done、defer reason、实际锚点/next-open。audit_profit_half(strategy,frames)校核每轮<=1次、D/W日期、严格阈值、整数数量、无RSI/short2，以及每trigger的order/实际fill或明确末期pending。不能把trigger数当成交笔数。
- 通过门：代码行为、源SHA、原19/参数/数据相同、无未来周、实际成本同步、一次性/换月重置、优先级、同约next-open、会计/余仓/滑点/全部原风险模块通过。收益门并排报期末权益/总收益/DD/Sharpe/成交/轮胜率/平均赢亏/Payoff/PF/滑点、实际1.65保证金天数及峰值、分年与2015—2019/2020切片/末未平。改善收益却恶化DD/早期或保证金则mixed不晋级；D/W都差保留负结果，不改阈值再跑。
- 源/置信边界沿用：零手续费、固定滑点、静态原19/规格、接受观察周会跳自然周、旧源争议及历史main/PIT不足。Stage028旧cohort分类不可直接套新候选。独审覆盖采用源内部勾稽、声明逻辑与会计，不证明历史全真/OOS/容量/生产。
- 外部资料：[Backtrader Strategy](https://www.backtrader.com/docu/strategy/)与[GitHub strategy.py](https://github.com/mementum/backtrader/blob/master/backtrader/strategy.py)支持close指定数量和market默认下一bar open；[Backtesting.py API](https://kernc.github.io/backtesting.py/doc/backtesting/backtesting.html)有部分close(next market)。只参考部分退出/因果执行纪律，不复制alpha或最佳阈值。

## 实施任务（短计划）

- [ ] Task1 tools/stage030_profit5_half.py与test_stage030_profit5_half.py：先行为red（原版不会半仓），再实现profit_half_strategy_class(base,weeks,frequency,enabled=True)、audit_profit_half(strategy,frames=None)。覆盖长短>与=5、日中高点不算close、D/W频率、实际同步价而非计划价、奇数/1手、一次性、换月/平后新开重置、保留余仓成本、prev2/layer/MA/每日风控优先、末pending、非法数据fail closed、disabled与原adapter等价。只该模块实现者写该两文件与唯一测试输出。
- [ ] Task2 tools/run_stage030_profit5_half.py：新入口--frequency daily|weekly --attempt 001；分别outputs/stage030_daily_attempt001、stage030_weekly_attempt001，拒绝覆写。套用原历史/数据/时钟/全AI关闭/metadata严格验收并以R003为唯一冻结控制，实际/设置/有效参数仅新增研究标记，旧字段零差异；绑定合同/source/test全SHA，回放前冻结；诊断与acceptance即使失败保留。
- [ ] Task3 tools/stage030_build_artifacts.py与test_stage030_report_builder.py：三臂只读会计/同窗源/flags参数门，复用已审配对和风险计算，新增三臂summary/逐年/品种/早期/已平段/末仓/权益回撤图；label明确仅profit退出频率不同、技术stop全周。不得新金融回放或覆盖Stage029图表。
- [ ] 非作者preflight审真实MRO/实现/runner与行为证据；本线回归，原全仓库1652测试已有5fail45error边界保留，不声称全库绿；必要时当前再核环境错误并记录。
- [ ] D/W金融顺序运行（共享纯profile builder避免并行写），每完成一臂就交独立结果agent，另一臂独立进行；基准R003仅只读复用。独审重算逐笔/日会计/采用周/每5%触发的实际成本及源close、余仓数量、执行锚点/一次性/分年/PIT边界。
- [ ] 中文结果stage、三臂图/表与独审/交付SHA闭包；复核Stage029 3313旧绑定源未变；本地研究提交，不push、不合并、不更正式版本。不写个人memory。
