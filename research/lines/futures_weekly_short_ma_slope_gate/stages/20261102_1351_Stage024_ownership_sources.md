# Stage024 既有持仓归属与开仓来源只读调查（脱敏）

- 时间：2026-11-02 13:51（北京时间）。研究线：`futures_weekly_short_ma_slope_gate`。
- 授权背景：用户允许按当前真实权益动态风控，不再要求启动权益恰等于基准金额或预设空仓。该授权不应被误写为原仓真实开仓时间、止损或策略归属已经得到证明。
- 本文只披露来源、字段可用性和缺口；实际合约、方向、数量、成本、权益与账号不写入Git记录。真实字段仅存原Stage023私有证据及独立0600调查副本。
- 重要突破：否。这是接管来源调查，不是策略优化或回测。没有修改任何gate、runtime、alpha、配置或生产内容；没有使用Git。

## 结论

在下述本机已声明生产/手工数据范围内，未发现能与目标既有仓逐笔匹配的真实opening-fill执行账本、旧C9持久保护状态或手工策略ownership记录。现有真实Stage023归档能证明其观测时点的聚合持仓及聚合成本字段，不能证明原始开仓日期、逐笔成交价、原始止损、C9归属或weekly19已接管。

原生聚合字段可判断该归档中的目标为隔夜持仓；“隔夜”不能推出具体OpenDate。该快照也已不是当前发送前可用的新鲜证据，不能替代后续原有fresh账户、持仓、订单、行情及交易时段门。

## 已检查来源与边界

| 来源 | 只读结果及边界 |
| --- | --- |
| `~/Library/Application Support/qmt-roll-stage179/production-live/` | operational `official-live`、`signal-input`、`runtime/state`、`logs`等目录没有实际运行状态文件；离线资格pytest fixture/回归副本不算真实execution证据。 |
| stable `examples/portfolio_backtesting/backtest_outputs` | 该目录是指向原person/vnpy输出的符号链接；核对实际目标，未发现默认phase_d execution ledger或Stage904 durable state。既有旧Stage174输出不提供目标开仓链。 |
| `/Users/mac/Desktop/person`已声明vnpy目录 | 排除Git、环境、研究回测及test sandbox后，没有发现execution ledger、C9状态、portfolio/CTA数据、manual ownership/trade/order记录等候选真实结构化文件。 |
| stable及用户`.vntrader` | 未见portfolio/CTA策略持仓状态JSON；现有database仅bar/tick及其overview表，没有交易/持仓ownership表；日志未发现目标合约事件。native flow文件没有作为账本解析或冒认历史成交。 |
| `/Users/mac/Desktop/fian`旧Stage901输出 | 仅见shadow研究理论positions/trades等；不能以其entry date、price、stop代替真实券商开仓及归属。 |
| Stage023真实私有raw/query归档 | 有目标聚合持仓的唯一匹配行；OpenCost/PositionCost等字段存在，缺OpenDate、TradeID、逐笔OpenPrice、StopPrice及root_position_id。归档orders/trades不提供该历史opening fill；同一contract归档也没有该持仓合约的匹配metadata，未擅自补size计算成本价。 |

未读取env、vt_settings、密码、SMTP配置或其他凭证。未穷尽未声明的其他软件、用户自定义外部输出路径、券商后台或本机之外历史；“本次范围未找到”不等于断言所有位置都不存在。

## 成本语义与资料核对

已对照[官方vnpy_ctp gateway源码](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)及[原生CTP结构头文件](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)，并核本机实际安装的gateway与header。判断：

1. 本机`onRspQryInvestorPosition`用PositionCost/(volume*size)生成PositionData.price。不能把这个归一化价格直接当作逐笔原始开仓价；OpenCost也只是聚合成本，不包含逐笔时间/归属/止损。
2. CTP InvestorPositionDetail原生字段含OpenDate、TradeID、OpenPrice、Volume、Direction、HedgeFlag、TradingDay；当前Stage023只有InvestorPosition聚合查询，不能凭字段缺失逆造detail。
3. 原始TradeDate/TradeTime、TradingDay和detail.OpenDate语义需保留，不能用“上一交易日”或当前目标日推造；真实明细可能支持持仓lot识别，但不会自行证明属于某个策略或原止损是什么。

