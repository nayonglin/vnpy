# 三重滤网趋势策略持续迭代研究线

- line_id：futures_trend_triple_screen。
- 建立时间：2026-10-17；来源分支codex/ai-training-data-expansion，起始HEAD cdac67c5a。
- 用户目标：按三重滤网思路持续迭代现策略，寻找扣成本收益更高且最大回撤更低的可复验版本；规则、AI特征及其他有机制依据方向均在范围内。
- 当前状态（2026-10-18 03:25 CST）：C_TS attempt2完整exit0并独立033验收P0/P1/P2=0/0/0，660825/340.55%/DD−32.758963%/Sharpe0.991077，382fills、163母59赢36.196319%。对A0净利润仅保留24.1800%，收益/Sharpe/峰margin门失败；停止固定C形状，不扫参、不扩多周期。实际R超u估值100/100、max50x；额外1.65日收盘margin峰122.329%（非分钟PIT），B必须先定一致估价口径。旧attempt1导出失败保留。金融7attempt/3 accepted、训练0；整体目标active、production_qualified=false。
- 研究与生产分离：当前m0008参数身份与已接受Stage249修复源码组合为离线对照，production_qualified=false；实际生产资格缺项不由本线修改或冒充通过。
- 记录规则：各轮中文stage、完整失败臂/参数/数据/源码指纹和独立复核；不向旧研究线追加，不覆盖原行情或用户脏registry。本线索引由合入者统一更新。

## 路线与禁止事项

1. 第一层增量：固定已完成周MACD(12,26,9)柱斜率，仅限制首次空仓入场；原AI10非fu+fu、0.5R/retry、换月、退出和风险不动。
2. 有序状态机：独立研究“周许可→日线FI2逆向波动准备→之后顺势突破触发”，不能以同日多个指标AND代替顺序；实施前另冻结触发/取消/止损和独立B及组合C。
3. AI条件质量：仅在可靠状态合同落定后，比较固定周方向/回调/恢复特征的严格时间与产品留出增量；保留旧108基准，purge/embargo，不能借AI代替人工扫指标。
4. 目标验收始终为更高净收益且更低最大回撤，随后验证独立起点、成本和弱段，不能以少交易、较高胜率或一段历史冠军替代。
5. 同一结构只允许一个主参数版本；失败后不扫MACD窗口、FI周期、小数门槛、品种/年份名单救参。所有试验计入累计研究谱系。

## 已有反证

- 原swing Stage008/009周线＋日线点火没有稳定成本优势；不是现C9同源试验，不能直接推定新候选失败，也不能把经典框架当alpha证据。
- winner_forensics Stage014慢趋势一致性未过可靠性门；禁止回到120/200日慢均线扫描。
- Stage269全市场ER样本不足且中组收益集中于重叠段；本线研究同一品种的跨周期时序，不把市场ER桶变成滤网。

## 结束条件

存在同时改善收益与回撤的候选并通过固定多周期、成本、独立数据/逻辑复核，才可称阶段候选；目标完成仍需与原需求完整核对。没有候选时保留目标active，依据新证据选择机制不同的下一步，不能把无限搜索本身当成功。

## Stage001 已有证据（2026-10-17 22:52 CST）

