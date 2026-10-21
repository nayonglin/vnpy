# Stage219：DOMAIN52 固定 K 四本现金适配实现

- line_id：`futures_full_market_long_signal_ai`；时间 `2026-10-19 20:17 CST`，本阶段仅实现、定向 fixture 与交接，没有实际回测。
- 是否重要突破：否。该阶段没有金融结果，不能据实现或 fixture 声称模型改善。
- 外部调研沿用 Stage217 冻结的 misspecification/domain-weighting 原始论文与 GitHub 方法边界；判断是仅值得做一次固定 loss 支持域的证伪，不支持预判 alpha，也不复制复杂优化器。
- 新增工具 `tools/stage219_training_domain_loss_cash.py`；为 Stage206 四本适配的最小独立复制，候选名称 DOMAIN52，仅改变217/218 lineage和累计计数；没有修改旧工具、旧全局 ARMS 或正式策略。
- 源码 `33687` 字节，SHA256 `3f216513c51025b5453b40ce9fce2169bf04ccc829c22e115726b21e47d5fb8b`；fixture `10201` 字节，SHA256 `0b7a634d2241009b319f96cf23df432feb84d140514f2bdd358010faaba83571`。源依赖集合由 `source_bundle()` 生成，必须等待218最终冻结后由root绑定。
- 四个必要定向 fixture：四个新臂及旧157自身只读身份；严格四CI/held/primary收益DD门；合成四本 raw/checkpoint先于metadata及禁止完成账本重放；218完整6fit/无动作变化现金硬停门。首次四个0.279秒通过；新增selection_identity小收据硬门后只扩展最后一个fixture再执行，0.024秒通过，另三个没有重跑。旧206 suite、旧账本均未运行。
- root cash auth：`stage217_exact_root_cash_authorization_v1`、root/cash/exact_source_authorized；217精确SHA `b86c21d02b70e55181b7324efc1ebb6b363ee9d842738efe0f2baedfc3747b53`、fresh输出、冻结source_bundle、217全部input_bindings加218 `fit_manifest/choices_main/boundaries/held_diagnostic`。工具另从218已绑定manifest读取selection_identity小收据，要求完整161014父行、changed_parent_rows>0、identical_actions=false、cash_eligible=true。
- 218必须completed、现金资格true、恰6次fit尝试与完成、完整protocol/source/input lineage与对应terminal；218无动作变化或失败的正常停机不能进入现金actual。未引入旧q系数门。
- 只复用旧157自身四本 `NARROW_VOLUNTARY_RESELECT_*` 控制，source_only=true/replayed=false；不调用旧157指向131无K结果的baseline helper，不重训练、重预测或重选旧控制。
- 新金融预算最多4本：2020连续/2023独立cold各base/stress，DOMAIN52每本自身现金递归。100万元、0.25N初始止损、单family风险0.0025/总风险0.02、buffered margin cap0.25、buffer1.1、参与率0.01、原费滑/tick/anchor/K/整数预算/优先级均不改。
- 132接受cache单读、0SQL、新标签/价格/分钟/下载/旧重放均0；继承070原bootstrap indices。所有四个paired日log CI下界严格>0，held两组已知增量严格>0且distinct unknown0；primary 2020stress收益与DD严格改善，其余三本收益正且不退化。现金不能覆盖held失败。
- 四本raw ledger/checkpoint、金融terminal先于metadata；有attempt/terminal/目录即拒绝重放，元数据失败不得重启已完成book。每完成一本累计cash=230+n；218恰六新fit完成后累计fit=433，四本全成时433/234。当前实现期累计仍427/230；不能提前计入预算。
- 新增参数：无；修改/删除既有参数：无。新增/修改/删除实际回测结果：均无。期末权益、总收益、最大回撤、Sharpe、手续费、总滑点、总交易次数及胜率均N/A，待root唯一actual和220独立核验。
- 运行前/后过拟合风险：是，历史反复择题风险仍在；实现未按任何新收益调参，fixture仅保障授权、身份和账本纪律。
- 是否仍值得继续：是，固定52维同target同执行，仅loss可行动域干预能被原控制有限成本反证；若固定门失败就关闭本包，不用模型、权重、K、止损或风险救参。
- TODO：220源码预审及218最终源冻结；root若签精确actual仅执行新四本一次，之后220只核未完成金融阶段。完整用户目标、未来跨周期/执行/加注资格均未达成。


