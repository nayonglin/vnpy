# 正式信号账户边际效用XGBoost线

- line_id：`futures_trend_xgboost_formal_signal_marginal_utility`
- 创建时间：2026-09-05 07:13 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 资产/策略：商品期货趋势 / 当前正式逻辑回归选品 + C9/15万入场事件的XGBoost二级过滤
- 当前状态：Stage001唯一执行已于2026-09-05 16:22 CST在A1模块导入阶段技术失败并闭线，authorization、claim和campaign均已消费，禁止重跑。失败为`sensitive_operation_forbidden:subprocess`，只有`subprocess_spawn_count=1`，其余标签、fit、predict、候选策略、holdout、网络、CTP、账户、订单和生产写入计数均为0。只读最小诊断精确定位首个触发链为`Stage901 -> Stage513 -> matplotlib.font_manager -> fc-list --help`；预置临时字体缓存后还会触发正式材料resolver的`git cat-file -e`，证明问题是生产模块导入图与“worker零子进程”合同不兼容，不能靠单点放行修复。本线未产生事件资格、标签、模型或回测结果，不进入Stage002，也不触发reviewer。
- 线上材料身份：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 线上执行身份：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / 15万元

## 为什么另立本线

- `futures_trend_signal_quality_ai` 已证明旧的静态桶特征不能稳定区分好坏交易；不能把评分器换成XGBoost后重复同一实验。
- `futures_trend_ai_xgboost_ensemble` 已证明月度rank10替换的九特征/账户边际标签族不能同时改善收益和回撤；不能继续调树参数、阈值或年份。
- `futures_trend_xgboost_pit_directional_continuation_utility` 已因月度动作日无法稳定产生正式方向而闭线；本线不再要求月末预知未来交易方向。
- 本线把研究对象改成正式C9已经在决策时点产生方向并批准的模型排名层`flat_entry`根入场事件。逻辑回归继续决定月度品种池，XGBoost只研究是否跳过一个已存在的正式入场事件。
- 固定`fu.SHFE`是发布卫星，不是逻辑回归模型排名行；其正式路径始终保持A，不进入本线样本、训练或未来skip动作。

## 核心假设

- 少量正式根入场可能在当时账户状态与市场状态的非线性交互下同时损害后续收益和回撤。
- 对每个根入场事件，比较正式接受路径A与仅屏蔽该根事件的反事实路径S；根事件引发的0.5R止损和一次重试属于同一事件生命周期。
- 后续固定训练形状为两个浅树回归头：预测接受该事件的账户收益边际和最大回撤边际。只有两头都预测“接受有害”时，未来C臂才允许跳过；阈值固定为0，不扫描。
- 历史数据只用于开发和机制反证。`2026-09-05`之后按真实时间首次产生的事件才属于前向OOS；历史结果无论多好都不允许直接晋级正式版。

## 固定决策时点特征

以下12项只允许来自正式候选快照和当月正式AI池，在完成日线后、报单前可复现：

1. `formal_rank_percentile`
2. `formal_score_margin_to_cutoff`
3. `directional_rsi`
4. `directional_ma_gap`
5. `directional_ma_slope`
6. `open_interest_change_pct`
7. `stop_distance_pct`
8. `portfolio_drawdown_pct`
9. `margin_to_equity_before`
10. `active_positions_fraction`
11. `same_direction_correlation`
12. `loss_streak`

禁止根据标签选择、删除、变换或增加特征；禁止加入未来价格、未来成交、最终盈亏、MFE、MAE、退出原因和事后账户状态。

## 阶段边界

- Stage001：唯一执行已在A1模块导入阶段技术失败闭线；没有开始正式基准回放，没有生成根事件或特征资格产物，禁止同线重跑。
- Stage002：仅在Stage001全部硬门通过并经独立复核后，预注册单事件屏蔽器与双目标账户反事实标签；不得在预注册前读取标签值。
- Stage003：仅在标签批次和独立复核通过后，进行固定浅树、purged expanding walk-forward开发验证。
- Stage004：历史开发通过也只允许启动前向shadow；至少积累9个自然月且60个闭合根事件后才能评估。
- Stage005：只有前向OOS同时改善收益、最大回撤、Sharpe、成本和跨阶段稳定性，才讨论正式A/C真引擎与接入；任何阶段失败即关闭对应形状。

