# Stage009 必要分钟批量补齐与一次C0结果推进计划

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-17 23:56 CST；性质：只读计划，未执行补数或金融回放。
- 目标：尽快得到真实完整C0结果，保持原alpha和严格分钟执行；不再每发现一个缺口就重跑账户。
- 当前依据：Stage005 C0潜在初始需求700个session，其中378个缺124,772分钟；这不是完整账户需求。两种加仓均关闭，仍需换月OPEN完整session及普通CLOSE首分钟。
- 调研判断：[官方回放文档](https://doc.shinnytech.com/tqsdk/latest/usage/backtest.html)和[源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/backtest/backtest.py)支持同一历史回放中的多行情序列；[版本记录](https://doc.shinnytech.com/tqsdk/latest/version.html)记有免费每日3次额度。Stage007已实际取得目标345根完成分钟，证明该账号单窗口可用，不能推广为无限批量授权；Stage008已按正确DB openOI语义重新资格及独立review通过，receipt SHA256为`aab0b7062ff32e67d4fdf2f3132b00188c5779cf59c1462144f002a7b25ddaa6`。

## 只推进三个步骤

1. **一次冻结C0必要需求清单。** 以Stage005的700个初始session为种子，做不算权益/手数/PnL的合约可达性闭包：只跟踪可能持有的合约、方向和换月pending计数；固定延迟首次计0、达到5才due，目标变化重置。保留可能继续持有/提前退出两分支；到强制换月关闭旧仓时转移到可能新合约。为不漏重开，不以普通日线金叉、周门、AI flat许可或AM41删换月机会，目标shape可能40个真实bar已足够。每个可能OPEN列完整首日session，每个可能普通CLOSE列下一全局batch的canonical首分钟；订单保持信号日合约。复用Stage004逐session覆盖cache和本机候选索引，仅对新增OPEN需要完整分钟、CLOSE需要anchor。冻结去重key、来源和缺口数后停止扩张；不把全部metadata/过期旧主的余生session当下载需求。若这个有限闭包尚不能证明不漏，先明确报告边界，**保留严格分钟执行**，不以daily-open fallback绕过。

   实现前须先据真实源码确认“强制换月关闭旧仓并转移”是否无条件、carry旧合约何时不再可达；在此边界确认前不实现复杂分支状态机，也不把上述设想声明为已证明完整的闭包。

2. **先本机、后提供商，批量取齐剩余必要key。** 优先复用已验base、Stage002 overlay和已独立通过的Stage008既有345根；随后仅扫描需求涉及合约的本机Stage491及Stage459/462等已完成来源，核旧manifest SHA、完成依据、时戳/重复冲突和日线聚合，合格者进入独立append-only overlay。OI合同沿Stage008：原CSV核OHLCV/首openOI/尾closeOI；DB核OHLCV及open_interest→首openOI，不捏造DB closeOI。只有剩余缺口才用正常鉴权的公开`TqBacktest + get_kline_serial`；同一TqApi/TqBacktest可订阅多份所需真实合约60秒序列，在一个冻结时间窗口按时间推进，只保存目标session和可观察后继完成证据，不为每session重连。长跨度会推进非目标时段，不能保证一次流在短时间内覆盖所有缺口；按所需合约/时间重叠预先打包，限制并发为1个API、设置墙钟/内存/行数预算并保存进度，遇权限/配额拒绝即停止，不自动重连或切私有接口。官方建议并行回放任务不超过10，不等于承诺无限订阅；本计划不利用配额重置或绕`tq_dl`。Stage007的38秒小样本不用于承诺大批时长。

3. **所有必要key齐备后，只启动一次候选金融回放。** 对整张冻结需求表统一做覆盖/价格/完成证据检查，来源审查只集中在新增数据；保留旧原值和冲突，不重跑旧全量清洗。另核新增分钟与A0实际读取key是否相交：无交集可沿既有路径等价证据复用A0，有交集则先说明共同数据变化，不能悄悄改基线。总readiness通过且新overlay获独立review后，root再决定唯一C0新attempt；数据未齐期间金融回放次数保持0。若仍出现清单外需求，留失败receipt并把缺漏作为闭包问题集中处理，不进入“补一处—跑一次”循环；禁止放松分钟门、改alpha或按截断PnL调整。完整结果后才安排一次结果独立review并判断收益/回撤是否改进。

## 本阶段结果与反思

金融attempt、下载、训练、正式源码修改均为0；权益/收益/回撤/Sharpe/滑点/交易数/胜率均N/A。本计划不批准立即连接提供商、重跑C0或启用fallback。

过拟合判断：否，本计划只按已冻结交易逻辑收敛数据需求，不看收益选参数；既有历史选择风险保留。继续价值：有，优先一次收敛、一次批量补齐、一次完整候选结果；无必要新增泛化数据源综述或逐个缺口的金融重试。
