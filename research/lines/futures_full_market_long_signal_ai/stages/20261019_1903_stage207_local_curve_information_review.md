# Stage207：局部价格形状单次信息实验的独立审查

- line_id：`futures_full_market_long_signal_ai`；已重新读取 registry 本线条目。
- 开始记录时间：2026-10-19 19:03 CST；工作区 `/Users/mac/Desktop/fian`，沿现有工作区，不改分支。
- 当前模式：独立审查 root 新冻结的 Stage204；与 Stage202 几何资格审查是两个不同阶段，不修改 Stage202 结论或记录。
- 协议：`outputs/stage204_local_curve_information_protocol/protocol.json`，独立核小文件 SHA256 为 `b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca`。
- 阶段性质：低先验、唯一便宜方向、53 维 Ridge 的有限证伪；非重要突破，非正式 C9/生产 A/B/C，不增加投注。
- 初始累计：**421 fit / 226 cash**；本审查不拟合模型、不重做源投影或回放资金账户；独立重算分数/选择仅用于核验既有实际产物。所有 actual 进程均由root精确授权并唯一启动。
- 当前状态：**2026-10-19 19:29 CST 全部独审完成，剩余核心阻断0；固定 q53/Ridge/K 包 unsupported，应关闭，不晋级、不加注。**

## 调研、方法与科学取舍

