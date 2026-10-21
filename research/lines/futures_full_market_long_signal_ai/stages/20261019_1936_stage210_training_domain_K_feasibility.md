# Stage210：训练行动域与 K 退出目标的可比性可行性

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 19:36 CST。
- 模式：只读小 manifest / 接受合同 / 源码的可行性判断；非重要突破，不是新标签、拟合或现金实验。
- 先读 registry、LINE、208最终决策及209小提案；208关闭固定 q53/Ridge/K 的结论不变。205/209及其他既有材料不修改，不复活103 log代理或局部弦 q。
- 本阶段未打开原 actions、COMMON、六个 train cache 内容或 native cache 数组；未读取行情大表、扫描 SQL、重审接受数据，未运行源 helper/authorizer/actual。
- 新 fit/cash/SQL/标签/预测/选择/价格数组读取/大输入 hash 均0；累计仍427 fit / 230 cash，无新金融指标。

## 结论

**最小下一步是仅盘点旧训练行动域是否包含当前 D≥K 的动作。** 六个130训练缓存已含身份、u_index、reference_epoch 和 sample_weight；配合同一5587日源日历与156的 `calendar_boundary`，足以统计各折 D<K、D≥K、K未知的行数及原权重质量，不需要原 actions、COMMON、价格缓存、标签值、拟合或现金。

此盘点尚未运行，不能预报被排除比例或判断 alpha。root已选择该单项方向，后续由单独213协议约束、214工具实现，actual仍另行精确绑定。Stage210只冻结下面的可行性与停止边界。

**不能把三件事混成“只换目标”：** A训练行动域对齐（原Y不变）、B同一可比域内退出Y→Y_K、C用新的成熟/持有区间重算样本权重与scaler。若训练身份、样本权重和设计基底任一不同，130旧拟合就不是“只换Y”的精确控制；156/157仍是冻结历史benchmark，但不能据其与新模型的现金差单独归因于目标。

## 现合同的明确事实

### 130原训练与129标签

[130 `fold_slices`](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:60)的训练条件是原 `u_action_eligible=1`、`closed_complete_bar_model`、u与非空 label_known_date 均严格早于cutoff、stress Y有限；held另按固定family哈希排除。没有156的D<K条件。

[129 action模拟](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage129_contract_choice_dataset.py:212)在u检查同epoch历史、经济资格、anchor、原生命周期、u成交量支持一手往返。其D=u_index+1为同源日历后继，不是下一有报价日。缺D报价为execution unknown，F≤u low20或无效SL0为已知不参与，后者诊断0与trade target null分开。

原Y=`每lot stress净PnL/(0.25*N_u*multiplier)`，不是含费预算风险分母，也不是组合复利。标签在实际退出日的 `after_all_source_close` 已知；只在完整闭合路径有trade target。原路径先应用已锁定的force，再开盘gap/日内stop；存续时更新20low，并按不可变u anchor发次日退出请求。缺持仓bar使unknown吸收，不拿后一个有效bar补成已知Y。

原action字段由129/070源码可定位，足够描述上述身份、N/low20/原价、入退出index/date、known date/phase、SL0/boundary、费用/滑点、per-lot PnL和label/unknown/cancel状态。**不存在已固化的全域Y_K字段。** 本次依据源码和小manifest，不读334.9MB action文件的内容。

[130权重](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage130_contract_choice_fit.py:36)由同family-u成熟动作的原 `[entry_index,exit_index]` 区间并集、family并发唯一性、动作数均分、等u质量后均值1得到。旧 COMMON scaler又使用这些原权重的训练内finite统计。因此仅删除动作、缩短区间或改变成熟域，原则上都可能改变权重、缩放与Ridge解，不能机械继承并声称已按新域重算。

| scope | cutoff | 已接受缓存训练行数 |
| --- | --- | ---: |
| main | 2020-01-01 | 247795 |
| main | 2023-01-01 | 445475 |
| holdout_0 | 2020-01-01 | 171712 |
| holdout_0 | 2023-01-01 | 297404 |
| holdout_1 | 2020-01-01 | 76083 |
| holdout_1 | 2023-01-01 | 148071 |

这些是fit_records原接受计数，本次未重新数行。六缓存覆盖重复历史身份，不是六份独立市场经验。

### 156/157的K与132价格缓存

[156 `calendar_boundary`](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage156_voluntary_choices.py:40)按完整YYYYMM，取名义合约月前月首个源交易日。全前向动作先D<K、原score>0、原u资格，再母内排序和ordinary/F固定优先。K在样本后不夹到末日；`after_calendar_pending`也不能伪造K日。

[157 `apply_boundaries`](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage157_voluntary_cash.py:59)只改私有signal的生命周期为min(原生命周期,K)，通过prev(K)收盘请求下一K开盘退出。[131 cash adapter](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage131_contract_choice_kernel.py:90)还包含各账户占仓/资金/整数预算/风险减仓、缺价deferred理想退出和全买卖容量审计；这些不是129单动作Y的全部语义。

