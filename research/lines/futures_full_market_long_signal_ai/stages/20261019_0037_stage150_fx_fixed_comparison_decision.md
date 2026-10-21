# Stage150：单一滞后汇率信息对照结案

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 00:37 CST。
- 非重要突破；接受本次计算，**固定FX包不获支持**。完整全市场高质量做多目标仍 active，未完成。
- 本次只新增6次模型拟合、4个资金账户；旧控制模型/账本复用，不重训、不回放。累计397 fit / 206 cash。

## 结论及其依据

汇率加入后，2020连续压力成本收益由56.9355%升至86.2847%，其配对日log差均值95%区间下端为正；但最大回撤由−10.7284%变为−10.8982%，没有满足收益前冻结的“严格降低回撤”。2023冷启动压力成本收益和回撤均退步，第二组留出品种的已知等u增量为负。因此不能把主窗口利润改善解释为稳定优势，不能晋级或增加投注，也不据此改变方向、lag、窗口、模型、交互、品种、年份、止损或风险参数。

独立149接受完整新增资料/模型/预测/选择/held/资金/统计计算，剩余Critical/Important/Minor=0/0/0。算术正确与策略可靠是两项不同结论；旧CONTROL仍只是历史研究参照，未恢复任何资格。

## 调研与收益前设计

