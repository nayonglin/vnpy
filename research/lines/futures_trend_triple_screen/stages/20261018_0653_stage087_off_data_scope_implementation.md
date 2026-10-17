# Stage087：OFF owner数据scope实施与三项有限接合

- line_id：`futures_trend_triple_screen`；记录 2026-10-18 06:54 CST。先读root 06:39 Stage087合同；实现约06:42—06:51，当前源码已冻结，后续只完成记录，不再扩修/重跑。
- 本人是本次实现者，不是本次独立reviewer；未实施/改写084 runner。只新增两源及一个test、087输出与唯一本文；合同原文件、旧source/LINE/registry不改，不stage/commit/push，不另派reviewer。
- 非alpha突破；新增/修改/删除策略参数和完整回测结果均0。全期权益、收益、DD、Sharpe、滑点、交易次数、胜率均N/A。

## 实际实现

`stage087_off_data_scope.py`负责真实root owner与current wait、原来源local/daily资格、白名单旧交付重新资格、独立minute reader、pointer及bounded driver；`stage087_off_data_provider.py`负责新scope packet和真实minute/ordinary daily parent/worker。两模块stdlib bootstrap，调用时配置原022冻结数值栈，未引入模型或金融入口。独立新进程导入两模块后numpy/pandas/sklearn/joblib/tqsdk均未加载；三文件compile exit0。

owner把A_OFF/B_OFF、attempt1、run_id、固定account_output/wait_root、金融runner最终path/SHA、真实PID/lstart+args、context/preflight/readiness与源SHA绑定；writer仍正确识别为中性checkpoint，而非把checkpoint writer冒充金融runner。root当前没有给真实owner，因此本轮没有生成真实owner/preflight/financial ready或运行provider。未来owner还必须绑定真正独立的data_scope_review，不能用本实现者收据自签。

旧模块globals未改。唯一runtime重定向遵root补充裁定：仅在调用原022.configure_runtime期间临时保存/重定向/恢复022.OUTPUT作为新日志目录；不改变037/041/051/052的owner/root/来源身份。新worker明确拒fixture owner；CLI没有fixture绕过。

数据侧复用冻结045/052/037/041纯资格和原012collector/018budget/API、051普通daily选择/DB/qualify算法。旧pure local函数在“不足时不返回部分proof”的接口限制下，为组合旧completed缓存，仅迁移其实际下一行id/time/同symbol合法后继提取段；最后full/anchor仍交原qualify_target，未造合成后继。scope控制/worker按新owner迁移，不复制金融main或另写账户PNL。

R/E/M保持原约束；整R交付，多需求不足不能签partial。full核完整grid+七值日聚合，anchor只完成首分钟+原open/可用openOI，不升full；新增键A0交集仍只R-E，旧重叠严格委托原021七值相等、所有symbol通过才append。冲突/rejected/缺后继不被新源救。缓存必须是root白名单、原独立receipt/origin/实际网络终态及raw/completion SHA闭包，不继承旧pointer/decision/commit。191只有已完成345来源可以按新实际R重资格，不能进入061继承；075fixture路径/receipt拒绝。

真缺daily时提供同scope普通API一次单目标子集prepare/run/worker，daily也占同batch4连接；独立reader重验实际raw与DB六字段/真实后继，closeOI保持DB N/A；原CSV/013合格或rejected目标不覆盖。同owner已完成snapshot可为之后实际目标日重新资格，跨owner只接受显式root白名单，origin与新目标分开；多SHA冲突拒绝。mutable audit/journal不作为不可变source消费。

driver每循环/launch/publish复核owner及当前真实request，保留4连接、840—3600批预算/840启动reserve及金融1800/7200余量，不重置原时钟。provider一次attempt/570soft600hard，已有失败/部分/无真实终态不自动retry；真实Popen句柄wait/communicate为0加parent0/inputs不变后才有terminal。独立review role重新查raw/proof/daily后签原021 receipt，driver再真parser/current guard后原子pointer。只有原engine data_qualified_appended是commit。

## 三项测试与全部候选历史

唯一入口：`.py311/bin/python research/lines/futures_trend_triple_screen/tools/test_stage087_off_data_scope.py`。仅三个具名合同test，没有新suite、旧suite、市场全扫描或金融。