- 周特征一次构建77368行、独立EMA复算0差异；初始信号非冗余，但unknown明确回退，不能以产品日覆盖替代真实候选覆盖。
- A0_attempt2为2262595/1408.3967%/DD−48.78985%/Sharpe1.367364，滑点605450、816fill、318个retry合并完整episode/35.5346%胜率；与旧A的1641日及全部成交经济字段完全一致，原生可开计划328中270有周状态。
- 首次A0因模型1.8/默认runtime1.6不兼容失败，恢复既有冻结stack后完成；首次C0严格缺rb2010 May15 21:00→May18交易日anchor失败，两个失败目录都保留，不伪造截断成绩。
- 本机Stage491源已含完整345min，七字段聚合匹配、SHA在旧A input_manifest；Stage002批量覆盖134个原completed文件，冲突隔离且原cache不改，以A0实际读取集合零交集证明数据补充不改基线，避免逐个缺口回放。
- Stage002接受1078530条新增分钟、117合约；与A0全部106731实际读取键交集0，独立验收通过，39项相关合同测试通过。16个SQLite缺CSV来源没有贡献新键，全部新增分钟均有原CSV日线七字段核验。
- C0_attempt2于23:04—23:05推进至2020-08-12后再次严格缺分钟；独立复核实际403输入SHA变化0，无metrics/daily，不给截断收益。累计4账户attempt/1完成、周特征1次、下载/训练0；没有alpha结论或晋级。
- Stage004先给保守数据上界，不能把当前主＋紧邻前主当全部路径，也不能把无真实日线的过期旧主上界当下载任务。Stage502 carry bar边界只作覆盖说明，本轮不改引擎。Stage003有序入场备忘已保留但未批准实施。
- 记录见23:05 Stage002数据结果、23:09 Stage001中止结论及23:12 Stage004协议；既有失败和真实runner字节都保留。
- Stage001/002已登记86个复现资产（约9.16MB），manifest `205f3868671b96ab0bc7a42f75a50a02dacb57af3b7b5412fd969f1f4d7a9720`，逐文件SHA复核通过；压缩周状态解压字节等原输入，模型与失败记录保留，不含原始分钟。位置：`research/ai_assets/futures_trend_triple_screen/stage001/20261017_first_screen_increment/`。

## Stage004—008 数据推进（2026-10-17 23:58 CST）

- Stage004已接受base+overlay共2,489,646个分钟键；当日主力6360/28451个完整session，只占22.3542%。理论旧主上界含大量carry诊断，不能直接作为下载任务。7912个本机路径多为5份工作区的同源副本，声明SHA未被误作实测验证。独立复核为有限session/语义抽核。
- Stage005复用原始纯信号方法，单次29秒枚举900个潜在初始事件；C0保留701个（含143个周状态未知回退），对应700个可生效session，其中378个缺124,772分钟。A0已知886个候选四身份字段全部命中，独立有限窗口复核P0/P1=0；不等同实际成交和完整账户路径。两次C0失败session不在该初始集合，order offset未保留，来源类型未知。
- Stage006固定535个A0首分钟成交锚点仅534个与日线open完全相同；唯一au2610/2026-10-14为canonical903.62与daily904.98。来源原因未知，不修复该孤点、不启用daily-open fallback。独立复核通过的是关系审计，普遍等价假设被反证。
- Stage007仅1次正规历史流连接、38.22秒取齐345根，原CSV七字段全部一致；鉴权源码未改、无委托、未连接券商。旧quality拒绝、exit1及P1映射错误保留；该P1属于原校验工具，不是分钟raw价格错误。
- Stage008零新网络、零账户，仅对原345行重资格；CSV七字段及DB OHLCV+openOI共13项一致。DB的closeOI为N/A，不能外推所有DB来源。原DB/策略OI语义和全部旧证据均不改；独立receipt为`aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6`。
- 累计金融attempt仍4、完成仍1，周特征构建1、模型训练0、provider历史流1。没有新C0成绩，没有晋级或部署。当前工作没有按PnL调整参数，过拟合判断为否；继续价值在批量覆盖后尽快取得真实对照结果，不能无限延长无边界数据审计。

## Stage010—014 进一步推进（2026-10-18 00:30 CST）