本包调研结论沿144—145保留：[ECB参考汇率](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html)提供EUR基准同批双币；[ECB发布时间变更](https://www.ecb.europa.eu/press/pr/date/2015/html/pr151207.en.html)说明时钟必须处理；[BIS Working Paper1083](https://www.bis.org/publications/working-paper-1083-commodity-prices-and-us-dollar)提示汇率/商品关系可能随结构改变；[Groen/Pesenti官方摘要](https://ec.europa.eu/economy_finance/publications/economic_paper/2011/ecp440_en.htm)不支持宏观变量平均必然改进样本外预测；[CurrencyConverter维护者](https://github.com/alexprengere/currencyconverter)提供官方ZIP获取参考。

判断：FX是国内COMMON/期限字段不能机械恢复的新增观测，值得一次有界检验；文献和开源工具均没有证明本中国期货日级窄损任务的alpha。057曾提出FX但未实测，不能称经济想法首次出现。本次不追加网络/数据下载或另调口径。

最终145协议18343B，SHA `be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270`。历史归档不是首发vintage：设n为u之前最后ECB行，d/w为原表前两行，S=CNY每EUR/USD每EUR，唯一新值q=log(S[d]/S[w])。保留同批、缺失不跳过、不插值；假设n欧洲日末已发布，赋值n+1上海08:00，u15:00后消费。该时钟保守但仍为历史重建假设，strict first-release PIT=false。

新增参数/字段：FX missing及训练样本自身标准化q两槽，共54槽。修改参数：无；删除参数：无。Ridge alpha=1、截距、成熟自身net_R_stress标签、family-u区间union权重、2020/2023×main/两held均沿原合同；原初始100万元、0.25N初损、1%往返日容量、u-anchor与D仅减仓、风险/费用/滑点口径不改。

旧六个52槽模型只有在成熟训练及完整前向两新增CONTROL列恒0、身份/权重/scaler不变时才复用；零列不改变原Ridge目标，桥失败整包停止，实际桥通过。FX自己对完整129域评分，不用旧B已选父域或正分池限制新臂。一个全局日级FX量也不是新的月份专属信息。

## 实际母体与执行次数

399252母行、1552456真实合约动作、98目录代码/95 family/六所全部保留。146一次投影覆盖4074国内日期、4021不同release cohort、53重复as-of状态，母行缺失0；147完整前向966740唯一动作，missing0，main/held累计1933480新分数，每臂main161014父行、held并集161014父行。main选择CONTROL4917/FX4952，held0 2471/2497，held1 3861/3856；未观察/未就绪行不删。

| 阶段 | 实际工作 | 秒 | 结果 |
| --- | --- | ---: | --- |
| 146 | 一次源投影；0fit/cash/SQL | 14.870506 | exit0 |
| 147 | 六新FX fit，各一次；旧fit0 | 77.847026 | exit0，6/6完成 |
| 148 | 四新FX资金账户，各一次；旧回放0 | 23.882959 | exit0，4/4完成 |
| 149原审 | 源及六模型/全部分数/选择通过后，held控制别名衔接失败 | 69.649252 | exit1，原证据保留 |
| 149有限续审 | 仅held、四新资金、四CI及决策门 | 48.602097 | exit0，一次逻辑完整独审完成 |

审查器根因是已改名CONTROL_REUSED后仍筛B。仅修检查器这一处，保留原源码/失败/检查点；不重算已通过源、矩阵、模型或分数。两次审查启动、完整重审0，金融与模型重跑0；全部新增SQL/标签/下载/大库hash0。原审未持久数值最大误差，保持null；续审最大数值误差1.3969838619e−9，现金helper最大1.1641532183e−10，不将后者冒称全部原审误差。测试采用有限新增fixture，未重跑旧全套。

## 八个资金结果

各本初始100万元；CONTROL为原131B已接受账本引用；FX为本次新账本。总交易同时列成交记录fills和闭合笔数；胜率为闭合扣费净胜率。滑点已在成交价内，下列归因额没有重复扣除。权益是研究应计账本，非券商逐日结算现金。

| 起点/成本 | 臂 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总费用 | 总滑点归因 | fills/闭合 | 胜率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020连续/base | CONTROL复用 | 2,791,088.19 | 179.108819% | -15.055150% | 1.247484 | 59,041.81 | 147,866.66 | 2630/1314 | 14.079148% |
| 2020连续/base | FX新增 | 2,943,480.44 | 194.348044% | -13.854745% | 1.304850 | 62,704.56 | 155,396.76 | 2629/1313 | 14.775324% |
| 2020连续/stress | CONTROL复用 | 1,569,355.17 | 56.935517% | -10.728420% | 0.949132 | 57,124.83 | 127,727.14 | 1547/772 | 13.989637% |
| 2020连续/stress | FX新增 | 1,862,846.95 | 86.284695% | -10.898245% | 1.083437 | 65,398.05 | 145,533.02 | 1696/845 | 14.556213% |
| 2023冷启/base | CONTROL复用 | 1,841,968.60 | 84.196860% | -16.652238% | 1.296265 | 23,651.40 | 58,375.70 | 1098/548 | 13.868613% |
| 2023冷启/base | FX新增 | 1,866,630.47 | 86.663047% | -16.181000% | 1.329723 | 24,364.53 | 59,068.94 | 1124/561 | 14.973262% |
| 2023冷启/stress | CONTROL复用 | 1,524,031.51 | 52.403151% | -11.832908% | 1.210469 | 41,628.49 | 90,365.35 | 922/460 | 14.782609% |
| 2023冷启/stress | FX新增 | 1,502,805.49 | 50.280549% | -12.487702% | 1.198198 | 42,139.51 | 89,014.14 | 946/472 | 15.677966% |

新增回测结果为四FX；旧CONTROL结果未修改；删除结果0。原始年度切片、95 family含零网格、行业/普通F分组、最大盈亏与完整账本由148 manifest引用，年度切片不冒称独立冷启动。

## 四组配对置信度

收益差、DD差均FX−CONTROL；DD差正数表示回撤较浅。区间是**平均每日log收益差**，不是总收益百分点。复用原070固定2000次、252日块indices，不重新抽种子；两起点重叠、同史多轮选择、宏观同日重复以及归档可得时钟使区间仅为给定重建路径下条件统计，非因果或全新样本外证明，也未校正整条研究线多轮选择。

| 窗口/成本 | 收益差pp | DD差pp | 日log差均值 | 95%区间 |
| --- | ---: | ---: | ---: | --- |
| primary_2020/base | +15.23922415 | +1.20040448 | +0.000032356147 | [-0.000054623115, +0.000108289441] |
| primary_2020/stress | +29.34917875 | -0.16982408 | +0.000104346394 | [+0.000012752949, +0.000206785784] |
| cold_2023/base | +2.46618645 | +0.47123773 | +0.000014535545 | [-0.000042234897, +0.000080918939] |
| cold_2023/stress | -2.12260260 | -0.65479416 | -0.000015328360 | [-0.000065218236, +0.000033491375] |

## 完整留出域与未知

| 组 | family-u全行 | 已知增量等u均值R | 不同动作差异未知 | 同动作共同未决 | 状态 |
| --- | ---: | ---: | ---: | ---: | --- |
| holdout_0 | 62434 | +0.000221776396 | 5 | 38 | unknown |
| holdout_1 | 93651 | -0.001066620700 | 0 | 35 | unsupported |
| main | 156085 | -0.000164046378 | 4 | 56 | unsupported |

同动作共同未知只在差值内相消，不是基础路径已知；不同未知不填0，unknown_R_bounds保持null。main已知单位R略负与资金收益改善的权重、资金路径、参与集合不同，不能当作算术矛盾，也不能将资金差完全归因FX的稳定识别。139—142原资金归因不重做。

## 执行与长期未平仓风险

| FX窗口/成本 | 容量未知root | 入场未知 | 历史stale天数 | 期末开放/stale | 期末名义持仓 | 历史最大stale名义额 | 最低stale归零情景权益 | 最低全多仓归零情景权益 | gap损失>1R |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 48 | 4 | 1227 | 3/2 | 1,114,990.00 | 699,800.00 | 801,198.40 | -186,857.68 | 39 |
| primary_2020/stress | 24 | 1 | 1227 | 2/1 | 437,460.00 | 348,200.00 | 756,234.34 | 449,356.16 | 25 |
| cold_2023/base | 20 | 0 | 3 | 2/0 | 759,825.00 | 293,230.00 | 957,114.39 | 50,689.41 | 19 |
| cold_2023/stress | 10 | 0 | 2 | 2/0 | 250,740.00 | 251,340.00 | 966,056.09 | 497,788.99 | 14 |

四FX都存在执行未知和历史stale。2020基础账户期末包括SHFE.FU.202110（2021-09-16入场，7手）与INE.LU.202209（2022-08-16入场，1手）的长期stale，压力账户也有该FU；两本历史stale达1227天。这是重要的经济可执行性疑点，尚未证明源表缺失、生命周期还是退出实现哪一层为原因，也不证明它们造成FX收益增量。

零价仅是暴露情景，不是有穷万能损失下界；基础2020某历史日全开放多仓归零情景权益为负，不能由名义正权益断言尾部生存。0.25N初损也不约束跳空最大损失。不得删掉后来stale交易、事后挑可平仓样本、任造到期成交或改标签0来清除unknown。

## 最终门与下一步

四本自身收益为正且名义权益为正，但cash_nominal=false、held_known_nominal=false、nominal=false，financial/execution/held_signal_unknown=true，最终unsupported。strictPIT、稳定全市场优势、真实执行、增加投注、正式晋级与完整goal均未成立。

下一步优先做一次有界生命周期/退出事实核查：从这两只过期合约的已有open/position/exit-request和真实数据最末日定位链路，再与当时交易所最后交易/交割规则核对，区分正常有限未知与实现错误。先解释事实，不自动改策略或启动新金融回测；如果是共性实现错误，单独冻结修复与最小必要重算范围。此优先级不是新alpha，也不因单个赢家选择规则。停止本固定FX包方向/lag/交互/模型/月份/风险救参，亦不扩成全面旧资格再审。

开始与结束反思：新增按本轮收益调参的过拟合，**否**，单一q/模型/风险在收益前固定；同史多轮择题、最终归档和选择性叙事风险，**是**，因此不能称真正未见样本验证。继续救此固定FX包，**否**；继续原全市场高质量long目标，**是**，先处理1227天挂账这类可能影响经济结论的实质问题比继续堆特征更有价值。

本阶段仅普通研究记录，不改根memory/back_log，不Git提交/推送、不新建分支或worktree，不触碰正式/生产/CTP/订单/邮件/自动化。

## 可复验的本地证据

- protocol：[protocol.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage145_fx_information_protocol/protocol.json)；18343B，SHA `be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270`。
- projection_manifest：[manifest.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage146_fx_projection/actual_run1/manifest.json)；4705B，SHA `c8e9c1a86a125b136bd2f3bbcf4dc711173ee06f3bbb8bcba0fc9f0baac95334`。
- fit_manifest：[manifest.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage147_fx_fit/actual_run1/manifest.json)；21310B，SHA `2fb1895f6240cbe4f5c16196e1a80944c8daca04c8e248708df329e7ac9dafce`。
- cash_manifest：[manifest.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage148_fx_cash/actual_run1/manifest.json)；63348B，SHA `8a9f7836efeeb02331409a1a57134e67080a0b61926834ccfeae530693615258`。
- review_receipt：[review_receipt.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage149_fx_review/actual_continue1/review_receipt.json)；61055B，SHA `f0fb01b60741df8bac520f1c797aaaabfc580232c774630ecb9b40cceea39a86`。
- review_terminal：[actual_terminal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage149_fx_review/actual_continue1/actual_terminal.json)；377B，SHA `81bc34e5c9de597e69d6877c357e7b2423a09b828d13a5147af0db0d7a07cd27`。
- review_stage：[20261019_0012_stage149_fx_review_implementation.md](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_0012_stage149_fx_review_implementation.md)；14437B，SHA `e9ff8af5403628ce03abb2ecaf47bd77aa58e1177dfdb270d2effb1835beb080`。
- 决策与全部八本指标、四配对、held/未知及open快照：[decision.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage150_fx_fixed_comparison_decision/decision.json)。只引用已有大资产，不复制或重hash大库。
