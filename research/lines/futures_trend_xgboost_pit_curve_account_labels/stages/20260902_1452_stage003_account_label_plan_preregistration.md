# Stage003 干净候选账户边际标签计划预注册

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：研究隔离/标签值读取前合同审计
- 记录时间：2026-09-02 14:52 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：账户边际标签样本切分、资格路径和运行前硬闸冻结
- 是否重要突破：否
- 是否触发A/B：是；本阶段不运行策略A/B

## 外部调研与判断

- XGBoost官方Learning to Rank文档要求同一查询组内比较候选；本线将每个决策月固定为一个`qid`，但Stage003不训练模型：<https://xgboost.readthedocs.io/en/stable/tutorials/learning_to_rank.html>。
- scikit-learn的时间序列切分文档强调测试样本必须晚于训练样本；本线采用连续时间切分，不随机打散：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。
- 我的判断：旧Stage015的账户边际标签口径有复用价值，但其“只替换正式表单月rank10”语义不适用于当前干净A排序。必须先把目标月之前的全部干净Top10路径写入资格表，再只替换目标月rank10，才能让账户状态和候选边际效应属于同一个策略基线。

## 冻结输入

- Stage002候选特征矩阵：`candidate_curve_feature_panel.csv`，SHA256=`9c57370ef9896ab9d64adadf2b8f3feb83e5873dba6a9bbffaad36de2670d7b3`。
- Stage002 summary：SHA256=`16db41bcf756903302006e6444421161240f898b160eab62ea25342ddb30fc4e`；manifest：SHA256=`aefe27338abaac7a0c4204d4327824f7bc96e6338b6e4b7f2720bb86c1a49187`。
- 干净A全排名：`ranked_a_panel.csv`，SHA256=`1c841acc3a76a1ecd0f5f3572013c3c97cf4092ac456657f1b87ad3031c14df2`。
- 正式资格表：release `m0005_20260901T165450+0800_1961d98ccb2b`的`combined_eligibility.csv`，SHA256=`fafe6fbaf9836706e2d70d40c799dd4ea4db279fb283fda76d18a797f126d018`。
- 正式CURRENT：SHA256=`f17c0f6bfeea4a08ec7c22a1eb63d4b51e4cfb2472f1ce07fac8ce2cc570b219`；生产checkout HEAD固定为`d492ee072aa5a9d71477235d79f17d2a5db59db3`且必须clean。
- 旧Stage015标签器源码只作语义来源，SHA256=`1033b573d3c9faf6f9630acf637649127c8731adaa639f4d66e65c84c51a1c92`；旧完成记录SHA256=`69838c28676077365c5e09a17dc5551b0c8a5423d5dd42fb70ed01e095fd1ccd`。不得把旧候选池、旧九项特征或旧标签值并入新面板。

## 冻结时间切分

- 47个决策月按`eval_date`严格升序，前35个月为`development`：`2022-01-28`至`2024-11-29`。
- 后12个月为`sealed_account_label_holdout`：`2024-12-31`至`2025-11-28`。这些月份已有市场代理研究痕迹，因此不能称为全局未看；本线只声明其账户边际标签值未读。
- `next_eval_date`只从正式资格表决策日序列机械取得，不从价格、收益或回测结果推断。
- 374行全部进入切分表；开发集预期266个主任务，封存集108行，均不得按活动度、收益、回撤或模型结果删换。
- 开发集A/A哨兵月索引固定为`(0, 11, 23, 34)`，即开发月序列的第1、12、24、35个月；预期4个额外任务，总开发任务270个。

## 冻结资格路径语义

1. 以正式634行资格表为不可变源，保留首个干净决策月之前的正式历史、目标月之后的正式未来行以及每月固定`fu.SHFE` rank11。
2. 对首个干净月至目标月的每个决策月，必须用干净A全排名一次性覆写rank1至rank10的产品和逻辑回归概率；这构成该目标任务的路径一致A基线。
3. 候选rank10任务等于上述A基线；候选rank大于10时，只允许把目标月rank10改成该候选产品和概率，rank字段仍为10。
4. 每个干净月必须恰有rank1至rank10；固定`fu.SHFE`必须仍是原正式rank11且逐字段不变。干净面板不含`fu.SHFE`，不得产生重复产品。
5. 非目标候选替换后，相对A基线只允许目标月rank10一行的`product_vt_symbol`、`score`和`score_type`变化；历史路径和固定fu不得变化。
6. 计划阶段只在内存构造资格表并记录确定性SHA，不写266份完整资格文件，不启动策略引擎。