复用本轮 Stage198/199 已完成的历史去重、网上主源和 GitHub 调研，不为同一个 q 重复网络批次。既有一日 basis-momentum 可由 COMMON 两点基差恢复，旧 return~tenor 斜率已实测关闭，不能换名重训。三点价格局部弦线确实不是 COMMON 的确定函数；同品种不同月份承受不同交付时点供需压力，提出相对便宜方向有可证伪的机制。但 [Bianchi 等作者研究](https://arxiv.org/abs/2308.00383) 的曲率 spread 成本后弱/负，也未证明本线单腿 long 首次退出优势。

我的判断仍是：**几何通过不提升 alpha 先验，直接训练的正面依据弱。** root Stage203 已另行授权一次有限检验：已有固定52控制可复用；单一 q、无方向/窗口/模型/阈值搜索；若全部六折不能支持便宜方向，就停止在六次拟合、零预测/零现金。这个科学取舍可作为有界证伪接受，不能解释为外部文献背书或覆盖率证明有效。

固定六折标准化 q 系数严格负，是本线性表示的必要停止门，**不是显著性、因果或充分经济资格**。失败仅关闭这个 q/53/Ridge/K 包，不证明全部价格曲线关系无价值；通过则仍须面对预冻结的预测、held/K 与四现金门，不可把训练方向当 alpha。

q 的 missing 设计固定为有限训练均值处的 0；均值插补仍可能隐含覆盖交互。因此对比对象是 **q+固定均值插补的预测包 vs 既有纯 COMMON52**，不是“只分离数值几何且完全控制新 missing”的因果实验。不添加 mask-only 或其他模型来救结论。

## 预审和后续实际审查范围

继承 Stage132 已接受的 COMMON52、训练准入、union/等日权重与源身份事实；只读 Stage130 必要 `fold_slices/design/fit_cell` 方法及已接受审查摘要，不重审旧全域或重算旧权重。Stage205 的核心要求如下：

- 六个 scope/cutoff 使用相同训练 action index、已存 sample_weight、成熟原 `net_R_stress` 和对应旧 common scaler；不按 q 有无缩小训练，不重标签或针对 K 换 target。
- 所有六折先完成 q 的正 finite weighted population variance 支持检查，再允许任何 fit；q 只以训练 finite 值计算 mean/scale，missing 精确 0，无 epsilon、clip 或符号补丁。
- 只进行六次新53维 Ridge、alpha=1、intercept/cholesky 不变；全部六模型完成后才评估统一符号门。任一非负/非 finite 系数必须正常 `completed_hypothesis_rejected`，无 forward 预测、选择或 cash。
- 若符号门全部通过，再审所有新完整预测/held K/选择/四现金与固定置信门；不能为了潜在现金提前扩建无关工程，也不能重跑已接受纯52/main K/四控制账本。

实际数学核验只在 root 发出精确完成产物绑定后执行一次，不读取正在写出的 partial 输出。计划 q/common 各一次、六个旧 cached train 窄列各一次；独立重算 q 有限权重统计、新增 q 正规方程行/列/target 项，继承旧52+intercept块后核完整53+intercept正规方程和 portable 参数。不新建 observer/wrapper/子审，不运行旧 suite、源投影或拟合。

核算顺序固定为 `[旧52槽, q, 截距]`：旧53维正规方程的原截距位置52映射到新位置53，q放位置52。令 `s` 为本折 q 设计、`W` 为原缓存权重，则新增交叉项为 `X52'Ws`、`1'Ws`，q自身项为 `s'Ws+1`，新增目标项为 `s'Wy`；截距不加惩罚。这样可独立拼出完整54×54方程，核 portable 参数残差；不是重新拟合、重新计算旧52权重或以生产者自报残差代替验证。

## Stage205 核心源码预审

完整核读新 `stage205_local_curve_information_fit.py` 和三个新 fixture；独立运行仅本次新测试，**3/3 pass，exit=0，physical fit=0**。覆盖 finite train-only weighted q 统计、缺值质量不混入均值/方差、零方差/全缺失拒绝、原52槽不变、missing/均值 q 精确0，以及六模型唯一身份和任意非负/非 finite 系数时禁止 forward callback。未运行旧 suite。

最终冻结候选实现 SHA256 为 `a1d506d20110bd82bc9baf74546659d5ea46b8af86717328f18fadf456096b01`，fixture SHA256 为 `c8dbdbc121b4635c23bc1e0ea837f01696ffb8ba7b26dde5ab184071f9b881a2`。小源码核验确认其复用的 `stage130_contract_choice_fit.py`、`stage071_settlement_narrow_fit.py` 与已接受130 manifest一致；没有为了本实验改变旧控制函数。

关键逻辑符合预冻结204：原训练 masks 与旧 cached train 的所有指定身份/target字段匹配、直接复用其 sample_weight；全部六折先报告正 finite weighted q 方差并预检53设计，再进入一次六fit；原COMMON scaler不重训；所有六模型先保存、再统一严格负系数门。拒绝时 `completed_hypothesis_rejected`、cash_eligible=false，并在任何 forward/selection 调用之前结束。预审剩余核心阻断 **0**，已同步root可以冻结源码并唯一actual。

205只保存 portable53，不另存 joblib。该差别不影响固定 Ridge 的实际数学核验：拟合调用已冻结，portable 参数须和保存的 coefficient_with_intercept 一致，再以独立正规方程残差核验其唯一有限解；不为审查增加新的模型序列化工程。

授权前 root 用纯数值小反例发现缓存 IO 假失败：已由原130 parser解析的 float 写为17g，再次 `pd.to_numeric` 会有约1ulp漂移，严格 target 身份比较可能误拒绝，同时改变已存 weight。实现者只将 cached NUMERIC+sample_weight 改为 `astype(float)` 恢复IEEE值；原 actions 仍沿130 parser，不放宽身份相等或修改标签/模型。本审查只核这一 delta，独立运行新增 roundtrip fixture **1/1 pass、exit=0**，没有再次运行前三个测试或旧 suite。它验证 seed204 原解析 → 17g CSV → 字符串 → cached helper 后 labels、weights、所有数值身份均 `array_equal`。这是授权前的工程边界修复，发生时 actual fit/cash 均0；不算因结果失败重训。

## 第一阶段：六模型、完整预测、K选择与 held 实际独审

root 唯一运行 Stage205，六个方向系数均严格负，故按原204继续生成完整分数与选择；没有因符号翻转重训。随后 root 对独立 `stage207_local_curve_information_review.py` 作精确源码/输入授权，唯一运行审查。审查源码 SHA256 `403fbea4ae795ba26a625daf84b9d40b2cba29d1c1a759636150503af847bdd1`；仅两个新增方程顺序/held未知语义 fixture，**2/2 pass**。该核算不 import205，不调用 fit、策略 replay、权重重建或 SQL。

本阶段实际第一 phase **completed、核心阻断0**；receipt 为 `outputs/stage207_local_curve_information_review/model_forecast_selection1/review_receipt.json`，12,934字节，SHA256 `7f64a4e962cb387f87e5ddbe764e823ed7276f1df346bb54b4b85ed1cfb94448`。先落地 `models_checkpoint.json`，后续 cash phase 不重做模型或预测。

| scope | cutoff | 原成熟训练行 | q finite 行 | 标准化 q 系数 | 独立完整方程最大残差 |
| --- | --- | ---: | ---: | ---: | ---: |
| main | 2020-01-01 | 247,795 | 172,709 | −0.03726038833 | 3.87e−9 |
| main | 2023-01-01 | 445,475 | 332,898 | −0.04034735129 | 1.99e−8 |
| holdout_0 | 2020-01-01 | 171,712 | 120,650 | −0.04485342507 | 6.37e−9 |
| holdout_0 | 2023-01-01 | 297,404 | 221,830 | −0.03971663082 | 4.54e−9 |
| holdout_1 | 2020-01-01 | 76,083 | 52,059 | −0.01695263496 | 5.82e−10 |
| holdout_1 | 2023-01-01 | 148,071 | 111,068 | −0.03087694894 | 5.44e−9 |

独审 q/common 各读一次、六个旧 cached train 窄列各一次；全部 q weighted finite mean/variance/scale、精确 missing0、训练时间成熟与 family 留出、原 scaler/weights 绑定、53维 portable 与新 q 方程块已核。旧52+intercept块沿132接受事实继承，拼出的完整54维方程残差通过既定数值容差；不把对旧块的继承说成重新独立全域重建。

全部 `1,933,480` 个新 forward child 分数独立重算，最大绝对误差 `1.7763568394002505e−15`；完整身份、cutoff、ordinary/F、held family、q/missing 与每fold行数均通过。新候选 main `161,014` 母、selected `4,470`；held0 `64,077` 母、selected `2,150`，held1 `96,937` 母、selected `3,810`，held并集仍 `161,014`。控制仅从冻结130 scores计算必要 held-K 选择，分别 selected `2,111/3,766`；旧 main-K 与四现金控制均未重跑。

K 全池选择使用已接受156纯函数独立重算，逐字段对齐全部 candidate main/held/control-held 母行与所有 K boundaries；原始完整母体、no-child、D<K 后再排分及 family 优先保留。新 held 指标另行手算，没有调用205或130的 held 统计函数：

| held | 等 family-u 后等 u 已知平均增量R | 差异选择未知 | 同一动作未闭合披露 | 204 held 门 |
| --- | ---: | ---: | ---: | --- |
| 0 | +0.002263041394377146 | 7 | 23 | 失败 |
| 1 | −0.0008020094736690167 | 7 | 31 | 失败 |

同一动作增量为0只用于精确抵消，23/31个共同未闭合仍披露；不同动作的14个未知没有填0。**方向训练门通过，但两个 held 门已失败，任何后续现金成绩不能推翻这一事实。** root 仍按204完整检验执行四个新 funded book，是为检验原 R proxy 与真实资金路径两个不同量，并没有修改最终全部通过门。

第一 phase 实际审查计数：common/q/原actions/mothers 各1次，六 cached train 6次，新score1次、冻结旧score必要held选择1次、新choice表3次；fit/cash/SQL/source_projection/大输入hash均0。此后不再重复这些已经完成的模型、预测或选择检查。

## Stage206 源码预审与现金追加审查

只读核 Stage206 的新适配层和专用 fixture，不重跑其已有四个 fixture。冻结源码 SHA256 `295009d493bf0b0e6032936793b3a70f5f807ba3dadfc2ed4e83fe3ac55e3549`；核心阻断0。确认对照只能是 Stage157 自身四个 `VOLUNTARY_RESELECT` 账户，不能误取其引用的131历史账本；四本 CURVE53 各走独立现金/持仓/整手路径，未采用 matched-trade 净额。原128风险/.25N/1%容量、原K的 D<K/min(source lifecycle,K)、原070索引、四CI严格正及严格 held 门均保持；四 raw/checkpoint/financial terminal 先于 metadata，禁止已完成账户重放。

root 已唯一完成四本新现金，Stage206 manifest 为80,845字节、SHA256 `2e8cba428b04426a74fbd771298b88c71ccc37a8acf3a041980d76804873e9ad`。本审查追加脚本 `stage207_local_curve_cash_review.py` 仅复用已接受158/132/102纯数学检查，不 import206/205，不调用策略/account driver。两个新 CI/严格held fixture **2/2 pass**；随后由root另行精确绑定，执行下述现金追加审查。只追加新账本/fee/slippage/position/risk/accounting/四CI/固定门结果，不重审前一 phase。

cash1 独审首次运行在最前 terminal schema 检查失败（约0.197秒），未读 ledger/cache。根因是本审查器把206 `actual_terminal.old_control_cash_replays` 和 `financial_terminal.old_control_book_replays` 当成同一字段，生产者两个字段实际均0；不是现金算术或策略失败。保留 `cash1/failure.json`、原源码 `source_at_failed_attempt.py`（SHA256 `a8164e1cf01c81a4188320131c9050eb9eeb26c09b75245e89a55b1ec0532e31`）及原fixture快照。

仅对独审终态 schema 分支修复：共有完整计数检查保持，actual检查 cash-replays/baseline-replays，financial检查 book-replays。新增一个定向 fixture 已red→green，正确双schema通过、任一旧replay=1仍拒绝；未重跑已有测试/现金/模型。续审 fresh cash2 源SHA256 `25611fc81241bf6f9ca412abb59adc02de74da8df5ed76423d465e3451956daa`。该修复不修改206、旧控制或第一phase；cash2仅继续尚未完成的现金审查。

root 对修复后新文件重新精确绑定，cash2 **exit=0 / completed / core_blockers=0**，约28.03秒。完成 receipt 为 `outputs/stage207_local_curve_information_review/cash2/review_receipt.json`，31,272字节，SHA256 `2e2b272517c64638e0a4c3a361fcc41036e45764c580ed6755809556119e1fe2`。**cash1/cash2 是两个独审进程启动，不是两个现金实验；历史失败保留，原四个金融账户各仅运行一次。** cash2不读取或重算模型/forecast，不重放任何现金。

本次逐四新book复核 `6,690` 成交行、`8,738` 持仓日行、`5,116` 账户日行、`12,619` 预算/减仓记录，以及 `3,339` 已闭合 root 和4个终态开放 root。逐笔价格、整手量、手续费/滑点、现金递推、已实现/未实现净值、完整 root 数量、风险/保证金/费用预留、D只减量、source/voluntary共同强制退出、缺价/陈旧与容量未知、全部拒绝行均通过。初损仍0.25N，不把跳空损失截在1R；滑点已在成交价中，仅汇总归因，不再二次扣款。

原132 native NPZ只读取一次做新账本 native price/capacity 核，不重新hash、不读取数据库；没有第二次扫描旧actions大CSV。四控制只核自身157 summary/daily/diagnostic绑定及配对置信计算，不重审旧fills、不重放旧账本。模型/预测 phase 直接继承已完成小receipt。

## 已核验的四个新现金结果

共同参数：初始100万；`2020-01-01—2026-10-16` continuous、`2023-01-01—2026-10-16`独立cold start；base/stress沿原128成本；单family风险0.0025、总风险0.02、buffered margin上限0.25、margin buffer1.1、日量1%且预留往返一半，0.25N初损/自身low20/共同anchor与K，均不改。2026是截至10月16日的部分年度。新增信息仅单q第53槽及其fold train-only mean/scale；旧参数修改/删除0，q没有阈值、clip或新增mask模型。

| 新账户 | 期末权益（元） | 总收益 | 最大回撤 | Sharpe | 闭合笔数 / 成交行 | 闭合净胜率 | 总滑点归因（元） | 总手续费（元） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 base | 2,178,251.36 | 117.8251% | −13.5468% | 0.912910 | 1,377 / 2,755 | 12.93% | 165,029.50 | 61,238.64 |
| 2020 stress | 1,423,082.18 | 42.3082% | −12.6545% | 0.607323 | 982 / 1,968 | 12.73% | 183,062.84 | 74,287.82 |
| 2023 base | 1,713,541.09 | 71.3541% | −12.5197% | 1.135724 | 535 / 1,071 | 13.64% | 61,173.95 | 23,433.91 |
| 2023 stress | 1,407,591.34 | 40.7591% | −12.7097% | 0.943136 | 445 / 896 | 13.26% | 92,258.73 | 40,093.66 |

这些是唯一206回测结果的独立复核，不是本审查新增四次回测。每账户终态仍有1个开放root，不当作全部闭合盈利；总交易闭合笔数与成交行数分列。

| 配对窗口/成本 | 旧157收益 | 新−旧收益（pp） | 新−旧回撤（pp，正为变浅） | 同070索引日log增量95%区间 |
| --- | ---: | ---: | ---: | --- |
| 2020 base | 122.9270% | −5.1019 | +2.0806 | [−0.000172724, +0.000168238] |
| 2020 stress | 52.8420% | −10.5338 | −1.2952 | [−0.000173722, +0.000096142] |
| 2023 base | 82.5437% | −11.1895 | −2.6175 | [−0.000285324, +0.000152111] |
| 2023 stress | 52.6646% | −11.9054 | −6.2869 | [−0.000246564, +0.000080880] |

四组配对原日期、252日块、2000次原索引完整重算；所有增量点估计为负，四区间均跨0，没有一项满足 lower>0。仅2020 base DD变浅，主压力及两个cold成本DD均更深。两held门也均未通过。因此独立固定204 gate 与206一致：own_returns_positive_all_four=true，但 return/DD/四CI/held 门均false，`nominal_pass=false`、status unsupported。不是用一个中间proxy替代现金结论，也不是用现金覆盖held失败。

## 数据风险、置信度与最终建议

数学与实施置信度：在已接受原源/COMMON52/权重块的范围内为高，六新模型、全新分数、完整K选择及四新账本独审无剩余核心问题；不把旧块继承包装为本次从原始数据库重建。科学结论为：**这个固定 q+均值插补 /53槽 Ridge/K 包没有支持稳定收益与DD增量；应关闭，不继续扫符号、窗口、邻月距离、月份/产品、alpha、模型、score阈值或风险止损来救参。** 不把该阴性包无限外推成所有曲线结构均无价值。

实际数据限制保留：新四book容量未知成交分别 `38/18/6/1`，入场执行未知 `4/2/0/0`，历史stale日 `9/6/0/0`；四book均 execution_unknown=true。即使忽略这些未知，收益、DD、CI、held的固定门也已经失败，不需靠未知风险才否定。源仍是最终重建归档，不是首发release-vintage严格PIT；日OHLC/1%容量假设不能证明实际盘口可成交。2000次同史块重采样是条件历史CI，不是2000个独立市场或全新盲OOS。

继续完整全市场做多目标仍有价值，但本包不支持晋级或增加投注。root可在Stage208登记关闭结论，保留源几何新信息事实、全部负结果与工程失败链；不得把训练六系数负解释成跨周期做多优势。

## 本次变更与结果

- 新增：本唯一 Stage207、两个有限数学审查入口及各自两个小 fixture；对应两phase小 receipt/checkpoint。
- 既有策略/标签/控制脚本、交易参数、历史结果修改/删除：0；本审查适配修复仅如上终态schema分支，不改金融代码或结果。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：见上表唯一206结果的独立复核，本审查不新增金融回测。
- 本审查 fit/cash 新增：始终 **0/0**；root 已唯一实际增加6 fit /4 cash，累计 **427 fit /230 cash**。
- 不改 Stage204/205、LINE、registry、memory 或 back_log，由 root 合入。

## 开始与结束反思

- 开始过拟合风险：**是，历史同史反复择题及新特征尝试仍有选择风险**；本次参数、方向、训练、预算和停止门事前固定，避免新增成绩救参，不承诺新盲 OOS。
- 开始继续价值：**是，限一次低先验证伪**；方向门不支持时必须零预测/现金收口，不因六次拟合已投入而继续工程。
- 结束是否存在过拟合风险：**是**，同一历史累计择题/新特征选择风险不能消除；本轮是否新增按成绩救参：**否**，唯一便宜方向/模型/窗口/金融门未改，缓存和独审schema修复均不改标签、参数或金融结果。
- 结束继续本固定包的价值：**否**，既定假说已被完整检验否定，禁止为救包继续投模型/现金或扩审工程；审查自身已收口。完整全市场高质量做多目标继续价值：**是，但本包不给加注或实盘资格**。
- 精确终态：第一phase completed/core0；cash1 reviewer-schema失败保留、0native/ledger；cash2 completed/core0，只续四新book独审，0模型/forecast/现金重放。新增实际6fit/4cash，总计427/230；本审查新增fit/cash/SQL始终0。