132的948字节cache metadata及[持久化/恢复源码](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage132_contract_choice_review.py:735)说明已存9520 epoch、1552456行的days、OHLCV、accepted/valid、N、low20、run；full calendar与economic_projection沿接受合同绑定。技术上有离线构造单动作路径的原料，157已证明可复用而不新SQL；**这不等于Y_K已经生成、全域支持已核或真实成交已认证**。本次未打开110.3MB cache，也未打开8.1MB economics projection。

原129序列对象与132恢复dict接口并不直接相同；未来若另签标签工作需一个小接口适配及新边界fixture，不能直接调用旧actual或hash-heavy全输入loader。没有新价格下载的必然需求，但当前可行性不能取代实际支持验收。

## 必须拆开的三个轴

设T0(c,s)为130已接受训练集合；G_K(a)由u当时已知身份、D与源日历决定，表示D<K；M_K(c)表示新K目标已知且严格早于cutoff。以下只是定义，未计算任何新集合。

| 轴 | 固定/改变 | 对旧控制的含义 |
| --- | --- | --- |
| A：训练行动域对齐 | 原Y不变，仅关注T0中G_K是否成立 | 0fit域盘点可直接复用六缓存。若未来真删行训练，控制130可作“旧全域→新域政策包”的历史控制；它不是新域内Y比较控制。若又重算权重/scaler，应另承认这些变化 |
| B：同域退出值 | 在共同身份、同权重、同设计、同截止时钟下比较原Y与Y_K | 只有旧T0全部满足K资格且新Y_K全可知、同时权重/scaler不变，130才有条件精确复用。当前元数据未证明这个桥；不能先假设通过 |
| C：成熟/区间权重 | 因K提前退出，纳入更早成熟的新行，或以K区间重算union/concurrency/等u权重/scaler | 这已改变训练测度；旧130不是对应新域/新权重下原Y拟合解。纯target比较必须有共同域、共同权重和共同设计的原Y新控制，不能称旧控制零改动 |

对A的盘点优先于B：它回答一个完全事前、无需Y/价格、可机械证伪的支持问题。即使盘点发现大量D≥K，也只说明旧训练域与新可行动域不同；它不证明这些行损害了学习、原Y错误或删除后收益会提高。

## 哪些身份和时钟可精确保留

**可直接保留的部分：** 原action_id/sequence、mother、exact product/family、u/native index、epoch/anchor；COMMON52列及原missing语义；原cutoff2020/2023、scope哈希、前向完整身份与原K选择规则；Ridge参数和既定风险/成本口径。前向即便D≥K、missing或no-child也保留身份，K只控制可选动作，不把未选事件从母体消失。

**可保守固定但必须正确命名的部分：** 若未来对Y_K只用原成熟T0，仍可按原Y已知时钟作为共同保守训练闸门；它会刻意丢弃K新近成熟的额外样本，检验的是固定旧成熟域内目标值。应另存真实K known date/phase，不能把原label_known_date伪装成K真实已知时刻。

对D<K且原Y为连续完整闭合路径的同动作，若采用同一孤立bar研究模型、仅增加K force，通常可使K退出不晚于原退出，从而已接受原成熟行有K目标提前可知的条件支持。但**这不是全域证明**：K资格、源日历、force优先、cost可表示性及chosen estimand均须先固定。若τ_old<K且其余政策相同，旧Y可机械复用；τ_old=K不能仅按日期复制，因为K开盘force可替代原本该日盘内boundary退出，费用/滑点也要从对应参考价计算。

**不能精确无条件保留：** D≥K动作没有可参与K政策的trade Y_K，不能为了保留T0把其trade target填0；原unknown/open/cancel不是负类。新K可能在原unknown之前已退出，或在原cutoff之后的闭合之前先成熟；把它们只加入K臂会混入训练覆盖/成熟效应。完整纯target对照应显式采用两目标共同已知域与同权重/设计，不能从两个模型各自闭合样本直接作因果比较。

权重也有两种不同问题：冻结旧w0和旧basis是“固定训练测度下换目标值”；重算K区间再共同用于两臂是“新K训练测度下换目标值”。二者不能互换名称。后者即使X列仍52也一般需要新原Y控制，因为同字段不等于同拟合问题。

## “同成交条件”目前真正的边界

可离线定义一个不含账户竞争的、同原入场/止损/anchor/研究费滑、另受K截断的**单动作理想per-lot Y_K**，并保留容量/缺价unknown。它仍不是同157真实账户约束后的可成交标签。

要把完整资金、占仓、same-day关闭、整数预算、risk-margin减仓和同epoch买卖共享容量也放入“Y_K”，结果就依赖整个账户状态和其他动作，不能再称只由action自身决定的独立监督标签。对每个动作都重复模拟自身账户会变成新金融实验，不能包装成0cash标签工程。

