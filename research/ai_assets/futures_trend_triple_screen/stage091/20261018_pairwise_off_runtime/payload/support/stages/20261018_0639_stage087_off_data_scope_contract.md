# Stage087：新OFF owner数据通路实施合同

- line_id：`futures_trend_triple_screen`；2026-10-18 06:39 CST，root。
- 依据：062/083/086及085真实源码审计；不是新alpha，不启动金融或网络。原八项共同OFF、原1800/7200预算、每批最多4条provider连接与570/600父子限额均不变。
- 085确认旧main有真实owner/PID/reader多层限制。root选择新增显式scope入口，复用已审纯资格和collector/budget函数，不改旧源或运行时改旧globals来冒称旧身份。

## 有界交付

新增`tools/stage087_off_data_scope.py`（owner、request、local resolve、独立review、publish、bounded driver）和`tools/stage087_off_data_provider.py`（packet、真实minute/daily parent/worker）及一个`test_stage087_off_data_scope.py`。各角色可同一入口用显式role/family选择，但raw provider与独立reader是不同代码责任/进程，外部来源与scope均须可验证；不要再造通用任务调度框架。

执行前由root在新runner真实启动、run_context真实存在且PID确认为live后创建owner manifest。它绑定A_OFF或B_OFF、attempt1、run_id、固定account_output/wait_root、新runner最终path/SHA、实际ps lstart+args、run_context/preflight/execution-readiness path/SHA及scope/provider/021/022源码清单。旧context writer实际为`stage065_account_checkpoint.py`，金融runner身份从source bindings取，不能把writer误当runner。

所有新decision/packet/review/journal输出放`outputs/stage087_off_data_scope/<arm>/<run_id>/`之下，再分request_digest；账户真实request仍原022生成于`stage065_pairwise_off_account/<arm>/data_wait`。request本身没有arm/run_id，digest可跨臂相同，不能因此复用新owner的decision/response。raw来源可共同只读，mutable live audit/journal不可当不可变source指纹。

本轮接口采用085的五个边界：`read_actual_request`、`resolve_actual`、`prepare_packet`、`review_packet`、`publish_reviewed`。CLI具体role flag由作者一次决定并写实现记录；driver传显式role/family/path/SHA，不从旧basename猜角色。没有任意output/provider脚本、绕过身份、放宽资格或扩大预算CLI。所有role原生stdlib bootstrap，在装载原numpy/provider helper前配置原022冻结runtime。

## 算法与缓存

- 当前request读取验证固定wait_root、request/fingerprint/fileSHA/canonical digest/真正最后waiting状态；每循环、provider启动前、publish前重验同owner live PID/lstart/args、runner源码、当前request。跨臂/换run/PID复用拒绝，缺真实owner不得启动provider。
- 新source/receipt解析尽量同已pin bytes，不把原文件校验后重开当新合同。旧纯资格函数以显式输入复用；不改原021/022、037/041、044/045/047/048、051/052、SDK或collector。新的scope源码与实际新输入闭包进入receipt/InputRecorder。
- local/daily优先级、rejected/no successor/真实值冲突拒绝、DB open_interest=openOI且closeOI=N/A，均沿085和旧52/45/37/41原语义。full核完整R、完成后继和日线七字段；anchor仅真实完成首分钟及原open/可用openOI核验，绝不自动给full权。
- 061数据层已保留190包，未来缺口才触发新通路。旧037/041 completed raw及旧独立delivery可以作为**白名单来源**按新真实R重新验收：核原origin、确有网络时原真0终态/parent/raw/completion SHA、原独立receipt精确scope，保存新当前request来源闭包。不得把旧pointer/decision直接当新签收，也不得调用075fixture wrapper。
- 191未commit不能进入061继承权；其真实345完成来源可以按新R重新资格。新source同key冲突整体拒绝，不挑有利价格。局部local不足不得签partial整request；R/E/M原约束及新键=A0交集边界沿旧合同，最终仍由原021全重叠七值相等后原子append。
- 若真实缺daily原始来源，支持同一owner scope下普通daily API的单次prepare/run/worker与独立target资格，复用051纯选择/DB与052 `ordinary_raw_evidence`算法；daily连接也占同批4条，不额外赠送。原有CSV/013合格或明确拒绝目标不能用新daily覆盖。没有合格来源就fail closed，不用daily-open兜底。

## 生命周期

packet一次prepare/一次network_attempt1；已有失败、部分、缺真实终态无自动retry。worker保留原合法API和后继collector、570soft/600hard；真父子returncode及全输入不变后才有terminal观察证据。独立reader重新核raw/proof/daily/精确R和scope后签原021 receipt，不写engine pointer。driver再次核source SHA和真实021 parser/current owner/request后原子发布原022 pointer；只有engine `data_qualified_appended`算commit。

driver每batch最多4条新连接（含daily），原840—3600批budget/启动前至少840秒reserve，不重置金融1800/7200时钟。若engine已终态或current不再等待则停止，不能跟随锁文件猜live。工具观测中断不是重启理由，任何已启动子进程须真实wait/poll原句柄，不启动重复请求。

## 有限验证与独立接受

最多三个合同tests，先RED后GREEN，不网络、不真实金融：

1. 两臂同digest仍不同owner命名空间；错owner/PID/run_id/请求fileSHA/当前等待拒绝；原源码/SHA不变。只在临时fixture使用受控process观察替身，真实CLI无fixture绕过，provider明确拒fixture owner。
2. 真实021 parser/Gate的精确local交付、anchor/full分权、多个requirement整R与旧七值冲突原子拒绝；旧cached source重资格含失败191可用来源边界（不是继承commit），source冲突/不完整拒绝；no response before独立review/current guard。只用tiny或已pin的单个真实345来源投影，不重扫市场。
3. driver/provider调用链有限fake child验证：父子真0才terminal/签收、失败/已有attempt不retry、daily计入4连接、余量/PID/current变化不启动/不发布；verify只正常subprocess存根，不造真实market签收。正确runtime先配置；无engine/账户/model/网络调用。

作者唯一Stage087实现记录与`outputs/stage087_off_data_scope_implementation`，不改LINE/registry或084源，不stage/commit/push、不另派reviewer。root随后组织一次有限独立接合审查，只有087+084都接受且实际来源/identity/readiness齐，才启动新金融。当前owner/PID尚不存在，不生成伪owner或金融ready。

新增/修改/删除策略参数及金融结果0，所有绩效N/A、production_qualified=false。开始新增过拟合判断否，来源/owner按固定合同而非PnL选择；继续价值是，真实旧scope锁会阻断完整对照，统一入口可避免逐请求打补丁。实际交付、测试和剩余问题另如实记录，不把本文当已完成。
