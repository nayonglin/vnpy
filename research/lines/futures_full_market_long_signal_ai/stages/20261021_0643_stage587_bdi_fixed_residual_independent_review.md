# Stage587：BDI固定残差包独立审查

- line_id：`futures_full_market_long_signal_ai`；建立时间：2026-10-21 06:43 CST。
- 当前模式：收益前协议审查与后续独审准备；当前不是实际回测验收或重要突破。
- 工作区：`/Users/mac/Desktop/fian`；同线唯一587stage，仅修改本文件及本587outputs，不改LINE/registry/正式/生产或其它agent文件。
- 本轮先读registry，研究目标仍为全六所98历史产品/95family的高质量多头、成本后收益与DD；与正式C9隔离。历史研究不等待今天日线。

## 585协议定向审查，06:43

仅读取冻结585完整协议及registry目标行，没有提前读取BDI原件、train/forward/mothers/choices大输入。

- 协议：`outputs/stage585_bdi_fixed_residual_protocol/protocol.json`；root冻结绑定15,532B / SHA256 `c7c7313a8ccac4a292e31ba87c2818f12acf47b9322c4ef289fcc9f8a6a2261a`。本阶段所写SHA为root冻结身份，实际独审时另作小文件身份核；不冒称已重新审计所有继承大源。
- 裁决：**协议GO，无实质矛盾，不要求改协议或新增门。**
- 外部资料/机制判断沿584原作者、官方与维护者GitHub有限实核，不重复搜同一论点或行情。BDI是新增的运输价格观测，可能混合需求/运力/拥堵等；不是52或PMI字段换名，也没有盈利先验。论文无法直接证明中国first-exit多头收益，当前源只限条件历史重建。

核准理由：

1. 月m为已完整月，各自月内最后weekday正finite候选先确定，再将18冲突端点留unknown，不能往前挑替身。m−3是公历月，2009Jul/2018Mar跨定义留unknown，不插值或跨月补价。每u消费前完整月，目标月缺失清旧q；完整u收盘后下一D，不回填较早夜盘。历史首发/精确Sina可知上界未知明确保留，不以不可达PIT全史认证阻塞此有限研究。
2. A/原52/目标/原权重不重训，B是known子集sum1原w的惩罚常数，C同支持加一条train-only加权标准化q斜率，lambda1惩罚全部残差系数。缺失逐值B=C=A。原权重拟合与来源月等权诊断已清楚区分，不将日×family×child当宏观N。
3. 全六own fold成熟来源月M≥60、加权scale>0先统一检查，全部通过才最多12head。60仅可估计性底线，不证明功效/周期稳定。全域forward/mothers以及旧A choices复用，新增B/C先完整域筛选，不截取positive或已有成交机会。
4. 前门对main全段C−A/C−B、main早后两段C−B、两held的C−A/C−B均严格>0，差动作unknown独列不填0；失败停止精确包且0CI/0cash。585始终0cash，过门后最多四本另由root授权，不自动晋升。

## 收益前source与实际独审边界

等待586 source-ready，只核新增清洗/month-q/因果join、known域head与预检先后、完整域选择/新分数、诊断/gate，以及必要fixture设计；不重复运行新fixture、不提前大输入、不重做旧52 normal或A现金。

root通知唯一actual真实终态后，独立读取本次BDI raw一次，必要六train/forward/mothers/旧A choices各一次，并先保存派生审计结果；用独立算术核全部clean与month状态、月映射、成熟支持/scale/系数、forward新score、完整域B/C choices、诊断和门。可复用568/539既有独审方法，原A、策略和模型均不重放；不引入新的策略测试或大缓存工程。实际若失败/未知则如实保留，不为负候选补齐无关小字段或扩门。

## 当前变更、计数、结果

新增仅本唯一stage。策略参数/脚本、模型、金融结果新增/修改/删除均0。

本587当前fit/cash/SQL/行情GET/原件与大cache读取全部0；原线累计535 fit /282 completed cash＋1旧partial不变。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。尚无586实际结果，不写虚构验收结论。

## 当前反思

开始/截至协议审是否按新收益过拟合：否，没有新收益或调参；长期同史自适应风险仍高。继续价值：协议及必要独审有价值，只允许一次固定低容量包；没有开启行业、窗口、符号或风险救参的价值。完整目标未完成，未授权加注/正式/生产。

