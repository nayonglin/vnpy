# Stage015：账户边际development完整标签批量生产

## 阶段信息

- 预注册时间：2026-09-01 18:30 CST
- 是否重要突破版本：否；Stage012 `PASS_WITH_P2`与Stage014标签前合同后的开发标签生产
- 当前线上：m0005 `ai_top10_plus_fu_official_live_v1`，生产HEAD `d492ee072...`
- 规则：15万元、当前Stage847-C9/Stage037、正式成本/保证金/整数手/相关性/最多4持仓
- 本阶段运行历史回测但不训练模型、不生成holdout标签、不连接CTP、不调用订单API、不修改生产目录

## 冻结任务

- 月份：Stage014 development首39个月，`2022-04-29 -> 2025-06-30`；每月标签期为下一正式eval date。
- 主任务：39月 × rank10..18 = 351个；每隔12个月增加rank10 A2确定性哨兵，共4个；总计355个独立冷进程。
- 每个candidate只替换目标月正式rank10这一行；Top9、固定fu和其他月份逐字段不变。
- 两个并发worker，每个进程强制单线程、独立`TMPDIR/MPLCONFIGDIR`，不复用策略checkpoint。
- 已完成job只允许凭共同campaign identity和输出SHA断点续跑；不得按部分标签值跳过或新增任务。

## 身份与审计门

1. campaign合同包含m0005 release、生产代码、vnpy/vnpy_portfoliostrategy、解释器/包/启动钩子、冻结数据库、全量分钟K、映射、合约元数据、产品全集、Stage009/012/013/014、review、runner/预注册、jobs和全部351份eligibility。
2. campaign开始/结束完整文件合同一致；每worker关键输入运行前后哈希一致，生产HEAD/工作树和active release一致。
3. 355个PID、job级独立临时目录、`checkpoint_reused=false`，单臂<=600秒。
4. 四个A2哨兵的标签、目标期curve/trades/entry_candidates/entry_risk/trade_events与对应A逐值一致。
5. 每月九臂决策日前curve/trades/三类诊断归一化SHA一致；四臂归一化runtime SHA在全campaign唯一。
6. curve与summary的`window_label`统一为真实起止日，不消费旧展示字段作为边界。
7. 为每个candidate生成账户标签差额对账：期末权益差=目标期每日净PnL差；收益差=权益差/共同基准权益；滑点和交易数差与逐日合计一致。误差均<=`1e-9`。
8. 保存目标期紧凑curve、combined、trades、entry candidates、entry risk和trade events；不保存全周期大诊断副本。

## 结果使用边界

- 完成后只允许把351行development标签交给已经冻结的Stage014九特征、双XGBRegressor、单一参数组。
- 禁止查看结果后改特征、树参数、月份、rank、收益/回撤权重或C门；若development失败直接停止该形状。
- sealed holdout 12个月标签本阶段不存在，只有development严格PIT通过且模型/规则哈希冻结后才允许另立一次性生成与评估阶段。

## 过拟合与继续价值（运行前）

- 是否过拟合：否。39个月完整九rank网格，不按未来活动或部分结果裁剪；特征、模型参数、臂和holdout已先冻结。风险仍高，因为development OOS仅约15个月，必须严格fail-closed。
- 是否值得继续：是。Stage012只证明一月可识别，Stage015首次提供能训练且不污染holdout的账户级真实标签面板。

## 启动前审查修订（2026-09-01 19:10 CST，仍未生成Stage015标签）

- 首次`prepare-only` campaign `campaign_20260901T185107+0800_70838`在生产模块导入时被QMT runtime guard拒绝，发生在campaign identity和任何回测之前；已标记`abandoned_before_identity_and_backtest`，job完成数和标签文件数均为0。
- 独立代码首审为`P0=0 / P1=5 / P2=3`，禁止启动；修复600秒父进程timeout、campaign/job文件锁与retry独立临时目录、worker完整执行输入前后重哈希、精确development/holdout/next-eval合同、payload日期语义、固定完成输出及三路对账后，二审为`P0=0 / P1=0`。
- 完整批次前冻结一次受控smoke，只运行同一campaign中的四个正式任务：`20220429_R10`、`20220429_R10_A2`、`20220531_R10`、`20220531_R12`。它们不是额外标签，也不改变355任务网格，PASS后按共同campaign identity和输出SHA作为已完成job续跑。
- smoke只验收：A/A所有目标期文件逐值一致；活跃月五类决策前payload一致；entry candidate目标期非空且`signal_date`无缺失并等于当前eval；curve、combined、trade行数三路对账；完整执行输入前后身份；runtime、PID、TMP/MPL隔离与600秒timeout；不发布`development_labels.csv`，不按四个部分标签值改任务、特征、模型或门槛。
- 完整355批次必须读取`stage015_smoke_pass_allow_full_development_batch` receipt；缺失或失败直接拒绝启动。
- 19:17增量复审发现smoke receipt若只信`passed/decision`可跨campaign复制绕过；启动前已修复为receipt绑定当前`campaign_id`、campaign file contract、固定四个job及各自worker receipt/输出SHA。完整批次启动时必须重新读取当前四个输出并复算全部smoke gates，不信任外部复制的PASS字段。
- 20:42原campaign在`20230630_R14`按`1e-9`金额门fail-stop；七项curve/combined/trades对账均为0，只有约528万元账户权益的两条float累计路径产生`-1.3969838619232178e-09`（约1-2 ULP）。原campaign永久废弃且133个输出禁止复用。20:45后新runner只在金额一致性比较前将end/base/net分别量化到`Decimal('0.000001')`元，标签原值、公式、阈值及其他七项门不变；真实三值回归测试先红后绿。新campaign必须重新prepare、smoke、独立review并从0运行355任务。
- 数值修复独立评审为`PASS / P0=0 / P1=0 / P2=1 / ALLOW_NEW_CAMPAIGN`；唯一P2已在新campaign前关闭：回归测试同时证明原R14 ULP差被归零，而真实增加`0.000001`元会保留为`1e-6`并继续超过原`1e-9`门。Stage015专项12个、整线80个测试全部通过。
