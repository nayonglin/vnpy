# Stage018 全体ready机会的固定入场确认执行归因

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18 12:15 CST；实际完成12:13:24。
- 当前模式：冻结Stage015的单项执行机制实验，不训练模型、不生成账户或金融收益；唯一实际完整实验完成后等待019独立联合审查。
- 是否重要突破：否。`quality_screen_pass=false`，`entry_increment_detected=false`。
- 写入范围：新增018入口、测试、本记录及018 outputs；未改015/旧源/LINE/registry/Git/原始数据，未派子agent。
- 工件角色：本记录与终态/测试/诊断为`qualification_evidence`；源/测试/协议为`feature_contract`；事件区间/日表/metrics为`decision_asset`；均`reproducibility_required=true`。原004/009价格与feature缓存、小日历只作已有来源绑定，`cache_or_visualization`、`reproducibility_required=false`，不复制原行情进入新决策文件。

## 调研、事前判断及合同

研究前已读registry、LINE、015完整冻结spec和协议。015协议SHA256 `73c991c2ed2c4d4dbc77147705b6f09d834e63c05d7a8b0f614a902c1b6ec5e9`；spec SHA256 `fa51d49dbff0d4a323d4313c56493bc8316e071ee50de9e936797f7d06a7006f`。沿用015实际核对的Backtrader作者[bbroker.py](https://github.com/mementum/backtrader/blob/master/backtrader/brokers/bbroker.py)和[官方执行语义](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)：开盘越过阈值用open、盘中触达才用trigger；这是连续理想成交模型的参考，不证明中国期货的窄损成交或优势。本次按授权未重复长外搜、未下载。

017独立有限合成oracle结果742+5、d50459 exit0，边际不符/配对越界均0。源码SHA256 `85709fc2ba5dd9b3f3da8a5252f88a0a84eb284b35b6ea27bf61d1bdab4fc2d9`，结果`2e146bacab2e6079758d515d7bdfb69bd9dc4bf329510ba377bcd48c6825c35d`，终态`1ada61d73cce68c9f3530f8c30b53383eb5d218363c495a115a05cfd46cb681f`；此处引用root已核终态，不重跑BFS，不外推全局sharp。

开始判断：新增选参过拟合**否**，继续价值**是**。全部原ready机会只改变入场条件，可将执行确认与事前AI识别/趋势筛选分开；不看新政策结果调参数。历史反复研究的选择风险仍存在。

## 实现与参数

使用TDD与executing-plans；新增`tools/stage018_entry_confirmation_experiment.py`和同名测试。4项方法验证：gap同路径（双触达也差0）；确定未触发真0与缺D/删失未知；触发前low反例、触发后必止及原价等号浮点边界；每日p归因、费用抵消与源日历NaN。初始4fail真实RED，随后4GREEN；两个有据输入适配各在原方法内先RED再GREEN，最终4方法在0.048秒通过，新增两源编译exit0。未跑旧suite。

所有策略参数原样：long-only；B=u.high；OPEN于D.open，CONFIRM为仅D有效触价；r=0.25ATR20(u)，PT=4r；当日close退出；基础每入场0.2R预算、压力1R；60源日block、2000次、seed20261018；15门合取。新增/修改/删除策略参数均无；没有趋势/周线/FI/setup阈值、月池、模型、retry、roll、stop/fraction或品种/年份扫描。

一次接合既有004机会（u.high）、009全行feature_labels和同event/同epoch的audit_paths；读各已绑定压缩bytes后解析，精确身份验证并一次merge。没有SQL或大库hash。004/009/audit实际分别399252/399252/212852行。沿用原009ready及identified共同集合，缺D不换执行日期。

新399252行CSV只含身份、ready/unknown状态、归一化b/h/l/c、比较位与政策区间；无原始绝对OHLC、ATR或r。全部D坐标、触发、填单、成熟与结果字段显式`label_only_columns`，不能作为u时AI特征。OPEN直接继承009已接受gross/proxy；CONFIRM全部触达在原价空间含等号判断，再除r输出R，避免浮点除法改变触边；保存label-only比较位和`confirm_day_close_r`供019复放，不加epsilon、不snap价格。gap同一路径paired精确0，其余为有效外界，不称全局最紧。

日内共同可评价产品等权，再源日期等权；不对已填单重新缩分母。每日报告p为当日共同cohort填单率：gap按(1−p)乘OPEN，未触发按−p乘OPEN，其他按有符号端点。费用在每日同参与率差中抵消；base/stress同参与率界数值一致。主表day_p用全体cohort；family异质性组内报告按该组cohort重算p。各组均报告，不选较好组。

## 实际命令、失败与终态

共同解释器为原路径`/Users/mac/Desktop/fian/.py311/bin/python`，Python3.11.5/NumPy2.2.3/Pandas2.2.3。实际3次启动、1次完整实验，前2次均在事件输出和政策统计前失败，未观察CONFIRM效用挑修复。

1. `--output .../experiment`：session12498→6674e1，12:08:08—12:08:11，3.244771秒，exit1。新增D身份断言误把009报告scope4074日当完整后继日历。只读确认399252行仅最后u=2026-10-16的98行D=2026-10-19与scope后继不同；对原绑定5587日完整npy后继，全部差0。封存失败源码c744ed...及终态。修复只将完整小日历用于D身份，bootstrap/report仍4074日，不删改尾行；原方法2增加future-successor回归。
2. `--output .../experiment_after_calendar_boundary_fix`：session73155→01f98a，12:09:51—12:09:57，5.575671秒，exit1。OPEN一致性断言发现除r后的边界分支改变。只读194168个已识别路径确认恰3行、两端均受影响，最大差1.7000000000002136R；均原价L==F−r或H==F+4r，除r落在边界内侧约1e−13。Python float roundtrip并原价比较时，与009所有端点逐值差0。封存7f1fc2...源码/终态；原方法3加边界回归，统一修全部CONFIRM比较，OPEN直接继承。未修改旧源/政策或看新政策收益。
3. 最终命令：`/Users/mac/Desktop/fian/.py311/bin/python /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage018_entry_confirmation_experiment.py --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes`。session70086→c5836f，12:12:59.406—12:13:24.312，**24.905924秒、exit0**。`attempts=3`、`completed_full_experiment=1`；fit/SQL/金融/网络/下载均0。

三个目录、两个失败源码/测试/terminal快照和诊断均保留，不覆盖旧终态。root在各真实终态到达后即获报告，不以写长文延迟结果交接。

## 全表覆盖与结果

399252行全部保留；194709ready，194168identified，541ready未知（missing_D460、right_censored81），204543不ready。已识别集合：gap23055、盘中触发72309、未触发98804，共填单95364行/4042日/94family。CONFIRM边际歧义45892行、paired外界非单点46203行；OPEN歧义6000行。未ready/缺失/删失均unknown，不填0，确定未触发的0仅来自合法已知D。

2020+外层161014行，ready107844、identified107437、未知407（missing_D326、right_censored81）。gap11919、盘中触发41331、未触发54187，填单53250行/1642日/87family。报告网格1643源日，其中1642日可评价；2010+网格4074日。2020+日期等权填单率0.496673674，未触发0.503326326；每日p是事后参与率归因，不能声称u时AI选品。

下表为2020+共同分母的每机会代理R日期均值与固定代理60日block条件95%CI，**不是账户现金、实际收益率或未来预测**。

| 指标 | 日期等权点均值 | 条件95%CI |
|---|---:|---:|
| CONFIRM下界 | -0.401270615813 | [-0.409766170593, -0.394172731761] |
| CONFIRM上界 | 0.086140716722 | [0.062659478435, 0.107778764216] |
| CONFIRM−OPEN配对外界下端 | -0.322316342159 | [-0.352973372135, -0.281091928681] |
| CONFIRM−OPEN配对外界上端 | 0.273532279010 | [0.252770163465, 0.298193358231] |
| 同参与率差外界下端 | -0.414278956362 | [-0.431919764420, -0.393310425602] |
| 同参与率差外界上端 | 0.126848656881 | [0.112494920848, 0.144363026298] |
| 1R预算压力CONFIRM下界 | -0.798609554996 | [-0.812495086243, -0.786607958162] |

CONFIRM自身点区间[−0.401270616,+0.086140717]、paired有效外界[−0.322316342,+0.273532279]、同参与率差外界[−0.414278956,+0.126848657]均跨0。保守下界显著为负只说明未证明所要求的稳健正效用；不能把外界lower的负值断言为真实政策必差，也不能从upper正值宣称alpha。

主期间未触发带走的正OPEN右尾代理机会成本，按全共同分母日期等权为[0.104234522,0.118249980]R；未触发行内条件均值[0.205292023,0.232782011]。2010+对应全机会成本[0.111895140,0.125246307]、未触发条件[0.213167941,0.239436108]。这些是已知代理集合的诊断，不用未知收益补齐。

2010+CONFIRM自身[−0.378386980,+0.068520221]，paired[−0.291293863,+0.251865395]；两family组2020+自身lower分别−0.396042282/−0.404084034、paired lower分别−0.329986085/−0.317171433，均未满足正向门。2020—2025完整六年paired lower正数为0/6，2026部分年自身lower−0.407081287。

| 年份 | CONFIRM lower | paired有效外界点均值 |
|---|---:|---:|
| 2010 | -0.320255742 | [-0.263946642, 0.157049392] |
| 2011 | -0.301898683 | [-0.147600461, 0.177389735] |
| 2012 | -0.310380797 | [-0.235094736, 0.168227715] |
| 2013 | -0.329063584 | [-0.167945660, 0.255921531] |
| 2014 | -0.350153346 | [-0.255107544, 0.248806985] |
| 2015 | -0.367991921 | [-0.261608044, 0.263044654] |
| 2016 | -0.405900600 | [-0.476551721, 0.233388424] |
| 2017 | -0.414307983 | [-0.315769365, 0.265839026] |
| 2018 | -0.413381148 | [-0.243632835, 0.317079691] |
| 2019 | -0.410066578 | [-0.331139362, 0.277587105] |
| 2020 | -0.400531963 | [-0.407134260, 0.250786734] |
| 2021 | -0.391517617 | [-0.351853572, 0.278635937] |
| 2022 | -0.404503672 | [-0.321140588, 0.262179419] |
| 2023 | -0.400753116 | [-0.298404195, 0.255233350] |
| 2024 | -0.399200306 | [-0.229589869, 0.288239515] |
| 2025 | -0.406648091 | [-0.287455546, 0.327940386] |
| 2026 | -0.407081287 | [-0.371481856, 0.245095864] |

| 固定门 | 结果 |
|---|---|
| `all_2010_confirm_lower_positive` | false |
| `all_2010_paired_lower_positive` | false |
| `all_2010_participation_lower_positive` | false |
| `family_0_primary_confirm_lower_positive` | false |
| `family_0_primary_paired_lower_positive` | false |
| `family_1_primary_confirm_lower_positive` | false |
| `family_1_primary_paired_lower_positive` | false |
| `four_complete_years_paired_lower_positive` | false |
| `partial_2026_confirm_lower_positive` | false |
| `primary_confirm_lower_ci_positive` | false |
| `primary_fill_dates_at_least_60` | true |
| `primary_fill_families_at_least_8` | true |
| `primary_paired_lower_ci_positive` | false |
| `primary_participation_lower_ci_positive` | false |
| `same_mask_cost_1R_primary_confirm_lower_positive` | false |

总门false，15门仅样本支持量2true/13false；`entry_increment_detected=false`。两期间共享bootstrap索引SHA为2010+ `f394bca43850bdce417cf2664a80142142c703bad1c11ee48839b3433933bed4`，2020+ `5c0b1b714adfa5aac8e05636efabd8d8b26606cf46693031b1dcf3a9c24321de`。无事件日期保留NaN后按完整源网格抽块，各指标共用索引。

期末权益/总收益/最大回撤/Sharpe/实际滑点/交易次数/现金胜率均N/A，本次0账户与金融回测。0.2R/1R仅研究预算，不是历史实际成本；没有保证金、容量、涨跌停、跳空排队或真实tick成交保证。

## 产物绑定

最终目录`outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/`有完整399252行事件gzip、六份日期表（main/两family×两个期间）、全部年度/期间/门/CI的metrics、来源与协议绑定、终态及manifest。`artifact_inventory.json`显式声明全部新产物角色，原cache只引用且false。

| 文件 | SHA256 | role | reproducibility_required |
|---|---|---|---|
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage018_entry_confirmation_experiment.py` | `e50126b4833b21005b775e41209c89e9a762b705159762f3b8bd2233c37aacb2` | `feature_contract` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage018_entry_confirmation_experiment.py` | `dfb0b92833bbd37097458ef0ec9f17fffe58c98532c9c21e9d1fdf0c025cfd6c` | `feature_contract` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/manifest.json` | `0d0bce1477ca430f85f1720005715f73318e6199a152bcfbad61d1847e018b8f` | `qualification_evidence` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/actual_terminal.json` | `417e5a1b4f2f78bc39f7dc7756dc977b22a0fc5a2146bb676503b1aa5a7562ec` | `qualification_evidence` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/metrics.json` | `5f51593ccfc539131003453fc62196cbe51ec60e79cb0798162fc8f994c1d9d6` | `decision_asset` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_input_boundary_fixes/event_intervals.csv.gz` | `a61cf6718b1179fab6bf824ab8ba6cbc93485a53361ed0e4240987e56f91bf6a` | `decision_asset` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment/actual_terminal.json` | `eb076fecec122d5cf20ec67043f58b342e2044d10c0728cf6f5d3077eb3605ab` | `qualification_evidence` | true |
| `/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage018_entry_confirmation_experiment/experiment_after_calendar_boundary_fix/actual_terminal.json` | `c2ff822677a2c14ac4a76a2a5b8ec78eec6e017419cfe34b92e84db020369fa2` | `qualification_evidence` | true |

## 结束判断与交接

新增选参过拟合：**否**。两次修复是有完全差集/原价比较证据的输入与浮点适配，未变政策、参数、母体或判据；前两失败未形成可用于救参的政策统计，失败记录完整。当前长期研究选择风险不消失。

继续价值：**当前全ready、仅u.high确认这一固定形状继续救参的价值否**；稳健正效用及相对/参与率增量门均未过，日线时间顺序歧义较大。不从本次结果挑setup、stop、年份或品种，也不以增加投注掩盖信息不足。继续原全市场高质量做多目标可保留，但本阶段不另开模型或分钟工程。

结果已立即交root及019作一次独立代码+真实全表/指标/CI联合审查，作者不自签结果资格；`real_economic_labels_ready=false`、`financial_ready=false`、`production_qualified=false`。不更新LINE/registry，不commit/push，不再运行或补小修，等待独审。
