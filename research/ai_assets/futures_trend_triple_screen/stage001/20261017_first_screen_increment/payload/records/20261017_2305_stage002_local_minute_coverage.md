# Stage002 既有完整分钟数据批量覆盖与对照路径等价

- line_id：futures_trend_triple_screen；记录时间：2026-10-17 23:05 CST。
- 工作区：本机原checkout；分支codex/ai-training-data-expansion；没有worktree。
- 性质：离线研究数据覆盖与复现治理；不是alpha突破，不是正式生产资格。
- 触发：C0首次严格回放缺rb2010、2020-05-18交易日的前夜21:00开盘分钟。过滤改变账户后会产生旧A没有使用的新路径，不能用旧账户已有分钟覆盖推定候选也完整。

## 外部调研与判断

继续沿用Stage001已保存的Elder、LEAN ForceIndex及Backtrader多周期资料。原始结构要求明确数据完成与可见时点；分钟缺口不能靠日线高低点估算成交。原Stage491 producer保存的是`klines.iloc[-2]`已完成分钟，Stage448目标日为零量forming快照，后者不作为替代源。优先复用旧A input_manifest已有且SHA相同的本机完整源，比扩大下载范围更直接。

## 变更与合同

- 新增`stage002_local_minute_overlay.py`及限定合同测试；只处理134份旧SHA匹配的Stage491 completed CSV，135,604,532字节。
- 范围2020-01-01—2026-10-14、原正式19品种；按原交易日calendar和session helper归属夜盘，逐session验证完整分钟网格、唯一键、OHLCVOI及日线聚合。
- 有日线CSV时必须匹配旧SHA；16个缺CSV来源只读原A同SHA数据库，按精确symbol/exchange/interval=d/日期查询，不猜符号，openOI保持unknown。独立审查确认这些SQLite来源没有贡献任何新增键；全部新增分钟均由日线CSV七字段复核。
- 原cache不变，重叠冲突整session隔离，只有通过的缺失键写研究overlay。没有下载、训练、正式源码/AI池/风险参数变更。
- 首次数据构建因日线CSV不存在中止，原`build_failure.json`保留；attempt2一次完成。数据构建不算金融回放。原协议字节保留`protocol_used.md`，SQLite澄清在构建后追加并有amendment receipt，时序不回填。
- 研究runner使用临时loader wrapper，拒绝overlay覆盖原键，finally恢复loader和三个缓存；summary、产物、builder、原协议和独立review SHA在preflight中固定。
- 新增数据参数：`--local-minute-overlay`，仅允许冻结的C0_attempt2；新增/修改/删除alpha参数均为0。

## 数据结果和独立复核

- 候选session 4,390；接受3,509，隔离881：425不完整、454日线聚合不匹配、2原cache共同键冲突。
- 新增1,078,530分钟、117合约；实际贡献新键的session 3,369，逐行绑定原source行，日线七字段最大差0。
- 原cache 1,411,116条；原SHA仍为`5c06124fac52ff37a19d1abe89f6f6a80d36b8ece874eb647286377317289189`。新旧键交集0，隔离session贡献新键0。
- 独立构造A0全部535条anchor请求及501条session scan，合计106,731个不同实际读取键：新增交集0，原键缺失0。结合确定性消费者，可接受A0路径等价，无需重复A0金融回放。
- 目标rb2010、2020-05-18交易日345分钟完整；OHLC 3469/3544/3455/3528、volume 1,869,234、OI 1,568,331→1,473,769，与原日线精确一致。
- overlay SHA：`dbe07b09fab834b6695e736af6a14669be9481094b82c059d76ec15eaa2a1e4f`；独立检查SHA：`2c57a48e5d0dd4d44d885af4da87266a3c7b5bc389360bcd31a942d000911e27`。
- 39项本线相关合同测试通过，候选零金融preflight通过；独立review确认consumer接线和恢复、原策略spec/settings逐值等A，strict_minutes=true。

## 金融结果及下一步

本阶段数据构建金融回放0，没有新增期末权益/收益/回撤/Sharpe/滑点/交易数/胜率；原结果不修改、不删除。A0原runner字节快照已核对原provenance SHA，原A0已接受结果沿用。

23:04左右root已按合同启动唯一C0_attempt2。候选终态另记Stage001，未完成前不报告双臂胜负。若批量覆盖后再次缺分钟，停止逐缺口重跑，先生成全部潜在信号的session覆盖清单。数据验收仅证明这些本地session及A0不受影响，不能声称所有新策略路径都有分钟。

## 反思与归档

- 运行前及运行后过拟合判断：本阶段没有新增按收益选参；以来源/网格/日线一致性接受数据，失败和冲突保留。历史策略和重复使用旧样本本身的选择风险仍在，不能称消除过拟合。
- 继续价值：有。真实数据覆盖是后续任何入场结构改变都会需要的基础；通过A0实际读集合证明避免重复账户回放，符合用户控制研究时间的要求。
- 本阶段只更新本线；不改用户脏registry、根memory/back_log或生产。保存精简manifest、独立检查和源码；原始分钟overlay不提交Git。
