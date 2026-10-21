# Stage128：初开合约月份选择一次固定协议

时间：2026-10-18 21:33 CST；非突破版。line_id=futures_full_market_long_signal_ai。当前目标仍是完整全市场long-only的高质量信号、窄损研究；不讨论Triple Screen，不缩旧月池，不改正式版本。

研究问题：canonical maxV→OI→epoch只是一个预定义动作，是否存在更合适的初开交割月？RBA论文、德银原披露和LEAN开源筛选支持这是独立的经济动作，但不能证明国内窄损收益。沿127已核对资料，不重复调研、下载或旧回测。

已一次读128数据/容量设计及独立审查C0/I0。最终协议统一：双方exact product内选月后沿普通优先/F的同一家族次序；单共享模型；容量毛上限1%，新开取毛量一半以预留完整往返；训练准入同样需至少1手往返；未来退出保留理想数量但逐笔审计原native紧前日量，unknown不伪装可成交。

完整399252母表/98品种/95家族/六所保留，原始观察月动作展开且未知全保留。COMMON26自身重算+26缺失，原2N特征单位不变。标签为各实际月.25N、20low和自身生命周期，初开存canonical anchor；其改变/缺失才请求下一native日实际持有月退出且请求锁存，held≠anchor本身不触发DAY。

2cutoff×main/held0/held1仅6次Ridge alpha1模型；A/B共分数。训练cutoff前已成熟、自身可行动标签；family-u各动作区间union控制跨u并发，组质量均分动作后逐u等总量。全部前向child预测与完整parent决策分开保存，held只用事前实际动作并控family-u重复，非全部月份oracle均值。

8账户：A/B×2020连续/2023冷启动×base/stress。本金100w、family风险.0025、总风险.02、margin.25/buffer1.1；联合u预留、D只减量、整数手、不回收未用额度。主stress收益改善/自身正、DD不更深/原252日2000次配对CI下端>0；另三非负增量且DD不深、B自身均正，两held增量非负并无可翻结论未知差异。历史stale/容量unknown限制独立保留。

实现129数据/130共享fit/131现金/132独审/133结案；native读取预算1+0+1+1，0下载/旧金融重跑/大库重hash。预绑定代码和输入后各阶段一次actual，超时先核原句柄，不重启。新增参数仅固定1%日量及新开往返预留、初开月动作；不改旧代码/正式/CTP/Git。

当前新增回测0；期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A，不填估算。累计385fit/110cash不变。开始/结束按本次收益调参：否；反复使用同一历史择题的过拟合风险：是。继续价值：是，仅本次固定可证伪检验；尚无增加投注资格，goal active。

精确协议：outputs/stage128_contract_choice_protocol/protocol.json，23194B，SHA256 `bbd24a6e352fe0fbc77f710eeee18918cc1b4670749339e4f3ae67632095efe0`。后续以此覆盖设计notes早稿的容量/家族次序/旧A等价文字，未重新开启设计审查循环。
