# Stage052：实际请求普通日线新来源接合合同

- line_id：`futures_trend_triple_screen`；2026-10-18 04:50 CST；不是策略突破。新工具/输出，不改已消费045/047/048或任何策略、模型、金融、LINE、registry。本agent实现052，root另审源码，038继续审完整金融/数据链。
- 当前实际等待：SM009.CZCE/2020-04-15/full_session225；digest=`2359178d438e2191ff3691ebb97a82f41be5c81f8fa3ecd279e5b0a631e9093a`，request文件SHA=`c48f52d6eb6bf8356c5d31762971a958233613d9baa6458c55a309e8e6341b3f`，existing0/missing225。原B同PID21822保持等待，不重启。
- 主流程复制冻结047最终SHA=`84f9ca450ec8854a3ae75d64f2eb152f0fb396d1ff1c2232cfe223084801b950`，仍固定45 SHA=`597551c51a021f763318086e4e3084bd5a54aa03abb8d4b038f63d131f8d02df`。1—8实际requirements、R/E/M、new=R-E、A0只new、整required签收、旧值委托固定021 exact compare/全symbols commit前保护全部不变；两provider仍由固定048最终3b220...785a独立reader接合。
- 原CSV/013已资格优先，原rejected保留。新增recover_daily先调用45原算法，只有真实无绑定raw或绑定raw没有目标日才允许051；若原raw中目标日有非法/未资格实值，或已有目标但缺真实后继，或精确DB缺失/六值冲突，一律保留拒绝，不用新来源救。
- 051普通日线由独立agent另实现并由root另审；固定051源码SHA后才允许052引用。051按实际request唯一目录 `outputs/stage051_generic_exact_daily_recovery/request_DIGEST/`，最多一次正常普通日线API连接，没有分钟网络。本工具从不发起051或其他provider。当前request的051根如存在则优先且严格只验该根，残缺/失败不能借旧根掩盖；否则仅在051既有root真exit0终态根中找同精确symbol，raw SHA不同拒绝，相同可去重并记录全部来源根。
- 只可消费root真实工具观察之后写入的terminal_observed：schema stage051_provider_actual_tool_terminal_v1、terminal_observed=true、exit/parent_exit0、all_inputs_unchanged=true、同一actual request digest、准确051 source/preflight/parent路径和SHA、1个provider且1个daily连接；真实parent再核worker exit0/status worker_terminal，普通日线worker确认TqBacktest0/单连接。若terminal另带worker_exit/parent_status/minute连接数则必须一致（0/worker_terminal/0）。052不能自签root真实终态，不以文件出现推断真实terminal。
- 同时绑定真parent0/worker0、未超预算/未retry/输入未改、preflight及target_manifest/symbol_receipts/raw SHA。终态/manifest/declared资格按各snapshot原origin request验证，051原target只能是其origin实际requirements非空subset；逐原target独立比对raw七值/真实id和time后继与declared proof，保存origin来源。不要求provider曾资格本次新day；symbol原始路径必须与manifest一致，不自动发现未审source。
- 每一个本次实际新target仍独立解析普通raw：准确日唯一合法七值、合法更大id/更晚时间真实后继、再次只读查询准确DB一行六字段并与本次raw匹配；原origin日则与其冻结manifest六值和raw/proof核对。DB.open_interest=provider.open_oi；DB.closeOI=N/A，收盘OI只能来自已完成raw。checks区分origin已资格日与newly-qualified实际日；snapshot其他raw日不自动qualified，不重算全DB/整1590来源资格。
- 新daily receipt仍是整个actual request内缺原批准日线的非空subset，CSV/audit/checks={'targets':...}与041/048完全兼容。分钟本地完整性、anchor只1权利、full225七值、价格冲突blocked、真实后继、actualGate旧键保护均沿047/045，不加阈值。
- CLI及JSON与047一致；root审源后实际main由现有044调用。缺root terminal、缺051target或新source不匹配均blocked；没有分钟交付前不签整request receipt，不写engine pointer。首次实际输出后052/协议及所有进入指纹的文件immutable。
- 只做1—2项新来源结构/缺真实终态拒绝的有限fixture与compile；不重跑旧suite、不金融/联网/模型/订单。参数与金融结果改动0，权益/收益/DD/Sharpe/滑点/交易/胜率=N/A。
- 开始/结束过拟合判断：否，只补实际冻结候选当前请求，不收益选日、品种或调参。继续价值：是，补明确的普通日线来源缺口；不证明收益或promotion。调研沿040/013/047既有实证合同，不外网泛搜替代本地准确raw/DB/后继证明。
