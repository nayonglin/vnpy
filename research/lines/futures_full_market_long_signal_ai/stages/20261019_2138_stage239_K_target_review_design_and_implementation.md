# Stage239：固定K目标实验的独立模型/前向/held审查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-19 21:38 CST；非重要突破、非生产。
- 本稿记录独审方法与工具准备，尚未由本agent启动actual或读取238的大输出。root另报告238完成；其经济结果以之后239实际独审及root最终裁决为准，本稿不先签接受。
- 已读237冻结协议（36,353B，SHA `8aad5f5b6afefec4b078ba7a32f48b806119977156ade22da04eb4e433885c06`）、236/235、217/218必要源码和小manifest。必要接口与238作者直接协调；238全面源码预审由另一agent负责，本稿未重复该工作。

## 科学合同与调研判断

未扩展外部搜索，沿237/236已核的[SPO原文](https://arxiv.org/html/1710.08005v5)、[作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)及先前数据复用边界。判断：same-C及固定坐标/权重可以识别有限学习程序的目标干预，不能自动解释市场因果、提供新信息或证明alpha。237无新增科学阻断；原DOMAIN52失败保持关闭，独审通过只接受算术与合同履行。

## 独立核法

1. 先核必要小链：冻结237、238精确源、root训练授权、源/输入/controls/folds相等、started/summary/terminal/source-read收据与计数一致、原三输入/六support/四control choices继承stat闭合。确认233/234标签资格及218/控制绑定后，才读大输入。不重hash旧大输入，不运行旧actual入口。
2. 一次读已接受233 labels的237指定列、原mother7列、COMMON数组与原calendar；六份218 support各一次，原scaler各一次。独立从旧state/u/旧known clock/legacy finite Y和family排除重建有序T，核support sequence精确一致；S=T[mask]，mask同时等primary与独立156日历数学。w直接用new_weight[mask]，不再乘factor，不重算uniqueness。
3. 六fold同C全部先验通过；旧T统计与S人数分开。新目标先复制legacy pd.to_numeric旧Y位值，仅primary潜在K报价分支解析233新token；原copy前缀token及旧位值保真。每个S行新strict stress known/finite、旧/新after-close clock满足tK≤t0<cutoff；新增744条known及旧Y未成熟行均不加入。失败仅审正常0fit停止，不补控制训练。
4. 复用已接受218 H0/r0，仅对S中exact `Y_K != Y_0`行独立计算`Δrhs=Z.T@(w*ΔY)`；H保持，intercept不受惩罚。核新存H/rhs/weight sum、portable53个系数，独立np.linalg.solve并核残差。沿220已接受容差，不调用estimator.fit；它不增加fit计数，也不是重训旧控制。
5. 逐块独核全部1,933,480新预测的身份、held归属、cutoff部署和52维数值；复用已接受156纯选择函数核全部322,028新mother选择、K边界及main对DOMAIN52/COMMON52两个完整动作向量。旧模型、分数、选择与资金均不重算。
6. 独立Kstress policy scalar：无选择0；选中缺label/非主域是身份矛盾；known cancel仅政策0、tradeY仍null；同action差0且same-unresolved单列；不同action任何strict未知保持distinct unknown。普通/F先合并为每family-u一个政策，再等u，按u而非退出日期分2020–2022与2023–末日。独核两held×两cutoff×两控制共8格、全部held_daily及全门；任一失败应cash_eligible=false，237始终不授权cash。

## 最小测试与源码冻结

- 新增 [stage239_K_target_review.py](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage239_K_target_review.py) 和独立 [四项tiny](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/test_stage239_K_target_review.py)。复用220的已接受design/日历纯函数与156 selector；不导入238的目标/held/fit实现。
- 四项分别覆盖：copy parser与same-C/晚clock拒绝；policy0/sameunknown/distinctunknown；u部署分段及八格任一未知拒绝；Δrhs/不惩罚截距和错系数检测。合成矩阵只独立求解，fixture fit=0。
- 先RED，随后每次新增实现/必要修改后运行同四tiny；最终四项全部GREEN，exit0，0.031秒。未运行作者tiny、旧suite或任何实际数据。不是仅四次总执行的宣称；这些反复均为新审查器开发验证。
- 最终 [fixture收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/prepass/fixture_terminal.json) 与 [source freeze](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/prepass/source_freeze.json)。工具38,113B，SHA `0fa8587785690ebec9214eb583558b7456072c8953efddfefe4482b06b97455e`；测试4,787B，SHA `d88e57c42cfd265e7cbe681224ea451f0c002160a58d472d6c2001465357a4a7`。
- root review授权schema为`stage237_exact_root_review_authorization_v1`，绑定完成238 manifest、237 SHA、完整239 source bundle及唯一fresh输出`outputs/stage239_K_target_review/actual_run1`。root唯一launch；本agent不读取半成品actual，不平行再启动。

## 结果、限制与反思

- 当前只完成工具与合成验证：新增实际fit/cash/SQL均0，未新读市场/原生价格或238大输出；不修改旧源码/参数、其他线、LINE、registry、根总账、生产或Git。
- 期末权益、总收益、DD、Sharpe、总滑点、交易次数、胜率均N/A。本稿不是实际独审完成收据；之后实际审查须以唯一新终态为准，不能用测试GREEN替代全表结果。
- 开始/结束过拟合风险：是，同史适应性选择仍在；新增按成绩调参否。继续独立审查价值：是，能验证固定目标与未知门是否如实实施；继续弱包救参、扩大模型或加注否。即使239算术通过，真正未见、资金/执行资格和用户完整目标仍未完成。

## 实际前置guard失败与唯一schema适配

- root首次launch失败于`COMMON52_main`小控制链的`KeyError: status`；该失败终态确认labels/mother/COMMON/support/scaler/normal-equation/score/choice/held大读取全部0，fit/cash均0。未开始数值审查，不能称已经独审模型。
- 根因是本工具错误假设所有旧控制manifest和receipt都有顶层status。冻结156的schema为`stage156_voluntary_choices_manifest_v1`，无顶层status；其artifacts.terminal是`stage156_terminal_v1/completed/exit0`。已接受158用`stage158_voluntary_independent_review_v1`、`completed=true`、C/I/M=0、research_arithmetic_accepted=true，inputs.choice_manifest精确关联156。旧文件不修改、不重审旧控制数学。
- 修改前已把v1工具、test、失败terminal和原source freeze保存到`outputs/stage239_K_target_review/legacy156_guard_repair/v1_snapshot/`。原actual_run1及其失败终态不覆盖。
- 只为上述已知COMMON52_main schema添加完成证据适配；其他控制继续原status判断。单一合成case放入现有第1方法，先观察RED，再仅运行该方法GREEN：1test、exit0、0.014秒，0fixturefit、0大输入；本次未跑其余3方法、作者测试或旧suite。
- root指定fresh `actual_run2`，237本体、门、238产物及金融参数全部未改；此路径差异由root操作性授权记录，不自动重启。授权schema仍`stage237_exact_root_review_authorization_v1`，必须绑定新的source bundle和fresh2输出。
- v2工具38,961B，SHA `38421e80018196faa019a142297ceff3fb2aa9ccda83a33c0c8bc3aaf81200d8`；test5,477B，SHA `9b77636b4cb183b5215a4af2b1777c6a76a1e40baba7c6bb76c78dac8eb0d64a`。修复[fixture收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/legacy156_guard_repair/fixture_terminal.json)及[新source freeze](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/legacy156_guard_repair/source_freeze.json)已交root。此处只记录前置修复，数值独审完成仍须等待fresh2真实终态。

## 最终实际独审：接受算术，held门失败，0cash关闭

- 实际结论补记：2026-10-19 21:43 CST。root在完成238后唯一启动239 fresh2，session56807，真实terminal exit0、耗时45.966750208秒。**共2次启动、1次完整数值审查**：首次只在旧156完成schema小guard处失败，所有数值大读取0；schema适配后fresh2第一次进入数据和数学阶段，没有旧数值阶段重跑。237本体与金融门保持原冻结，fresh2路径由root操作性补记授权。
- 本补记只读取完成的26,640B receipt与小terminal，不二读labels、COMMON、support、scores或choices。最终[独审收据](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/actual_run2/receipt.json) SHA `a4642db25e5d8c1e9ed9c9b6101c26380de7a97fe1625eb09caa10f377ea0f16`；[成功终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage239_K_target_review/actual_run2/terminal.json)保留完整计数。
- `core_blockers=0`。六fold有序T、S=C、原52/scaler/精确w及旧/新clock全部一致；六模型Δrhs和独立求解均通过。最大独立解系数误差`1.171582484e-9`，最大正规方程残差`1.501757652e-8`，沿原220容差，未按结果放宽。独解不调用estimator.fit，独审新增fit=0。

| fold | 原T行数 | 精确S=C行数 | exact目标变化行 |
| --- | ---: | ---: | ---: |
| main / 2020 | 247,795 | 216,443 | 4,218 |
| main / 2023 | 445,475 | 390,340 | 7,675 |
| held0 / 2020 | 171,712 | 150,511 | 2,923 |
| held0 / 2023 | 297,404 | 261,338 | 5,136 |
| held1 / 2020 | 76,083 | 65,932 | 1,295 |
| held1 / 2023 | 148,071 | 129,002 | 2,539 |

- 全部1,933,480新child分数逐块核过，最大误差0；全部322,028新mother选择核过。main161,014母体中候选相对DOMAIN52改变1,297行，相对COMMON52改变1,030行；两main向量均非恒同。main选中4,569；held0的64,077母体选中2,056，held1的96,937母体选中3,810。这里是选择计数，不是实际成交或胜率。
- strict K stress held的8格、family-u聚合、等u日均与全部held_daily及gate独立一致。下表均为候选减控制的已知等u净R差，不能当现金收益；unknown始终未填0。

| 控制 | held组 / 部署cutoff | 已知等u增量R | distinct unknown | 结果 |
| --- | --- | ---: | ---: | --- |
| DOMAIN52 | held0 / 2020 | −0.003988232668 | 5 | FAIL |
| DOMAIN52 | held0 / 2023 | +0.000096943348 | 3 | FAIL |
| DOMAIN52 | held1 / 2020 | −0.001284773070 | 3 | FAIL |
| DOMAIN52 | held1 / 2023 | −0.002714307014 | 3 | FAIL |
| COMMON52 | held0 / 2020 | +0.001172104124 | 3 | FAIL |
| COMMON52 | held0 / 2023 | −0.001130079000 | 3 | FAIL |
| COMMON52 | held1 / 2020 | −0.002772785146 | 7 | FAIL |
| COMMON52 | held1 / 2023 | −0.001586654336 | 3 | FAIL |

- 8格都有distinct unknown，且6格已知增量为负；两正点估计也不能覆盖未知门。`all_eight_held_pass=false`、`main_differs_from_both=true`、`cash_eligible=false`、`automatic_cash_authorized=false`。接受新模型与前向/held算术，**拒绝本固定K_TARGET52/52/Ridge/K包进入现金**；root240据冻结门关闭它，不补跑四本现金、不换duration/权重/scaler/K/模型/阈值/止损或风险救参。
- fresh2实际只读labels1、mother1、COMMON1、calendar1、六support/六scaler/六旧小normal-equation各一次、四旧choice各一次；新score1、新choice2、新held_daily1。原actions、旧score重预测、旧选择重算、旧现金重放、SQL、新fit/cash均0。审查读取新分数并核矩阵乘法不是重预测控制。
- 本轮训练由238实际新增6fit，239独审0fit/0cash；当前累计**439fit/234cash**。资金回测未运行，期末权益/收益/DD/Sharpe/总滑点/交易次数/胜率均N/A。独审无剩余核心阻断不等于alpha、真实执行或生产资格。
- 结束过拟合风险仍是：同史择题不能由对象修正或独审消除；新增按成绩救参否，8格固定门照实失败。继续本固定包价值否；完成独审价值是，避免用目标更合理替代真实泛化支持。完整全市场高质量long目标仍active、未达成，极小止损可靠性和加注资格均未建立。
