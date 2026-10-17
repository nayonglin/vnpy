# Stage045：实际单请求离线数据解析器合同

- line_id：`futures_trend_triple_screen`；2026-10-18 04:15 CST；不是策略突破。由独立数据审者著作算法，root另审本实现，038仍另审最终全部金融/数据链。本文件与源码在首次实际输出前定稿，其后immutable；扩展须另版本。
- 入口仅接受同一B等待目录已存在的request绝对路径、实际文件SHA、原request_fingerprint与canonical digest。首版只支持一个实际requirement、physical existing0、missing等于全部required；multi/非空旧键/partial scope严格blocked，不能冒称已完整支持。
- CLI：`--request ABS --request-file-sha256 SHA`，可选成对 `--reviewer037-path ABS --reviewer037-sha256 SHA`、`--reviewer041-path ABS --reviewer041-sha256 SHA`。默认固定046/043准确SHA；显式覆盖必须由044的root allowlist校验，045只核对文件SHA并返回，不执行reader。原037、041 provider路径/SHA固定，不接受新provider自动发现。
- 严格按冻结037相同优先级选择原CSV与013approved；保留013全部rejected和原exit1事实。已有原CSV但目标无已完成合法资格时blocked，不以新日线覆盖。只有确实没有原CSV且未approved/rejected时，才从已绑定013/040 raw独立资格当前准确一日：精确DB六值、真实更大id/更晚合法后继、完整七值、DB.open_interest=provider.open_oi、DB.closeOI=N/A。raw天然其余日期不自动取得资格。
- 无已绑定raw、raw无目标/无真实后继或DB无精确日线，返回needs_daily_raw，由root保留缺项；不自动网络下载。重复/六值冲突blocked。数据库只查当前准确一行，继承已接受DB身份，不重复全DB哈希。
- 本地只读002/011既已签source manifest里当前准确symbol的来源，先校验原SHA，再只解析当前请求所需canonical范围。该范围非法值、重复或来源价格冲突blocked；每个新增分钟要真实源后继的同symbol、唯一更大bar_id、合法OHLCV/OI与至少后移一分钟。full_session仍须完整grid与所有后继、整日七值匹配已资格日线，不加新阈值。
- 本地anchor仅核验grid[:1]这一个key的合法七值、源间无冲突、same-symbol真实后继、daily open及可用openOI匹配；不要求未请求时段、全日HLCV或尾OI聚合，明确full_session_qualified=false，只授anchor1。实际所需分钟或完成性缺失才needs_provider；所需范围冲突或daily匹配失败blocked，不能换一次下载掩盖冲突。
- 本地通过则独立Stage021 receipt及真实_read_delivery解析；A0实际read keys交集必须0，保存全日后继证据、交付权利与请求范围existing0。真实021最终仍执行原逐旧键七值完全一致及原子append保护；不载入引擎或大base cache。
- 真缺分钟时：没有新daily收据选固定037+046；新增精确daily非空子集选固定041+043，并返回已签daily receipt路径/SHA。首版packet_count=1。provider/reader均由044再次对root allowlist全等检查，未绑定reader不准返回可运行provider。
- 每actualrequest独立唯一目录；decision/audit和产物保存后只读复用，重新核对绑定输入，禁止覆盖。成功JSON末行：status=accepted及request_sha256/receipt_path/SHA；缺分钟：status=needs_provider及request_sha256/packet_count/provider_path/SHA/reviewer_path/SHA（041多daily_review_path/SHA）；缺日线raw：status=needs_daily_raw及精确原因。上述状态exit0，不能处理/冲突为blocked且非0。044只有accepted/完整provider终态验收后才可能发布response；045不写engine pointer。
- 本入口从不运行provider/引擎/金融/网络/模型/订单，不新增日期/品种/收益筛选；策略参数与金融结果改动0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A。
- 开始与结束过拟合判断：否，只验冻结B当前真实数据需求，不收益选样或调参。继续价值：是，减少每请求手工副本与等待，但缺项和冲突必须可见；不是策略有效或promotion。
- 调研判断：复用已接受039/042的准确raw/DB/后继与011/021/037资格合同，不外网泛搜或重跑旧suite/1590来源；公开资料不能替代精确原始数据。
