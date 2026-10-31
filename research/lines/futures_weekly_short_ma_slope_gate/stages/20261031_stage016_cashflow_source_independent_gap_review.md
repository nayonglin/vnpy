# Stage016 最终现金日结来源独立只读分析

- 2026-10-31；未发起网络、CTP、订单、银行或SMTP调用。仅检查本机CTP头文件、Python binding和当前源；真实来源/production资格为false。
- 结论：有可用的结算全文查询接口，故“用户没有导出目录”不等于完全取不到券商文档。当前仍没有真实accepted样本与最终现金日结parser，不能放行跨日现金连续性。

## 可用接口与现有缺口

本机公开binding存在reqQrySettlementInfo/onRspQrySettlementInfo。请求含BrokerID、InvestorID、TradingDay、AccountID、CurrencyID；数据块含TradingDay、SettlementID、BrokerID、InvestorID、SequenceNo、Content、AccountID、CurrencyID。现有Stage174原逻辑只捕获SettlementInfoConfirm；确认回报没有现金额，不能充当结算内容或FINAL证明。

最小collector应在同一受控只读连接内保留精确请求、reqid/return/error/last、连接/服务generation、每个原生data/error callback与时序，以及全部SequenceNo/Content；私有0700/0600存原包并SHA绑定runner/native解码来源，不改写、猜字段或以normalized对象补。Python回调Content已经过被冻结扩展toUtf解码，不能冒称原始wire字节。

Root正在另加可选raw collector；该增量只能标raw_complete_unparsed_unqualified、statement_finality_qualified=false，不能替代当前dayclose stub。实际采集授权/环境与资格由root独立执行，本审查没有连接。

## 硬边界

query-last证明本次返回结束，不证明旧交易日银行现金流已经最终封账。QryTransferSerial请求本身没有TradingDay参数，不能据此保证取全旧日所有银行/冲正/费用。Content是券商文本，需真实vendor/template/version与完整样本来确认FINAL语义；只有净“出入金”也未必能给gross Deposit/Withdraw。

例：最后已知E150000；新日E160000且Deposit/Withdraw均0。既可能无现金流、PnL+10000，也可能旧日末补20000且PnL−10000；日计数reset后端点完全相同。即使文档净出入金0，也可能deposit20000/withdraw20000，不能冒认两者均0。PreBalance或clock没有消除该不可辨识性。

现资金reconcile_trading_day还要求真实FINAL gross Deposit/Withdraw等于具体closing account原包、finality时刻及权威nextTradingDay，然后新日0现金流初始快照。缺这些或完整等价总账证据就须继续阻新开；减仓保护不应随建议/现金证据缺口一起丢失。

是否过拟合：否，只有来源与会计证明，无alpha/历史调参。是否继续有价值：是，可以只读采样结算全文，但采样成功本身不等于最终现金连续性、实盘资格或到账。

字段与精确本机路径/原字节SHA、三条端点反例见同目录JSON。