## 冻结任务与smoke

- 主任务ID：`YYYYMMDD_R<a_rank>`；A/A哨兵ID：`YYYYMMDD_R10_A2`，哨兵复用同月rank10资格SHA。
- 最小smoke固定4项，不得看到结果后换月或换候选：`20220128_R10`、`20220128_R10_A2`、`20220228_R10`、`20220228_R11`。
- 若固定候选无交易/无活动，也必须按原样记录失败，不得改选更活跃月份。
- Stage003只输出smoke合同，不执行smoke；真实账户回放一旦运行，必须追加根目录`back_log.md`并拉独立reviewer。

## 运行时硬闸

- 旧Stage015冻结数据库SHA=`ecbe812bd092ec8cedbd00d8b4b3ec2b1fa9311034dc8379fc6981033405eaf3`当前不可用；生产数据库当前SHA=`5845010108e73661557e723556520d7a3ea42dc6bca4bbe5d50ca3bd419d4cad`，不得冒充旧快照。
- 后续若运行smoke，必须从当前生产数据库建立隔离且只用于研究的新冻结快照，记录新SHA、字节数、SQLite `integrity_check`、bar行数和最大日期；不得让回测直接读写生产数据库。
- 启动前可用磁盘必须至少`1 GiB`；生产HEAD/CURRENT/release/正式资格表身份必须逐项匹配，生产checkout必须clean。
- 新快照只授权新研究证据，不能宣称字节级复现旧Stage015。先过4任务A/A smoke，才允许270任务开发标签批次。

## 技术门

1. 所有冻结输入运行前后SHA不变，CURRENT解析出的release和strategy匹配。
2. 47月/374行切分精确，开发35月/266行，封存12月/108行；封存任务数为0。
3. 开发主任务266、A/A哨兵4、总任务270，job_id唯一；smoke四项精确匹配预注册。
4. 每个开发任务的路径一致资格表满足Top10全量覆写、固定fu不变、目标候选唯一变化和未来月份不变。
5. rank10与对应A/A哨兵资格SHA精确相同；双跑计划、任务和资格SHA逐值一致。
6. 标签列读取0、标签值读取0、模型训练0、策略回测0、CTP和订单API为0。
7. 结构门通过但运行时未冻结时，决策固定为`stage003_account_label_plan_pass_smoke_blocked_on_runtime_preflight`；结构门失败固定为`stage003_account_label_plan_fail_stop_no_labels`。

## 回测/归因参数

- 数据区间：`2022-01-28`至`2025-11-28`。
- 账户规模：后续标签沿用正式15万元账户；本阶段不运行账户。
- 成本口径：后续沿用旧Stage015正式成本/滑点/保证金/整数手/最多4持仓口径；本阶段不计算。
- 样本过滤：仅按预注册连续时间切分，不按效果过滤。
- 策略/归因口径：只审计资格路径和任务合同。

## 结果

- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：0。
- 胜率：不适用。
- 其他关键指标：待Stage003运行。

## 结论

- 本阶段结论：允许按TDD实现只读计划器和资格语义审计；不授权读取标签值或运行策略。
- 是否进入下一步：是。
- 下一步：结构门通过后，单独预注册并构建新冻结研究运行时，再运行固定4任务smoke。

## 过拟合反思

- 运行前判断：否，但整个期限结构方向已有较高先验风险。
- 运行后判断：待运行。
- 原因：切分、任务、哨兵、smoke和资格变化范围均在标签值前固定。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：待运行。
- 原因：账户路径错位会使所有后续标签失真；低成本先证明语义，是继续昂贵回放的必要条件。

## 合入建议

- 是否更新本线`LINE.md`：Stage003出结果后更新。
- 是否更新`research/registry.md`：Stage003出结果后更新。
- 是否追加根目录`memory.md/back_log.md`：否；没有回测。
