# Stage097 跨日历史表示对照结案：收益增加但风险未改善

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 18:42 CST；分支 `codex/ai-training-data-expansion`，当前checkout。
- 重要突破：否。完整目标仍是全市场高质量做多、成本后更高收益且更低回撤，进一步验证小止损和增加投注；本轮目标未达成，goal active。
- 结论：接受独立复核后的研究算术，停止固定20bar/四通道/RFF181/NARROW包。ORDER四组收益均高于BAG，但四组回撤均更深、四组收益差CI跨零、一个品种留出组增量为负。不按本结果救参数、不据此加注。

## 本次改动与调研判断

依据[Deep Sets论文](https://arxiv.org/abs/1703.06114)和[作者代码](https://github.com/manzilzaheer/DeepSets)把同一组历史派生观测的集合与时间位置分开。文献支持对照思路，不证明期货预测力或收益。当前070跨日首次退出目标此前已独立固定，与旧DAY/4R不是正单位变换；旧负结果和历史曝光保留。

复用023纯X，不读旧目标/资格mask。093仅按event_id接入399252完整母体，194709有序列、204543缺失，缺失不删除或硬门控。旧21bar资格未替代当前20ready；模型主/held每臂均161014条完整前向预测。

新增桥接：两臂相同53项背景（common26＋26missing＋sequence_missing）接128项RFF，共181项。旧139→181增加42项共享背景，不能称旧模型未变。RFF仍原91维、固定seed20261018与W/b；BAG按原float32完整四元组canonical排序，不是逐列排序或随机打乱。

两cutoff2020/2023×main/held0/held1×ORDER/BAG，12fit。各fold自身成熟标签/家族留出、唯一性→u等质量权重；common和pooled四通道尺度只来自本fold成熟训练；缺序列标准化80维直接置零。Ridge alpha1/intercept/cholesky，未扫模型参数。

交易参数新增/修改/删除均0；沿070原现金引擎：100万元、单family0.25%/总2%、缓冲保证金25%与1.10，初损0.25 Wilder20 N、因果20low、无硬止盈/固定最长持有/retry。u预留、D只减不回收，gap/换约/缺价与破产规则保留；不用080预过滤或OI。两个起点分别独立执行，起点与年度切片重叠，不算独立重复证据。

## 一次运行与独立复核

093唯一5.538秒准备；094由root唯一执行44.852秒、12attempt=12complete；095由root唯一19.138秒、8start=8complete，共享一次native SQL。0新label/下载/旧金融重跑/大库hash，未改正式版、生产、CTP或Git。

096独立agent唯一完整复核：全399252身份/194709 tensor映射、12个181项模型、644056预测、8账本、四CI、held与门，C/I/M=0/0/0，最大数值差5.82e-11；0模型重拟合/现金重放/新SQL。只接受此研究重建合同内算术，不是broker、首发PIT或实盘盈利资格。累计357研究fit/86现金账户，含重叠对照，非357次独立市场经验。

## 全部账户指标

| 表示 | 区间 | 成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 闭合交易 | 净胜率 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ORDER | 2020至今持续 | base | 1,207,765.23 | 20.776523% | -29.205395% | 0.314847 | 634 | 11.5142% |
| ORDER | 2020至今持续 | stress | 1,151,346.42 | 15.134642% | -22.375327% | 0.296217 | 498 | 11.0442% |
| ORDER | 2023独立冷启 | base | 1,377,070.01 | 37.707001% | -9.234498% | 1.050504 | 195 | 12.3077% |
| ORDER | 2023独立冷启 | stress | 1,262,442.18 | 26.244218% | -8.661465% | 0.901931 | 177 | 11.8644% |
| BAG | 2020至今持续 | base | 1,161,881.11 | 16.188111% | -17.558630% | 0.274830 | 413 | 12.1065% |
| BAG | 2020至今持续 | stress | 1,116,693.90 | 11.669390% | -12.650852% | 0.255967 | 341 | 12.0235% |
| BAG | 2023独立冷启 | base | 1,277,307.39 | 27.730739% | -7.093117% | 0.923997 | 117 | 16.2393% |
| BAG | 2023独立冷启 | stress | 1,242,745.29 | 24.274529% | -7.500573% | 0.875849 | 107 | 15.8879% |

胜率为闭合经济根净CNY>0比例；成交数量、订单fill和闭合交易不是同一单位。滑点已计入成交价，下表仅归因，不重复扣除。

| 表示 | 区间/成本 | fills | 手续费CNY | 滑点归因CNY | 期末open/stale |
| --- | --- | ---: | ---: | ---: | --- |
| ORDER | primary_2020/base | 1272 | 22,649.77 | 56,030.62 | 1/0 |
| ORDER | primary_2020/stress | 1000 | 40,283.58 | 85,839.06 | 1/0 |
| ORDER | cold_2023/base | 391 | 7,574.99 | 15,340.62 | 1/0 |
| ORDER | cold_2023/stress | 355 | 16,512.82 | 29,819.77 | 1/0 |
| BAG | primary_2020/base | 827 | 14,553.89 | 34,280.89 | 1/0 |
| BAG | primary_2020/stress | 684 | 27,756.10 | 57,062.32 | 1/0 |
| BAG | cold_2023/base | 235 | 4,212.61 | 8,493.70 | 1/0 |
| BAG | cold_2023/stress | 215 | 9,859.71 | 17,382.48 | 1/0 |

## ORDER减BAG的冻结检验

| 区间/成本 | 收益差pp | 回撤差pp | 日均log差95%块CI |
| --- | ---: | ---: | --- |
| primary_2020/base | +4.588412 | -11.646765 | [-0.0001683249813, 0.0002109156287] |
| primary_2020/stress | +3.465253 | -9.724474 | [-0.0001219125553, 0.0001682238937] |
| cold_2023/base | +9.976261 | -2.141381 | [-0.0001228323594, 0.0003399283364] |
| cold_2023/stress | +1.969689 | -1.160892 | [-0.0001334355597, 0.0002008961412] |

回撤差为ORDER DD减BAG DD，负值表示更深。CI复用预先固定252源日块、2000次、seed20261018和同一indices；单位是日均log差，不是累计收益百分点。均跨零，且未对整条历史研究的多轮择题做调整，不能将它们包装成全新盲测显著性。

ORDER自身四收益均正这一必要门为真，但回撤门、主stress CI门与held联合门为假。不是仅由unknown导致不支持；没有COMMON新臂，不能据此推断比当前COMMON或正式版更好。

## 跨品种与年度

| 品种留出 | 已闭合共同事件 | 源日 | 按u等权增量R | 未决动作分歧 | 判断 |
| --- | ---: | ---: | ---: | ---: | --- |
| holdout_0 | 39712 | 1642 | -0.0045378393 | 11 | unsupported |
| holdout_1 | 62228 | 1642 | +0.0007051710 | 41 | unknown |

留出只按完整family哈希排除训练，诊断域为closed且known_date<=end/ready20；同动作0在已知域保留，unknown未填0。不拼held分数进主现金，不能把该条件标签均值当全机会现金价值。

| 年度（主stress连续切片） | ORDER收益 | BAG收益 |
| --- | ---: | ---: |
| 2020 | +1.067577% | -4.458077% |
| 2021 | -9.708004% | -7.597189% |
| 2022 | -4.697893% | +0.383340% |
| 2023 | -0.475638% | +3.143027% |
| 2024 | +6.748766% | -1.797592% |
| 2025 | +2.705292% | +2.163877% |
| 2026（至10-16） | +21.326961% | +21.768222% |

ORDER主stress的2026不完整年现金增长202,384.70，占全期净增长151,346.42的133.72%；此前累计为净亏。2021—2023连续负，不能称已穿越周期。上述是同一持续账户年度切片，不是逐年独立冷启动。完整44条年度切片与95family含零贡献表保存在095目录。

## 风险与数据解释

| 账户 | 历史stale源日 | gap止损fills | gap损失>1R |
| --- | ---: | ---: | ---: |
| NARROW_BAG_cold_2023_base | 0 | 7 | 5 |
| NARROW_BAG_cold_2023_stress | 0 | 7 | 5 |
| NARROW_BAG_primary_2020_base | 3 | 17 | 14 |
| NARROW_BAG_primary_2020_stress | 3 | 16 | 13 |
| NARROW_ORDER_cold_2023_base | 1 | 12 | 10 |
| NARROW_ORDER_cold_2023_stress | 1 | 11 | 9 |
| NARROW_ORDER_primary_2020_base | 6 | 24 | 19 |
| NARROW_ORDER_primary_2020_stress | 5 | 21 | 16 |

八个账户期末均有1笔正常开放long、无期末stale；不因此抹掉历史缺价。所有账户未发生研究账本破产，但日线收盘估值、静态vendor费用/保证金和开盘/stop成交模型不是真实保证。极窄止损不能封顶跳空损失；末端所有开放long置零仅是情景，非普适下界。

主分数有24个未决动作分歧、52个已知不参与分歧。未成交信号标签不确定性与真实cash stale分别报告；没有把unknown变负类或给收益0。

有序版本增加了交易、费用与右尾暴露；目前只观察到收益/回撤交换，不能把较高终值归因为稳定的高质量识别。模型规模或数据行数不是独立样本量，重叠持仓与同市场日期相关仍在。

## 决定、反思与后续

- 是否新增按本包成绩调参：否，设计和门在结果前冻结；历史多轮择题与同一历史复用的过拟合风险：是，不能声称已消除。
- 继续固定RFF包：否；失败门明确，不改窗口、通道、seed、核、容量、目标或风险去救它。继续原全市场目标：是，但当前无加大投注资格。
- 下一步仅由098独立审查风险敏感学习目标的经济与数学可行性；它不新增信息，不允许把正单位变换冒充alpha，也不因当前成绩挑风险小数。若定义域或组合现金代理解释不成立则否决，不自动启动新训练。
- 未新增正式候选、未改任何旧结果；不触发正式多周期/发布/生产门。研究算术可信不等于策略目标完成。

## 精确证据

- protocol：`outputs/stage092_crossday_order_bag_protocol/protocol.json`，7146B，SHA `580c59d77964b27372570b2d48e197ce7a75f5edd77dac0a9aa5e42548d3a736`。
- prepare_manifest：`outputs/stage093_sequence_alignment/experiment/manifest.json`，4446B，SHA `4824bb1c88e9eea6778a35f6a5b85fc5954486701b63dc9fef1bd446692612f4`。
- prepare_terminal：`outputs/stage093_sequence_alignment/experiment/actual_terminal.json`，300B，SHA `0c111545d97a32595d791e7b0401795a00e43071b637ea56d2cd1e3f7d8918c1`。
- fit_manifest：`outputs/stage094_crossday_order_fit/experiment/manifest.json`，34812B，SHA `8d4d26d4c1e7b6a0c1aad2f25e11d9b63c4c8aeea02ded6a5b64f3dc82e96532`。
- fit_terminal：`outputs/stage094_crossday_order_fit/experiment/actual_terminal.json`，344B，SHA `7f4770ef168578d7fc8c42f9e3a2b69cee24b2100677129e6d0c14d82fdc5d00`。
- cash_manifest：`outputs/stage095_order_bag_cash/cash/manifest.json`，44820B，SHA `8e6a43cd0b846a8653b615dbe66e291d3c6051471bc94ce2801e5231368334de`。
- cash_terminal：`outputs/stage095_order_bag_cash/cash/actual_terminal.json`，518B，SHA `c3aec1194bf7b28f26d42753350037eebaaaf8805f7a9daf7ded7e94f0fa2cf2`。
- review_receipt：`outputs/stage096_order_bag_review/actual_review1/review_receipt.json`，56002B，SHA `cfd121fe1e7efdd3d29cc73022a1e358e889125df9b26faa9d123faf6c3ade24`。
- review_terminal：`outputs/stage096_order_bag_review/actual_review1/actual_terminal.json`，302B，SHA `8244d1ad664585590d43561249fbf964cb08314dfb1d627ed00f179718f2455c`。
