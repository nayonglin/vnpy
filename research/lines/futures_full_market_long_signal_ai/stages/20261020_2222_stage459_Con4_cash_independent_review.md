# Stage459 固定 Con4 四现金账独立审查

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-20T22:22+08:00。
- 当前模式：非实现者对已封存四候选账做唯一实际独审；不是重要突破；不改策略、参数、正式 C9、LINE、registry 或 Git。
- 关联冻结：Stage453 protocol SHA `c82dfb499558b0ecc32e8f9654b3361f68741a74400c67507b1d01a69ca9e053`；Stage457 source SHA `a9e262902ec5b997824f1c7485707b42f6645fb4635bb6e2ec042a51d8d5bc7b`。
- 精确现金 manifest：`outputs/stage457_Con4_cash/actual_run1/manifest.json`，39,219 bytes，SHA `ec05a8f444d9c41be1a6a8b7b02cc5d2b8c36d42546e9f9630437d62002c1ffb`。

## 外部调研与独立判断

- 本阶段不是新 alpha 研究；沿用冻结453已列 CFTC 官方时钟/定义、原论文和 cot_reports 血缘边界，不新增网络或 GitHub工程，不把美国周频关系写成国内窄损现金证据。外部资料本阶段未重新访问；本阶段判断来自已封存本地账本。
- 判断：一次固定 Con4/Ridge53 包的现金结果可审计，但不足以通过原157经济门及独立 held 门。不得把失败解释成所有 COT 无效，也不得据本结果改 lag、符号、映射、窗口或模型救参。

## 本次变更与参数

- 新增脚本：`outputs/stage459_Con4_cash_review/review_cash.py`，无作者模块导入，只读保存结果。新增审查输出为 `actual_run1/review_receipt.json` 与 `checks.json`。
- 新增/修改/删除策略参数：均0。新增/修改/删除回测结果：均0；仅独立复核Stage457四账，不重放现金、模型或目标。
- 原口径：初始1,000,000；单家族风险0.0025、总风险0.02、buffered margin cap0.25、buffer1.10、SL0=0.25N、参与率1%；2020与2023起点，结束2026-10-16，base/stress成本。
- 原 accepted157 自身四账作为唯一A，不替换成157原来引用的131/155控制，不引入HGB的Sharpe或年度硬门。

## 实际覆盖与验证

- 独立执行一次，`status=completed`、`core_blockers=0`、`core_problems_remaining=0`；完成148,560项条件核对。
- 最大绝对数值差：`4.6566128730773926e-10`；94个路径在该审查进程均只物理读取一次，DataFrame也缓存复用。
- 覆盖四候选账户全部9类账本（fills/reservations/daily/positions/closed/open/capacity_audit/entry_execution_unknown/rejections）：5,116个账户日、6,316笔BUY/SELL成交、8,207持仓日、3,149个已平root。
- 复算：固定场景费率、人民币滑点、每笔realized gross、root数量守恒及净收益、每日cash/equity/unrealized/margin/frozen risk、净胜率、回撤、Sharpe、stale零价情景、全部95家族含零年度贡献和费用/滑点/成交量、年度连续切片及原A差额。
- 执行纪律：检查全部新信号和boundary lineage、D=u+1、D<K、source/voluntary取min、不可变anchor/contract、整数与1%容量审计、联合预算与D自身预留取min、全部成交与预留身份。原16个小源码精确哈希闭合，原kernel中强制退出、stale和canonical母域合同未变。
- 配对：直接复用原A四本summary/daily及diagnostics，不读其旧fills或重放控制；原252日/2000次indices逐字节绑定，不再生成indices，无epsilon修补。
- 本审查新增fit=0、cash=0、旧cash replay=0、SQL=0、API=0、原nativecache读取=0、原fullactions读取=0。

## 四候选账复算结果

