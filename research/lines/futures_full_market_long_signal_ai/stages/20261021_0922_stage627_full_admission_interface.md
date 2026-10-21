# Stage627：完整52+K准入诊断的输入接口

- 2026-10-21 09:22 CST；研究线 `futures_full_market_long_signal_ai`。先读 registry，仅本线；非重要突破，不修改 LINE、registry 或正式版本。
- 本轮为接口核查，625 尚未冻结。恰读三份小 metadata：130 manifest、156 manifest、155 protocol；另查小源字段/选择逻辑和623既有交接，未打开分数、标签、母表、日历/indices载荷、actions、COMMON 或 native。0fit、0cash、0SQL、0下载、0Y读取、0实现；未跑 fixture 或旧 suite。
- 判断：**无需补数据、重训52或重建K标签，已有绑定足以实现一次完整E诊断。** 但只有 main 有已验收156选择表，held需要按同规则重建其正分＋K对照，不能冒称已有156 held成品。

## 精确输入

完整绝对路径、bytes、SHA及拟投影列已写 `outputs/stage627_full_admission_diagnostic/input_handoff.json`。所有大载荷仅 stat 相符，SHA继承已验收 metadata，不谎称本轮全量重验。

| 角色 | 现成来源 | bytes | SHA256 |
| --- | --- | ---: | --- |
| 完整 child 分数 | `outputs/stage130_contract_choice_fit/actual_run1/child_scores.csv.gz` | 124127126 | `e94b4d3d8d076edc7d76af4f219fc2cfc57f52b5e7eafeb8d4dedf98dbae8457` |
| 原母身份 | `outputs/stage129_contract_choice_dataset/actual_run1/mothers.csv.gz` | 19551936 | `4392e66061d77936aab4ece8aa414291f80da084a0cca0df7ca92a922da48130` |
| accepted156 main选择 | `outputs/stage156_voluntary_choices/actual_run1/choices_main.csv.gz` | 8476649 | `cce87a0012beb39ac64cd41c730215ffe562dc88f8a7b80ad71eb0a516fd9ddd` |
| 已有K标签 | `outputs/stage233_K_payoff_measurement/actual_run1/labels_K.csv.gz` | 205038809 | `b499a7a559ee7f8ada7f67631e665302bb3ffd3c92d6ca8121ce44d82fdcc1ec` |
| 原完整日历 | rollover线 Stage265 `rqalpha/trading_dates.npy` | 44824 | `57dd7f539d1cdbefb528978a6c7bd79b118790f933ce63c37b10747b999f9585` |
| 2020原block indices | Stage070 `cash/primary_2020_bootstrap_indices.npy` | 13144128 | `1991a9ba4cb6d71c17e08a639bf3e38c49d8c317e035b49c7ca9359ee0467ea3` |
| 2023原block indices | Stage070 `cash/cold_2023_bootstrap_indices.npy` | 7320128 | `957dd6dc9cedc126fe8d517daf698aae68876721c725ce6c338f36433157c9fc` |

130与156对分数、母表的精确绑定一致。原分数只有一个完整文件，不需再打开538：原实现写出14列身份/eligible/score/scope/cutoff，包含 main、holdout_0、holdout_1 × 两cutoff，不按正负分删除。1933480总行、main966740（2020折366634、2023折600106）、完整399252母/161014前向母、5587日历均是已验收计数，本轮没有重数。各 held 子折具体行数留待唯一actual输出，不补猜。

main覆盖所有family；held按 `int(sha256(family_id),16)%2` 分区，同一action有main和一个held预测，不是两个独立经济动作。2020-01-01至2022-12-31用2020模型；2023起至2026-10-16用2023模型；必须核原cutoff，不能混用未来模型。分数 `sequence_index` 是已核 action sequence alias，不是母 sequence；按 action_id连接K并核母、anchor、u等身份，不能只用epoch/date。

## 最小连接与保留原动作

先在完整分数定义E：原 `u_action_eligible` 与**纯因果calendar gate**，不得混入正分门、K已知、闭合、filled或未来收益。直接用156的 `new_eligible` 会丢负分并覆盖reason，不合本轮目标。复用156 `calendar_boundary` 的完整日历及D<K；after-calendar-pending用已知D早于目标月首判断，不虚构未来K，不把K截到样本末。

先按原156执行正分＋K的 product内 `(-score, reference_epoch, action_id)`、再普通/F及product等family优先，保留原赢家逐值；只有同family-u没有正分赢家时，才在同E移除sign一次求fallback。不能直接跨family取最高分，不能简单删sign导致普通负分替换原F正分。main用accepted156完整选择表复核原分支；held复用同纯规则，但另明示为重建对照。

K值取 `K_stress_net_R` 及其known/date/phase，不能拿无K前缀的旧 `net_R_stress`。primary明确 known_nonparticipation 的policy0可参与相应结果核算；nonprimary_noaction虽也存0仍在E之外。未知、右删失、不可表示成本保留，不能为凑完整结果填0；同动作的差为0与两个不同未知动作的差不可混同。单动作K一手净R并非157真实现金贡献。

预计唯一actual仅读母7列与小日历，然后对分数和K标签各一次组合gzip读取＋压缩字节hash，选列并保存供独审复算的小投影；先从分数决定动作，再消费Y，不以Y重选。accepted156只作原分支核对，不作E母体。旧indices为2000次/252block，复用不再生；具体诊断单位与未知处理等625冻结，不能将旧现金loggrowth CI直接改名为本轮R证据。不读旧52模型/scaler、COMMON、actions/native，也不重建权重。

