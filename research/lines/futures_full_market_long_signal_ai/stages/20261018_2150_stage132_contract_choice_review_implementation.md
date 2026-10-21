# Stage132：合约月选择独立复审实现

- 时间：2026-10-18 21:50 CST；line_id：`futures_full_market_long_signal_ai`；非重要突破。本记录仅为独立审计器实现，尚未启动实际独审。新真实SQL、标签、fit、cash、下载均0；未改129/130/131、旧代码、LINE或registry。
- 已读registry、127、最终128协议（`bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0`），确认往返half-cap、product内选月再普通/F family次序及新A口径均已统一，不再循环设计预审。实际授权需root另给三份最终manifest SHA和三份terminal SHA。

## 覆盖与实际运行界面

命令为`.py311/bin/python tools/stage132_contract_choice_review.py --dataset-manifest … --dataset-sha256 … --dataset-terminal-sha256 … --fit-manifest … --fit-sha256 … --fit-terminal-sha256 … --cash-manifest … --cash-sha256 … --cash-terminal-sha256 … --output <fresh>`；实际路径以本线绝对tools目录为准。拒绝旧输出目录，保留失败终态，不自动重启或重复金融。

1. 三阶段schema、完成终态/执行计数、root授权、源/测试/产物绑定及跨阶段身份闭合；原399252母体/98产品/95family/六所、全部子动作、末端未成熟状态保留。
2. 允许一次只读native SELECT，按既定2010起始和完整5587索引生成紧凑数组；只比大库stat和继承SHA，不全库重hash。独立重建每epoch Wilder N/20low、每child own SMA20的11特征、可重复peer池13特征、COMMON原2N成本/距离。逐child独立检查u准入/容量、label状态及全部可模拟的自身路径与R目标，非只抽被选赢家。未知/取消/右删失不能转0目标。
3. 六fold自算成熟mask、family整组留出、family-u区间union并发/组内均分/等u权重、有限值scaler、52槽、全部normal equations、现有六个joblib与portable系数、全部前向shared scores、完整两臂parent先product后family选择，以及实际choice的held family-u去重诊断。仅核现有充分方程，不调用fit。
4. 八账户逐笔资金、持仓数量、费用/滑点、权益/回撤/Sharpe、u联合预留/D只减量、cap后不重分配、所有入场/减仓决策与强制/stop不能遗漏。逐真实native bar核开盘/止损/mark/own20low/anchor请求；逐fill以exact D−1量做买卖毛量共享审计，验证episode/account吸收unknown与缺D入场unknown，不改理想账本。
5. 全年度/2026不完整年、95family归因/集中度、gap及>1R、全部四组2000固定共同索引CI、held与容量门及置信度限制。复用已冻结独立102资金算术和诊断函数，不导入129/130/131计算器、不重跑研究账户。`holdout0/1`到`holdout_0/1`仅序列化别名，同family哈希划分不变。

## 验证及边界

八个新纯fixture通过（0.027s），py_compile和CLI help通过；未重跑旧suite。覆盖roundtrip整数边界、anchor持久且远月不变DAY、union月份不膨胀与跨u并发、最高分合法月/普通F优先、D−1毛量不净额/缺量不回找、相同未知差0与不同未知null、gap重暖/SMA与Wilder差异，以及远月持仓直到anchor改变后下一native open才退出。尚无实际review_receipt；此实现通过不能代替真实数据/现金复审。

