# Stage008 最小差异独立复审

结论：通过，P0=0、P1=0。可接受原Stage007保存的**rb2010.SHFE、交易日2020-08-12、345条完成分钟K**作为研究补数。raw SHA固定为`0805e7083b24e988469bee78fabc53419d2855e85f92928256a184d9db9480ac`。此资格不等于已并入缓存，也不等于C0_attempt3就绪。

本次复用Stage007独立完成的345行网格、合法性、逐bar后继及原CSV七字段聚合核验，没有重跑这套核验、SDK、网络、SQL或金融账户。新增工作仅是读取新源码/合同/产物、核对13字段映射及14个输入当前SHA，并核查末bar证据。审查脚本运行exit0。

13个必需比较恰为：原CSV的OHLCV/openOI/closeOI七项，DB OHLCV五项，DB `open_interest`对首分钟openOI一项。全部精确相等，绝对差为0；没有伪造第14项“DB closeOI匹配”。`database_close_oi`明确为`N/A_not_independently_available`。导入器源码SHA和第115行openOI解释与Stage007独立证据相同；本次未修改原策略仍使用的DB OI口径。

分钟首OI1,064,817、末OI1,053,986。两值分别由CSV相应字段验证，DB仅独立提供本来源的首OI1,064,817。末目标bar为08-12 14:59，保存的后继为同日21:00，完成证据引用不变。字段语义限定于这个已证明的导入来源和目标session，不泛化其他DB来源。

Stage007原quality SHA仍为`9bf02a770b12c7fe65d2efb105e3bfc4f29227d2961352eb0a614a6d5eb6625e`，`accepted=false`、worker `completed_quality_rejected`、parent exit1都保留。原Stage007字段映射P1由另立Stage008正确来源合同处理，没有回写成“原运行就已验收成功”。

本次没有发现Stage008新增P0/P1。资格通过只允许把这份精确raw作为后续单独受审的append-only研究补数来源；不能自动合并base/overlay、启用fallback、修改alpha/正式资产或启动C3。Stage005即时初始需求仍不覆盖两个已知实际失败路径，完整订单需求闭包尚缺。累计金融attempt仍4、完整仍1，C0 alpha不可评价。

过拟合判断：否，依据已验证字段语义、原始字节和固定比较，不看收益或寻优。继续价值：是，已确认可用的一份数据不应因旧校验错位而被丢弃，同时应先完成需求覆盖再安排后续补数。调研沿用Stage007/008预声明的官方资料和本地导入器证据，本次未增加外部事实假设或联网调研。