- Stage010纯状态枚举只0.985秒，不算资金/手数/PnL；1162个full需求与27106个anchor互斥去重。旧主在mandatory平旧后的下一batch移除，峰值22状态，不无限延长到期末。16个fu无真实fill日保留约束、20个terminal未生效；该表是过近似，不等于可行成交集合。独立4个真实边界核对通过。
- Stage011当前checkout四completed族及008共906源测SHA；单次205.6秒构建4646214新增分钟，完整session合格13752，source/旧key冲突均不覆盖。剩余9557项＝215full＋9342anchor：5036项有已绑日线但分钟不齐（54full＋4982anchor），4518项缺94份日线CSV（159full＋4359anchor），3项既有base冲突。16carry约束在4518中，不能作为真实下载目标。
- Stage011新增与A0实际106731读取键交集0，原base/002 SHA未变，可复用A0；独立复审P0/P1=0。完整新键唯一/有序检查不等于全13752session独立重聚合，价格独立样本为8session，完成性继承原completed证据。
- Stage012唯一连接用公开API正常鉴权与10000暖机历史，2合约11session/2475分钟全部有后继完成证据并匹配CSV七字段，parent输入未变，独立复审P0/P1=0。原raw留本地，不自动并入旧overlay或启动C0。
- Stage013拟恢复94精确合约的4502个真实DB日线目标（原4518减16carry），普通TqApi日线公开接口，未将尚未实测的权限/覆盖称为成功。正常openOI字段固定核验，DBcloseOI为N/A；不修改策略OI语义。
- Stage014三处旧冲突分别225/283/1个键，O/openOI相同但H/L/C/V/closeOI有差；旧Stage859 producer未等后继就保存末行的源码证据明确。三冲突与A0实际读键均无交集；A0来源为Stage246 72889、Stage249 33842，Stage859为0，不对其余旧源作无证据泛化，也不重跑基准。
- 本轮金融attempt仍4、完成1、训练0；provider历史流累计2次（007与012），没有C0新attempt。Stage010/011/012资产manifest分别6232d2e15fc8dbe0746e77da3835cb4a8fdfbb4ff14145face7fb5bb760c733b、d7f636d37fa2ba4d9b3331e254a54e529f637111f5ffc517a0cacec13b9cf69c、1813d4cae7b8e3a87b77faa0d95199af4d8c51e841e397389f217c69a4a74ee2；大审计表无损压缩并核原字节，不含原始分钟overlay。未推送、未部署。

## Stage013/015 已有结果与源859边界（2026-10-18 00:49 CST）

- Stage013普通日线接口实际可用，无TqBacktest，94/94快照约251.75秒、峰值489MB；4500/4502目标逐条固定DB六字段匹配并有更大id/更晚时间后继，DBcloseOI仍N/A。fu2605/2026-04-30与fu2609/2026-08-31缺后继按原合同拒绝，原exit1/partial不改写；16carry另列。独立审4500全身份/合法/后继/六字段及4raw样本，P0/P1=0。
- Stage015单次28.79秒，只重验4511session/96合约；1480合格、新452401分钟/56合约。原13752session未重验，23757未受影响readiness行原样继承，base/002/011 SHA不变，新key与A0实际读取交集0，独立P0/P1=0。
- 继承覆盖20191、剩余8077=135full＋7942anchor。这个数字不是所有旧价格重新资格；已确认source859在4个full网格的735键另须处理：cu2010/2020-08-27、fu2205/2022-03-30、AP210/2022-04-06、cu2507/2025-06-11。前两cu在旧冲突表；fu/AP旧ready只说明timestamp齐，未证明盘中H/L。
- 三个session已有同SHA completed源/原CSV七字段匹配替代，AP210当前没有完成替代。Stage016只允许已证据源的具体差异，非859不得覆盖、open/openOI若变拒绝；全部变更而非只新key要与A0实际读取disjoint。Stage017将唯一取回AP210及同窗必要数据，正常BT/公开API，不用多合约价差历史窗口捷径。
- 金融attempt仍4/完成1、模型训练0，累计数据provider连接3（007历史流、012历史流、013普通日线）；没有C0新回放、没有alpha结论、没有生产操作。继续数据修正有实质价值，不按收益改参数；若无合格新数据，不得用fallback或覆盖计数启动候选。
- Stage013/015复现资产manifest分别bd6978434b286eb97d01f2d4147e4be532d612c39b3895e98e94e39a937717e1、35fdb3539716b974395ae29a4022f8a908589b137d9b9ebc1cc58461731cccff；原始日线快照、DB目标价格表、原始分钟overlay均未加入Git。


