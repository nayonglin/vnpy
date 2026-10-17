# Stage002 既有完整分钟源的批量研究覆盖合同

- line_id：futures_trend_triple_screen；时间2026-10-17 22:50 CST。
- 性质：数据读取覆盖，不改Stage001候选定义，不下载、不改原数据或模型，不是新的alpha试验。
- 原因：Stage001 C0首次严格回放在rb2010、2020-05-18中止，原cache缺前一交易日May15 21:00开盘anchor。没有C0完整收益，不能把数据缺口当滤网失败。
- 已验事实：Stage491原文件SHA在旧A_final3输入manifest中；目标345分钟完整、重复/非法0，OHLCV和首尾OI与对应日线7字段完全一致。Stage448同日零量forming快照不用于真实盘中路径。源producer明确保存klines.iloc[-2]完成K线。

## 固定数据范围与规则

1. 一次处理本机tqsdk_stage491_covered_key_full_session_backfill的134个completed CSV（共135.6MB），逐个要求路径与SHA匹配旧A_final3 input_manifest。无追加网搜文件，不以候选PnL挑日期。
2. 复用既有真实交易日calendar与盘中session函数，将夜盘按前一源交易日映射；每个合约×交易日验证完整预期分钟网格、唯一键、有限合法OHLC/量仓和对应日线聚合。日线开盘OI有值才做该项核验，缺失保持unknown，不编造；核心OHLCV/closeOI须一致。仅处理2020-01-01—2026-10-14研究范围和正式19品种。
3. 原Stage861 cache（SHA5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189）全部键和值原样保留。源session与base存在交集时核对共同OHLCVOI，出现实质冲突则整session隔离，不自动覆盖或按收益选源。
4. 输出只含可验收session的新增分钟键，附逐源SHA、交易日/时段、原行号/来源、接受/隔离原因、日线交叉与完整度。partial/forming/冲突不硬补。一次输出overlay.csv与manifest，原cache不改写。
5. 用A0_attempt2已记录的全部execution_anchor_requests与minute_scan_requests证明新增keys不落入其实际读取范围；同时原cache无新增/删除/修改。独立审查接受路径等价后不重跑A0。如果不能证明等价，先明确原因，不静默把旧A当新数据基线。

## 研究loader与重试

新研究runner仅用临时wrapper在原loader结果中加入冻结overlay；finally恢复。不改正式模块或公开数据cache路径，source与consumer SHA均记账。A0/C0共同数据合同明确为base＋只补未消费的已验收本地键；A0已有读取路径等价是证明，不冒称重新运行。

保留原C0失败目录，下一次仅允许C0_attempt2；周状态CSV、MACD参数、初始入场门、AI、风险、费用、退出/retry/换月完全不变。仍要求严格分钟完整，任何后续缺口不得乐观回退。如果一次批量覆盖后仍中止，停止逐个缺口重跑，改做全潜在信号session覆盖清单后再决定；不能给未完成路径收益或回撤。

## 验证、记录和判断

- 有意义测试：旧键不会被覆盖；重叠冲突整session拒绝；不完整/重复/非法/日线不匹配拒绝；夜盘交易日归属；A0读取集合不相交证明；loader恢复。
- 只运行一次批量overlay构建，候选账户最多再启动一次。独立agent审核数据来源/时间/合并/控制等价与C0结果，避免反复全量周特征或主库QA。
- 新增alpha参数无、修改/删除无；金融结果目前仅A0已完成，C0尚未验收，不能报告双臂胜负。
- 过拟合判断：否，本轮根据既有source证据补齐真实数据覆盖，不根据收益选择分钟价格；部分来源/已见历史选择风险仍保留。继续价值：是，解决的是所有后续入场迭代都会遇到的基础读取覆盖，而不是修饰某个版本收益。


## 2026-10-17 22:59 CST 日线交叉来源澄清与实际执行时序

134个已接受Stage491分钟源中，16个精确合约的旧日线CSV在本机不存在。仅这些缺CSV源改用原baseline SQLite数据库（SHA273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54），以symbol、exchange、interval=d及2020—2026研究日期精确只读查询对应日线；核验OHLCV和closeOI，openOI保持unknown。CSV存在时仍优先要求旧SHA及七字段核验；数据库也无对应bar时继续隔离，不猜别名、不填值。

首数据构建因AP005日线CSV不存在停止，失败目录原位保留。根代理的明确来源澄清到达时，加入上述精确只读交叉的attempt2已经完整结束；因此保存本次真实使用的协议字节于outputs/stage002_local_minute_overlay/attempt2/protocol_used.md（SHAa28e249309a762ec4be10930ead9ef8b38ddef6e6124366aeeeceddb01a564c8），本追加没有倒签为运行前原文，也没有为文字澄清重建数据。只有一份接受的overlay，未新增金融账户回放；alpha定义与周参数不变。