| 日志/时间 | 实际执行 | 触发本次执行的实质变化 |
| --- | --- | --- |
| red / 06:42 | 3 tests/0.001秒/exit1，三项新能力缺失FAIL | 先写测试，缺新scope功能；不是import/runtime错误 |
| candidate1 / 06:46 | 3 tests/0.405秒/exit0 | 首版owner/local/parent-child链实现 |
| candidate2 / 06:49 | 3 tests/0.455秒/exit0 | 补闭worker/parent真状态和ordinary raw后继、新daily后续实际日复用；加入原test3断言 |
| candidate3 / 06:50 | 3 tests/0.562秒/exit0 | 真实已pin191缓存正向重资格、minute reader到guard/pointer序列；加入原test2/3 |
| final green / 06:51 | 3 tests/0.559秒/exit0 | 收尾金融runner source binding和terminal/parent冗余身份一致性及记录 |

总共仍为3个唯一test，15次方法执行（含RED3），不是15次回测。root要求收尾后已停止源修改/测试；不以每份日志数冒充额外金融或全市场资格。

1. owner：同digest两臂目录不同；错owner/PID/lstart/run_context字节/文件SHA/current wait拒绝；旧044/037/041/051/052源原字节不变。真实CLI无fixture开关，provider拒fixture owner。
2. 真实021 Gate/parser：tiny两需求full345+anchor1整R交付；anchor不获full，保留旧值故意冲突时两symbol原子拒绝；不完整不签整单，新source真冲突拒绝。另**实际读取已pin原191receipt和345完成值/345证明**，核origin闭包后用不同fixture request重资格，明确无061/commit继承，不重新读市场全集或deadengineRAM。075fixture拒绝。该新receipt仍fixture_only，不是新市场数据签发。
3. 全部child为受控替身，无API网络：父子零码及raw结构后才terminal；daily算第4连接，已有attempt/不足840/PID改变拒绝；ordinary raw真实合法id/time后继及后续实际日复用同snapshot，DB查询只替换为声明的tiny六字段；minute原始proof到独立reader/真实021 parser后才能fixture pointer，current wait变化则拒绝发布。测试没有把fake terminal写到真实packet或owner目录。

全部命令、elapsed/exit和变更理由在execution_history.json；final证据test1/2/3.json、green.log与compile_bootstrap.json均在087实施输出。四次GREEN之间仅上述必要main路径/身份闭合，未扩大alpha或重跑旧数据suite。

## 最终身份、API与交接

两源source_bindings（供之后独立reviewer原样绑定，恰两项，不含test/dependency）：

- `/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage087_off_data_scope.py`：SHA `7c65bb01147a687529e27901d82b74ff4284a4dc1c84be2c7fe22e8f3aa5d737`，49864 bytes。
- `/Users/mac/Desktop/fian/research/lines/futures_trend_triple_screen/tools/stage087_off_data_provider.py`：SHA `d8ecebf5b27ebb4179f81f7b960165a14ddbe9ce8655837bbf58ff1ecbf4706f`，16482 bytes。

test SHA `629f81cb4ce3880e96f52756f8fd33c62e7f104b18803356d33b92d89fbe8e2f`；记录于独立test字段，不混入两源source_bindings。

确切CLI和owner字段：`outputs/stage087_off_data_scope_implementation/CLI_AND_API.md`。五边界为scope.read_actual_request/resolve_actual、provider.prepare_packet、scope.review_packet/publish_reviewed；scope --role resolve|review|drive，provider --role prepare|run|worker，全部显式owner路径/SHA。固定输出为scope/<arm>/<run_id>/request_digest，真实request仍是原账户arm/data_wait。root未来独立reviewer接合receipt需independent_review=true/P0/P1=0、source_bindings恰两源绝对path→SHA+bytes；本实施收据明确independent_review=false。

剩余已知阻塞实现失败：无；**真实网络/真实owner/完整账户路径没有执行**，本次仅代码及三个有限fixture，不宣称真实SDK交付成功、数据集齐备或金融readiness。root随后只组织一次有限独立审查，再按084/087共同合同和真实owner/readiness决定下一步，不由本人开跑。原A0限制、原B失败N/A和原目标未达成均不变。

开始及结束新增过拟合判断：否，按统一身份/来源资格合同实现，不看PnL、不挑日期或改参数；历史选择偏差未消失。继续价值：是，旧B scope锁已有直接反证，本实现提供一次性接通必要数据链的有限机制证据。金融/网络/真实provider/整库预检/模型load-fit-predict/外部订单均0，production_qualified=false。
