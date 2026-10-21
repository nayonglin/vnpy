# Stage487：FOMC宏观包的最小预测与现金检验设计支持

- 时间：2026-10-21 00:46 CST；line_id=`futures_full_market_long_signal_ai`；非突破；**仅提案，未冻结、未授权或执行actual**。
- 已读registry、482及128/130/156/157源码与155/469/470/130的小JSON。未读取大actions、COMMON、saved scores、native价格、原始CSV/H5、SQL或数值标签；未做模型拟合、现金模拟、数据扫描、下载或全库hash。只写本stage和487小设计输出，不改LINE/registry/旧协议。

## 直接建议

根代理提出的**12个低维头、8本新现金**比最初6头更合理：A157使用原130的2020/2023两个模型fold，2023后底座确实变化，不能拿单一pre2020残差头冒称同一残差母分布。保留其六个52维模型、完整saved scores与157自身四账，只补B/C两臂、两cutoff、main/held0/held1的12次小Ridge。非事件日及缺测行，B/C逐值回退A。B只控制事前流动性，C加入匿名原变量主项与交互，所以C−B是**宏观数值包的增量**，不是纯交互、已识别货币冲击或因果效应。

本设计继承481/482已经核证的一手方法：[作者固定commit](https://github.com/marekjarocinski/jkshocks_update_fed/tree/f788aef7d573f87f28b70ffc3763e73c4886a53f)、[BoE1114](https://www.bankofengland.co.uk/-/media/boe/files/working-paper/2025/liquidity-monetary-policy-and-the-commodity-futures-market.pdf)的事前名义成交额暴露与交互思路；本阶段不重搜、不下载。判断：可作一次历史政策反证，不能照搬海外公告日结果，不能将FF4正号命名紧缩，不能以PCA、FUT补位、缩短25h或换窗口救参。所有时钟采用483/484已接受的25h、上海15:15假设，不采用482早稿18:00。

## 精确模型定义与训练边界

事件/epoch/pre_date仅取484已核请求；对应原actions的`action_id/sequence_index`。使用匿名`x1=FF4`、`x2=SP500`，保持原数值和缺失。事前`L=log(clean_single_sided_volume * contract_multiplier_cash_per_quote_point * settlement)`；V/S/M必须同exact epoch与pre_date，均为有限正数且来源身份成立。不重复乘volume_factor，不用close代S，不把缺行/坏值转其他源。

两臂共享事前可用mask：事件有合法pre/u/D映射、原两个数值均有限、exact V/S/M有效。mask独立于score/未来标签/是否赢家/closed状态。非事件、无事件子、任一字段缺失、pre缺观察等所有原因均留行并输出`head_state`；对mask=false行，`score_B=score_C=score_A`，直接复制原值，不能用近似加0改变round-trip。**B即使只需L，也必须因原pair缺失与C共同fallbackA**，否则C−B混入不同适用域。资格0仍保留，不能因它减少分母；原资格只在训练准入和选择时按旧政策生效。

六个cell=`scope∈{main,holdout_0,holdout_1}`×`cutoff∈{2020-01-01,2023-01-01}`。预测2020fold只用于[2020,2023)，2023fold用于[2023,2026-10-16]，与原score部署完全相同。训练明示u>=2010-01-01、u<cutoff，`u_action_eligible=1`、`label_state=closed_complete_bar_model`、`label_known_date`非空且<cutoff、`net_R_stress`有限及共同mask=true。held_h训练只用`sha256(family_id)%2 != h`；预测只用==h。事件若标签尚未成熟，只影响可训练支持，不能把未决目标当0。

每cell应用**同cell的原130 scaler/portable coefficients**，仅对事件训练COMMON行计算冻结`score_A_train`；目标`r=net_R_stress-score_A_train`。这不是再拟合52维模型，也不是新标签。因为原saved scores只有前向，训练基准值需要这一次冻结模型运算。它是底座的样本内残差，不能叫交叉拟合残差；后续时间/家族反证才检验是否有预测用途。该低维加法也没有将52列逐一作为nuisance，不能声称完整52维条件独立的新信息已证明。

同cell/B/C采用同训练行和权重：每事件u总质量相同，同event-u内每family等质量，family内所有ordinary/F及月份动作均分，最终权重均值归一为1。显式避免多月份伪增样本；事件重叠仍需后续依赖披露，权重不等于独立性。按root 00:49最终规格，先在每event全部事前可行动域（原u资格且155 D<K、共同source/raw有效）的完整横截面，对L作equal-family/within-family均分的事前中心化；不按mature/Y/held做事件中心。再在各scope/cutoff成熟训练内按上述训练权重求L/x1/x2均值和std；常量scale=1且显式报告，不为补秩换源/删列。B显式为`[1,zL]`，C为`[1,zL,z1,z2,zL*z1,zL*z2]`；交互后不另scale。alpha1只罚非恒项，截距不罚，weighted normal-equation solve每次计1fit，总12fit；不扫超参、不约束方向、不另做象限/门限。该纯小解与固定Ridge目标一致，不调用旧52维fit。

每个可用前向事件行：`score_B=original_saved_score + B.predict(...)`、`score_C=original_saved_score + C.predict(...)`。原saved score按原scope/fold读取一次，未受影响行精确复制。函数接口建议分离为`build_event_features(requests,pre_fields,raw_pair)`、`fit_residual_head(train,base_portable,arm,scope,cutoff)`、`overlay_saved_scores(original_stream,heads,event_features)`。现有`stage130.design`可复用冻结26+26缺失设计，`training_weights`不直接调用（这里是显式event/family质量），新训练矩阵最多5列加截距。

## 完整政策与现金入口

完整身份不变：399252原母、1552456原动作、六所98历史产品/95家族；2020+161014主母和966740主子、全部非事件日保留。全体forward子score流交给`stage156.select_full_pool(mothers, score_rows, calendar, '2026-10-16')`，过滤D<K后重新argmax，普通/F优先及score>0保持原值。held可按470 `select_scope`方式局部alias main调用纯selector，再还原scope，但不要采用annual的训练cutoff路由。不能拿旧已选/已成交157集合做新候选池；事件日可替换成原先没选的月份。每scope必须输出每个原母的选择/不选/无子/资格状态。

现金复用157 `make_voluntary_signals`/`apply_boundaries`和131纯内核，仅B/C分别2020连续/2023冷启×base/stress，共8新本；A**只读157自身四本**。不能直接启动157 CLI（硬编码4本、旧131B control）；新封装最多8本，共享一次native cache restore，零SQL、不重放A。2020连续在2023只切已冻结score fold，不重置账户；2023冷启为独立账户。原100万、.25N、family风险.0025、总风险.02、margin.25/buffer1.1、1%往返容量、整数、D开盘、20low/anchor及自愿K等完全不改；不新开止损/杠杆/阈值参数。全95family×year含零的权益分解，六所/98产品/ordinary-F和缺失支持单列。

精确复用定位（绝对根均为`/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/`）：

- 原模型与scaler：`outputs/stage130_contract_choice_fit/actual_run1/folds/{scope}/{cutoff}/{portable_model,scaler}.json`；六项bindings在`fit_records.json`，已读小metadata确认2020/2023模型不同。
- 原score：`outputs/stage130_contract_choice_fit/actual_run1/child_scores.csv.gz`，124127126B，SHA `e94b4d3d8d076edc7d76af4f219fc2cfc57f52b5e7eafeb8d4dedf98dbae8457`；主2020/2023预测子366634/600106。只读一次，非main966740行也保留held所需。
- 原actions/COMMON：`outputs/stage129_contract_choice_dataset/actual_run1/actions.csv.gz`与`common26.npz`；bindings从469 `input_bindings`继承。actions一次usecols流服务训练目标与新选择所需cash字段；COMMON一次读取仅提取事件训练行，不重算COMMON。
- 完整forward母身份仅取156 `actual_run1/choices_main.csv.gz`的7身份列（8476649B，SHA `cce87a0012beb39ac64cd41c730215ffe562dc88f8a7b80ad71eb0a516fd9ddd`），复原161014所有forward母，不能用其selected/score作为准入。held按事前family哈希分这个完整forward域。cash `organize`只建立逐日canonical映射，两窗口从空仓开始，2020+完整母足够；不重读129/470全399252母、227元数据。399252历史身份与98/95 roster使用接受484的provenance，明确此轮现金实际用全forward母，不能伪报重新核过399252源。
- A四账：`outputs/stage157_voluntary_cash/actual_run1/NARROW_VOLUNTARY_RESELECT_{primary_2020|cold_2023}_{base|stress}/`下summary/daily/ledger；manifest `0c27edef98e636032404272dda9e067e2794d7b7cf49e4ca5401b8b3ea34c7a4`。**不要用该manifest的baseline_books或原157 baseline_references**，它们指向131B。469 `cash_contract_inherited_exact.control_accounts_reused`已逐文件列出157自身bindings，可只读复用；不再调用469/470/471 actual。
- native cache：`outputs/stage132_contract_choice_review/cash_only1/native_store_cache.{json,npz}`；calendar与041现金乘数沿469 inherited market dependencies；原070两组252日/2000次bootstrap indices只读复用，不生成新seed。

## 判别力、未知与裁决

2010—2019最多82场事件、两个raw联合非缺至多81（复用477/478的141总/59个2020+及138/57联合覆盖计数之差；**不是新扫描，也不是实际成熟mask支持数**）。不能凭上万合约行说样本足够。B2/C6的强约束使一次反证可行，但真实成熟event-u数、参与family、overlap及设计秩要actual记录，后两年新增品种训练支持不能伪造。2023头纳入2020—2022已成熟数据，但每fold只有当时可知标签。held0/1是跨家族诊断，因共享宏观事件并非独立冲击复制；2020+时间反证也已被历史多轮研究观察，不叫盲OOS。2026尾部不成熟单列。

最小结果矩阵：C−B为macro package主要contrast，B−A用于暴露校准归因，C−A用于用户收益/DD目标。主2020连续stress要求C相对A与B的收益严格更高、DD严格更浅，并报原日log增长配对CI；其余三个窗口/成本C不得收益下降或DD恶化，C自身正收益/财富正。held两组按实际事前选择的原first-exit stressR配对差，同行同action消去可记0，distinct未知绝不填0；能翻转结论的未知/无界则完整held结论unknown。CI只保留现有条件性解释；另报事件u/路径重叠与删事件影响，不能给按54089子行计算的独立t值。根协议可更严，但不能看到结果后放宽门。

**政策fullscope与机制fullscope必须分开**：fallbackA使B/C是涵盖全部98/95的明确定义策略，完整现金差值可以估计这套策略的历史表现；并不恢复缺失pair/V/S/M，也不证明缺失产品的宏观机制。报告mask覆盖、缺失原因和状态，包括4029个旧pre无观察、全部无子/资格0；不能只展示有值98的一部分再称全市场机制。未决Y、stale/capacity/缺价按原现金未知保留，不因fallback或零交易而认证执行。原snapshot首次可得时间、跨年代单位/工具映射和逐事件消费时钟仍未认证，因此即便历史名义门通过，也不能称PIT/上线/窄损高下注合格。

建议一次合并执行：精确pre字段提取（沿482/484本地source预算）→唯一训练/score/selection→最多8cash→一个独立agent审数据/12头/全母选择/8账/未知/CI，不重训重放；无独立的经济诊断actual，不额外2次FWL，不重扫旧母体/旧回测。每个阶段记attempt/completed和不可变checkpoint；终端失败只修元数据，不重复已完成fit/cash。无成熟训练/非有限输入或解则停止当前固定包，常量按冻结scale1规则报告；不拿填补、FUT、窗长或新代理重试。

### 最小真实IO和纯函数接口补充（root要求）

129 actions唯一usecols流为原148 `ACTION_FIELDS`16列并上`sequence_index,entry_index,exit_index,entry_date,exit_date,label_state,label_known_date,net_R_stress`，去重后读取；只对484 event action IDs保留Y/成熟信息，同时把全部2020+的16列cash字段存为共享紧凑表。选择结束从共享表取B/C两臂chosen IDs并集，现金不再读129。不需要为不同scope/arm重读输入。COMMON NPZ一次仅提取事件训练sequence行；130 score一次，156 forward母一次，原native cache一次。源提取的exactSQL/CSV/H5属于488独立必要预算；经济阶段SQL=0。不把旧wrapper的`load_selected_inputs/execute`拉进actual。

`stage131_contract_choice_cash.make_signals(actions,mothers,choices,arm,market,dates,economics)`只需所选动作+完整forward母，不强制399252；局部choices将新臂alias为B、scope=main、policy=NARROW，结果arm恢复新臂。`stage157.apply_boundaries(signals,boundaries)`保持自愿/source min，不调用157 hardcoded ARM/4cash/131B control wrapper。`stage131.organize(signals,forward_mothers,dates)`返回potential与canonical refs；`stage131_contract_choice_kernel.run_cash_account(signals,market,dates,economics,cost,account_name,start,end,prepared=prepared)`才是唯一cash核。131 `make_signals`会用cached native独立重核N/low20/entrycap，原N/low/uclose保留供一致校验，不能视为可免quote数据。新wrapper由共享cache/内存选择给8账，A只读，不会再查129。

488将`source_numerically_verified`（exact row/identity/OHLC/finite positive/range）与067原`rule/lifecycle/value_observed/PIT`分列。建议本次条件历史数值研究用numeric-verified构L，不让_F历史规则未知抹掉已验证的原数值；原资格仍沿129及cash核，历史规则/PIT仍unknown，绝不因此获得执行资格。该取法需root协议显式写入，两臂mask共同一致。只用严格067也可定义另一条件策略，但不得结果后更换，两规格不能都跑。

## 终态与反思

本阶段新增fit/cash/预测/SQL/下载均0，累计仍481fit/258完成cash及1旧partial；权益、收益、DD、Sharpe、总滑点、交易次数、胜率N/A。新增/修改/删除已回测金融结果0。开始/结束按本轮收益选参：否，无新金融观察；长期同史适应性选题风险：**是且高**，12头/8账本身不能洗掉。继续价值：**是，限一次有约束的宏观包反证**；继续字段盘点、重复源扫描或把新旧残差混着解释无价值。用户更高收益/更低DD/全市场超高质量做多及极小止损加注目标尚未证明，goal active。此稿不签发actual；root需独立冻结唯一protocol、输入和预算。