## Stage016—022 数据与执行准备（2026-10-18）

- Stage017单次30秒无更新即中止的控制流问题已在018独立工具中修正；旧017失败不改。018实际同连接经历2次False后117秒取齐，证明继续等待语义；未改SDK、授权或下载接口。
- Stage019普通latest10000一次45.96秒取得221session/57045分钟，峰值495MB，无TqBacktest。019及018均只有精确来源资格，020逐session完成旧键/范围/独立日线核对后才进入研究stack。
- Stage016的1199实际变更、020的69765新键均与A0实读106731键零交集；020还与016全1500scope零交集。已有A0不重跑。016/020独立receipt分别98b6ad7b3e312e839abb51eefb3377e8e5c7239fbdd44c4ae30df5e9ace2308b、307a41cfdbff3d120b21a59fc216ed161cafe0d6d887332af8cdbcc395ff9271。
- Stage021将普通订单context前的数据资格阻塞在同一个engine调用栈：OPEN完整时段、CLOSE真实首分钟，原context仍一次；浅copy策略minute字典避免污染_GLOBAL/cache别名，finally恢复。full与anchor-only源859资格分离，不以物理existing或scope phantom key自动通过。纯门独立receipt4cb45007591510c34598937fd3dc8e186954031fd5a9115318a8676887133367；未授权真实金融成绩。
- Stage022保持原C0周滤网规则与全部A0参数门，复制真实新runner/旧001/diff，固定stack与已签各层输入，动态数据先独立资格和record再注入，最后verify；每次等待1800秒、整次7200秒。固定stack SHA2b650761fbf2bc30aa0046147b7e369a2a0a10a68ee6b520204dde8d4d7226a0、完整preflight SHA62cbcce2a016fd6881f722769821a7a4c394e55967834e21338de8df1a4fb91a。初次freeze的schema读取失败保留，未重建数据或放宽资格。022/023随后已获独立接合/静态审查通过（P0/P1=0）；C0第三次已在单一独立CLI启动，实际数据仍须逐request独立验收才注入。
- 不再将全部可能CLOSE上界作为开跑硬门，也不在异常后重放bar补缺口；先准备合法响应通路，再只对同一回测真正需要的精确数据阻塞等待，未合格就不推进，不跳订单、不用daily-open替代或截断成绩。
- 数据资产manifest：016 dcdd282a40584fb5f36ae7e3d960dff332f2c20c7d00c8c8d749461af38a1891；018 f1b1da54166beb05b69aedd21754ea579f3ad5a6f1a3cfe9482bc1743d3fddc7；019 b8f6c1dc35a4ae812e166e4d38d071045d0d27ac843e33bd80b6907bcdcf40bf；020 de43d3f6a9e28b79b212a4b78082ff87a92cf2e2b445c79696624b971fb237ba。原始行情、overlay/correction价格CSV、凭证不加入Git。
- 本阶段运行前后过拟合判断为否：只修正已证实来源/控制流并改进必要数据接合，不查看C0胜负选参。继续价值为是：目标仍是同周期更高净收益且更低回撤，不能把取数成功或代码预检当策略优势。

## Stage024 完整首层负结果（2026-10-18 02:04 CST）

- 真实C0_attempt3只运行一次，411.843914秒完整结束，1641日同A；必要精确request只1次，provider18.389015秒。没有以数据观察超时重启金融、截断成绩、日线开盘价fallback或额外训练。
- 原生可开331，周ready273/unknown58；实际拦77（long60/short17），unknown维持原策略。回撤改善5.7581pp，但净利润仅保留49.2425%，收益少714.8667pp，Sharpe下降。胜率35.4582%对A35.5346%，不能靠少交易/省成本证明质量提高。
- 完整经济/执行/参数及动态数据终验P0/P1=0，receipt d06eef3568de0aeeb8ae1ecf736eee46ab0239b851a7b2201570ac1c5f618f93；2项既有P2和继承旧数据资格边界保留。母单胜率基于fills/retry母链，opened计划标签不等同真实成交。
- 此负结果不否定完整三重滤网。下一机制须先冻结『周许可→FI2逆向准备→之后顺势突破』的时间/epoch/过期/真实fill/R/账户资源合同；不能把日首anchor执行换成条件入场后仍称纯gate，也不能回到已失败MACD/FI小参数扫描。
- 前后过拟合：本轮未按PnL调参，但历史研究选择偏差仍在，无严格新OOS主张。继续价值：此形状为否；不同机制的有序设计有条件为是。正式生产资格及基线不由本线变更。

