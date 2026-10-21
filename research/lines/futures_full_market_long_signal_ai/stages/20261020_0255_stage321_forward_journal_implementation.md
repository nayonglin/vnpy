# Stage321：前瞻时钟与本地不可静默改写记录

- line_id futures_full_market_long_signal_ai；2026-10-20 02:55 CST；非重要突破，0fit/cash/SQL/行情/大表，未创建T0或receiver。
- 实施319/318的321部分，只有一个新clock/journal测试组（多子例）；先缺模块RED，再实现GREEN。补充同key原object删除不能被幂等调用静默复建的回归例，先实见失败再修GREEN；最终1方法0.005秒，无旧suite。两次RED与最终源绑定见[fixture](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage321_forward_journal/implementation/fixture_terminal.json)。

## 实现与验证

evaluate_clock严格带时区：u完成>T0与及时决策分开，未知/冻结前/收到时尚未完成/输入晚于Dopen/封存晚于Dopen均保留原因，不用自然日代替夜盘交易日。它只核给定时间关系，**不证明传入源时钟或session日历来自真实权威来源**；clock_provenance_certified始终false。

ForwardJournal只用标准库：同一policy身份一目录，canonical JSON对象内容hash、小索引序号/prev链、append文件锁/fsync；recorded_at由本机当前UTC写入。相同key/内容幂等保留原首次时间；不同内容须新版本key，旧对象删除/损坏不能静默补；NaN拒绝，缺失由上游明确转null并保留missing flags/状态。entries完整核对象，append只核小索引和当前对象，不每次hash所有旧对象。修订可指向旧entry，不覆写决定。

测试覆盖冻结前晚取、T0相等、未知时钟、夜盘UTC等价、late input/decision、时区缺失与反向封存；幂等/修订/身份冲突/缺失object/损坏object及断尾index。没有模拟任何真实市场收益。哈希是本地重现与改写检测，非外部签发的发布时间证明。

接口冻结：evaluate_clock(*,frozen_at,source_completed_at,received_at,decision_sealed_at,D_open_at)->dict；ForwardJournal(path,policy_identity).append(kind,payload,*,key)->receipt；entries()->含payload的完整记录。新状态与clock分类不授予真实交易资格。

source {'path': '/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage321_forward_journal.py', 'bytes': 8441, 'sha256': 'b687c3d6ae8f78dee30a05094c09fb0da3d5c9daa4e12d7132262c3ee052e003'}

test {'path': '/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage321_forward_journal.py', 'bytes': 5453, 'sha256': '3331e6f13c6e21fb43f94783a0021f27be9ad8c7244ec4236ff4c344fca22de4'}

## 外部判断及反思

318及root复核[sklearn官方](https://scikit-learn.org/stable/common_pitfalls.html)与[维护者GitHub](https://github.com/freqtrade/freqtrade/blob/develop/docs/lookahead-analysis.md)：预处理须固定、未来不影响过去；此处据此保留缺失/可用时钟，不把测试通过当alpha。原模型历史择题风险仍在，本实现未寻优；继续接最少因果生成/连续状态有价值，避免对旧样本继续加特征。期末权益/收益/DD/Sharpe/费滑/交易/胜率N/A；原参数0修改，生产与forward均未启动，待323独立静审。
