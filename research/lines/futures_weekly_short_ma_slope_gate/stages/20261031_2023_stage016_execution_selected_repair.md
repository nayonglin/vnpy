# Stage016 完整CI两失败修复与查询节拍边界

- 时间：2026-10-31 20:23，北京时间；line_id=futures_weekly_short_ma_slope_gate。
- 本阶段只修改931查询节拍family及两个测试文件，不操作Git/index、生产、CTP、SMTP、委托或金融回测。非策略优化、非重要突破，production_qualified=false。
- root完整新默认CI原结果：88套件2254项，2252通过/2失败，385.65秒，critical前后SHA无漂移。原log/xml/json在/private/tmp/weekly19_selected_final_attempt001.*，不得把它改称全绿。

## 第一失败：旧C9 monthly-AI fixture身份遗漏

Stage947的test_stage935_reads_stage173_from_data_and_ai_candidates_from_control直接调用Stage935._run；此前仅给launcher/session_launcher声明旧C9，却没有给实际Stage935模块声明历史profile与历史AI物料。当前weekly默认因此正确触发disabled_for_weekly19_fixed_universe。

测试现在同时显式patch C9_15W_PROFILE与OFFICIAL_AI_PRODUCT_POOL_STRATEGY历史material identity；不修改当前config、CURRENT或Stage935 guard，不弱化原数据/控制目录、published receipt或命令参数断言。只补profile时又正确被historical_ai_material_identity_required拦住，该中间RED保留。最终该单例+Stage935历史/weekly disabled测试36项通过，1.18秒。

## 第二失败：精确复现与真实节拍竞态

原seal集成case报final_snapshot_q2:final_order_query_pacing_timeout/final_order_query_missing_or_incomplete，单例当时4.450秒。作者先原样精准重跑两失败：1失败/1通过20.29秒，seal本身通过；加只读时序probe单例仍通过20.09秒；按CI紧邻5个warm cases后再seal同进程重放，6项通过76.73秒。因此原CI没有逐查询时序，不能确定声称原失败就是本次竞态，也不能简单说18秒不足或随意增大时限。

probe确认fixture虽patch CTP_QUERY_INTERVAL_SECONDS=0，order/position/funds helper定义时默认仍捕获1.1且门内min1s，实际每O-P-O约3.23–3.32秒、原8秒budget不变。这说明存在真实时钟依赖，但本阶段没有删掉节拍或将其当虚拟时间。

进一步读源发现五个同family循环：while谓词先读monotonic判断尚未到next_allowed，body再读monotonic算remaining=min(next_allowed,deadline)-now。两个读数跨过允许时点时，remaining<=0会错误报pacing_timeout，虽然absolute deadline尚远。例如next_allowed1.1、两读1.099999→1.100001、deadline8。新增scripted测试先3失败/2真超时负例通过；独审又独立确认trade/detail两处，扩展作者测试2失败/6通过。该真实bug可确定复现，且与原CI早期Q2误超时的时序相容；原CI精确因果仍未知。

最小修复只令每轮使用同一now判断允许时点及remaining，五处全部修复，不改变interval、min1s、原budget、18秒caller截止、25秒trace、授权或send门。七个此前quota/native/deferred关键函数AST与20:02封存逐项完全相同；整931 SHA当然更新，不能复用旧整文件pin。

独审还确认trade缺post-pacing deadline门：首次poll已越允许时点和真实deadline时，原函数仍发1次reqQryTrade然后才timeout；detail已有前置门。作者追加第9反例先失败（真实fake query计数1），再对trade加同样>=deadline拒绝，确保reqid/API前0查询。没有真实交易API调用。

## 验证与交接

最终定向回归137项通过，22.26秒（readiness全文件、原executor serve、原失败seal单例、Stage947该历史单例与Stage935全文件）。包含9个新增时钟/真实deadline边界case。三处owned文件compile与逐行空白检查通过。所有RED、中间legacy identity失败、只读probe代码/时序、最终log/JUnit、源码SHA及AST关系见20261031_stage016_execution_selected_repair_manifest.json。

新931 SHA：ac3176c8752fd49c8527953deed6a2bef8ff1e9305327dfe86b33136f4e06c10。交独审运行其独立时钟probe，并由root在clean source上重跑完整88suite。137定向绿色不代替该完整重跑，不把2252+定向137相加宣称全CI通过。真实source/现金/statement/capture与production qualification仍未通过。

新增/修改/删除策略参数、金融回测结果均无；权益/收益/回撤/Sharpe/滑点/交易数/胜率均N/A。运行前后过拟合判断：否，修确定性工程边界；继续价值：是，消除可复现的误超时及越截止只读查询，同时保留真实资金、订单与来源失败阻断。
