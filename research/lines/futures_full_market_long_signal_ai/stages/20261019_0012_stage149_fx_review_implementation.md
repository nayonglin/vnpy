# Stage149：FX 新增内容独立审查器实施与有限静态预检

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 00:12 CST；非重要突破。仅本人维护此唯一 stage 与 `tools/stage149_fx_review.py`、`tools/test_stage149_fx_review.py`；未改 LINE、registry 或作者工具。
- 已读 registry、本线 LINE、145 最终协议/plan/protocol-review 与 144 content-review。最终协议 SHA：`be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270`。actual 仍由 root 精确授权；本阶段未运行实际数据审查。

## 有限静态预检

本次只读 146/147/148 新工具、相关固定执行函数与已接受 130/131/132 小型 manifest，未重审旧全域。146 的 n/d/w 原表相邻发布行、n+1 上海 08:00 → u15:00、母体完整保留与缺失不跳过符合协议。147 在所有六 fold 的零列桥及 q 加权正方差通过后才进入首个 fit，使用原成熟训练身份/权重/COMMON scaler，独立新 FX 对全域评分选择。148 仅以局部 B schema alias 进入固定 131 kernel，原 B 四本作为引用；主 stress 严格收益/DD/CI 与 unknown 门保留。

发现 Important 1：148 在循环中反复用 accepted042 的 `open('x')` JSON writer 写同名 `cash_progress.json`，会在第二个账户前中断。已报告作者/root。作者改为 `write_cash_progress` 每账户唯一 `cash_progress_01..04.json`，新增连续两次真实 writer 小测试；本人读回修正调用与路径，确认该 I 关闭。未改策略、参数、收益或重跑现金。剩余静态 Critical/Important：**0/0**。这是实施预检，未签实际结果。

## 新检查范围与边界

1. 自行解析保存的 144 raw ZIP，重建双方同批 `CNY/EUR ÷ USD/EUR`、n/d/w、q、08:00/u15:00 与自然日年龄；逐格核全 399252 投影及 source_dates、重复归档状态/独立发布 cohort。
2. 原 130 成熟训练身份、权重、COMMON scaler/模型是已接受输入，只做 exact 引用与本次两新增 CONTROL 零列桥，不重算旧 union weights/旧模型/旧全域资格。独立核六 fold 新 q 统计、54 维设计、55×55 含不罚截距正规方程、新 joblib/portable/all-child scores、全部新父域选择、完整 main+held family-u，保留不同动作未知与同动作共同未知。
3. 复用 SHA 锁定的 accepted132/102 独立纯数学账本函数；只读取 accepted132 native cache，0SQL/0大库 stat/hash/0指标或标签重建/0策略重放。核新增四本九类账本、费滑/权益/summary/annual/95 family 零网格、金融/商品与普通/F、尾部、暴露/stale/anchor/容量/入场 unknown。
4. 旧 131 B 四本仅核 exact summary/daily/diagnostic 引用；用其保存日曲线与新增曲线按原 070 两份固定 indices 重算四组配对 CI。独立核 145 名义门/未知门，首发归档/PIT、重叠起点/同史择题、全局 FX 非月份专属信息与日线理想成交限制均写入最终 receipt。
5. 实际 CLI 只接受 `stage145_exact_root_authorization_v1`、`authorized_by=root`、`stage=review`、最终协议 SHA、精确 source_bundle、三个 `input_bindings`（`projection_manifest`、`fit_manifest`、`cash_manifest`）及 fresh Stage149 output。失败保留终态，不自动重试。

## RED/GREEN 与交付

先建立 5 个有限 fixture；RED：独立检查器尚未实现，`setUpClass` 报明确缺失；GREEN：五项全通过，覆盖原 ZIP 相邻缺失不跳过与时钟、q 加权统计/54 维正规方程、精确产品排名/普通-F 固定优先级、未知相消/不同未知不零填、复用配对 indices 与主 DD 严格门。全部 fixture 不读取 accepted 数据、0 fixture fit/现金/SQL。

