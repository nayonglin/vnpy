# AI选品XGBoost PIT全曲线与账户边际标签线

## 研究线身份

- `line_id`：`futures_trend_xgboost_pit_curve_account_labels`
- 创建时间：2026-09-02 13:55 CST
- 当前状态：Stage001-005技术门通过；Stage006完成唯一一次冻结双XGBRanker development OOS运行，技术门通过但效果门`2/9`，收益与回撤边际均为负，独立review确认`FAIL_STOP_NO_TRUE_ENGINE_NO_HOLDOUT`。当前8特征、双Ranker和严格双头selector形状关闭，不得二次运行、调参救援或读取holdout
- 线上基准：`m0005_20260901T165450+0800_1961d98ccb2b` / `ai_top10_plus_fu_official_live_v1`
- 研究目标：在严格PIT上市资格和条件PIT逻辑回归A排序上，以逐合约全曲线、持仓量和成交量描述量提供独立信息，并最终用正式15万元账户的候选边际收益与回撤标签训练XGBoost，追求全周期收益提高、最大回撤下降。
- 隔离边界：不修改生产checkout、正式release、CTP、订单、邮件或launchd；数据覆盖失败时不补值、不删月、不降门；只有真实策略回测产生结果后才追加根目录`back_log.md`并触发独立reviewer。

## 为什么另立本线

- `futures_trend_ai_pit_scorer_rebuild`已反证旧108项策略损益特征、二分类标签和固定融合形状；继续扫树参数属于结果后救援。
- `futures_trend_xgboost_pit_market_context_after_listing`已反证六项同合约历史收益上下文与组内未来利润等级标签；模型虽充分分裂，但收益和市场路径回撤代理同时变差。
- `futures_trend_ai_xgboost_ensemble` Stage015曾构造正式账户边际标签，但它绑定旧的历史候选池和九项旧特征，不能直接证明严格PIT候选池上的结果。
- `futures_trend_rebuilt_c9_15w_optimization` Stage073已反证“front/next期限结构顺风阈值过滤”。本线禁止复活该过滤器、阈值或方向规则；差异只允许是无阈值的全曲线原始描述量、干净候选集和账户边际目标。

## 第一性原理判断

- 排名目标最终是账户组合，而不是单品种未来收益。候选加入后可能因相关性、保证金、整数手和最多4持仓改变账户路径，因此标签必须来自同一正式账户口径的边际重放。
- XGBoost只有在输入信息与旧逻辑回归显著不同、且标签与账户目标一致时才有继续价值。模型复杂度本身不是alpha。
- 期限结构反映库存与便利收益，OI和成交量分布反映合约链上的资金集中与迁移；这些是商品期货特有、同日可观测的信息，但经济含义不等于必然可交易，必须先过PIT覆盖再过OOS账户效果门。

## Stage001标签前覆盖合同