- Stage023精确anchor实际运行元数据登记13资产，manifest2ddd56143477a0f1448caffec294fe506f2fb66c6c7dbd8a40aa62e9051ea390。Stage024负结果登记63资产，manifestef4a9b7a9951ee2af575c5a05dcd2b3f4fa37507570eee4facc97c4e0f6fa800；大JSON/CSV无损gzip并核原字节，实际runner/源diff/账本/归因/独立receipt保留，原始行情及私有配置不入Git。

## Stage025—028有序入场接合（2026-10-18 02:39 CST）

- Stage027纯组件/真实特征构建已独立验收，P0/P1/P2=0/0/0；116394真实日线、112953 FI ready，900 native身份全匹配。唯一builder3.213秒，未重复FI或周cache；13895潜在intent（B13600/C295）及104 unknown候选不含资金、持仓或收益，不能当真实交易或全量下载需求。
- CMT/LEAN/Backtrader机制与本地源码共同确认：真正的周许可→更早逆向准备→之后突破，不能靠原session首open context伪造条件成交，不能用D最终日线/账户值决定D盘中手数。
- Stage028已冻结最小单一执行口径：保留u日native已admitted q/保护止损/名额，过滤后不再分配；D真实trigger才建立layer/order/fill。actual fill风险/保证金可超u预测，不把830 sizing gate说成fill guard，按原门审计；首分钟不能使用pre-entry open作入场后价。同一engine必要数据资格等待复用，普通路径不变。
- 当前实施本线隔离strategy/engine/runner，C_TS真实金融仍待运行，B_TS后续独立机制仍在范围。金融累计仍5attempt/2完成，训练0、生产资格false。目标active，尚无更高收益且更低回撤候选；不因组件完成而缩小目标。
- Stage027已精确登记20项复现资产，manifest `d8525c536bcc6a2c87d6b9fd1196f7f5e69c30d25f53c40ad8ff1328da599842`；FI派生值和潜在决策表无损gzip，原始日线/分钟/数据库/私有配置未入Git。原review stage算术笔误在root实际记录中明确13895，不重建数据。
- Stage028隔离策略/引擎/runner已完成并独立接合验收：26项实现行为测试、4个真实native组合场景/10fills，P0/P1/P2=0/0/0；不是金融回测或alpha结论。Dclose新持仓排除入场前整根分钟H/L，同时AM/history/env保留fullD。029只调整原provider四行作用域绑定。21项复现资产manifest `c1c5b57fbb4e61e61220467192e0e529699f51728c6bc32cf91d048230a2472b`。下一步唯一C_TS全周期run内联preflight，独立金融agent已新建等待真实终态；不重复A0或再跑单独大preflight。

## Stage028实际失败与Stage031最小修复（2026-10-18 03:12 CST）

