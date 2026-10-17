# Stage028 C_TS第一次完整单遍回测运行记录

- line_id：futures_trend_triple_screen；记录2026-10-18T02:51:59.424805+08:00。
- 真实启动时间：2026-10-18 02:50:55.673737+08:00；PID 15292；工具session 67762；来源HEAD 4d120ef42f018ed1b672e4fd67b60fec5adeb62f。本轮唯一CLI --run内联preflight，未另跑一次大preflight。
- 当前状态：真实进程仍运行，已通过内联参数/缓存/模型读取身份预检，尚无完整金融成绩。A0_attempt2复用，不重复回放；C0负结果不变。
- 固定2020-01-01—2026-10-14、150000、历史AI资格严格signal-day prior eval、原佣金滑点、0.5R ON及一次retry。新增研究规则为周许可→更早FI2准备→C9新信号→次交易日真实分钟突破；native u手数q/保护S固定，未触发无持仓且不重分名额。actualR/margin可超u预测，原830不是fill-time gate；收盘持仓H/L只用入场以后分钟，AM/history/env仍fullD。无新增/修改/删除正式参数。
- 开跑前代码独立复核P0/P1/P2=0/0/0，4真实native组合场景通过；只有真正需要的数据才Stage021同engine阻塞等待，029只对实际请求补数并外部独立验收。不能把观察超时当进程终态或自动重启。
- 是否重要突破：当前未知，尚无金融结果。期末权益、总收益、最大回撤、Sharpe、滑点、成交次数、胜率均待完整终态及独立金融复核，禁止用部分路径报成绩。累计金融attempt6、完成仍2，模型训练0，新增provider连接0，production_qualified=false。
- 调研判断：原始三重滤网与Backtrader/GitHub条件单实现提供机制/执行参考；本地实际信号及账户决定能否改善，经典名称不作为alpha证据。
- 开始过拟合判断：本轮新增否，规则/成本/执行口径在收益前固定，不扫参数；已有历史选择风险继续存在。继续价值：是，条件入场首次真实经济证据尚缺，完整结果会决定该固定C_TS形状是否继续。结束判断待终态，目标保持active。

## 已确认终态（2026-10-18T03:04:01.467357+08:00）

- 工具67762返回terminal exit1，error=ValueError('execution_clock_identity_unmapped:signal_datetime')。引擎已返回、captured_bar_failures为空、487分钟请求零缺失；总耗时477.246799秒，其中实际数据等待252.943967833秒。没有完整summary/daily/trades/positions，不接受任何绩效数字；金融累计6attempt/2 accepted。
- 真实唯一provider session3259 terminal exit0，16.820751209秒，OI009.CZCE/2020-07-15 CLOSE anchor1根。独立delivery SHA09444de4ec525a874b5f03caacfe0742836c3a4f8b4d6ba0aec0eea69d1303fa；full权利0、anchor1、A0实读交集0。同一engine等待后恢复，未重播bar。
- 独立金融失败复审为P0/P1/P2=0/1/0，完整原始账户checkpoint缺失；代码review亦确认synthetic usage schema假设的P1。旧前置review未覆盖该缺陷；保留全部旧证据，不能把100条件fill当完整账本或用A0填补。
- 这次不是alpha负结果，更不是收益突破，所有金融指标N/A。新031只修导出身份/先保存完整账户证据；策略/引擎原SHA与规则不变，必要新attempt显式计数，已有分钟复用。后处理若再失败将能只重导出。
- 结束过拟合判断：本轮没有新增收益选择，未获得可信PnL，不改规则救参；历史选择风险继续存在。继续价值：是，当前失败只定位导出契约，仍需一个可独立核验的完整C_TS账户结果。目标active。