- 冻结A排序输入：`research/lines/futures_trend_xgboost_pit_market_context_after_listing/artifacts/stage001_market_context_coverage/ranked_a_panel.csv`，SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`。
- 冻结逐合约源：`.vntrader/database.db`，SHA256=`7e2633909f73d77c3b0b044199418d7c1ed2989afde480596aefbb18a83b724a`；只读`dbbardata`中`interval='d'`且`datetime=eval_date`的普通合约行。
- 普通合约必须能映射到当月候选产品，交割年月可从3位或4位合约码在`eval_date`下唯一恢复；拒绝连续/指数/主力伪合约、非法月份、非正价格、非正持仓量和非正成交量。
- 每个A面板行必须在同一`eval_date`至少有3个合格合约；不得向前或向后填充。全部797行、47个月和18个品种必须覆盖。
- 每行合约到期月份必须严格递增，前两合约月份间隔大于0；合约明细不得重复，特征日期不得晚于`eval_date`，未来标签读取数必须为0。
- 通过只授权Stage002冻结原始曲线/OI/成交量特征；不授权标签回测、模型训练或效果评估。
- 任一门失败，决策固定为`stage001_curve_coverage_fail_stop_no_labels`；禁止补0、删月、删品种、放宽合约数、使用最近日或按结果救援。

## 后续预设边界

- 特征不得包含未来收益、账户标签、交易回放结果或旧sealed holdout。
- 特征设计只允许少量、经济含义固定的连续量，不做carry正负阈值、分位阈值、年份/品种方向或窗口扫描。
- 账户标签适配必须先独立审计生产身份、候选替换语义、任务数、A/A哨兵和冷进程隔离；双门通过前不运行真实标签任务。
- 最终模型仍采用按月严格时间切分；训练标签必须在测试月前成熟。候选只有同时改善账户收益与回撤才允许进入真实全周期A/B/C。

## Stage001结果

- 决策：`stage001_curve_coverage_pass_ready_for_feature_preregistration`，12/12技术门通过。
- 797行、47月、18品种全部按`feature_date=eval_date`精确覆盖；合格逐合约快照7,615行，每行合约数最少/中位/最多=`4/10/12`。
- 209条非正价格/OI/成交量合约按统一规则机械拒绝，未造成缺口；非法交割码、交割月重复、PIT违规、同日错配、fallback、未来标签读取均为0。
- 双跑逐值一致，数据库只读；测试`6 passed`。本结果只授权特征预注册，不授权标签回测或模型训练。

## Stage002特征合同

- 样本固定为每月rank10及以后，预期47月/374行；rank10是A锚点，后续排名是挑战者。
- 模型特征固定8项：逻辑回归概率差、rank距离，以及相对rank10的近远月年化basis、全曲线年化backwardation斜率、曲线拟合RMSE、OI HHI、成交量HHI、OI加权期限。
- 禁止carry方向/分位/month-gap阈值、品种/年份、历史策略收益、账户结果和任何标签派生字段。
- Stage002只验证有限性、非退化、rank10精确0和双跑确定性；不读取标签、不训练、不回测。

## Stage002结果

- 决策：`stage002_curve_features_pass_ready_for_account_label_contract`，13/13技术门通过。
- 797行原始描述量；候选矩阵374行/47月，其中锚点47、挑战者327；8项特征全部有限，rank10逐位精确0。
- 六项曲线差值在挑战者上均327个唯一值、327行非零，并覆盖8/8 folds；概率差保留1个真实并列，不做抖动。
- 标签读取、阈值特征、训练、回测、CTP和订单均为0；全线测试`10 passed`。通过只表示可进入账户标签合同，不表示效果有效。

## Stage003账户标签路径合同与结果

- 47个月按时间连续切为前35月开发、后12月账户标签封存；374行全部保留，开发266行、封存108行。
- 每个目标任务先把首个干净月至目标月的全部Top10覆写为当前A排序，再只允许目标月rank10替换为挑战者；固定`fu.SHFE` rank11、正式历史和目标月以后行必须不变。
- 266个主任务加4个A/A哨兵共270个任务；哨兵索引固定`(0,11,23,34)`，固定smoke为`20220128_R10/R10_A2`与`20220228_R10/R11`。
- 结构门`20/20`通过；266个资格SHA双跑一致，rank10与A/A资格SHA相同，挑战者只改变目标月rank10一行。
- 决策`stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight`：磁盘、生产HEAD/CURRENT/release均通过，但旧冻结运行时已不存在，新隔离研究数据库尚未冻结。
- Stage003未读取标签值、未训练、未回测；下一步只授权新运行时身份审计和固定4任务smoke。

## Stage004新运行时与固定smoke结果

- 生产数据库经APFS clone冻结到`/private/tmp/vnpy-stage004-curve-account-runtime`；源/目标SHA256均为`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，inode不同，`1,020,397`条日线，运行前后均未改变。
- 成功campaign `campaign_20260902T153215+0800_55582`重新冷启动完成固定4任务；4个PID/TMPDIR/MPLCONFIGDIR均唯一，最大wall `59.294921208s`，无checkpoint/result复用。
- `20220128_R10/R10_A2`八类输出逐字节一致；`20220228_R10/R11`五类决策前payload SHA一致，边界均为14行且signal全非空。
- R11相对R10未来净利润`+120,910`、收益`+2.5507046pp`、最大回撤改善`+1.3925030pp`、滑点`+3,420`、交易`+2`。这只证明标签可辨识，不代表挑战者、XGBoost或完整策略有效。
- smoke门`16/16`通过，决策`stage004_runtime_smoke_pass_allow_development_label_batch_preregistration`；sealed holdout标签、模型训练、CTP连接和订单API调用均为0。
- 独立review结论`ALLOW_STAGE005_PREREG_ONLY`，`P0=0/P1=0/P2=2/P3=1`。Stage005必须用新orchestrator修复父进程环境/恢复留痕，持久化可复算predecision证据和显式零计数，并冻结货币量化顺序；修复和预运行评审前不得启动开发批次。