## root 唯一 actual 四本终态与完整金融记录（2026-10-19 20:25 CST）

以下追加 actual 结果，保留上文实现期“0新现金”记录作为当时快照，不覆盖或混淆预算与实耗。root session `45782`，开始 `2026-10-19 20:21:47.941054 CST`，完成 `20:22:14.010265 CST`，elapsed `26.06907762499759` 秒，exit `0`。started/completed/raw-checkpoint=`4/4/4`，actual fit `0`、新现金 `4`、旧控制重放/SQL/新标签/下载/全库hash均 `0`；累计 `433 fit / 234 cash`。本次仅读取小 summary/comparison/diagnostic 与 terminal/manifest，没有读取大账本或重新执行。

**是否重要突破：否。** primary 2020 stress 收益小幅增加 `1.686429pp`，但全部四本回撤更深，其余三本收益下降，四个增量 CI 均跨0；两held已知均值小正仍各有16/7条distinct unknown，冻结门不通过。**Stage220 对本次四本实际现金的独立审查仍 pending**；本记录不是实际复审收据，最终路线决策由root Stage221结合最终审查作出。

### 变更、参数和对照口径

本包只将原 COMMON52 的成熟训练loss样本限制到事前固定 `D<K` 可行动域，原Y仍是原129首次退出stress净R，沿用原scaler与相对训练权重，并以 `W/W_A` 保持总loss质量；不是新增feature、新target、K截断标签或因果收益证明。Stage218六个新 DOMAIN52 模型按原Ridge1/52维完成，本阶段不再fit。新增现金结果四本；既有结果修改/删除均无。现金参数新增/修改/删除均无：100w、0.25N、单family0.0025/总风险0.02、buffered margin cap0.25、buffer1.1、参与率1%、原tick/费滑/anchor/K/整数化与ordinary/F优先顺序保持不变。固定bootstrap为原070、2000次、252日block，未重生成索引或修补wealth log。

原157自身四本是完整接受的COMMON52+同K只读控制，`source_only=true/replayed=false`，不是131旧无K引用；新 DOMAIN52四本各自递归现金、手数、持仓与资金占用。2020continuous/2023独立cold均截至2026-10-16，窗口共享历史，不是相互独立的盲OOS。

### 完整八本账户摘要

金额单位为元，胜率为已关闭episode的净PnL胜率。滑点已经进成交价和现金PnL，下表只作归因，**不得再次扣除**。closed trades与BUY/SELL fills分开列示。

| 账本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 手续费 | 滑点归因 | closed trades | 已关闭净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 新 DOMAIN52 · 2020 base | 2,133,245.62 | 113.324562% | -17.048641% | 0.889222 | 66,024.38 | 181,052.86 | 1,641 | 12.492383% |
| 新 DOMAIN52 · 2020 stress | 1,545,284.00 | 54.528400% | -13.831021% | 0.762467 | 82,906.00 | 208,263.30 | 1,178 | 12.054329% |
| 新 DOMAIN52 · 2023 cold base | 1,742,914.06 | 74.291406% | -13.084681% | 1.172309 | 24,195.94 | 62,779.99 | 599 | 12.353923% |
| 新 DOMAIN52 · 2023 cold stress | 1,453,839.49 | 45.383949% | -13.369355% | 1.009409 | 39,130.51 | 91,488.75 | 481 | 12.266112% |
| 旧157只读 · 2020 base | 2,229,270.22 | 122.927022% | -15.627420% | 0.978453 | 52,034.78 | 140,259.04 | 1,295 | 12.200772% |
| 旧157只读 · 2020 stress | 1,528,419.71 | 52.841971% | -11.359301% | 0.787447 | 68,710.29 | 167,960.05 | 952 | 12.079832% |
| 旧157只读 · 2023 cold base | 1,825,436.55 | 82.543655% | -9.902149% | 1.320956 | 20,778.45 | 53,623.57 | 494 | 12.955466% |
| 旧157只读 · 2023 cold stress | 1,526,645.82 | 52.664582% | -6.422761% | 1.223020 | 36,269.18 | 83,952.08 | 422 | 13.033175% |