- C_TS attempt1工具67762真实exit1，总477.246799秒，其中252.943968秒等待精确数据。487分钟请求零缺失；完整账户帧在进程退出前未持久化，100条件fill不能替代全账本，全部绩效N/A。前置028复核遗漏了真实827 synthetic usage不含signal identity的producer/consumer契约，旧0P1不覆盖此缺陷。
- 唯一实际OI009补数16.820751秒、full0/anchor1、与A0实读键交集0，delivery SHA09444de4...03fa。029实际证据已登记14项，manifest9e78e4939ccfa4af040f74043b2c03cfd910f441bce9d9dc7cba4e6f886d6a12；原始分钟未入Git。
- 失败证据及030独立失败审查登记17项，manifestb7cdc6f74de1a31838fa8d37e319c910ef4620165c19dba5d3e36018d0c1c137；大证据无损压缩并核原字节。不能从部分证据恢复或借A0补造金融结果。
- 新031 runner绑定真实TradeData信号字段并验证synthetic母OPEN；返回后任何guard/导出前原子保存全部账户帧/capture，原guard通过才seal。后处理失败可仅sealed checkpoint重导出，新目录保留旧失败。真实producer与持久化/恢复3项有限测试通过，26旧suite/FI/行情资格未重复；032仅改4行provider作用域，无新网络。
- 本阶段过拟合判断：新增否，只修导出/持久化、规则不变，历史研究选择风险仍在。继续价值：是，仍需一次可独立验收的完整C_TS金融闭环；绝不把基建完工或部分fill当alpha突破。

## Stage033：完整C_TS负结果（2026-10-18 03:25 CST）

- 新C_TS完整1641日，修复导出后仅必要一次新尝试221.568秒、无新增下载。原raw快照与全部导出经济表一致，独立现金/库存/成本/母链验收，033收据3fbcc1a3...b7ea；C0/A0不重跑、不改成绩。
- C_TS收益340.55%/DD−32.758963%对A0的1408.396667%/−48.789850%，只保留24.1800%净利润；原七门收益、Sharpe、日收盘margin峰失败。停止此固定组合，不根据结果救周/FI/阈值。
- 保留u-close native q/S使100/100条件实际R高于估值，max50x；这是本次固定合同的经济局限，不是风险匹配。原1.10报告口径之外，1.65日收盘峰122.328964%、>100一日，非分钟PIT。原费率佣金0、原滑点78550均完整核验，不能把旧native deployable_pass字段当晋级。
- B_TS独立假说仍在原范围，尚无新金融；先定u-known trigger一致估价且S不改、保留active通用过滤、unknown禁开与19特征旧模型域外推披露，再决定最小实现。没有高收益且低回撤候选，目标active。新增过拟合否、固定C继续价值否、独立B有条件为是。

- Stage031 reviewed delta登记12项，manifest34b317d76886a848e6984e4a90bcbb60d4200063d0387bf9676acb863430eb53，已提交f0c9f1580。Stage033完整负结果登记68项，manifestfa62dd88c3bf7da874e1030ef6aed5310144f63bdeb219c0e1f823a0d7380466；包含自有sealed账户checkpoint、原始导出、独立复算/消费者失败、实际source/协议与中文记录，不含原始行情/私有配置，不推送或部署。

## Stage035/036：独立B源码与真实接合完成（2026-10-18 03:47 CST）

- 用户持续自主目标范围内，B首个金融收益前冻结0333合同：独立周/FI准备信号，unknown禁开，保留原generic filters/OI/AI，u已知T估q/S仍真实u，原allocator后按原gross前缀只缩量最终预算、不补位；这是B新增约束，不冒充原A/C已有。
- 新035 pricing/strategy、036 B自有checkpoint、037四行provider scope；5+4+2新tests通过，独立真实long/short/unknown三场景8fills通过，receipt10c74fc9...d0c P0/P1/P2=0/0/0。没有B金融/模型训练/下载/旧suite重跑，累计仍7attempt/3 accepted。
- 接下来单次B全周期内联preflight，A0/FI/周缓存复用，037仅实际缺口；038独立经济准备已就绪，需真实terminal后才审。B机械接合不代表alpha或晋级；旧C负结果保持，goal active、production_qualified=false。新增过拟合否、继续价值是。

- Stage035执行源码/真实组合26项复现资产manifest e1c03af12704503a67871d0737a9cae4607f85185d55c79546a6fc23ac244807；Stage038收益前审计准备3项manifest3e88255d7c0ea00edbd889f6e66099b02634eb3974b96cec4d8aa1fce773a743。原始行情/私有配置未加入Git，未推送/部署。