命令：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage149_fx_review.py -v`；最后运行 5 tests / 0.033s，OK。`py_compile` 两文件 exit0；`--help` exit0。按本次明确有限新增范围未跑旧大型 suite。

源码：59223B / SHA `d07df252bcc0776855dc29db0426e78017641075d5bf68a0462d5f10a431f846`；测试：5022B / SHA `f6df9200030a8ef20c3be8c3a39299675b0a88e204464acfcc047e29ff69eff5`。实际 source_bundle 再加 SHA 锁定的 stage132 与三项 stage102 数学 helper，不 import 146/147/148 作者计算。未运行 actual，未签实际 C/I 或结果结论。

外部有限调研：[ECB参考汇率说明](https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.eu.html)、[scikit-learn Ridge 官方源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/linear_model/_ridge.py)。判断：发布机制与 Ridge 目标支持本次延迟时钟/正规方程核法，但不能由今日归档证明历史首发 PIT；不据网络或既有收益扩展实验、换参数或下载数据。

本阶段新增/修改/删除策略参数与回测结果均 0；权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均 N/A。新增实际审查/fit/cash/SQL/下载/大库 hash 均 0。开始/结束新增按收益调参过拟合：否，本阶段核固定协议与新增计算，不选策略；同史多轮择题风险仍有。继续完成一次有界新增内容独审有价值：是；扩展旧资格审计或因结果救参无价值。完整目标、生产与加注资格均未完成。

## 00:25 CST：首次实际审查终止、根因与有限续审准备

root 已签原精确授权并启动唯一 `actual_run1`；该进程 exit1、69.649 秒，错误为 `AssertionError: complete held family-u`。`failure_trace.json` 明确位于 `review_models → held_result`。原目录、`actual_started.json`、`actual_terminal.json`、输入闭包、raw ZIP 投影检查、六个 `model_<scope>_<cutoff>.json` 与原 `checker_snapshot` 均保留，未覆盖/删除或自动重启。

根因按 systematic-debugging 流程确认：`review_control_choices` 已把原 B 引用改名为 `CONTROL_REUSED`；`held_result` 却仍以 `control.arm.eq('B')` 筛选，导致控制侧空表，与 FX 侧完整 family-u 断言不相等。新增有限 fixture 用真实 `held_result`、已改名控制和共同未知动作精确复现同一路径 FAIL；仅修这一处筛选为 `CONTROL_REUSED` 后，原五项及新回归共六项 GREEN/0.034 秒。未改公式、训练、选择、未知规则、资金或结果。

原 run1 在失败前已完成：全 399252 ZIP 时间投影；4021 独立 release cohort、4074 国内日期及53重复状态；全六新模型 q 统计/54维正规方程/portable 与 joblib、1,933,480 新分数、322,028 新父域选择，完整 CONTROL 引用/零列桥与输入闭包。依据是已保存检查点、冻结原源码的执行位置及失败调用栈；不重新执行这些已完成阶段。原失败进程未保存全局数值最大误差，**不能补造数值最大误差**，仅能证明已完成断言在原源码固定容差内通过。

新增独立入口 `tools/stage149_fx_review_continue.py` 及三个 guard fixture。续审必须另获 root 精确授权：同 `stage145_exact_root_authorization_v1`，`stage=review_continue`；精确绑定原三份 manifest、run1 failed terminal/started/failure/input_closure/projection、六 model progress、原 checker snapshot，共15角色。新入口逐字验证当前149源码与原snapshot仅这一处 alias 替换；原helper SHA不变；源和manifest/terminal身份闭包不变。所有原已完成矩阵/新childscore/正规方程/训练文件不打开、不重hash，不冒称重新证明其当前全局字节；继承原精确检查证据。

续审只从原accepted完整 B choices、新FX choices、必要 action 标签/身份重算尚未完成的完整 held/unknown 及全明细，再核四本新增 FX 现金/原070 indices四CI/固定门。0fit、0现金回放、0SQL、0下载、0完整重审；一个 logical 新内容完整审查跨两次启动完成，原失败计数不删除。续审自身最大误差单独记录，与原未留存误差分开披露。失败仍保存终态，不自动重启。

另由只读静态 agent 核剩余 `review_signals/review_books/extra_book_checks/review_comparisons` 与 accepted132/102、148 小型manifest/表头，C/I=0/0；未读大CSV/NPZ、未改文件、未actual，此接口预检不替代实际账本核验。

续审 guard：alias 外任一计算变化拒绝、原终态必须精确对应 held失败且全部新增工作为0、六组唯一完整检查点缺一拒绝，三项先RED后GREEN/0.228秒。两续审文件 `py_compile` 与`--help` exit0。原149新alias回归六tests全绿。新增实际续审仍0，等待root精确签发。

当前修正版149源码59236B / SHA `51e7d4c1b2e9f93f915afc88d588a4f422b0b9e699660bc337ea8b0f306cd9a1`；测试6274B / SHA `adea6c4c7682a6d96c5e3629acc46f9cf6fe592284698a57adece62c267dcb64`。continue源码16248B / SHA `de01a32edbf18581230acedc83a7795c8c19ded410e609e7681aa6921d577aed`；continue测试2176B / SHA `855ee85c388982a9d493ffda511340d6d927d0ae172e3eaca84f1dce6aaed731`。原run1源码与测试绑定保持原记录，不将补丁冒称原运行源码。

本次开始/结束新增收益选参过拟合：否，修复检查器名称衔接不改变科学比较；同史择题与归档修订风险仍有。继续有限续审有价值：是，可完成尚未检查的 held与新增现金；重做已通过阶段或重跑金融无价值。结果暂未获得完整独立接受，生产/加注/目标完成仍false。

## 00:32 CST：有限续审实际完成，接受计算、否决固定 FX 包

root 精确签发 `authorize149_held_cash_continuation.json`（7261B，SHA `938b06adc923d76c0ff24b53b4195e66390ade798b007d4decb95496272e8f26`）后，唯一 `actual_continue1` exit0 / **48.6020975 秒**。只读回最终小型 receipt/terminal/started，未另开审查、未改源码或重跑模型/资金。

- 最终 `review_receipt.json`：61055B，SHA `f0fb01b60741df8bac520f1c797aaaabfc580232c774630ecb9b40cceea39a86`。
- 最终 `actual_terminal.json`：377B，SHA `81bc34e5c9de597e69d6877c357e7b2423a09b828d13a5147af0db0d7a07cd27`；`status=completed/exit_code=0/automatic_retry=false`。
- 续审 `actual_started.json`：7167B，SHA `a0cfb48156207cffe430459dc3ccbe48b6071591260f59810ece6d0b64e34339`；其8项 source_bundle 与上节冻结源一致。
- 结果：`completed/research_arithmetic_accepted=true`，**C/I/M=0/0/0**；`fixed_package_supported=false`，固定门 `unsupported`。两次审查启动、一次 logical 新内容完整审查完成、完整重审0；原 run1 alias失败与原source snapshots保留。两次均0fit/0现金回放/0SQL/0下载/0新标签/0大库hash，原6新模型/4新现金没有重跑；本线累计 **397 fit / 206 cash**。
- 续审自身数值最大误差 `1.3969838619232178e-9`，accepted现金数学helper误差 `1.1641532182693481e-10`；原 run1 最大误差仍为 `null`，仅确认原已保存检查阶段在其冻结容差内通过，不补造全局最大误差。

四本新增 FX 保存账本均已完成独立算术核对（100万元初始资金；以下胜率为闭合净胜率；fills是成交记录数，闭合笔数另列）：

| 窗口/成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总费用 | 总滑点归因 | fills / 闭合笔数 | 胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020连续/base | 2,943,480.44 | 194.3480% | -13.8547% | 1.304850 | 62,704.56 | 155,396.76 | 2629 / 1313 | 14.7753% |
| 2020连续/stress | 1,862,846.95 | 86.2847% | -10.8982% | 1.083437 | 65,398.05 | 145,533.02 | 1696 / 845 | 14.5562% |
| 2023冷启动/base | 1,866,630.47 | 86.6630% | -16.1810% | 1.329723 | 24,364.53 | 59,068.94 | 1124 / 561 | 14.9733% |
| 2023冷启动/stress | 1,502,805.49 | 50.2805% | -12.4877% | 1.198198 | 42,139.51 | 89,014.14 | 946 / 472 | 15.6780% |

这里滑点已进入成交价格，归因值没有再次扣除。全部新增年度/95 family含零网格、金融/商品与普通/F分组、最大盈亏、逐笔、费用/滑点、权益、暴露、容量、anchor及未知披露完成核验；旧B四账本只作为精确引用，没有全域复审或回放。

对CONTROL的四组收益差/DD差（DD正数表示较浅）与配对日log CI：

| 窗口/成本 | 收益差pp | DD差pp | 原070 indices配对CI95 |
| --- | ---: | ---: | --- |
| 2020/base | +15.23922415 | +1.20040448 | [-0.0000546231, +0.0001082894] |
| 2020/stress | +29.34917875 | **-0.16982408** | [+0.0000127529, +0.0002067858] |
| 2023/base | +2.46618645 | +0.47123773 | [-0.0000422349, +0.0000809189] |
| 2023/stress | **-2.12260260** | **-0.65479416** | [-0.0000652182, +0.0000334914] |

主stress FX收益86.2847%高于控制56.9355%，且其配对CI下端为正，但回撤更深0.1698pp，已失败冻结的严格DD改善门；2023冷启动stress收益/回撤共同退步。不能只挑主stress利润或CI宣称支持。

完整held family-u重算：holdout0 `62434`行，known等u增量 `+0.0002217763964R`，不同动作未知5、共同未知38，状态unknown；holdout1 `93651`行，增量 `-0.001066620700R`，不同动作未知0、共同未知35，状态unsupported；main完整 `156085` family-u增量 `-0.000164046378R`、不同未知4、共同未知56。全明细/日表/年度与汇总一致；相同未知仅在增量中相消，不声称共同执行已知。

四FX容量未知roots为48/24/20/10，入场执行未知4/1/0/0；期末开放3/2/2/2、stale2/1/0/0，历史stale四本均true。控制侧原未知也保留。因此 `financial_unknown/execution_unknown/held_signal_unknown=true`，`cash_nominal_pass/held_known_nominal_pass/nominal_pass=false`；名义利润不能清除这些限制。ECB最终归档、发布可得时钟假设、重复宏观状态、同史择题、重叠起点和日线理想执行限制不因算术通过消失，strict first-release PIT/生产/加注/goal_complete仍false。

结论：**接受这一次固定包的新增资料、模型、预测、选择、held、现金与统计计算；不支持该固定FX scalar/model/execution研究包。** 不因本结果改方向、lag、窗口、交互、年份、品种、止损、风险或救CONTROL。开始/结束新增按收益调参过拟合：否，本次修复的是审查器alias，未改变实验；历史择题与归档修订风险仍在。继续此固定包救参：否；有限独审现已完成，不再重复资格工程。全市场高质量long原目标尚未达成，后续方向由root另行判断。