| 账本 | fills | 累计成交手数 | 最高buffered margin | 最高frozen initial risk | 容量未知roots/fills | 入场执行未知 | 历史stale日 | 期末open/stale |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 新 DOMAIN52 · 2020 base | 3,284 | 10,503 | 426,401.80 | 16,500.29 | 43/43 | 4 | 7 | 2/0 |
| 新 DOMAIN52 · 2020 stress | 2,362 | 4,788 | 355,572.80 | 7,500.61 | 19/19 | 3 | 3 | 2/0 |
| 新 DOMAIN52 · 2023 cold base | 1,200 | 4,000 | 342,339.25 | 13,844.86 | 9/9 | 0 | 0 | 2/0 |
| 新 DOMAIN52 · 2023 cold stress | 964 | 2,208 | 336,129.20 | 6,921.34 | 6/6 | 0 | 0 | 2/0 |
| 旧157只读 · 2020 base | 2,592 | 8,385 | 435,693.50 | 18,229.08 | 40/40 | 2 | 9 | 2/0 |
| 旧157只读 · 2020 stress | 1,912 | 4,047 | 318,089.20 | 7,453.61 | 18/18 | 2 | 5 | 2/0 |
| 旧157只读 · 2023 cold base | 990 | 3,472 | 361,550.20 | 14,125.25 | 9/9 | 0 | 0 | 2/0 |
| 旧157只读 · 2023 cold stress | 849 | 2,071 | 318,089.20 | 7,453.61 | 4/4 | 0 | 0 | 2/0 |

八本均 `execution_unknown=true`。期末stale为0不代表历史无缺价：新continuous base/stress为7/3日，旧为9/5日，cold四本为0日；未知容量与入场执行按原状态保留，不能写成真实订单簿可成交。八本wealth log有效，未发生账本定义的insolvency，但这不证明极窄止损可约束跳空损失或支持加注。新base路径的all-open-long-zero情景最低权益，2020为 `-170,677.45`，2023cold为 `-112,104.88`；这是持仓置零情景，不是已发生破产、严格价格下界或普适生存保证。

四本新账本的closed数量、手续费和滑点归因均高于对应旧控制，同时选择、持仓路径和现金也变化。**没有做成本或交易数量的因果分解，不能把收益差全部归因于更多交易或更多成本。** 本次数据只支持上述共同观察以及固定整包的比较。

### 固定 paired 日级log-growth比较

CI单位是每日log-growth差，不是收益百分点；收益和DD差才以pp计，DD差正为更浅。复用既有070同组索引，未重放旧控制、未加epsilon、未将破产log置0。

| 窗口/成本 | 收益差pp | DD差pp | 平均每日log差 | 95% CI下界 | 95% CI上界 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2020 base | -9.602460 | -1.421221 | -0.00002679835040 | -0.00023849600407 | +0.00022703833069 |
| 2020 stress | +1.686429 | -2.471721 | +0.00000667886884 | -0.00014963515107 | +0.00016839563051 |
| 2023 cold base | -8.252249 | -3.182532 | -0.00005055814956 | -0.00025617421056 | +0.00021537406583 |
| 2023 cold stress | -7.280633 | -6.946593 | -0.00005340445124 | -0.00021796957896 | +0.00009509887745 |

主2020stress自身收益由旧 `52.841971%` 到新 `54.528400%`，但DD由 `-11.359301%` 到 `-13.831021%`，变深 `2.471721pp`，不能称为更高收益且更低回撤。其余三本收益各降 `9.602460/8.252249/7.280633pp`；四本DD全部变深，最严重为2023cold stress深 `6.946593pp`。四CI均跨0且下界为负，不能支持稳定正增量，也不能把跨0写成显著负增量。统计仅是给定这段历史、训练包及成本假设的条件区间，多轮历史择题风险仍在。

