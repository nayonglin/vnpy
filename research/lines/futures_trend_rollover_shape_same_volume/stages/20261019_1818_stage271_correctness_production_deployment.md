# Stage271：正确性修复与15:10自动交易生产部署（进行中）

- 研究线：`futures_trend_rollover_shape_same_volume`
- 用户授权：2026-10-19明确选择“同时完成资格验证并启用自动交易生产任务”；不是只读邮件升级。
- 本记录在发布闭环完成前不代表生产已激活。当前真实状态：旧邮件服务仍工作，canonical七任务未加载。
- 是否重要突破：属于实盘工程正确性和部署治理修复，不是alpha突破。
- 开始/当前反思：不过拟合。保留C9/15万、Stage037、Top10+fu、0.5R和既有信号规则；只修会计、成交时序、依赖、实际数据及调度一致性。值得继续，真实预演发现了仅单元测试不能覆盖的生产阻塞。

## 已完成证据

1. 原m0011候选`6b607203a41a47b1255ac1328dde2dc489bb487c`，可信资格59套、1743项、失败/跳过0；两次生产CTP只读采集成功，order/send/cancel=0/0/0。资格在私有生产state的`stage271-candidate-qualification-m0011/`。这仅证明原候选，不证明后续新字节已资格。
2. 生产候选环境原sklearn1.6.1无法执行现有1.8.0模型，真实predict_proba报错。已将main `.py311`精确匹配既有Stage249/邮件环境：numpy2.4.4、pandas2.3.3、scikit-learn1.8.0；pip check通过，真实双行预测通过。CTP库未更换。
3. 独立克隆、独立SQLite快照及数据目录，禁止网络/邮件/订单运行严格Stage901，窗口2026-07-23至10-19。08原匹配runtime和09新候选runtime结果一致：权益159197，收益6.131333%，最大回撤-12.976628%，Sharpe0.884481，总滑点2868，成交32，非零日胜率44.444444%；该值不是逐笔胜率。持仓、信号、pending均0。
4. 只真实补回fu2611.SHFE自然日2026-09-17 21:00一根平仓anchor；逐字段保持1411116条旧行情不变，新增1/删除0/旧值变更0。16条分钟扫描、19条anchor请求全部完整。未泛称全市场分钟完整。
5. 独立agent审查08/09的每日PnL、权益、回撤、滑点、32成交、五件套cohort/hash及唯一分钟patch通过。09与08两份RSI审计CSV最大浮点差1.42e-14，经济决策字段无变化，不声称所有CSV字节一致。

## 新版最小改动与真实阻塞

- 15:10不只改plist：947→909/935/929的日期边界必须一致；945交易会话默认16:30及原交易闸保留。postclose-report为watchdog，移到15:30；18:20重试保留。
- 15:12纯账户只读不能依赖被15:10流水线改写的信号receipt。保留owner/stable/release/activation/代码资格/凭证闸，只解除不相关的信号数据前置；不放松真实下单的新鲜度要求。
- 929账户快照缺失、陈旧、年龄未知须明确告警并隐藏旧资金数字；未知不能折算0秒，也不能暗示“无需交易”。
- 新增19个既有Static18+fu品种目标日主力映射、唯一当日日K、有限正价格/非负量仓、OHLC一致性检查；18/19不得因max日期已到就签receipt。8项独立helper测试先红后绿；真实SQLite worker接线回归也先红后绿。
- 现有pairwise模型和特征summary确实决定并发排序/手数，却不在原281项物料中，需原字节补冻并只从新活动payload运行，不能回退mutable BT。
- 模型joblib按物料合同必须Git LFS；本机缺git-lfs，原publisher对含LFS的正式晋升明确拒绝。正在验证官方工具及真实远端上传/下载能力，不能改后缀或用普通Git绕过。

## 参数与结果变更

- 新增策略参数：无；删除策略参数：无；修改alpha/risk参数：无。
- 新增工程参数/行为：15:10目标日期口径、15:30watchdog、严格19品种日K门、未知账户年龄保持未知、固定兼容运行依赖、pairwise不可变绑定。
- 历史回测结果不覆盖；本次预演为部署数据/行为验收，非参数优选。

## 尚需完成

1. 完成pairwise物料/源码接线与独立复审，冻结新的不可变release，不能覆盖m0011。
2. 精确新release可信资格、正式activate/promote-master、remote fresh clone审计。
3. 最终stable精确promoted SHA重新生产资格、manifest/activation receipt、Stage948原子准备与激活。
4. 把已核验的运行数据、静态依赖与唯一真实分钟带入正式运行目录，生成同版本当日receipt；7/7任务/冲突0及Stage946验证后再认定启用。
5. 正式链路成功接管后退役旧local.fian.mail任务，避免旧源码重复邮件；保留恢复备份。