## Stage005A v2运行身份修复结果

- 当前生产数据库更新后，重建`/private/tmp/vnpy-stage005-curve-account-runtime-v2`，冻结数据库源/运行库、主力映射、全量分钟数据和合约元数据；数据库SHA256=`db3342006f4220767f06e466bb40c046f372961cea41cef9a6d8bc1727fa0c4b`。
- 两个失败campaign均已`ABANDONED/reuse_forbidden`；第二个partial明确定位为worker wrapper覆盖job级TMP/MPL，未换任务、样本或策略参数。
- 修复后的最后一个新campaign `campaign_20260902T192840+0800_77391`完整完成固定4任务；PID/TMP/MPL `4/4/4`唯一、无结果复用，A/A八类输出一致，16/16门通过。
- 202202 R11相对R10仍为未来净利润`+120,910`、收益`+2.5507046pp`、回撤改善`+1.3925030pp`；只证明标签可辨识，不是XGBoost效果。
- execution scope中holdout/model/CTP/order及意外命令/产物计数全为0；生产checkout保持clean，HEAD `d492ee072aa5a9d71477235d79f17d2a5db59db3`。
- post-run review结论`allow_stage005_migration_to_v2_and_batch_prereview_only`，`P0/P1/P2/P3=0/0/0/0`。下一步只能把Stage005完整绑定到v2及本次成功证据，再做独立批量前review；没有结构化批量授权前不得创建或运行270任务campaign。

## Stage005完整development标签结果

- 唯一授权campaign `campaign_20260902T214308+0800_13888`在同一attempt内完成`266 main + 4 A2 = 270/270`个独立冷进程任务，开发月份`35/35`，最大worker wall `85.2773285s`。
- 发布`development_labels.csv` 266行，SHA256=`b4e5f7f638298ff1bd572b378ae096345273488df67c5b5386ba776deec3798d`；reconciliation 266行，最大绝对误差`0.0`。
- 4个A2七类输出逐字节一致；35月共175个决策前原始文件精确；270个PID/TMP/MPL唯一，checkpoint/result复用均0。
- holdout、模型训练/产物、CTP、订单和意外命令/产物计数均为0；生产checkout、冻结runtime和campaign输入身份运行前后不变。
- 决策`stage005_development_account_labels_complete_allow_stage006_training_preregistration`只表示标签数据集技术通过。266个主任务是互斥反事实，不发布期末权益、总收益、组合最大回撤、Sharpe、总滑点、总交易次数或胜率，也不代表XGBoost已提高收益或降低回撤。
- 独立运行后review结论`ALLOW_STAGE006_TRAINING_PREREGISTRATION_ONLY`，`P0/P1/P2/P3=0/0/0/1`；唯一P3是review时registry状态滞后，现已同步关闭。当前只允许Stage006训练方案预注册和独立预审，不授权实现、训练或读取sealed holdout。

## Stage006首次预审阻断与修复