| 起点/成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 费用CNY | 滑点CNY | 已平交易 | 净胜率 | 全成交数 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| primary_2020/base | 2,235,109.6160 | 123.51096160% | -14.43792733% | 0.982999450 | 52,185.3840 | 140,777.498107 | 1293 | 12.374323% | 2589 |
| primary_2020/stress | 1,527,536.4215 | 52.75364215% | -10.94062750% | 0.785084994 | 68,213.5785 | 167,027.045100 | 937 | 12.273212% | 1880 |
| cold_2023/base | 1,884,799.2035 | 88.47992035% | -7.98700314% | 1.395587641 | 20,945.7965 | 54,058.027638 | 496 | 13.306452% | 995 |
| cold_2023/stress | 1,531,189.3740 | 53.11893740% | -6.37735977% | 1.231264049 | 36,595.6260 | 84,549.391160 | 423 | 13.002364% | 852 |

- 滑点已在fill价格中，净权益只再扣费用，没有重复扣滑点。胜率按净已平root，BUY/SELL数量与已平交易次数分开披露。

## 相对原 accepted157 自身A的配对差额

| 起点/成本 | 收益差pp | DD改善pp | 日log均值差 | CI95下端 | CI95上端 |
|---|---:|---:|---:|---:|---:|
| primary_2020/base | 0.58393975 | 1.18949255 | 1.592207194e-06 | -2.688084242e-05 | 2.707454566e-05 |
| primary_2020/stress | -0.08832885 | 0.41867305 | -3.518421816e-07 | -4.8005541e-05 | 3.107557032e-05 |
| cold_2023/base | 5.93626490 | 1.91514558 | 3.497500056e-05 | -7.209809658e-06 | 0.0001045055873 |
| cold_2023/stress | 0.45435505 | 0.04540160 | 3.247809182e-06 | -9.264931927e-06 | 1.711462298e-05 |

- 四账自身收益均正且财富全程为正，DD均较A浅；但主2020/stress收益差为-0.08832885pp，未满足严格增益；其配对日log增长差CI95下端为-0.000048005541，未大于0。其余三账收益改善不能替代预声明主门。
- 两held已知均值门：holdout_0通过，holdout_1失败；holdout_1另有4个异动作结果unknown，未给无界unknown填0。该held诊断不是K现金收益，也未倒用为cash准入否决。
- 独立重建与Stage457 decision一致：`status=unsupported`、`cash_nominal_pass=false`、`held_known_nominal_pass=false`、`nominal_pass=false`、`held_signal_unknown=true`、`financial_unknown=true`。

## 限制与置信度

- 账本算术、精确身份和冻结门重建置信度高，未发现核心bug；无新增native报价重读，不能把本次审查称为独立市场路径再现。实际native open/low/close、tick-size及tick-lots未另行回算；原数据/元数据资格依赖已有接受记录和精确内核源码血缘。
- 候选stale日依序9/5/0/0；容量unknown成交39/19/9/4，entry unknown 2/2/0/0。原A也保留其stale和execution unknown，不因名义现金表现认证执行资格。
- 2026只有截至10月16日的188个源交易日；2020/2023高度重叠，年度是连续账户切片而非各年冷启。CI是同史条件诊断，未经择题校正，不是未见新样本显著性。
- 固定普通发布滞后仍是重建假设，历史first-seen PIT未证；未映射产品可能因53维共同重估间接改变，不能把整包结果归因于纯Con4数值因果。
- 没有新增正式策略、真实券商结算、实盘、加注、goal完成或高质量做多资格。

## 反思与后续

- 开始时过拟合判断：本次机械独审本身否，没有按收益选择参数；历史长期同史择题风险是，必须保留。结束时判断不变，本次失败不允许救参。
- 开始时继续价值：是，仅为封存唯一实验给出可复验裁决。结束时：本固定Con4包继续调参价值否；结束该分支并保留负结果，原四向前账户等待真实21日新事实仍有价值。
- TODO：由root完成研究线合入摘要及实验裁决；本审查不改LINE/registry/根账，不继续扫变体或补原生报价工程。

## 输出

- 审查receipt：`outputs/stage459_Con4_cash_review/actual_run1/review_receipt.json`。
- 检查清单：`outputs/stage459_Con4_cash_review/actual_run1/checks.json`。