## 最小接管资料与可复用API

这是供root设计接管事务的字段清单，不是已取得或已授权发送的声明。

- 券商事实：同一账户的fresh原生account/positions/orders、完整reqid/last/error、当前connection/service generation；目标原生持仓明细OpenDate/TradeID/OpenPrice/remaining Volume/Direction/HedgeFlag/TradingDay，以及可绑定的实际opening fill标识与时间。逐笔剩余量应与聚合数量守恒。
- 策略来源：若要沿用旧C9归属，应有真实ledger intent/order/fill/root/epoch和持久原始/现行保护状态，能与上述lot唯一绑定；目前未找到，不能拿shadow或新建假fill替代。
- 若用户要以外部持仓接管而非声称历史C9，应明确记录operator_manual接管来源、账户/release/profile、接管时点与原始证据SHA、所接剩余lot、起始持仓owner/epoch、真实成本语义和当前保护方案的来源/适用时点。新保护线如由当前完成行情按正式规则建立，必须如实写为“接管时建立”，不能称作“原开仓止损”。资金仍只用fresh CTP E/Available，不把未用备用金或假定利润虚加入账。

可复用代码与限制：

- `qmt_roll_weekly19_broker_evidence.load_broker_snapshot/read_account_snapshot`：沿原真实source与freshness核验账户/聚合证据；本调查没有执行连接。
- `run_qmt_roll_stage931_official_live_ctp_submit_adapter._final_position_detail_query_epoch`：现有真实同连接detail查询/完整性路径，可在root后续授权的只读连接里复用；本次没有调用，不声称detail已取得。
- `qmt_roll_official_live_broker_position_ownership.validate_position_detail_ownership`：在真实ledger与完整raw detail已存在时验证owned lots，不负责凭空建立归属。
- `qmt_roll_official_live_broker_open_date_seal.build_open_date_seals/validate_open_date_seal`：需要原native订单、canonical fills、reservation历史及query绑定；缺历史不能凭当前detail造seal或假称旧C9通过。
- `qmt_roll_weekly19_runtime.build_weekly19_runtime/Runtime.export_state/Runtime.reconcile_broker_snapshot`：可承接与持久化已证明的runtime状态；目前没有公开adopt_position API。reconcile核对已有confirmed layers，不能把外部仓自动变为有保护策略仓。`apply_broker_fill`要求原pending intent及严格原生身份，不可用于假造历史入仓。若接管外部仓，需要显式、可审的初始化/ownership事务；不能仅删除flat gate后冒称链路齐全。
- `qmt_roll_weekly19_funding.initial_state/validate_state/apply_operator_cash_review`：资金人工核验及R/T守恒仍可复用；不能以“当作已盈利”推导虚构transfer或把旧余额变化当到账。

## 私有证据与操作计数

私有副本（目录0700、文件0600）：
`~/Library/Application Support/qmt-roll-stage179/weekly19-qualification-candidates/Stage024_ownership_20261102T135053/ownership_investigation.private.json`

SHA256：`90794191be63141fd2d316b32ffa03cf7895e602aff3eeca2875bbc26224aaf0`。其中只保存所需聚合字段、原始来源引用及明确缺项；没有假造OpeningPrice/日期/止损、native回调、HMAC或operator确认。原Stage023 raw前后SHA一致。

本次CTP连接/订单/撤单/SMTP/转资/安装/金融回放均为0；未修改已有账本、私有运行状态、生产、源码、manifest或历史物料。新增/修改/删除策略参数均无，新增/修改/删除回测结果均无，收益/回撤/Sharpe等不适用。

过拟合：否，只核已有事实来源。继续价值：是，明确了“当前实权可用”和“既有仓可证明接管”是两个独立问题；下一步应补真实lot/人工接管合同与保护状态，不能用缺失的历史字段作默认值。
