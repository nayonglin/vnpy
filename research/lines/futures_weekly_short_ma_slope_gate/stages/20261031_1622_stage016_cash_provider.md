# Stage016 原始券商现金/持仓/成交provider条件组件

- line_id：futures_weekly_short_ma_slope_gate；day。
- 记录时间：2026-10-31 16:22 CST。
- 工作树：/Users/mac/.codex/worktrees/weekly19-official-20261031/fian；旧研究树及生产目录只读。
- 性质：真实原始只读查询的capture/转换候选组件；不是完成真实验收或实盘上线。
- 是否重要突破：否，是必要证据链补齐；production_qualified=false。
- A/B：不触发。alpha、原19、周线保护、风险参数与此前研究业绩均未改。

## 外部调研与判断

- 对照[官方vnpy_ctp原始CTP头文件](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/api/include/ctp/ThostFtdcUserApiStruct.h)及本机已安装CTP6.7.2.1头文件读取TransferSerial/QryTransferSerial字段；对照[官方网关源码](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)了解generic AccountData没有Deposit/Withdraw/TradingDay的丢字段边界。
- 本地核验：TransferSerial原始字段有PlateSerial、BankSerial、FutureSerial、TradeCode、TradeAmount、AvailabilityFlag、ErrorID、TradingDay、TradeDate/TradeTime等。CTP6.7.2.1 valid=1、invalid=0、repeal=2；银行/期货发起入金代码102001/202001，出金102002/202002。
- 判断：不复用Stage655无generation松散CSV证明真实入金。Stage174现有原始回调、reqid、v2 query bundle、生命周期generation、mutation firewall和exact-zero counters具备可复用结构，但原账户callback此前未持久保存；本组件补充可选private capture。
- SHA只证明字节一致，不能证明broker来源；同一用户手工伪造的raw/fixture即便自洽也不能获得生产资格。所有接口始终qualification=false，默认生产模式缺accepted capture/qualification authority直接block。

## 变更

- 新增 qmt_roll_weekly19_broker_evidence.py；新增 tests/test_weekly19_broker_evidence.py。
- Stage174最小增量：可选 --weekly19-material-release-id、--weekly19-execution-profile、--weekly19-private-capture-dir；需要非空invocation-id。关闭这些参数时保留旧发布行为。
- Stage174 account/positions/orders/trades四类callback除reqid外明确匹配当前connection_generation，记录generation元数据；只保存命中显式查询的原始data。
- 新增private JSON原始artifact，保留原生账户/持仓/订单/成交、四类callback、五类query metadata、runner invocation/source commit/source SHA、firewall关闭窗口和0订单/银行mutation counters；0700父目录、0600文件、全路径O_NOFOLLOW、不跟软硬链接、原子不可覆盖发布。原始账户ID/银行字段不写入stage或stdout。
- 原始artifact SHA与generation引用同时进入summary和最后发布的manifest。没有增加默认连接，没有执行银行查询或转账，没有改CTP凭证与生产定时任务。

## 公共接口