## 生产隔离

- 不修改`/Users/bytedance/Desktop/person/vnpy_production_live`。
- 不连接CTP，不读取券商账户，不调用订单API，不修改launchd、邮件、正式AI池或生产材料。
- 父进程claim前只以直接文件、Git元数据、`os.uname()`和Python运行时属性冻结输入身份；禁止生产模块导入、网络和任何子进程。
- A1/A2由`.py311/bin/python -I -S -B`经标准库bootstrap进入macOS `sandbox-exec` deny-default策略：不继承任意父环境，不执行site或`.pth`启动钩子；bootstrap在任何第三方/生产导入及capability消费前核对父进程一次性密钥，并以worker目录外真实写探针证明OS拒写。sandbox只读全部输入，只允许写各自worker目录，网络全部关闭且禁止worker派生子进程；Python guard额外覆盖`subprocess`与`os`全部进程入口，并拦截敏感模块、fit/predict、CTP/账户/订单及越界写入并记账。
- 唯一执行的claim与序号1基准event在同一状态目录中一次原子发布；空、claim-only、event-only、截断event或完整pre-rename staging都只允许恢复为技术失败，不允许重放。执行状态目录是不变的线程/进程锁锚点；锁锚点路径/inode及当前claim在每次event追加前必须重新核对，claim缺失、替换、bytes/payload、nonce/lease、authorization SHA或输入合同漂移均fail-close。每个worker必须在任何输出和生产导入前消费与固定claim、注册该capability的不可变event条目、nonce/lease、worker、bootstrap/runner、解释器、环境、sandbox及全部路径/SHA绑定的一次性capability；completed/failed只能保持同终态，禁止终态反转和final/failed并存。
- failed bundle使用完整nonce/lease命名的可恢复staging；成功final同时保存原始worker回执、已消费capability、严格portable回执、完整输入manifest和发布前execution event。首次发布在原子rename前后、attempt cleanup后及写sequence=7前分别重验当前authorization/精确bound files和1410项输入/runtime/正式身份；恢复清理后复用同一完成原语再次执行强校验。所有event更新由不随event原子替换而变化的claim文件锁串行化；成功完成只允许完整publishing event CAS到唯一sequence=7，精确completed状态只读幂等，不能由旧内存对象、竞态写入或内部自洽但语义错误的回执晋级成功。
- 正式相关性快照之外独立枚举当时真实同向持仓并重算候选/同向品种收益样本、有效相关性数量及最大值；候选历史不足、任一同向持仓不可测或原快照与独立trace不一致均fail-close，不能再把unknown当成零同向仓位。
- 所有锁内event更新都以已加锁状态目录fd执行相对读取、临时文件创建、无覆盖提交和fsync；writer不得重建状态目录。序号1基准event及每个后续条目均不可变，后续文件名携带序号和前一条原始bytes SHA；相同前态的竞争writer争用同一目标名，只有一个`linkat`成功，其他writer因`EEXIST`失败，不允许覆盖。读取端必须从基准沿连续唯一哈希链解析到末端；目录路径/inode、claim原始bytes、当前event原始bytes和当前条目名在提交紧前及提交后再次核对。所有代码、测试、记录和产物只写本研究线；任何未来生产动作必须重新走实盘SOP和独立授权门。

## 过拟合与继续价值

- 当前过拟合风险：高。历史区间已被多条研究线反复观察，动态LR根事件预计只是百余量级，对树模型属于小样本。
- 控制：先标签前冻结对象、特征、双目标、0阈值与前向起点；历史只作开发反证，真正结论依赖新增前向事件。
- 继续价值：本线已停止。总目标仍有条件继续，但必须另立新线，先做不进入正式回放的纯导入零子进程预检，并用版本绑定字体缓存与无进程Git对象校验消除已证实的基础设施假阴性；不得放宽安全门。常规修复与失败诊断不拉reviewer，只有后续真实回测跑出同时改善收益与回撤且通过基础稳健性门的候选版本才拉独立reviewer。