### 原 target 的held诊断与冻结门

held仍是原首次退出 `net_R_stress`：先family-u后equal-u；不是K现金target或资金收益。同一未解决动作增量0按共享路径处理并披露，distinct unknown不得填0。

| held组 | 已知equal-u平均增量R | distinct unknown | 同动作unresolved（增量0并披露） | 新/旧selected数 | nominal_pass |
| --- | ---: | ---: | ---: | ---: | --- |
| holdout_0 | +0.0012949367541513 | 16 | 22 | 2900/2111 | false |
| holdout_1 | +0.0010706489401883 | 7 | 31 | 4190/3766 | false |

两组已知平均均正，但16/7条不同选择的未知结果尚无有限R界，两个held门均失败；不能从已知子集小正推广到全组。即使四本现金改善，也不能覆盖此独立门。本次现金门本身也失败：`status=unsupported`、`cash_nominal_pass=false`、`return_gate=false`、`drawdown_gate=false`、`all_four_daily_log_CI_lower_positive=false`、`held_known_strictly_positive_all_two=true`、`held_known_nominal_pass=false`、`held_signal_unknown=true`、`financial_unknown=true`、`execution_unknown=true`、`any_historical_stale=true`、`nominal_pass=false`。`goal_complete/production_qualified/increased_betting_qualified` 均false。

### 冻结身份与输出

- [actual manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/manifest.json)：81462B，SHA256 `9dbf1bc4e7874b5b103784fcd16f319831b2050df761179d19befda6e492b823`。
- [actual terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/actual_terminal.json)；[financial terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/financial_terminal.json)。financial terminal中的metadata_pending=true是金融完成时的快照；实际terminal/manifest已经完整完成metadata，不是重新执行或第五本。
- [八行账户摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/account_summaries.csv.gz)，SHA `830d71a6df45f8b1517ea3f737d1d1744bd35a21ab8a8bba5c12a7aa466a20eb`；[四比较](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/comparisons.csv.gz)，SHA `4e49ed90a51cc20ff7a21782fa88371a275af6f8efa9f265a0116c558078e300`。
- [新账本diagnostics](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/diagnostics.json)；[旧157只读引用](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/baseline_references.json)；[continuation gate](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage219_training_domain_loss_cash/actual_run1/continuation_gate.json)；[原target held诊断](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage218_training_domain_loss_fit/actual_run1/held_diagnostic.json)。
- root现金授权 SHA `422bc88ac2e38e0a7c6f1ff2273a41dee6704e41b9384b7f17a2edf3ac138b91`；承接218 fit manifest SHA `c75dff54a0fa2b8fa0c0672314a2c98dc87487d5c00b64d7a5ff8c6b93fb47a8`；held SHA `a7419889f005d93f2901b83362054fd84a7cf1f2d2ecc929e2a3e568e9d65a98`。
- 同一manifest绑定各本完整raw ledger/checkpoint、signals/boundary lineage、年度、family-year/total含零、sector/variant及年度含零、尾部、bootstrap distributions与budget/tick披露。这里只读小摘要，无大账本重读、源码修改、行情下载或新fit。

### 运行后反思和后续

- 过拟合风险：**是**。相同历史上反复择题，冻结217与严格独审只能防本包事后改门，不能创造未见样本；本次没有按单本小胜挑年份、品种或归一权重。
- 是否值得继续本DOMAIN52包救参：**否**，按冻结门，四本回撤更深、三本收益退化、四CI与两held未知门失败；不得换域边界、K、scaler、模型、alpha、权重变体、target、阈值、stop或risk救参。这个判断仍待220实际金融独审排除核心算术bug后由root221最终签发。
- 是否值得继续完整目标：**是**。本次反证了一个具体训练域干预，不等于所有全市场高质量做多、AI或规则方向无效；识别优势、极窄止损和加注资格仍需分别验证。当前没有加注依据。
- TODO：等待220对本次四本实际现金/费用/持仓/CI的独立复审，只处理未完成审查阶段，不重训或重放完成账本；由root221结合最终收据决策。该agent只追加219唯一stage，没有改LINE/registry或根总账。