1. load_broker_snapshot(summary_path, manifest_path, *, expected_account_key, material_release_id, execution_profile, now, trusted_source_hashes, require_production_qualification=True)。验证Stage174 v2完整query bundle、独立重读normalized CSV字节SHA、raw capture与callback计数/last/error/reqid/generation/时间、runner source SHA与release/profile/account绑定，返回account/positions/orders envelope。默认生产资格缺失阻断；显式false只供条件组件/离线审查，不是绕过发布门。
2. read_account_snapshot(account_envelope, *, expected_account_key, material_release_id, now, max_age_seconds=300)。返回equity_fen/balance_fen、available_fen、margin_fen、unrealized_pnl_fen（缺PositionProfit明确None）、currency/trading_day/observed_at/raw_sha256/account/release/generation。Balance已含MTM，不再加PositionProfit。要求strict decimal、query_error_rows=0、query_last_seen=true、fresh/aware时间；仅条件解析不赋源资格。
3. load_broker_fills(summary_path, manifest_path, execution_ledger_rows, **相同policy)。成交量、价、时间仅来自native Trade字段；stable trade ID须匹配原始Broker/Investor/Exchange/TradeDate/OrderSysID/TradeID；原始OrderSysID唯一反查FrontID/SessionID/OrderRef形成broker_order_id，再与durable execution ledger唯一映射原intent/signal identity，拒caller completed_volume自报。query成交明确source_callback=onRspQryTrade，不能伪称onRtnTrade实时。
4. TransferSerialCollector(account_envelope, connection_generation=...)；begin(td_api, query_reqid=..., now=..., current_connection_generation=...)只可调用原生reqQryTransferSerial，不含任何银行转账/报单方法。
5. instrument_transfer_serial_callback(td_api, collector, connection_generation=callable, clock=callable)安装对应native回调，上下文结束/异常恢复；同进程锁拒并发class monkeypatch。由已有可信runner在同一firewall内持有原生连接与generation；本工具不创建或认证连接。
6. persist_transfer_serial_capture(path, collector, now=...)把完整原生银行流水字节以0600不可覆盖artifact保存；仍qualification=false。
7. load_bank_cashflow_receipt(raw_source, *, state, request_id, bank_serial, now, require_production_qualification=True)。支持上述原生query条件解析，核对真实原字段金额/流水ID/账户/名义日/时序，拒未知、撤销、出金、费用未定义、失败或重复serial；默认缺accepted真实runner资格仍block。显式false只用于fixture/协议审查，不能直接用于生产。
8. load_cashflow_day_close(raw_source, **policy)保留严格未接受来源闸门：accepted_cashflow_source_missing:final_cashflow_statement_parser。

## 尚缺的真实证据及下一步

- **没有真实capture运行，也没有真实银行流水或完整日切验收。** 单元fake不是broker源证明，私有SHA也不是来源签名。require_production_qualification=true尚无accepted authority，因此资金实际开仓/发布不能由此放行。
- 仍需root把真实Stage174 raw capture runner纳入不可变release、qualification与activation provenance闭环，并真实核对0 mutation counters/源哈希/env runtime与账户。当前collector本身不能自己宣称资格。
- 银行流水：需真实reqQryTransferSerial的完整原始回调样本、匹配reqid/connection generation、当日完整列表及其原始private artifact，由trusted runner绑定manifest。当前提供可调用原生只读adapter接口，但未执行真实query、未自动插入Stage174连接流程。
- 正常日切（含无pending）仍需最终现金流证明：真实券商最终statement完整原字节及格式/版本、账户与TradingDay、所有银行/冲正/费用覆盖、FINAL Deposit/Withdraw、finality/cutoff语义、权威next TradingDay和匹配关闭account原始SHA。缺这些不能把cashflows_complete置true。**query-last仅证明本次查询结束，clock到收盘不能证明后续再无转账。**
- 当前无accepted statement样本/解析器，load_cashflow_day_close明确阻断；不能把“全部永久block”说成可实盘资金功能已完成。需真实凭证驱动下一阶段parser/连续现金流qualification，禁止用JSON自报complete救门。

## 测试与证据

- TDD：实现前15tests全部因provider缺失失败；实现后新增公共账户/collector/原始映射反例先红后绿；再补源时间刷新、成交名义日和callback安装/私有保存反例，最终23tests OK。
- 新provider 23 + 既有Stage174 22 + 既有broker_account_snapshot 25 = 70 tests，全部exit0；日志及SHA见同前缀_unittest.txt/_manifest.json。
- 三个改动文件用Python内存compile通过；未跑金融回测。期末权益、总收益、回撤、Sharpe、滑点、成交数、胜率、payoff/PF不适用，旧研究结果不变。
- 未执行真实CTP connect、SMTP、银行操作、生产文件写入、Git index或commit。
- 已请求root安排独立只读审查；最终审查结论另存，不在本记录预先宣称通过。

## 反思

- 开始/结束过拟合判断：否。只修证据和现金守恒执行边界，不看历史收益、不扫参数、不改变alpha。
- 开始/结束继续价值判断：是。完整generation原始现金和实际成交归属是必要生产前置；后续价值在真实provider/statement及资格闭环，不在调资金比例或事后变更信号。
- 本agent只写本线唯一stage，不改LINE/registry/根总账或已锁资金组件。
