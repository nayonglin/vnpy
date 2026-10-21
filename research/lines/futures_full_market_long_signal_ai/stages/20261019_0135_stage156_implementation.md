# Stage156：完整旧分数域的自愿日历准入重选实现

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 01:35 CST；非重要突破。
- 已完整读取155冻结协议及root说明，协议仍为17348B、SHA `7ec4f92b31b46b04e0a17812878acb7f6305c9c476f9350d84bb7d873fe11e47`；152/153/154的历史资格未知不因本实现改变。
- 仅新增`tools/stage156_voluntary_choices.py`、`tools/test_stage156_voluntary_choices.py`及本唯一stage；另依root此前请求只给154实施记录补记actual事实。没有改155、旧源、LINE或registry。
- **本实现者没有启动actual**。新fit/SQL/labels/价格/预测重算/cash均0，累计397fit/206cash。新金融权益、收益、DD、Sharpe、费滑、交易次数、胜率均N/A。

## 固定输入与选择语义

实现直接消费accepted130完整`child_scores.csv.gz`中的main行，不借旧B选中、旧正分月份列表或现金结果作母体。原130源码132行先校验`sequence_index==action_sequence_index`，167行将原pred.sequence_index写入child_scores，因此本轮chosen_action_sequence_index明确由这个已验证别名映射，不是猜测。仅只读原130代码与小manifest/fit_records确认字段，不import或重跑130模型。

实际输入合同为main child **966740=366634+600106**、完整前向父母 **161014=71344+89670**，分别沿2020与2023原模型时钟；全399252 mothers只投影原7列identity/family/reference/u_date/u_index，再按原forward区间取161014，no observation和not-ready父行不能丢。这些是accepted130小记录给出的预期断言，**尚非本实现者新跑出的全域结果**。

K纯由完整epoch的名义YYYYMM定义：前月首个source日历交易日，1月回到上年12月。原u eligible==1、有限正分及事前D<K先作用于完整child域，再逐产品按分数降序、epoch/action_id升序取最好者，最后按原130的u/family/普通优先F/product/epoch/action顺序取家族唯一胜者。旧B式选择也只从同一完整score流用原predicate重建，**仅诊断比较**；不是恢复旧选择后veto，不重算预测。

完整source日历5587行来自132相同的128→052协议绑定`trading_dates.npy`（44KB），不读取132 NPZ里的任何price/indicator数组。root另有132receipt/calendar clarifier；155原字节不变。K在完整日历内但晚于样本2026-10-16时保留真实index/date，绝不夹到样本末。K晚于完整日历时index/date=null并标`after_calendar_pending`；已知D早于目标月首可证明准入，不造未来K日。缺未来D源日则positive动作new_eligible=null、保留unknown且不选；K在日历首端之前明确阻止新入场。

18个经济metadata缺项不复制日期；选择沿原eligible，不以新metadata/donor/stale状态删身份。本轮只保存自愿K，不重解释旧法定字段，cash作者另取old/voluntary/effective三者trace，effective为原边界与K较早者。K不是历史账户截止认证，也不制造现金交割或市场成交。

## 与157/158约定的输出

已直接与`/root/voluntary_cash_impl`及158独审同步以下接口。manifest的artifacts为字典：

| role / 文件 | 内容 |
| --- | --- |
| choices_main / choices_main.csv.gz | 完整161014父行，原131 helper所需identity、proposed/chosen_action_id、chosen_action_sequence_index/chosen_epoch、anchor、score、selected、scope/main、cutoff、policy/NARROW；外部arm=VOLUNTARY_RESELECT，现金可局部alias B |
| action_eligibility / action_eligibility.csv.gz | 完整966740 main action，原score身份及原eligible、K_target/index/date/state/after_sample_end、D_index/date/state、new_eligible/reason；被拒或unknown动作也不丢 |
| boundaries / boundaries.json | `.epochs[epoch]`为上述K字段；另含calendar绑定、sample_end、policy_version、account_deadline_certified=false；不含伪造的old/effective期限 |
| summary / summary.json | 完整action及每cutoff分母、所有拒绝/unknown原因；父状态、新旧selected及cutoff分组、unchanged/removed/newly_selected/different_action逐cutoff比较；不只报告新selected数 |
| started / terminal / manifest | 新鲜输出路径、实际终态与耗时、全输入/代码绑定；失败保留、不自动retry |

manifest的`policy_version=stage155_voluntary_reselect_lead_months_1_v1_not_certified`、`not_certified=true`；source_bundle只含新作者/测试两文件，另绑定原130 alias证据源码。只校验并绑定实际读取的score/母表与小JSON/calendar，不读/rehash大库或训练矩阵。旧130choices并非输入，比较源由原分数重建，故不会用旧已选集合缩减新机会域。

## 有限TDD与交付状态

先写6个fixture，实际首次6个明确FAIL（实现缺失），实现后6/6 GREEN；最终加入完整选择差异汇总后同6项再核，**6/6通过，0.021秒，exit0**。六项分别保护跨年/非交易日K、K当日入场拒绝、K样本外与缺D unknown、完整pool重选、普通/F及month/action tie优先、无观察完整父行与cutoff错配拒绝。未运行旧全套、金融或真实选择actual。

CLI --help exit0；禁用数据open/read的import检查确认IO0；已有输出目录在任何输入读取前拒绝且不新增文件。root静态实读报未见C/I，158已收到纯接口以准备独立重建、不import作者计算。完整真实结果与置信度的独审仍须actual后一次完成。

| 最终源码 | bytes | SHA256 |
| --- | ---: | --- |
| stage156_voluntary_choices.py | 17062 | 4c56ad2f0e812a10aca9a153e3328c8a8aa6e8df1a1b588f3aecf898713f7200 |
| test_stage156_voluntary_choices.py | 5837 | bfa22b9b2d49697df32a928c640dec99aace64a368d1eab3ed977a6575c87a18 |

root的exact-source authorization在外部保存，不另建authorizer类或修改155；本CLI只需fresh `--output`，以下命令本实现者**未执行**：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage156_voluntary_choices.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage156_voluntary_choices/actual_run1
```

开始/结束新增按本轮收益救参过拟合：**否**，唯一K/排序/原模型已由155收益前冻结，代码不读D bar、标签、未来stale或收益。已有过期仓案例启发与同史择题风险仍是**是**，不称新alpha或全新样本外。继续这一项全域政策检验**有价值，准备已足够，交root唯一actual**；换K、只保留易验证品种、重训或现金结果前救参数**无价值且未实施**。完整目标active，资格和加注均未证明。
