# Stage055：期限信息三臂与12研究现金账本独立结案复核

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 14:49 CST；本stage初始协议预审14:36，现更新为完整独审终态。
- 仅修改本stage及`outputs/stage055_maturity_information_cash_review/`，不改作者源、LINE、registry、其他线或正式配置。不是重要alpha突破，不触发正式A/B晋升；不commit/push、部署或连接CTP。
- **Critical/Important/Minor=0/0/0；接受保存研究计算，不接受期限信息增量优势、可实现盈利、窄损或加注资格。** 3个预声明继续条件为不支持/不支持/未知，完整goal未完成。

## 设计、调研与源码预审

实读registry、LINE、051接受、052文档/机器协议，052 SHA `968fa3505143587950d65fe27db0aa376916b0f005ffc6219b2af880a7e6974c`（11987B）。design、051 decision、042核绑定匹配；共同26列+26缺失+q共53槽，3cutoff×3scope×3arm=27fit、2起点×2成本×3臂=12现金。

本阶段复用052已实查的[sklearn官方HGB文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)、[维护方GitHub](https://raw.githubusercontent.com/scikit-learn/scikit-learn/main/sklearn/ensemble/_hist_gradient_boosting/gradient_boosting.py)和[PBO原作者论文](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)。判断：固定同容量与同值shuffle可检验这个期限对应关系，重复历史研究的选择风险仍在；本次不另起策略调研或下载。结果不能据小树和正式接口文档推断盈利。

源码预审只覆盖052相关实现。初版Important为合并held文件覆盖scope，已在actual使用前改为保留holdout_0/1，054逐行严格核family hash；最终无剩余阻塞。有限native首次case由21bar改成完整连续暖机段，case不扩面、只用已加载数组，无新SQL。053源 `045168b069bddef62777a010277a8e7409ea094dc2ac57db33f81cd5b63c7c9b`；054源 `f5f73732747b64b812e48c09202f5d52dcf3f59726e20e05e21ba616453884bd`。没有重复作者/root已跑的合成suite；独审脚本先做py_compile。

新增独审脚本/收据与本记录；策略参数、作者成绩修改/删除0。本轮实际新增固定HGB27fit、12现金，累计研究矩阵315fit/30现金；此前必要240行HGB格式characterization单列为测试，不作新增市场实验或搜索。HGB lr.05/100树/leaf7/depth3/minleaf100/L2=1/bins127/earlystopFalse/seed20261018、单family0.25%/总2%/margin25%/100w及两成本均沿052，不按结果变更。

## 一次actual与完整独算

root先验完整终态后授权本轮总审。053唯一actual27/27fit、118.2001205秒、0SQL/现金；manifest `04268bb8c6f183139443b0e94d2eb51741c079d722c2987439fe37f81e085f8f`。054唯一actual12/12/12账户、62.8544902秒、1SQL、0fit；manifest `b3f07f6ecf931f11181a5c6e7bacabaa000f4ca9da081e71b0642320706e2b2d`，terminal `0590a30fac643638607f4efb844e1ecd2ed6a1ee00cc8e7f15af5359e67ea096`。不是按partial成绩选择。

055唯一actual session22602，**2026-10-18 14:48:10—14:49:35 CST，84.913963秒，exit0**，无修复重启。独审自身0SQL/fit/策略重放/作者核心模块import/下载。只读已绑定规范化输入、保存节点/现金输出及有限原价case；原始审计价不复制或登记。

- 全27模型cell、9套预处理、966084预测。独立重建训练ID，核u与known均早于cutoff、完整闭合、family普通/F整组留出，按训练集合inclusive entry—exit并发重算U、u等权和均值1；不拿测试或未来事件算权重。U最大误差1.01e−13、weight1.45e−12；共同scaler最大方差误差5.16e−14、q方差2.89e−15。
- 原26列逐值独算与prepared_common精确一致，旧009只S11 X；母体399252不删，main与held并集每臂161014个2020+机会。预测路径用保存精确raw26/saved scaler及同语义q文本解析，**自行遍历100树节点**；全预测最大误差2.22e−16，selected均为ready20且score>0。独算scaler末位误差不混入树路径，无重新fit。
- 全12现金账户、7689fills、15348账户日、54999持仓日；55088预算记录、39508新分配，实际existing joint reduction为0。独立从saved fills重建剩余qty、cash=初始+realized−fee、mark unrealized、equity、margin/buffer、initial risk、stale/全开放置零情景、全部summary和闭合net胜率；滑点已入fill价，不二扣现金。核所有fill不利报价/Decimal tick/经济身份、own D风险与margin+fee额度、qtycap/roundlot、u联合实数预留后floor及D不借释放额度；无用未来标签执行。金额等全部比较最大误差`2.328306436538696e-10`。
- 逐年连续账户切片、family×年归因/赢家集中、全部daily log、配对252日circular MBB的2000×1643索引、同索引两contrast分布/CI、两held的全母体与已识别条件诊断均独算一致。bootstrap分布最大误差1.09e−18。不是2000个市场，年度切片不是新冷启动账户。
- 7类有限native案例实际仅5个不同event；完整暖机N/20low/close最大误差0，4类cash原价邻域42个已保存fill参考价/触发关系一致。3个首次选中case恰为同一event且未成交，未虚报成交验证。没有第二次完整原生策略重放。

## 12账户成绩与增量判断

各账户初始1,000,000；至2026-10-16，2026为部分年。滑点为金额归因；闭合次数/胜率不含未完成仓。COMMON与SHUFFLED独立维护状态但主预测相同，成绩重复不增加证据数。

| 账户 | 期末权益 | 收益% | 最大回撤% | Sharpe | 滑点金额 | 闭合次数 | 净胜率% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| COMMON / base / 2020连续 | 1,033,811.42 | 3.381142 | -8.142695 | 0.156053 | 15,337.72 | 454 | 37.89 |
| COMMON / base / 2023冷启动 | 955,144.73 | -4.485527 | -7.108249 | -0.415059 | 7,342.42 | 211 | 31.28 |
| COMMON / stress / 2020连续 | 975,621.59 | -2.437841 | -8.817986 | -0.105777 | 36,889.56 | 411 | 34.79 |
| COMMON / stress / 2023冷启动 | 931,704.28 | -6.829572 | -8.846724 | -0.709191 | 18,657.48 | 191 | 29.32 |
| ALIGNED / base / 2020连续 | 1,026,053.41 | 2.605341 | -8.168680 | 0.124878 | 15,811.76 | 461 | 37.53 |
| ALIGNED / base / 2023冷启动 | 944,581.22 | -5.541878 | -7.072951 | -0.463804 | 7,935.12 | 219 | 29.22 |
| ALIGNED / stress / 2020连续 | 990,693.94 | -0.930606 | -7.910108 | -0.028271 | 38,130.75 | 417 | 35.25 |
| ALIGNED / stress / 2023冷启动 | 921,212.27 | -7.878773 | -8.979956 | -0.810840 | 20,048.83 | 203 | 30.05 |
| SHUFFLED / base / 2020连续 | 1,033,811.42 | 3.381142 | -8.142695 | 0.156053 | 15,337.72 | 454 | 37.89 |
| SHUFFLED / base / 2023冷启动 | 955,144.73 | -4.485527 | -7.108249 | -0.415059 | 7,342.42 | 211 | 31.28 |
| SHUFFLED / stress / 2020连续 | 975,621.59 | -2.437841 | -8.817986 | -0.105777 | 36,889.56 | 411 | 34.79 |
| SHUFFLED / stress / 2023冷启动 | 931,704.28 | -6.829572 | -8.846724 | -0.709191 | 18,657.48 | 191 | 29.32 |

ALIGNED主2020base比两参照少7,758.01元、收益低0.775801pp、DD深0.025985pp；paired日log点值−4.584649e−6，95%CI **[−2.360058e−5, +1.279593e−5]**。两contrast因参照相同而相同；区间跨0，不能声称稳定有害或有利，但预声明正增量/收益与DD要求失败。ALIGNED主stress虽较参照高1.507234pp、DD浅0.907878pp，**自身收益仍−0.930606%**；不能单挑此情景说优势。2023冷启动base/stress收益均低于参照约1.05pp，stress DD也更深。

两held条件日等权mask×stressR点值+0.000591829/+0.000415973；但分别17/20个差异选中未知/开放事件没有可接受有限R界，故均为未知。不是全机会价值或现金收益，不能据条件正值覆盖主现金失败。原049完整闭合训练标签亦有参与后完整条件性，不自动代表未识别事件。

ALIGNED连续base与stress的2020—25均4/6年正，但2023/24都负、2026部分年负；2025base仅+0.039826%，不能挑早年说穿越周期。ALIGNED base2022最大赢家RM占正贡献40.52%，2024 FU占51.87%、前五占97.40%；stress2022 RM占50.66%。已核全年/family归因，不删赢家或弱年救结论。

## 相同参照的保存模型解释与估值限制

描述性检查只读保存树和分数，不新增fit或按结果改设计。主COMMON/SHUFFLED三cutoff **q（0-based第52列）分裂均0**，161014分数及selected精确一致，解释相同现金结果。ALIGNED主q分裂2020/2023/2026为1/5/0；相对参照动作一致率99.5767%/99.4807%/100%，前两段分别302/370个动作不同。全9scope/cutoff合计COMMON/ALIGNED/SHUFFLED q分裂0/19/1；SHUFFLED的1次在2023 holdout_1，故不得扩大成所有留出模型都忽略q。保存`q_slot_description.json`，只作解释。

**陈旧估值显著限制绝对收益声称。** ALIGNED主2020base/stress分别936/994个source日曾有stale（参照935/993日），最大stale notional127540/155790；ALIGNED期末base3仓/stale1，stress2仓/stale1。按冻结“末开放long全部置零”情景，ALIGNED期末权益分别892633.41/907133.94，均低于本金；这不是普适损失下界，也不是改持仓/仓位的输入。不能拿名义base微正当成可实现盈利。已保存延迟退出和未知敞口，没有删仓、补零标签或改mark掩盖。

静态vendor规格、close mark、缺价延迟、收盘可得与研究选择均仍是假设，不是历史broker settlement、逐时PIT或真实成交资格。低名义DD同时来自固定较低预算；没有证明相同收益保留的更低风险。完整全期高质量long、极窄止损与加注更未证明。

## 决策、反思和交接

接受**研究算术及本次有界复核**；不支持继续本q+固定学习器+经济政策组合，不扫tree/窗口/seed/阈值/风险/窄损救结果。停止本组合的alpha推进，不把它扩大为所有期限信息或所有AI无效。

开始与结束新增按成绩调参过拟合判断：**否**，收益前冻结、一次27fit/12cash、一次独算，不追加搜索；重复历史择题、条件样本、稀有尾部和宏观有效样本不足风险仍**有**。继续本组合调参价值：**否**，主经济/置信/冷启动条件未过且陈旧估值不确定性大；继续用户完整目标：**是**，但须真正新信息或数据/机制证据与完整经济检验，目前不启动新实验。A/B正式晋升、窄损/加注、生产和goal_complete均false。

独审主receipt SHA `91764c7031eb3f910f95f8cde5da9bbc53112919910659ed0097a7e81175fc66`；terminal SHA `0ae312686170f23e6bb41ff0acd877461a8c934a328d6cb08e1ad2cb55613805`；q说明 SHA `2b45375c289769730ed18894afd8ef3d7059aefef140c7f6485e7789e435f43d`。预审与必要脚本/收据见`artifact_inventory.json`，原价case仅引用054 excluded审计，不入本目录/Git。root负责最终Stage056决策与本线状态/归档；本agent不改LINE、registry或根总账。