- 冻结规格为8项PIT全曲线/集中度差值、双`XGBRanker(rank:ndcg)`、17折扩展PIT OOS、A逻辑回归rank10、B双头月内average percentile等权、C两头原始分数均严格胜rank10才替换第10席。
- 首次独立预审`P0/P1/P2/P3=0/0/3/0`并阻断实现；问题是测试标签阶段未机器化、关键数据/selector/scope规则只在Markdown、`mean` pair缺少平台/二进制身份。
- 修订后改为266个main job JSON逐月后开：前18月115行先开放，17个测试月151行必须逐折先完成模型/预测/选择SHA和fsync seal再开放；holdout预测及标签全0。
- 机器合同现显式冻结有限值/变换禁令、rank/qid/mergesort、average percentile、17月zero-fill、34主+34重复模型、manifest和命令/scope计数。
- runtime冻结Darwin/arm64、Python可执行文件及`libxgboost.dylib` SHA，训练前/模型后/效果后必须一致；当前只允许修订后独立复审，复审放行也只授权TDD实现，不授权训练。

## Stage006冻结Development OOS结果

- 实现后首次独立评审发现可替换授权路径、可替换Ranker工厂和seal未重算实际payload三个阻断，严重度`P0/P1/P2/P3=0/2/1/0`；修复后专项`30 passed`、整线`87 passed`，第二轮复审`0/0/0/0`并签发唯一授权。
- 唯一冻结运行完成17折、151条OOS预测、34个主模型、34个重复模型哈希和68次fit；重复预测最大差`0.0`，模型字节、实际estimator/参数、PIT、三点runtime/input/auth和17个pre-effect seal全部通过。
- 标签访问精确为前18月115行先开、17个测试月151行逐折seal后开；seal前测试标签、aggregate CSV数据行、同折训练/预处理/调参/选择/tie-break和全部holdout访问均为0。
- C在8/17月替换rank10，覆盖2023与2024，但双目标同时为正仅`1/8=0.125`。`sum_return_delta=-0.10596712219705573`、`sum_drawdown_improvement=-0.029383673739694305`，两年分项和两项leave-best-out均为负。
- 九个效果门仅替换月数和替换年份2门通过，其余7门失败；决策`stage006_dual_ranker_development_oos_fail_stop_no_true_engine_no_holdout`。
- post-run独立review复算64项manifest工件、授权消费、技术/标签/scope和九个效果门完全一致，结论`CONFIRM_STAGE006_FAIL_STOP_NO_TRUE_ENGINE_NO_HOLDOUT`、`P0/P1/P2/P3=0/0/0/0`。
- 本阶段不是完整组合资金曲线，不发布期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数或交易胜率；上述delta仅是月度互斥账户标签差求和。
- 当前形状关闭：禁止二次运行、参数/月份/品种/selector/门槛救援、true-engine、holdout和正式接入。若未来继续XGBoost，必须另立独立经济信息与新假设，不能把本结果作为调参反馈。

## 外部调研与判断

- Gorton、Hayashi、Rouwenhorst从库存理论说明商品期货期限结构与风险溢价有关，并给出近远月basis的年化定义：<https://www.nber.org/papers/w13249>。
- Erb、Harvey说明商品配置效果高度依赖期限结构和权重方式，历史结果不能自动外推：<https://www.nber.org/papers/w11222>。
- XGBoost官方Learning to Rank要求同一月份候选用`qid`分组，模型优化组内次序而不是把月份样本当独立分类：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- 我的判断：该方向仍有研究价值，但由于Stage073已看过同源front/next结果，过拟合风险高于全新数据源；只有无阈值全曲线特征与直接账户标签的双重结构变化能证明它不是旧失败路线的参数救援。

## 当前反思

- 是否过拟合：Stage001-006单次冻结流程本身**否**，因为任务、样本、标签、模型、selector、金额量化和硬门均事前冻结，Stage006只运行一次且失败后未修改规格；但17个OOS月和8次替换样本偏少，现在按结果删月、删品种、改参数或阈值将构成明确过拟合。
- 是否值得继续：**当前8特征、双Ranker与严格双头selector形状否**。技术门全过而收益、回撤、分年、leave-best-out和联合命中率同时失败，继续救参的信息价值低。若未来继续XGBoost，只能来自独立新信息机制和全新预注册研究线，不得读取本线holdout或运行true-engine。