证据目录：`../outputs/stage271_deploy_correctness/`。本记录将以最终实际结果更新。

## 2026-10-19 19:09 CST 继续部署检查

- 用户已授权新建公开独立物料仓库。`nayonglin/vnpy-official-materials` 已建立，初始提交 `c663df3c8dad19e9a7e28bd1fc20b9e7f03e60bb`；模型真实 LFS 上传、公开文件下载和独立空缓存 Git LFS smudge 均通过，2865 字节 SHA256 `ba982708a476be74e30ed966883d1eae8ef52010bf8df3763a83d6fc5c719d66`，模型未训练。
- GitHub HTTPS batch 端点连接超时，同仓库 SSH 认证后 HTTPS 对象传输已实际通过；发布器受限端点改为已验证的同一仓库 SSH 路由，完成针对回归和独立评审后再冻结。
- 已把经验证的13项真实静态/行情文件和截至10月19日数据库带入固定候选生产路径，旧数据备份在私有 `stage271-data-before-upgrade`。不安装测试心跳或伪造执行证据。
- 仍未创建新 release、晋升 master 或激活7项生产任务；旧邮件链路保留至正式链路成功接管。旧候选资格不能替代新源码的完整验收。
- 过拟合判断：否，本次不改变alpha、AI池或风险参数，只修复依赖、数据、记账与生产时序。继续价值：是，必须以新物料和实际生产闸门闭环结束。

## 2026-10-19 19:12 CST m0012冻结

- 18项已审源码提交 `7e13664e09128a478863318e297349450295bcd3`；独立提交前P0/P1/P2=0；发布器完整106项测试通过，额外时序/日线/报告82项通过。
- 新物料 `m0012_20261019T191034+0800_7e13664e0912`，release commit `d55887e1def72629fbfa310e439dc3a879969a14`，288文件，manifest SHA `6dab79f90b7e4580141d4bdef10707050f513ba87c72d1ba1734831ea264e312`，material tree `e9cd0086b4c2261ffbe6483f2f2635e60ce53844039111771990bc8ddb6e20b2`。
- prepare已实际完成绑定source/tool/config的模型LFS上传和独立空缓存下载，非仅沿用三字段网络预证据。
- 稳定路径已在无生产任务、clean前提下切到候选release精确HEAD，等待新候选独立review报告后跑61suite可信资格。CURRENT仍旧m0008，不宣称新版本已激活。

## 2026-10-19 19:23 CST 本轮资格结果及真实外部阻塞

- m0012候选可信runner实际执行61项suite、1805 tests，failed=0/skipped=0；但完整生产资格**失败**，不能把测试通过冒称实盘资格通过。
- 失败为 `release_builder_production_readonly_raw_capture_invalid`。实际Stage907 refresh被阻断，Stage174 `readonly_logs_without_ctp_progress`，broker_query_bundle.complete=false，账户/持仓/委托/成交/合约均未开始新代查询。正式TD/MD两端口TCP实测均ConnectionRefusedError；当前前置没有接受连接，尚不能断言具体开放时刻。
- 原始只读JSON/查询证据已留在私有state `stage271-m0012-readonly-blocker`；不复制账户原始数据到研究/Git。三项order/send/cancel API均0。
- 此前已通过的m0011/16点只读记录不能替代本轮d558的新证据。未activate物料、未promote源码master、未加载7项生产任务；source master仍e41a0a01d53b7256001e45e686acad53667ef7bf。正式稳定checkout在clean的m0012候选d558，CURRENT仍m0008，不能认作已生产启用。
- SMTP辅助脚本经独立复审并以纯临时fixture修复目录fsync失败回滚缺口后，已实际执行备份和两份生产env仅两个开关变更：enabled=true/dry_run=false，其余配置一致、权限600、未连接SMTP或发信；旧mail服务未退役，避免正式链路尚未接管时中断现有通知。
- 后续必须待正式前置恢复后，以新的外部输出目录完整重跑可信qualification，不复用本轮测试直接手拼资格；通过后才执行material activate/promote、最终promoted SHA再资格、manifest/receipt、Stage948、当日precompute receipt和7/7闭环。现有activate_qualified_material.py固定读取失败目录，需要在重试后显式绑定新的真实成功bundle再执行，不能误用。
- 公共资料旁证：券商公开说明CTP可能在结算/非开放时段关闭（https://futures.pingan.com/service/question/1740709268219.shtml）；这不是本账户前置的具体时间承诺，恢复只认实际TCP和正式只读证据。
- 过拟合：否；本次未调整alpha、AI池、0.5R等策略风险参数。继续价值：是；代码/物料/数据/邮件准备已完成，但生产启用仍被真实CTP资格证据阻断。
