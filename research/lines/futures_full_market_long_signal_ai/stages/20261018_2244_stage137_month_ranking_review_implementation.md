# Stage137 条件月份排序增量独立审查器实施

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：固定134协议下的增量独立审查实施；尚未收到137实际审查授权，未读取135/136新成绩，未执行实审。
- 记录时间：2026-10-18 22:44 CST。
- 工作区：`/Users/mac/Desktop/fian`；不创建分支或worktree，不修改其他研究线、LINE、registry或旧脚本。
- 阶段性质：工程与有限新边界验证，不是新策略或金融回测。
- 是否重要突破：否。
- 是否触发A/B：否；固定版本纯归因，不形成正式候选。

## 外部调研与判断

- 查阅[Python JSON官方说明](https://docs.python.org/3/library/json.html)及[NumPy官方GitHub分位数实现](https://github.com/numpy/numpy/blob/main/numpy/lib/_function_base_impl.py)。前者明确排序键、UTF-8相关选项及紧凑分隔符；后者用于核对固定bootstrap统计的分位数口径。
- 判断：规范化hash只保证选月规则可重建，不证明随机种子独立或策略有效；原252源日块、2000固定indices只对20条既定路径作条件推断，不包含完整策略搜索或Monte Carlo不确定性。有限20seed排名只能描述，不能作为p值。

## 本次变更

- 新增 `tools/stage137_month_ranking_review.py`，增量范围为135选月、完整父表delta重建、精确标签归因，以及136新84本账户、诊断和比较。
- 新增 `tools/test_stage137_month_ranking_review.py`，8个有限合成边界；仅其中1个验证作者136新桥的纯API，使用合成NativeBars，不读取真实缓存。
- 复用最终132的compare、rejection_equivalence、review_capped_budgets、account_native_and_capacity、restore_native_cache；复用独立102现金账本与诊断纯函数。不调用132总入口，不重新复审129源标签、130六模型或131旧B4。
- CASH_HELPER、ACTIVE_POSITIONS与cash.review_budgets由上下文管理器设置并恢复；每本账户通过后单独持久checkpoint，只有精确同身份才可显式resume。关键科学/资金不一致抛错并保留失败终态；非关键展示差异集中披露。
- 新增参数仅为exact CLI：134/135/136三个manifest及SHA、accepted132缓存manifest及SHA、137源bundle SHA、独立输出目录；可附root授权路径。`--resume`只恢复本137已通过checkpoint，不放宽身份或重新查询原库。
- 修改/删除旧参数和旧结果：无。

## 验证与结果

- 执行 `.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage137_month_ranking_review.py -v`：8项全部通过，0.063秒；另py_compile及CLI help均exit0。
- 边界覆盖：正分S与不含scope/cost的固定随机键；精确分数抵消共同未知；family-u后equal-u；父表原顺序/selected0状态及selected提案更新；不删除坏seed或epsilon修log；现金上下文异常恢复；CSV数字/布尔/null语义；136桥对合成NativeBars有效/无效行和直接数组引用。
- 初始夹具装载报错和缺实现RED、父表selected提案未更新RED均发生于有限测试阶段，已修正并GREEN；没有真实数据审查启动或回测重跑。
- 未运行旧资格suite，遵守本次限定增量范围。
- 本agent新增SQL=0、模型fit=0、实际现金账户=0、下载=0、整库重hash=0；没有137实审结果。135/136实际执行和研究总计由root合入记录，本阶段不据其成绩作结论。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率：均不适用，尚未审查新现金数据。

## 结论与后续

- 已具备待root精确授权的一次增量审查入口；待135和136完整manifest/terminal确定后，只审查新增结果。旧133 unsupported及不加注/不晋级边界保持。
- 是否进入下一步：等待root exact绑定授权，再按固定范围审查，不自行读取新成绩或启动。
- 本阶段仅保留此唯一stage；实审完成后在本文件追加实际审查证据，不修改LINE/registry，由root合入。

## 过拟合与继续价值反思

- 开始新增选参过拟合：否。目标、S/E定义、20seed、84账户、原bootstrap和风险口径均已收益前冻结；审查不改变策略或按成绩筛样本。
- 结束新增选参过拟合：否。8项夹具验证语义与资金检查连接，不评价真实收益；历史多次择题与条件推断局限仍存在。
- 开始/结束继续价值：是。增量独审能够检查AI正分池内排序与动作扩张的归因，以及新控制账户的自身资金路径。它本身不能证明稳定advantage、可加注或生产资格。

## 2026-10-18 23:02 CST：唯一一次实际增量独审结果归档

- root精确授权：`outputs/stage134_month_ranking_protocol/authorize137.json`，6,775字节，SHA256 `50338775e8fa9ba8bd1f1fdfe61afcd0e0d86784e2bd5810acf85dc8773fdc27`。作者135/136最终manifest与冻结137源bundle均经exact CLI绑定。
- 唯一会话 `94573`，exit0；实际耗时 `902.366364` 秒，未修改冻结源、未重启或resume；新的SQL、fit、现金重放、下载、整库hash均为0。
- 收据：`outputs/stage137_month_ranking_review/actual_run1/review_receipt.json`，400,347字节，SHA256 `3693a912790073185a1e2f4fac9def74f0219f870860b20d99ba12cadde2b94d`。
- 终态：同目录 `actual_terminal.json`，231字节，SHA256 `af20c6e8916e14c30b44e78d94942c1c5d6e710fc7caf62c53a978cdb7ab5a59`。
- 最终问题计数：Critical/Important/Minor=`0/0/0`；非关键展示差异=`[]`。
- 核对新增236,229条control×selected-parent覆写；原B完整父表322,028行，selected父行11,249；完整312,170个family-u诊断及720条汇总。未入选原状态/顺序/身份、固定winning product、正分S、原score与u_volume、20个u-only hash规则、同动作精确有理系数抵消及未知质量均一致。
- 用已接受132缓存核136薄桥1,552,456行、9,520个epoch；未重新计算指标或查询原库。
- 新84本账户全部独立核完，保存84个book checkpoint：131,320次fills、107,436个账户日、224,738个position-day、290,617条预算记录；包含每次预留与拒绝、成交价费滑、持仓数量及mark、anchor/lifecycle/stop退出、entry half-cap和逐日gross容量、95family归因与年度/gap/unknown诊断。
- 旧129源标签、130六模型、131旧B4沿已接受绑定复用；没有旧资格suite、旧B4资金/原生重审或策略重放。研究总账在作者136之后为391个实际fit、202本实际现金账户，本审查不再增加。

### 核验后的新增结果与置信度

- 8组比较（2起点×2成本×MAXVOL/固定20随机均值）及原2000次252源日块配对分布均复算一致；全部8个95%CI跨0，全部8组 `financial_unknown=true`。
- 新84本账户全部带执行容量未知；62/84本有历史stale。它们没有被删除、填0或用epsilon修log。所有20seed、完整CNY账本和诊断保留。
- 主预声明 `primary_2020/stress`，AI减固定20随机daily-log均值为 `0.000053160790`/日，95%CI `[-0.000033002305, +0.000164859130]`；AI减MAXVOL为 `0.000105561688`/日，95%CI `[-0.000011898111, +0.000237561722]`。
- `cold_2023/stress`：AI减固定20随机均值 `0.000126114395`/日，95%CI `[-0.000061994405, +0.000321350557]`；AI减MAXVOL `0.000109743848`/日，95%CI `[-0.000157659646, +0.000383535844]`。冷起点AI相对MAXVOL回撤还恶化约0.4774个百分点。
- 固定MAXVOL主stress账本：期末权益 `1,319,465.803`，收益 `31.9465803%`，最大回撤 `-15.3111641%`，Sharpe `0.57343594`；总滑点 `131,584.806046`，778个闭合episode、1,562次fill，闭合净胜率 `11.4395887%`。
- 同一主stress的全部20随机账本，期末权益范围 `1,158,273.676—1,712,098.9825`、中位 `1,424,309.896`；收益 `15.8273676%—71.20989825%`、中位 `42.4309896%`；回撤 `-18.7509500%—-8.9205405%`、中位 `-13.9609641%`；Sharpe `0.3515105—0.9739513`、中位 `0.7451730`。滑点范围 `122,596.917889—179,450.646477`；闭合episode范围744—961；净胜率10.8%—12.6712329%。这些是20本分布的各列统计，不是一条可交易“中位账户”，也不选最大值作为候选。
- 主scope admitted标签域中，AI减uniform(S)的已知域equal-u均值 `-0.0876074691`个own-policy净R，103个增量未知；multiple域已知均值 `-0.0881210189`，同样103未知。全母体已知域均值 `-0.0009860087`，整体已识别均值均为null。这不能将未知域补0，也不能直接换算成资金收益。
- 标签own-policy R与资金账户具有不同权重和非线性资金约束；其正负差异不是算术矛盾，不能互相代替。

### 独立研究判断与结束反思

- 接受新增选择、精确条件归因与现金算术；没有剩余关键bug证据。统计/执行资格仍不足，未证明当前AI在正分月池内具有稳定优势，不具备加注或生产晋级条件；旧133 `unsupported`保持。
- 8个CI均跨0不是证明所有月份排序AI永远无效。其推断仅条件于这20条固定政策路径与既定已接受历史评分；有限seed排名不是p值，也不包含完整择题与模型搜索不确定性。
- 结束新增选参过拟合：否；本次严格核对收益前冻结的全量新结果，没有按利润改规则、删seed、重训或救参。历史反复研究选择与已知域选择的风险仍明确存在。
- 继续本排序包调参/挑seed：否。继续全市场高质量做多目标：是，但需要真正不同的信息或可证伪机制；不把本次计算通过改写为alpha通过。
- 本独审已完成。LINE/registry/138判断与归档由root统一合入，本agent不修改。