保留的CLI位于handoff：`.py311/bin/python -B .../tools/stage627_full_admission_diagnostic.py --output .../outputs/stage627_full_admission_diagnostic/actual_run1`。**当前脚本尚未写，命令只是可实现入口，不是source-ready或actual授权。** 等625冻结后才实现唯一627工具与必要小行为fixture，root唯一actual；628已收到接口边界，后做一次独立源/结果审。

## 调研、价值与过拟合

本轮复用623及其引用617/621当天已核的原作者/GitHub方法边界：预测误差、动作准入和现金结果需分开，未为接口重复网络调研；本轮本机事实以小metadata与原选择源为准。它是针对完整拒绝域的固定诊断，不是新alpha或正式晋升。

开始/结束按新Y调参：**否**，没有读Y或改参数；长期同史重复研究的适应性过拟合风险：**是**，本轮不能追加阈值救结论。继续这个有界诊断：**有价值**，它能区分52+K准入是否比完整E更有选择性；重训、补GLD或重演现金：本轮无价值。全98/95和原无观察母行保留。

新增/修改/删除参数及收益结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A；累计551fit/290完成cash+旧partial1不变。

## 09:42 实施与 source-ready 补记（尚未 actual）

625已冻结，协议 `outputs/stage625_full_admission_protocol/protocol.json` 为16892B，SHA256 `a9f4363c6069fc95ad7e845e45fb925619ae69b73e256bd12010f67b4c484651`。按其完整合同实现单文件诊断，无新参数/标签/候选策略；没有新读取真实分数或Y。采用 test-driven-development 技能，只跑必要新增行为，按明确预算不跑旧大suite。

- `tools/stage627_full_admission_diagnostic.py`：30315B，SHA256 `90f33f4cc8803ddc5f028554f2dd632afe1cf21a2b1804649cc620aceceae673`。
- `tools/test_stage627_full_admission_diagnostic.py`：7148B，SHA256 `500963ea813ddd2c9a308daa91c610f05a31b07e3f297033e73a2394931b7b9b`。
- 8个新fixture首次实际8 FAIL（缺新实现的assertion，不是历史结果失败），实现后8/8 GREEN；最终冻结源对应一次8/8、unittest0.039秒、整个子进程0.112119秒、exit0。`fixture_receipt.json` 2664B、SHA256 `0fe9b52f27711f46f689059f559a5b57a572e1d2a9a61b3fdd5240d01cea710e`保存命令、输出与最终源/测试绑定。
- 行为覆盖：正分F不被负分普通替换、原rank/纯K去sign、主156身份保持与anchor异常、未知D、真实cancel0和非primary0/未成熟时钟、full未知与条件I分别计算、退化对比抵消、成对二元外界、同数量均匀期望手工枚举、完整source日期/固定indices、条件门不可冒称fullE成功。首个时间fixture在写实现前补入明确D日，避免把D=K误当允许。
- 原156只复用无数据副作用的纯函数；原源四份均由协议冻结。原52不fit、不加载模型、不改原positive policy。历史研究 **END=2026-10-16** 固定，和当前u20→D21前向判断是两件事；本入口与所有摘要明确 `current_day_close_dependency=false`，不等待今天收盘。

实际时将先落完整all-sign `forward_scores_slim.csv.gz`（原14列literal＋独立pureK/clock）和 `E_before_Y.csv.gz`，才一次读取K标签。母身份全399252与完整前向scope coverage另留；accepted156 main只作精确对照。`selected_K_literals.csv.gz`最终48列保留union E源身份、K值、未知/取消原因及各已知clock，不能只缓存已知结果；`E_linked.csv.gz`保存known/Y/原因但不逆向影响E。输入CSV各一次结合hash/parse，小日历和旧indices各一次，源码不打开actions/native/COMMON/model/GLD。

输出daily/windows/eras/annual及全部family-year零机会覆盖。完整E、known-I和二元界三层独立；全E有非零未知系数或membership unknown时fullDelta为null且不发其CI；k=0或k=n的差异代数为0不冒充信息量；known-I重新算nI/kI/pI。二元界先成对系数再包围未知Z，只有描述性，不当净R界/胜率或晋升门。固定旧indices配对所有scope，年度/早后段按原u日期；conditional与fullE分别判门，不把条件正向转为完整市场成功。

`outputs/stage627_full_admission_diagnostic/source_ready.json` 为6598B，SHA256 `4facde0cd61b0cb650367ead5335c5d49eed6d48bf9a5a09579491a2639dfcc3`，冻结协议、两份源码、真实测试收据、完整cache schema及精确命令：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage627_full_admission_diagnostic.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage625_full_admission_protocol/protocol.json --source-ready research/lines/futures_full_market_long_signal_ai/outputs/stage627_full_admission_diagnostic/source_ready.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage627_full_admission_diagnostic/actual_run1
```

本agent没有执行该命令。已交root与628一次完整源审，待GO后root唯一actual；source-ready本身不代表actual授权。此补记不更改冻结源码或数据。开始/结束没有根据真实Y调参；整条线适应性历史风险仍高，有价值的是一次不可救参的原模型准入诊断。财务指标仍全部N/A，0fit/0cash及累计551/290+旧partial1不变。