后续本stage顺序补记source定向审与真实actual后独审，避免同线多stage互改。

## 586 source-ready唯一收益前补审，06:48

root通知核心稳定后，独立一次读取`stage586_bdi_core.py`与8项fixture源码；runner ready后一次读取`stage586_bdi_residual_fit.py`及`source_ready1/source_ready.json`，没有运行fixture或读取真实输入。

- core：8,351B / SHA `1cda86df2a2f2e8e7b85675f1cfee1e1a6c8a8815795711c24f9688f2202f9d2`。
- runner：19,356B / SHA `bb15216e4245e7aed4ecd0135045a7b820bb281d2f4590cc026b0d27ccbc9012`。
- test：4,107B / SHA `e095b69810ab9399ba59dcc2cb99509bc8a8c9a93210199027e9e93aa67903c2`。
- 以上SHA为source-ready绑定，实际终态独审另检查源冻结；旧567/538/156/130/071依赖使用已验收身份，不重跑旧体系。

**收益前source审GO，可由root唯一启动actual。** 新core正确先选最后候选再判冲突，完整公历m与m−3、跨方法段unknown、每u上一完整月和缺月清旧q；按known成熟原w计算train-only scaler与normal方程，B/C全部系数lambda1，预测缺失位级保留A。八项fixture设计覆盖这些必要新增边界、无缺失信号回退和全6预检先于solve，不需为辅助字段新增fixture。

runner先核已接受538/fold身份和source-ready，BDI raw一次、六train各一次，全部支持通过才12 solves；forward保留1933480全child、161014母事件与原非正score，旧A仅filter复用、旧B/C offset不消费，B/C全域选择完成才消费forward标签。每u公共offset不改变同product内差序。u日历月/reference_month同时保存，era/annual用u年；同动作差0合法，不同动作未知仍NaN/count。八个固定严格正门与0CI/0cash、无自动重试一致。candidate_rows与quote_date足够在独审派生lag披露，辅助metadata不升级新门。

为后续节省IO，仅查看旧568独审脚本及539独立choices/diagnostics方法，不执行、不读它们旧数据、normal或现金。当前587全部实际/大输入计数仍0。等待root真实terminal通知后再执行既定全面独审；当前GO不能冒充终态验收。

## 真实actual后的唯一全面独审，06:52

root唯一586实际`actual_run1`、session75136终态exit0，79.473902秒；恰12新残差head，0 base refit/A cash replay/新cash/SQL/download/CI。原线累计变为**547 fit /282 completed cash＋1旧partial**。没有第二次策略或模型实验。

587审计脚本在真实终态通知后才启动：`/private/tmp/stage587_bdi_review.py`，唯一session57909，exit0，49.850819秒。**6,137项审计断言全部通过，critical/important/minor=0/0/0；没有审查器失败、恢复或重启。** 断言数是程序核验量，绝不是训练N或独立统计样本量。

独立读BDI封存raw一次；六fold原train compact各一次；完整forward、mothers、两份旧A choices各一次。先独立保存小source/month/u派生文件，训练大表消费后释放；只复用已接受539独立选择与诊断函数，没有导入586/567的抽取、head或gate计算，没有重算52 normal、并发权重、基模型或A现金。source bundle、585冻结、ready/terminal、原件与全部所需输入/新输出的hash/大小绑定均通过。

### 清洗与时钟

独立重建245个月状态，其中233个q known、跨已知方法段6个月、missing_base_endpoint4个月、frozen_conflict1个月、未完成月1个月。已知冲突最后候选不退前；相应m−3引用也为unknown；坏年/周末原行保留。5587个完整source u中4718个q known。最大完整月末到实际endpoint的间隔为9个民用日，属于实际最后已有观测的披露，不额外调age阈值/补假价格。

原month字段、endpoint索引/原值、q、regime、全部u映射和missing原因逐值一致；每u仅前完整月，月缺失清旧，不回填夜盘。这里通过的是条件历史重建合同，并未增加Sina首发/PIT或Baltic逐值认证。

### 六fold支持与head

