# Stage039：全市场跨日long参考与研究现金账本固定协议

- line_id：`futures_full_market_long_signal_ai`；2026-10-18 13:22 CST。
- 范围：国内六所全部98目录产品/真实epoch及无观察状态；沿当前分支，不新建branch/worktree，不改正式策略，不提交、推送、部署或CTP。
- 目标：建立能承载跨日趋势、同期资金竞争和真实货币损益单位的固定参考，供后续AI质量识别、窄损、加注分别检验。**本参考无AI、不是窄损成果，不替代完整目标。**
- 过程：按已授权自主研究先完成设计/独立复核再实现。新增独立研究基准，不与正式版组合或晋升；不跑无关正式A/B/C和资格套件。

## 调研、取舍和收益前冻结

读取registry、LINE及038收益盲设计、040独立设计复核。root实际核对[原Turtle规则发布页](https://www.tradingblox.com/originalturtles/originalturtlerules.htm)、[原作者长期趋势论文](https://arxiv.org/abs/1404.3274)和[pysystemtrade作者breakout源码](https://raw.githubusercontent.com/pst-group/pysystemtrade/master/systems/provided/rules/breakout.py)。长期趋势实证不保证本国内long政策盈利；55/20/2N是经典风格的收盘适配，不是双向/盘中/金字塔原Turtle的精确复刻，也不搬用其收益。

取舍：停止继续DAY价量派生信息包；不把三重滤网提问变成一组新增指标矩阵。一次实现完整跨日政策和同期研究账本，比延长DAY标签或仅做事件R更接近用户终点。038无新成绩选择，040指出的三项Important在此明确修正：u收盘预留、研究假设与生产资格分开、缺价模型有限延迟退出。040设计C0/I3不是已运行代码缺陷。

冻结输入：003绑定、004已接受全产品日表/身份/代表规则、266只读真实合约行情、完整5587源日历及4074报告日期、Stage265 futures_metadata.json的epoch经济字段。041仅提供有限经济字段投影与来源；其最终SHA在同目录机器协议input bindings中绑定，未绑定前不得执行实际全期。DB沿003接受的size/mtime/inode与SHA继承校验，不再大库hash；只读一次所需行情，不新下载或盘点。

## 价格政策与全母体

1. 母表保留004全部399252行，包括无accepted观察、历史未上市/结束/缺价；reference沿u日当时成交量→closeOI→epoch，不使用D成交量/未来主力。family为exchange+去末尾_F的product，只用于重复敞口管理。
2. 对同epoch连续合法正量source bars计算历史。入场需56根连续bar；u的确认条件为`C(u)>max(H(u-55)..H(u-1))`。原009的21bar ready不覆盖本合同。TR首bar为H−L，后为max(H−L,abs(H−prevC),abs(L−prevC))；连续段第20个TR均值为N种子，之后`N=(19*Nprev+TR)/20`，缺口重新暖机。
3. 每个产品日均保留ready/不ready及breakout状态。符合时形成potential意向，不因已有仓、资金不足或最终失败而删除。D严格为下一source day，只尝试一次同epoch D.open；末尾意向为右删失。入场前u的20日低为Bpre；若D.open<=Bpre，`stale_breakout_cancel_at_open`。R0=2N(u)，SL0=D.open−R0；非正风险或SL0<=0明确取消。
4. 仅做多，一family最多一个活跃root，无retry/pyramid。入场日B=max(SL0,u已知20日低)。后续v收盘用含v的过去20个连续同epoch合法low计算L20(v)，下source day的B=max(SL0,L20(v))；不要求B单调，不偷偷改成只能收紧的另一政策。无固定止盈、最长持有日或盈利倍数规则。
5. 先执行上一收盘已知的强制开盘平仓；否则O<=B按O参考退出，L<=B按B参考退出，其余持有。入场同日止损可生效，含当日的20日低不能反向同日生效。跳空可小于−1R，不截断亏损。
6. v收盘代表epoch改变或无accepted代表，则下source day用**旧epoch**开盘参考退出；不自动续仓、不拼新旧绝对价。保守研究期限取标称交割YYYYMM首source日与已知vendor maturity/delist对应source日中的更早者；执行日达到边界则禁止新入，已持仓预先请求该日开盘退出。_F/INE实际到期可能早于标称合约月，不能只读symbol。它不是全部交易所真实期限制度证明，也不回看最后一bar决定退场。
7. 同family多candidate时，仅对有经济身份的现金候选普通表达优先于_F，再product/epoch字典序；不按未来质量排序。被占用/经济缺项/F候选全部保留原因。价格母体和每个现金账本分别维护占用；资金拒绝不能让现金账本照搬本来没有成交的价格母链持仓。平仓日不重入，收盘后才能形成下一日意向。

## 价格证据、缺价、成熟和右删失

精确价格母链遇预定入/出场或持仓日缺合法bar，记path/execution_unknown，后续不伪造已知闭合标签。末尾正常持仓open_right_censored，末close浮盈单列，不贴完结训练标签。闭合已知label_known_date为exit source day收盘；未来训练按真实entry/exit区间purge，必须严格成熟后才能用。本轮0模型。

研究现金另采用明确假设：入场D缺价则一次取消；持仓缺价不释放仓位/预留，last valid close作stale mark，停止该family新入并持续退出请求，首次随后有合法旧epoch open时按不利成本延迟平仓，之后下一收盘才恢复。原价格证据仍unknown，研究平仓不是成交事实证明。不为增加样本前填OHLC或跳过缺日后继续正常趋势持仓。

终点未决列出数量、最后mark、stale天数和名义额，并另报未决long按0价估值的全名义损失压力，不称普遍现金下界。每个daily还保存stale-long零价估值供不确定性评估，不用该压力账本决定实际模型下一日手数。正常开放仓按末close mark，留未实现与已实现分解。

## 唯一研究资金/成本合同

两scenario都交付，不择优。所有元金额CNY，初始资金1,000,000；与官方15万无关，不扫本金。全部日盯市统一采用同epoch close，明确是研究mark、不是实际settlement；不在中途混合切换计价法。保证金冻结不是损失，日损益不能与最终全段PNL重复入账。

| 项目 | base | stress |
| --- | --- | --- |
| 单family新仓目标初始风险 | u权益0.25% | 同base |
| 总开放初始风险上限 | u权益2% | 同base |
| 总保证金预留上限 | u权益25% | 同base |
| 研究保证金率 | max(epoch vendor率,20%)；缺率20%假设 | max(epoch vendor率,40%)；缺率40%假设 |
| 每手每边手续费 | max(2元,成交名义额×0.0001) | max(6元,成交名义额×0.0003) |
| 不利滑点价格 | max(已知1tick,参考价×0.0001) | max(已知3tick,参考价×0.0003) |

tick缺失使用相应bps并标未tick化；若有已知tick，买价向上、卖价向下对齐格点。只使用有证据的epoch multiplier，不拿当前产品均值替历史变更；来源不明的经济身份只留potential/unresolved。静态vendor margin/tick/费用fallback均标历史假设，不能声称逐日真实。041确认的可用元字段投影与映射规则在代码中固定，无按收益选择来源。

初始风险单位包括`2N×multiplier + 预估往返手续费与滑点`；预估价格u close，实际SL仍按理想D.open−2N，不能入场后缩stop来维持账面风险。现有持仓按初始入场风险每手持续占用，不因浮盈/退出位提高而增加额度。

## 因果预算、开盘执行与风险退场

u收盘，先用已发生的现金/持仓close mark计算权益、margin、已持仓初始风险。不能提前释放预计D平仓的保证金或使用D盈亏。对全部明日候选以u close形成单family目标实数手数，按**全体共同系数**同时缩放，系数=min(1,剩余2%风险/候选风险,剩余25%margin/候选margin)。新仓预留margin用1.10×u close×multiplier×margin_rate；现有持仓也按1.10×close计预留。最后统一整数floor到round_lot，不min+1，不按文件顺序补手或重分配剩余零钱。每个候选记录独立风险/保证金额度和qty上限。

D各自开盘时仅能在自身预留内执行原qty或减手/取消；实际名义额和滑点/手续费若超过自身margin+费预留/风险额度，按同一公式floor减手，不可放大或在订单间重分配。D已退出释放资金和稍后开盘价格不能用于当天新仓。用D收盘结果只能影响下一次u预算。budget是保守模型额度，不保证跳空/盘中亏损上限。

若u收盘已有仓的初始风险或buffered margin超上限，暂停新仓，并按u收盘共同缩放系数确定所有持仓的下一日减仓目标（floor），D以各旧epoch open执行所需差额；正常价格/期限强制全平优先。缺价减仓转持续待退出，不伪释放预算。不得用全D.open重新共同求系数。若权益<=0，账户标insolvent、永久停止该window新仓，下一日请求全平；继续报告负权益/剩余敞口，不把资金归零重启。margin上限只验证收盘/预留状态，不代表实际盘中保证金峰或broker资格。

## 一次实际运行、固定窗口与交付

实现/小fixture验证后只启动一次实际全期任务，一次读取accepted source，在同一程序交付：

- 全399252行signal status/potential（可用压缩状态表）；2010全期无资金价格母链、episodes/position_days/unknown。
- 2 scenario×9独立现金冷启动window=18账本：2010全期、2020全期、2020..2026各自然年（2026止于10-16，明示不完整）。同一warmup资料可用，期初持仓为空、不可带入前窗账户；终点未平仓正常mark而不生成假exit。
- 窗口第一source开盘前即为空仓账户；若前一个source u有已完成信号，可用初始资金在该u预留以便首日执行，warmup只供历史和该次预留。没有前source时首日收盘才可预算。不因把首日预算挪至收盘而漏掉整个首日机会。
- 各window全部fills、cash/realized/unrealized/equity/margin/reserve/risk、逐日恒等式、potential拒绝原因、source与经济假设覆盖、stale/右删失及费用/滑点。
- 期末权益、总收益、最大回撤、Sharpe（日收益样本std ddof1、sqrt252）、闭合交易次数、闭合net胜率、费用与滑点金额；开放和未知分别披露。初始权益纳入回撤峰值，无风险利率0；若破产则保留负权益/总损益，Sharpe标N/A，不在负权益上计算常规收益率。

不训练、不下载、不重跑旧套件、没有2/3年大矩阵或阈值扫描。计算成功不是盈利通过；本轮结果仅建立参考及评价下一研究是否值得。两情景都负或经济未知足以翻转结论，则保留负/不确定基准，停止本55/20/2N包主动救参。即使正，也不直接宣称AI、窄损、加注或跨周期稳定优势，更不晋升正式版。

## 实施与独立验收计划

Stage042只新增本线独立engine/runner及必要行为测试，先有限RED/GREEN，核心覆盖未来prefix、N暖机/缺口、entry-day退出位时钟、gap超1R、真实旧epoch换月、family/F与现金拒绝独立占用、u预算/D不复用、stale延迟、分批减仓和现金PNL不重复；不写镜像实现测试。root读取新合同与测试范围后授权唯一actual；不得自行pilot或重启，失败需保留terminal再判断。

Stage043独立agent在一次实际任务结束后复核：新源码、输入/经济映射、事件因果与缺价、全fills/每日现金恒等式及所有18报告、参数固定和主要局限；不调用作者核心计算函数、不重训/重跑全策略。重大bug仅修影响结果的实际问题，记录所有真实启动次数，不为小问题反复跑。Stage044由root决策/更新本线状态，必要资产按显式role保存，不复制raw DB/OHLC。

开始过拟合反思：没有用新收益选择数值，故不属按成绩救参；但经典框架与资金情景仍有研究选择风险，不是全新未见策略。继续价值：是，这是从价格proxy转到跨日经济与真实资金竞争的必要一步，未改变完整目标。所有运行后指标/反思待实际结果，不预填成功。
