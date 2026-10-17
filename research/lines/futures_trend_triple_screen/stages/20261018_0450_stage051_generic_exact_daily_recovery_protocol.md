# Stage051：通用实际请求日线缺口的有界恢复协议

- line_id：futures_trend_triple_screen；冻结设计时间：2026-10-18T04:50:59.105129+08:00；非alpha突破。当前唯一B attempt1/PID21822/session70433继续，不重启、不延长原1800/7200秒预算。
- 用户已授权必要数据恢复。本工具只受理B现有真实request与实际文件SHA，canonical、fingerprint、日期/网格/kind/active-order关系必须吻合；默认全部requirements或显式选择1—8个真实合约作为日线缺口子集。选中原CSV已存在、013已合格或拒绝的目标一律fail closed，不覆盖既有权利，不生成未来理论需求。
- 数据库固定SHA273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54，非空WAL拒绝，只读immutable SQL按原合约/交易所/d区间/精确日期取唯一六字段。DB.open_interest固定对应provider.open_oi；DB.closeOI=N/A，不允许挑选另一字段救资格。
- 复用013原qualify_daily_snapshot：每个目标真实day、有效完整日级raw、严格递增id及时间的真实后继、固定DB六字段。普通TqApi86400/data_length10000只读快照，其他raw日可保存但不自动资格或注入引擎。
- 正常SDK3.10.2、API/auth/sim源码指纹与013既有preflight完全一致，端点环境覆盖拒绝；凭证只本地读，SDK stdout/stderr/logging DEVNULL，不写原数据、不连接CTP/券商、不报单、不训练。
- 每request只允许network_attempt1、至多1普通TqApi/TqSim连接、1—8单合约订阅；570s soft/600s hard、1.5GB、worker预算及parent kill/wait闭环不变，不自动重试。prepare与run分开，run须明确preflight路径和已审source SHA；既有attempt拒绝重复。
- 输出outputs/stage051_generic_exact_daily_recovery/request_DIGEST/preflight.json、target_manifest.csv及network_attempt1/{raw/EXCHANGE/NATIVE.csv,qualified_daily.csv,target_qualification.csv,symbol_receipts.json,worker_receipt.json,parent_receipt.json}。本工具不签独立review、不写terminal_observed、不写engine response；root真实工具exit0后另签stage051_provider_actual_tool_terminal_v1，独立052再逐actual目标复算。
- 新增/修改/删除策略参数及金融结果0；权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。有限scope/DB6/完成后继测试RED→GREEN，禁止旧suite与金融重跑。
- 开始过拟合判断：否，只补冻结候选实际缺口，不看PnL调参或扩大权利。继续价值：是，复用通用一次恢复，避免每个新缺合约另造硬编码副本；终止证据以真实provider+独立资格为准。production_qualified=false。
