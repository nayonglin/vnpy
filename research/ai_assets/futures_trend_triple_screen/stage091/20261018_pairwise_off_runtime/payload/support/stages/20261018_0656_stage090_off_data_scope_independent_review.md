# Stage090：OFF data scope 的独立有限接合审查

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 06:56 CST。
- reviewer：`accepted_delta_review`，未参与087实现；同线唯一Stage，不改LINE/registry/作者源或Git。
- **结论：P0=0、P1=2、P2=0；当前固定087源码有限接合不接受，不能使084的data_scope_ready门通过。** 三测试通过不抵消下列真实入口缺口。

## 固定身份与验证

两源SHA/bytes：scope `7c65bb01147a687529e27901d82b74ff4284a4dc1c84be2c7fe22e8f3aa5d737` / 49864；provider `d8ecebf5b27ebb4179f81f7b960165a14ddbe9ce8655837bbf58ff1ecbf4706f` / 16482。test SHA `629f81cb4ce3880e96f52756f8fd33c62e7f104b18803356d33b92d89fbe8e2f` / 24721。receipt的source_bindings恰两源绝对路径，不掺test/dependency。

root先固定三SHA并授权不等纯文档落盘，随后补交最终实现记录与metadata；本reviewer核Stage SHA `929850ea55f00f4957d5899a01553458cf5dc5b85c3ee30bc11c4f081b124f76`、作者implementation_receipt SHA `59fdd0fe6346cd7c1b057c37d537af73e8986db2371db0cc8e93f8f5c4da83f2` 及14个artifact绑定。补文档后未重跑测试。作者RED/四次GREEN共15方法执行是其历史，不能冒称本次审查或金融。

本reviewer仅一次运行当前原三个具名tests，OUT在内存重定向090：**exit0，Ran3，0 failure/error，0.600s**。原test、源和087证据未改。额外只做未覆盖的owner绑定与公开provider余量门两个小反例；均临时文件/受控进程观察器/fake child，无真实owner、SDK、provider、网络或金融。

## P1-001：owner未闭合实际授权和原始run clock

位置：`tools/stage087_off_data_scope.py:125–147`，关联151–175、628–631。

verify分别hash context/preflight/readiness，但不核context.preflight_sha256与绑定preflight、不核owner readiness是否实际preflight.execution_readiness及argv所用同一路径/SHA，也不核owner.run_started_at是否context.started_at。load_owner的args只查runner basename、--run和--arm。

严格非fixture校验分支的临时反例保持source/runner绑定正确，却让preflight与argv指向A的dummy readiness、owner指向另一份B dummy readiness；context起点为3小时前、owner起点为现在。load_owner/verify仍接受，context的7200剩余约-3600秒，scope报告剩余约1800秒。反例不是实际账户授权，仅证明校验缺门。

应在非fixture入口闭合固定真实context/preflight路径、相互SHA、实际readiness及argv，并严格继承/核对context原始起点。原022本身仍有权威超时；不能据此宣称金融时钟已被改写，但新scope的启动余量会与其脱钩。

## P1-002：公开provider run绕过金融余量门

位置：`tools/stage087_off_data_provider.py:97–110`。

driver.run_provider_connection正确检查原金融剩余余量和840 reserve；文档支持的provider --role run直接进入run_once，却在read_packet/SDK检查后创建attempt并Popen，不检查该余量，worker网络入口也未补门。

必要反例只替换read_packet/SDK/Popen：remaining_engine_seconds设为0时run_once调用预算检查0次，仍启动1个fake child并返回worker_terminal。真实provider启动0。公开parent与实际连接入口应重新核同owner/current和金融余量，保持driver持久计数/4连接及attempt1无retry；不要新增宽松路径或扩大预算。

## 已验证的其余合同与限界

- 固定A_OFF/B_OFF、attempt1、run_id+digest目录；同digest跨臂分离，PID/lstart/args及当前request/fileSHA/wait状态持续复核。完整readiness/run clock闭包受P1-001阻塞。
- 整R/E/M与原021/022接口保留；full核canonical完整grid+完成+日七值，anchor仅首分钟/open及可用openOI；test2真实Gate/parser证实full345、anchor1，anchor不升full，旧七值冲突时两symbol原子拒绝。
- 本次只按已pin原191 receipt读345值和345 proof作不同fixture request重新资格，不继承061或commit权；075 fixture拒绝。旧缓存白名单/origin/完成/network terminal闭包重新核，源冲突和不完整仍拒绝；未重审061/071或扫描190/市场。
- 新Bindings JSON/CSV同被hash bytes解析，immutable来源进入receipt；当前mutable audit/journal不作immutable source。ordinary daily用原raw/DB六字段与后继，DB closeOI仍N/A；普通daily计入每batch4连接。
- 正常driver真实句柄wait/communicate+parent0+inputs不变后terminal；独立reader核raw/proof/daily/worker/parent后签原021receipt且不写pointer；driver真parser/current再publish，只有engine appended是commit。
- driver 840–3600批预算、840 reserve、四连接以及provider570/600/attempt1无自动retry保留；公开入口余量受P1-002阻塞。
- 无旧owner/root/provider globals改写，仅允许的022.configure_runtime期间OUTPUT路由并恢复；stdlib bootstrap先配置原冻结栈。当前没有真实owner；CLI没有fixture绕过。没有真实SDK/完整账户路径的正向证明。

## 交付、结果与反思

完整实际命令、exit、stdout与SHA见090 evidence.json；receipt independent_review=true但p1_findings=2、integration_accepted=false。本次是有限代码审查，不是实际来源资格、数据集签收、金融授权或生产资格；不生成未来owner/PID/readiness。阻塞清单一次完整报root，由作者后续按root裁定处理，本reviewer未修源、未自启修复波次。

root已确认两项为必要接合问题，只授权原作者一波修复；090本失败记录不得覆写。未来独立Stage094最小复核边界：核修复源/差异与实际context/preflight/readiness/argv/起点同一性，正确闭包应过、错readiness/起点须拒；再以fake child核公开parent及worker连接前的0/839秒拒绝、840以上正常小分支，不碰SDK/真实owner。除修复改变其他已测语义外，不重跑整组三测，不扩大旧scope，不真实preflight/金融。当前只给复核边界，不提前执行094。

新增/修改/删除策略参数和完整回测结果0；权益、收益、DD、Sharpe、滑点、次数、胜率均N/A。真实prepare/provider/网络/金融/模型load-fit-predict/订单0，旧suite/整库预检/全市场hash0，不读新途中PnL。原A0限制、原B失败N/A、PIT限制及“不能只赢弱A就达标”均继承。

调研与判断：遵root明确无网络边界，仅读冻结本地合同与实际API；没有新网上/GitHub研究，也不从资料推导alpha。开始及结束过拟合判断：**否**，不看收益、不调参数，只核固定身份/权限/预算。继续价值：**是**，两项入口缺门可以定向收口；当前不应进入真实金融。