沿127已查的[RBA原论文](https://www.rba.gov.au/publications/rdp/2017/2017-03/data-and-measurement-of-commodity-risk-premiums.html)及[LEAN源码](https://github.com/QuantConnect/Lean/blob/master/Common/Securities/Future/FutureFilterUniverse.cs)：选月值得单次检验，现成资料不能证明国内窄损alpha或1%开盘可成交。不重复搜索同一来源，不按新收益改变审计标准。

开始/结束按收益调参：否；反复使用历史数据择题风险：是。继续价值：是，一次完整独审能阻止薄月理想收益、隐藏未来筛和预算错误被当优势。无新增策略参数，本次权益/收益/回撤/Sharpe/总滑点/交易次数/胜率N/A；不形成晋级、上线或加注资格。真实完成后root汇总133；goal仍未完成。

## 冻结文件

- `stage132_contract_choice_review.py`：73644字节，SHA256 `1dbf3b9abb70332e382b0352301f9ec5ca8db484d8ea8530f2f38979e9a80cb5`。
- `test_stage132_contract_choice_review.py`：6063字节，SHA256 `27cdeab1b80e21553b3832c9293fb1d6b60c4d540b579478ea615d7375a44a0a`。

## 2026-10-18 21:59 CST：一次checker身份修正及有限续审

首次实际独审exit1，原源码快照/终态不改。完整1552456子动作、40363856特征值、1022543可模拟自身路径/1012388闭合路径、全label状态/准入已独立通过；随后第一个fold的parent选择检查失败。实读失败事件为2020-05-28 DCE.PP_F（母序255114），无child/anchor，正确selected0；同family普通PP母序251040才是A选PP202009、B选PP202010。132把family-u winner误要求写到该family所有产品母行，违背exact product身份；130实际输出符合合同。

先加回归fixture复现同一断言失败，再仅改winner必须归属当前mother；覆盖F无child和F有proposal但被普通优先压制两种情况。九个新fixture全通过（0.043s），compile/help通过；无研究代码/参数/金融产物修改。继续采用已完成source阶段，不重做全feature/label loop。原进程仅内存保留native数组，退出后不可取；后续cash全量native引用需额外一次只读SELECT重建紧凑store。实际续审需root新授权，运行时对原source-report/失败terminal/原checker snapshot SHA、相同三manifest及source函数AST逐项绑定，并写continuation_receipt。诚实记录review累计SQL2、含129/131全序列SQL4，较原总3增加一次工程重建；不是原预算未变。研究fit/cash重跑均0。

新CLI在原9个exact输入后增加`--resume-source-review <actual_review1> --resume-source-report-sha256 <报告SHA> --resume-terminal-sha256 <原失败终态SHA> --resume-checker-sha256 1dbf3b9abb70332e382b0352301f9ec5ca8db484d8ea8530f2f38979e9a80cb5 --output <fresh>`。仅续六模型/全部choices/八账本未完成审查，原source通过不是完整review通过；不因修checker改变科学门或加注。开始/结束按收益调参否；历史择题风险是；继续价值是，有限修复已定位的审计身份错误并完成原定独审。

- `checker`：80567字节，SHA256 `747e1c9f27cc5d9a734e58044a4ce00112b6ca8909ad0f27a2769058d0a52088`。
- `test`：8023字节，SHA256 `684a6e31926122037b8ecdd543bbf8aa256d3f6b83cc7510c22aeda134aedbcf`。
- `accepted_source_phase`：1732字节，SHA256 `3e2389bb5393b6bf2fac2ffde23142554ed32f3de6ec5c9ea020a70b43b952ef`。
- `prior_terminal`：493字节，SHA256 `92bf8b6fd5f486b08f0e7c2c75111c25db79d28aabbd083dfa01553119dc4f57`。

## 2026-10-18 22:09 CST：现金审计类型误判的有限修正

continuation1保留exit1；复用source阶段及六共享模型、全部前向child分数、完整parent选择和held诊断均已通过并持久。首账户在现金关键检查后，rejections展示表比较失败。实读2312条拒绝行：原始CSV与reservations中D_qty=0原始切片，预算ID、52列及每格字符串完全相等；仅checker先把budgets七列转numeric而rejects仍str，DataFrame.equals返回False。不是金融数据差异。

修为ID和关键数值/政策状态按语义比较；纯展示列差异收集到presentation_warnings，不把金额、手数、状态差异当格式放过。新增回归先失败再通过，十个有限fixture通过（0.044s），compile/help通过；无金融代码/参数/产物变更。现金独审按账户先保存ledger和native-policy-capacity检查结果，再集中诊断/CI，避免下游展示问题丢失整段进度。

最短cash-only入口在原三manifest/terminal九个精确参数后加`--cash-only-evidence <cash_only_resume_evidence.json> --cash-only-evidence-sha256 <SHA> --output <fresh>`，不传resume-source-review。evidence绑定上次已通过source/model/held、两个阶段身份、失败终态/源码快照；续审校验source/model核验函数AST未变，直接复用其证据，不重跑全source和models。先前native store仅在已退出进程内存，仍需root批准一次额外只读SQL做现金原生引用；实际会保存简单native_store_cache.npz，避免后续展示修复再次查询。诚实计review累计SQL3、129/131/review全序列SQL5，研究fit/cash重跑0。

尚未启动cash-only实际审查，未形成完整review通过结论。开始/结束按收益调参否；同史择题风险是；继续价值是，有限完成同一既定结果的关键现金审计。此前两个失败终态和源码快照保留，不为任何新实质差异修改金融结果。

## 2026-10-18 22:15 CST：空列序列化等价与0SQL缓存续接

cash_only1保留exit1，失败仅为rejections省略全空列。已核2312行缺少的D_unit_margin_plus_fee、D_unit_risk、existing_qty、root_id、target_existing_qty五列在对侧全为空。只修“缺列且对侧全空即等价”；非空关键金额或root仍失败。新增此边界先红后绿，十一fixture通过0.047s，compile/help通过。

下一次仅读取cash_only1已保存的exact native_store_cache.npz（110273488B，SHA d2976090f9353b071eb62e28eca843b96b4a33a33a4233a508049cfeab9360b7），0新SQL；原source/models验收和已通过首账户ledger JSON复用，剩余现金关键核验继续逐账户持久。CLI仍为原九exact参数＋`--cash-only-evidence <cash_only_cached_resume_evidence.json> --cash-only-evidence-sha256 <SHA> --output <fresh>`。审计累计SQL维持3，全序列维持5；研究/训练/资金回测重跑仍0。此次不声称完整审查一次直接成功，三份debug失败及源码快照保留。开始/结束收益调参否；历史择题风险是；继续价值是，完成未完现金核验而非重开研究。
