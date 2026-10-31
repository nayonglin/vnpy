# Stage016 资金V2与私有存储独立复审

时间：2026-10-31T17:04:10.844996+08:00；line_id=futures_weekly_short_ma_slope_gate。PASS_OFFLINE_COMPONENT_WITH_LIMITATIONS，组件未解决P0/P1/P2均0；仅条件接受离线资金纪律/持久化，不接受真实provider、到账E2E或生产qualification。production_qualified=false。未金融、连接CTP/银行/SMTP、改实现/生产/原Stage014、改Git index或提交。

资金作者55 tests（0.191s）与独立40 tests（0.226s）全部通过，95 tests/exit0。40为旧25安全反例在V2重跑＋15个V2/首创锁反例，所有账户与银行JSON都手工FAKE，不是现实资金资格。命令和关闭后日志SHA见JSON，前后源码SHA相同。

V2接受语义：旧建议不是债务；真实E>=150000时旧pending不额外封开，partial已达floor不强补未付余款，R仅按真实已确认现金递减、不因权益涨跌回填。未知Deposit/Withdraw即使E恢复仍拒；当前gap不同原cap不能改，request_refresh_required不可操作；完整已证现金链retire后新attempt，旧request/receipt与first admission归属不重指、attempt只追加。已confirmed或equity_recovered/expired退休候选不能被source/broker generation变化重补。晚到旧款、未知款和缺名义日连续链仍阻断，过期可沿完整链收齐证据后退休，但不延长原expiry。

独审从Git09e7e07e8真实V1资金源码构造partial账本，验证升级前后身份/金额/request/receipt逐项一致、revision只+1且单CAS；旧同版WAL恢复后才显式迁移，变异升级/版本降级/retirement和attempt删除拒绝。V1原接受JSON SHA8db39cd...仍与该Git checkpoint完全同字节，不覆盖旧证明或把新语义写回V1。

存储保留逐dir O_NOFOLLOW、0700父目录/0600文件、owner/nlink/私有检查、flock、CAS、WAL/fsync/atomic及单调账本。Mac27.0原始openat(O_CREAT)首次同名并发探针20次6失败，根因在stage016_openat_independent_probe.json保留；新store用O_CREAT|O_EXCL后EEXIST纯open-existing、最多8次removed-race处理，无绝对路径/安全降级。独立首创锁、两进程CAS一胜一冲突、WAL三故障点、重启/重复receipt不双扣、0E/负E不fallback均通过。旧1636 manifest/store e519...保留；本次接受实际store d5d40...，这是修后新快照，不宣称旧manifest可验证新store。

必要条件仍在组件外：真实native admission稳定且仅在新信号批次；真实qualified原始account/cashflow/day-close完整来源；成功CAS持久化后才发布/开新；broker Available/保证金/时段/报价/仓单与全局资格单独核验；平仓减风险不误经open资金门。自造hash自洽raw可通过离线函数且state始终false，故hash与测试绿灯不是源真实性。真实银行serial若无native request ID，request归属还需另证；退休旧付款不得并入新request。

95测试无历史收益寻优，组件审查过拟合判断否；原Stage014同历史选择风险及NO_PROMOTION记录保留。V2处理真实等待而Stage014模型即时补入，其实际资金/手数路径不能直接等同旧曲线。继续价值是，下一步验证真实provider/完整现金流与全消费者，不是凭本记录完成生产晋升。[Python锁](https://docs.python.org/3.11/library/fcntl.html)与[同类openat上游修复](https://github.com/entireio/cli/commit/9c18f31b23a62749b804718125b17c236420a28a)仅供参考，本机独立反例是主要证据，未升级Python/vn.py。
