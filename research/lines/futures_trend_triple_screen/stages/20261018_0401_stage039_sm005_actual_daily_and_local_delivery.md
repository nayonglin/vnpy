# Stage039：SM005 实际请求日线与本地完整分钟独立签收

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 04:01 CST。
- 本阶段不是重要策略突破版本；只签收实际请求数据，不产生策略金融结果。
- 独立 reviewer：`ordered_execution_review`。040 provider 由另一 agent 实现，root 已通过真实工具 terminal 确认 exit 0 后明确授权签收。此前冻结的035独立审查资产不变。

## 结论与精确权利

接受实际 request `53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae` 中唯一 `SM005.CZCE / 2020-01-06 / full_session`，共225分钟。P0/P1/P2=`0/0/0`；置信度高，但只覆盖本请求数据完整性、来源、因果完成与解析合同，不能证明收益或全量分钟质量。

独立交付收据：`outputs/stage039_independent_delivery/request_53e251e1034a04c76c81f26838eec78388484bf2c14742953fb9efecfce040ae/delivery_receipt.json`，SHA=`de75f009e2d6858089f03b72544bf5754d59440e54b837f78c3faaf5a5254a78`。真实 Stage021 `_read_delivery` 已实际解析通过：rows225、full_keys225、anchor_keys0。reviewer 不写 engine response；由 root 读取此收据并发布原子响应，同一等待引擎继续。

## 040 日线核验

- 真实 terminal：session54177、exit0、elapsed9.048秒、all_inputs_unchanged=true、1个普通日线连接、0个分钟网络连接。terminal_observed SHA=`e13d4b523b507bc7267bbcac0d2cd7ccf7e08798c961c90405e372d1efbd55e0`。
- 工具040 SHA=`32ddecd055d7bb52b8d7f68ab8f1c5d3023ce0943f47045620b254d4e09cc820`；preflight SHA=`ae032b5c8ad1ac1e9efa1a51c6af3f1ec0e537bcf47411853327547b1c824b9a`。所有 parent 声明输出均重新核对 SHA。
- 独立读取040原始快照，唯一目标日实际 source_id157、source_ns1578240000000000000，真实合法后继 id158/ns1578326400000000000，即2020-01-07日线。没有用推算时间伪造完成。
- 一次只读精确 DB 查询，以准确合约 `SM005/CZCE/d/2020-01-06` 核验：O6378、H6380、L6262、C6280、V76307、openOI68372，六字段差均0；连续 `SM.CZCE` 不可替代。
- 历史 importer 的 DB.open_interest 对应 provider.open_oi；DB.closeOI 明确为 `N/A_not_independently_available`。收盘 OI61153由 SDK 原始已完成日线提供，不谎称 DB 独立核验。
- 不重算全 DB SHA；继承040已绑定的数据库身份与真实父进程输入未改证明，再独立查询本次一行。原始快照其余日期不因本次签收自动取得资格。
- 日线独立收据 SHA=`f169294e85e86e1d185d97f2f63017f07ec211e92606903293e71ad96d2b56ec`；六字段、真实后继及继承边界见同目录 `daily_checks.json`。

## 本地225分钟与旧键保护

- 使用已冻结 Stage002/011 来源：stage491 的 `CZCE/SM005_completed_minute_backtest.csv`，source_id `s491_052`，13050行、1275839字节；SHA=`391899b58a6d58265fc02629e99622e16f6877dd84299800e1e0214373aa32b8`。其来源 manifest SHA=`318da737a0a9e041919fbe6687669de3bf3aadacdbf191232b11ec43c6feb1ed`；与当前B preflight 的已接受输入记录逐项相符。
- 仅资格225个 canonical grid：09:00—10:14、10:30—11:29、13:30—14:59，无重复、缺失或非法OHLCV/OI。沿用真实011全日资格方法及全部七字段日聚合：6378/6380/6262/6280/76307/68372/61153，全部一致。不会把“已有225行”等同“已取得资格”。
- 每一行另验真实源下一行：same-symbol、合法七值、更大唯一bar_id、timestamp至少后移一分钟。首行35325→35326，尾行35549→35550，尾行真实后继为2020-01-07 09:00。225条后继逐行保存在 `completion_evidence.csv`；SHA=`36e9604603eede401e75711637b8c46148fc2492a2d11d0bca80abd0816fdceb`。
- A0实际535条anchor、501条scan展开为106731个读取键；新增225键与之交集0，原A0字节不变。没有重跑A0或读取金融结果。
- 本请求 `existing_source_timestamps=[]` 只表示 required范围内物理旧键为0；不是宣称全局没有旧数据。故本次225均为新增物理键，其余日期不动。只读子审另行确认真实021先对全部overlap做七值 `np.array_equal`，拒绝冲突，仅拼接不存在键，全部验证后一次提交updates；本次仍由实际gate执行该保护。未重载巨大base cache或重审1590个来源。
- 交付CSV仅包含本请求225行与原gate九列，SHA=`fe79c2063c4cdbf612ea044bda273dfd333577c118ae4109c57bc202a92d043c`。

## 实际执行、限制与反思

实际命令使用 `.py311/bin/python` 执行 `outputs/stage039_independent_delivery/review_local_delivery.py --request <上述实际request绝对路径>`；真实 exit0、耗时0.649秒。脚本SHA=`695eaa41b5b8e7b45b5d0677ecc7e33d6727a0199669628d24b11cb7d7e727bb`。最后复核所有实际使用的绑定输入仍未改，解析结果文件SHA=`6260d46cd2cb4a08f5164198173ec712a242bfb51310d5679e0cb070a5253a4b`。本阶段无新增通用suite、无模型、无金融回放、无网络、无订单，无原始CSV/DB写入。

041分钟provider仅保留未启用草稿，未调用、未联网、未取得代码独立审查或交付权利。039工具允许未来已有真实请求按显式路径再审当前已绑定SM005 raw，但每次必须创建独立新目录、重新检查该日精确DB和后继；不会扫未请求日期、扩大品种范围或自动签收。非空旧键范围当前严格拒绝，需另绑原值。现在已签收目录保持不可变。

调研与判断：本阶段按root限定沿用仓库已接受013/011/021算法及真实原始证据，未作外网或GitHub泛搜；新增网络资料无法替代精确本地请求、DB与后继验证，故不扩大调研范围。

- 参数新增/修改/删除：0/0/0；回测结果新增/修改/删除：0/0/0。
- 期末权益、总收益、最大回撤、Sharpe、滑点、交易数、胜率：N/A，本阶段没有金融运行。
- 开始与结束过拟合判断：否，只补冻结B当前实际下单需求的数据，不按收益选日期、调整参数或救参。
- 开始与结束继续价值判断：是，当前最小证据足以让原引擎按公平分钟执行继续；不意味着策略有效、promotion或下一请求自动通过。
- TODO：root按已签收据原子发布response；实际B完整终态后由038另做账户独立审计。本阶段不启动新金融attempt。