129缺持仓bar时unknown吸收；cash则保留stale/deferred理想后续退出并披露unknown。若要求两者完全同成交语义，这本身也是额外改变，不可悄悄夹进“K对齐”。同样，退出容量在131只是理想数量的审计，未进行盘口部分成交重写；不能用cache中的日量构造一个已经通过真实成交资格的Y_K。

## 最小可实施的下一合同：只有无收益域盘点

后续213/214应单独绑定以下范围；本210没有执行。

- 输入：130六份 `training_identity_weights.csv.gz` 的序号/action_id、product_id、family_id、u_date、u_index、reference_epoch、sample_weight；同一源calendar；130 fit_records和156原helper源码身份。不读Y、entry/exit收益字段、COMMON、价格或native cache。
- 计算：D=u_index+1，用156原calendar_boundary在训练epoch上计算K；不能仅复用156的forward boundary字典，因为2010—2019训练epoch不保证在其前向字典中。
- 输出：每fold的总行/总旧权重、D<K/D≥K/Kunknown行数与旧权重质量；按fold/year/family/product保存同一机械统计。分类必须照搬156完整gate，保留before-calendar blocked、after-calendar的D_before_target逻辑和D后继sentinel未知；不能仅凭K_index缺失就把可确定的156门判成unknown，也不能补造K日期。检查行数、权重和分组加总守恒，不读取任何收益排序。
- 原缓存数值是130已解析后17g导出；身份整数做严格整数检查，sample_weight直接round-trip恢复，不再次pd.to_numeric引入已知非幂等漂移。大缓存只沿接受SHA/size和前后stat，一份一次窄列读取，不重hash。
- 证伪与停止：六折全无D≥K且无未知，则A的域差异机制在这些旧训练行上无支持，停止域对齐方向；存在差异则只确立设计资格，不能触发fit或宣布经济收益。Kunknown或无法守恒时如实不完整并停止，不补源、不读Y寻找有利子群。
- 预算：0fit/0cash/0SQL/0价格/0标签/0预测/0选择，最多六次旧训练缓存窄读与一次小源calendar读取；未来actual须由root按最终源码精确绑定。该盘点不改变旧模型或账本，不是target-effect审计。

## 进一步Y_K工作目前的blockers

1. **估计对象尚未固定。** 仅K截断的孤立理想per-lot目标，还是还要改缺价defer、退出容量及账户条件？后者不能伪装成单一退出目标；本阶段不替root选择。
2. **旧T0的K行动支持未知。** 目前只有潜在差异的源码证据，没有行数/权重质量；先完成上面的无收益盘点，不能假定130桥通过。
3. **全域K结果与真实known_at未固化。** 132有原料，不是Y_K输出；当前不能宣布新标签支持、成熟行数或纯target对照已可运行。
4. **共同训练测度需要选择。** 删行、提前成熟、K区间权重/scaler会影响控制身份。若需要共同域新原Y模型，这是科学上新控制，不是已有130可免费替代；在预期辨识价值和预算未成立时应停止，不为补清单重跑。
5. **执行未知与历史反复使用保留。** 日线、静态经济快照和容量审计不等于真实成交；重新定义Y也不产生新信息或盲OOS，且可能成为失败后救参。

因此当前可实施的是A的机械支持盘点；**不是已经获准B重标、共同域回归、C重权或新金融**。旧130/156/157继续按原身份保存和引用；不因提出新问题而重审已接受结果或抹去208失败。

## 调研、结果和反思

方法资料沿用209已实查的[SPO原论文](https://arxiv.org/abs/1710.08005)、[作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)与[CME订单机制说明](https://www.cmegroup.com/content/dam/cmegroup/education/files/a-traders-guide-to-futures.pdf)，本次不重复网上或GitHub批次。判断以本仓当前接受合同与源码为事实源：预测误差与决策误差可不同，但不由此断言原标签错、没有alpha的根因已定位或应上SPO。103 logproxy与208 q包均继续关闭。

- 新增代码/模型/交易参数/回测结果均0；只新增本stage和小JSON。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。
- 开始/结束历史选择过拟合风险：**是**。已有427 fit/230cash是重叠同史研究，改变训练域/目标也属于研究自由度。本稿新增按收益调参：**否**，没有新收益读取、拟合或按成绩筛样本；不能称新OOS。
- 开始继续价值：**是**，澄清是否真的能复用控制，避免混合多个轴；结束继续价值：**是，仅限一次无收益训练域盘点**。立即重标/训练/旧数据全面再审的价值：**否**，估计对象与支持尚未清楚。
- 不改LINE、registry或根账本；本stage没有回测，后续若真运行任何模型/现金须另有冻结合同及独立review。
