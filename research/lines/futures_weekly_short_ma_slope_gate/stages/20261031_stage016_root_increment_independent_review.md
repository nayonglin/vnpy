# Stage016 context、quote缓存、周五建议与raw结算采集增量独立复审

- 时间：2026-10-31；精确时刻/源SHA见JSON。仅新独审工具与记录，不改作者源码、Git或生产。
- 结论：离线组件条件接受；本次两项P1关闭，开放P0/P1/P2均0。冻结九源批220次、最后missing-day增量26次全部通过，合计246次成功测试调用，有重复，不冒称unique。其中33项新独立测试。
- 本审查无网络、CTP、银行、SMTP、订单或金融回放。真实来源、最终现金日结、生产资格、master晋升和安装均false。

## 两项P1与修复

1. context最初pin目录FD却绝对路径重读，父目录替换会成功写入已移走目录、可见context仍旧。现在读取/替换均同dirfd，且读前后、replace前及fsync后重新NOFOLLOW核可见parent dev/ino。独立leaf-read替换与actual-replace替换均明确失败，可见context不被冒称更新；同generation并发仅一winner，最新cash配置保留。
2. 缓存authority最初只核disk raw SHA，允许内存registry增加未经disk授权的capture kind。现在全body等于实际raw解析结果、真实private key的SHA及缓存key都一致，warm共用同门。独立8例含body/资格元数据污染、key轮换/内存key变化、mtime复原、raw重格式、wrong身份/type及正例复用。

两项初次probe在预冻结阶段未事前pin整个旧文件；记录明确old SHA=null，不反向伪造历史hash。当前1943冻结修复源逐字节验收，旧V5/V6证据不覆盖。

## 资金、行情与周五建议

- context仅推进已验证market generation，不回写旧资金ledger；held来自同连接完整broker positions，未通过base/source不启动market请求。父目录异常可能发生在replace后，须读取对账，不承诺一律回滚。
- quote缓存只省JSON解码，每次仍读并重hash真实committed prefix；同size/mtime复原重写、增量时旧prefix改写、坏tail伪cursor、monotonic过期均独立拒绝。缓存返回分离值；真实journal reader校验commit祖先/序列/字节界限，不以caller标志或mtime替代。
- Friday advice按当前E/R/现金连续性/原native admission算，旧unpaid建议可完整证明后retire并新attempt，建议非债务。已确认整批不能因同批其他ID或后来亏损继续补资；账户gap与付款建议分开。holiday Thursday原decision和decision_state不重跑/改写；先同一CAS提交资金/runtime/advice，再生成receipt/mail；当前data receipt漂移拒绝。
- 最后增量按authoritative calendar查cold-start/恢复cursor与target之间缺失的已完成日；有缺日就要求显式恢复，不跳过AM/daily风险、不回放历史open。周末/假日自然空白不误拦。独立3例与pipeline17/daily6通过，最新support/helper AST单独绑定；session_cycle不在整链签收。
- legacy研究summary即使给出漂亮C9指标，当前weekly19分支仍review/allow_real_new_orders=0、未知E=None。真实weekly typed gate另有来源与资金门，不能从旧summary授权。

## 结算来源硬边界

本机确有reqQrySettlementInfo/onRspQrySettlementInfo；原SettlementInfoConfirm不是全文。新collector只在已完成四查询的同连接/防变更窗口内采原生块，保留空error{}、SequenceNo/SettlementID/Content、原请求与时序；重复/缺号/跨statement拒raw_complete，未知AccountID/Currency不补成CNY，序号起点资格仍false。独立8例及作者7例通过，未执行真实查询。

raw query完成不等于文档FINAL，更不等于全部银行/冲正/费用与gross Deposit/Withdraw完整。QryTransferSerial请求无TradingDay参数。相同新日E/Deposit=0/Withdraw=0可能来自不同旧日现金流与PnL，净出入金0也不能证明gross均0；PreBalance/clock不消除此歧义。真实样本/最终parser仍missing，load_cashflow_day_close保留failclosed。最小原生字段、实际本机header/binding SHA与数字反例见cashflow专属分析。

## 边界与反思

本批不接受真实provider/现金到账/CTP身份、整执行服务/当前生产host；初次真实FULL资格及上层release/activation/startup仍不可由cached fixture替代。原Stage014经济NO_PROMOTION及PIT/零成本/容量局限不变。

是否过拟合：否，不改alpha或历史风险参数，只验证来源、CAS、时序与重复处理。是否继续有价值：是，真实日结来源与整链执行仍是用户目标的技术必需；组件绿灯不能写成已替换生产。