| own scope | 2020 cutoff成熟来源月 | 2023 cutoff成熟来源月 | 2020 C的z斜率 | 2023 C的z斜率 |
|---|---:|---:|---:|---:|
| main | 117 | 153 | -0.02342845537 | -0.02257991644 |
| held0 | 117 | 153 | -0.02499224489 | -0.02430245114 |
| held1 | 117 | 153 | -0.03831908835 | -0.03149603495 |

六fold均通过60月及正scale预检。成熟身份/held排除、原w known子集归一、train-only加权均值/scale、训练月支持、G/rhs、B/C系数与df均独立算术一致。2020/2023 main B常数分别0.000792866889/0.000649577004；C常数因加权z中心化与B只差浮点误差，符合全部系数lambda1。不同月支持及三月重叠意味着有效独立信息少于原行数；117/153不是跨周期稳定性的证明。斜率为负是训练解，不是预先经济因果或允许再做反号候选的理由。

### 完整域选择与诊断

完整forward共1,933,480 child，main966,740、held0 388,666、held1 578,074；原非正分数分别944,504/377,399/558,554，均参与完整新选择前域。forward母事件161,014、全部三臂choice共966,084行；所有A逐字段复用，六个B/C全域独立选择的身份/排序/日历K/家族优先/分数/状态一致。缺q的main25,215、held0 10,607、held1 14,608个child逐值走A，相关最终choice亦相同。

新增head没有缩品种/母事件/positive域；公共q只能改参与阈值，不能声称改善同u/product的child排序。全部chosen-action标签链接、family-u差值、每日/月/年、来源月context以及包含零值family-year输出核验一致。只有同动作的抵消差可为0；不同未明动作保持NaN及计数。main早段C−A/C−B各有2个unknown family-u，未填0；正诊断仍限known支持，不能外推全政策。

| scope，来源月等权known机会R增量 | C−A | C−B |
|---|---:|---:|
| main | +0.001254418826 | +0.001257028790 |
| held0 | +0.002038052728 | +0.002049239022 |
| held1 | **-0.000041246093** | +0.000191642252 |

main2020—2022的C−B=+0.002295362142；2023以后=+0.000444420079。main C−A早/后段为+0.002392272769/+0.000363924436，不能替代冻结门。八项严格正门仅held1 C−A失败，**nominal_cash_prerequisite=false**，独立结果与作者报告/terminal一致。没有因为负差很小或其它均值为正放宽门，也没有另选B（其全段主/held均值未显示优势）。

### 最终裁决、输出与限制

**`ACCEPT_ARITHMETIC / STOP_EXACT_BDI_PACKAGE`。** 数据处理、因果合同、12head、完整域选择、未知处理与否决算术接受；这一固定BDI三月单斜率包未获得稳定优势的充分证据，按585关闭，0CI/0cash。不能把其描述为已证明BDI对所有多头有用，也不能把一个held小负差外推为全球BDI永远无效；本包不改窗口/lag/endpoint/方法段/sector/learner/family/stop/risk救参。

- 小验收摘要：`outputs/stage587_bdi_fixed_residual_independent_review/actual_run1/acceptance_summary.json`，7,016B，SHA `889bc77097b5f649b0416e599d26c1b44a8c1fd5704eff4eb51a0153b6e63b34`。
- 全审计：同目录`review.json`，671,265B，SHA `a04d97296e4f87835f6b346b93b2504acb5409adf4a60ed49a5cb74dc27c55ed`。含所有断言、原输入各一次读取清单、actual manifest绑定与复核方法。
- 派生小源：同目录`independent_source_months.csv`及`independent_calendar_u.csv`；只为本次复核，不替换正式数据或声明生产可用。
- 新收益/权益/DD/Sharpe/滑点/交易次数/胜率：全部N/A。本次是stress机会R筛选诊断，未发生现金回测；不能把上述R增量称现金收益率。新现金/加注/正式/生产资格全部否，完整目标仍未完成。

运行结束是否按新收益过拟合：本次固定包未作收益后调参，否；全线反复同史择题风险仍高，是。运行结束继续价值：完成这一精确包的独立审查有价值，已收口；继续调整这个失败包无价值，不在587另提模型。只允许root整理本线总状态；本587仍不改LINE/registry/根总账/Git/生产。
