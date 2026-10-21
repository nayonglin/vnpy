# Stage670：真实营销年字面适配修复与恢复入口

- 时间：2026-10-21 13:54 CST。
- line_id：`futures_full_market_long_signal_ai`。
- 是否重要突破：否；修正输入schema合同错误，尚无新历史训练结果。
- 权威协议：Stage669 `protocol.json`，32,929字节，SHA256 `9562629fe8d190e092ef042b51aa1d3027d2b3ea69382ca19891224bcc1f7725`。

## 问题与责任边界

Stage666错误假定原`myDefinition`以四位年开头，Stage667据此实现，旧fixture也使用虚构`YYYY/YYYY`。Stage668唯一actual虽然流水线exit0，但所有源相位无效，24头全部unsupported，实际fit尝试/完成均0。root观察到真实字面为`Sep 1989/Aug 1990`，665独立确认；本agent静态核第51行regex，并只看3个新小head支持状态，同样全部0训练支持。没有因此重读任何金融大缓存。旧666/667/668全部保留不可变。

这不是数量信息失效，也不是无alpha的证据；没有训练出数量模型，A/B/C全部回A。旧unsupported门失败不能作为经济证伪结论。

## 唯一修复

新增`stage670_esr_schema_kernel.py`，复制旧667，只改模块说明、月份字典和MY字面解析block。严格识别`Mon YYYY/Mon YYYY`（允许空白），起月必须等冻结源起月，终月是前一月，终年是起年+1；不再接受虚构leading-year替代格式。经济MY起点、下一MY起点及365/366相位公式完全不变。

新增`stage671_esr_recovery_runner.py`，复制旧668，只改协议/ready/GO身份、金融输入缓存路径及恢复记账。统计、选择、训练验证、前向验证的逻辑保持；原七合取门、24拟合上限、0现金、98品种/95家族、5映射族/90回A、3经济组、原时钟/黑窗/季节/签名数量/尺度/权重/Ridge/标签/风险/止损均未更改。没有新参数寻优，也没有更改、删除任何历史回测收益。

金融输入使用668已经落出的完整六train、完整forward与mother，仅读原白名单列，丢弃全部旧sourcevalid、源特征与新预测列后重新构造。恢复新金融缓存压缩预算268,527,025字节；原538金融大表重读预算0。旧668确实已经消耗原538单流，透明记账。669明确允许五个原小源CSV在恢复actual再各读一次，另读原calendar 89KB一次；不为节省350KB源小文件创建额外适配工程，0新GET/SQL。

## 必要验证和当前计数

唯一真实格式fixture先在旧行为克隆上RED：Sep/Oct/Aug三种实际字面全被拒绝。修复后GREEN：1 test、0 failures、0 errors、0.009秒；覆盖正确Sep/Aug、Oct/Sep、Aug/Jul及空白，并拒绝错误起月、末月、末年和虚构年格式。没有重跑旧六类suite，没有合成/历史拟合。

唯一新`--check-source`通过，只读取小JSON、源码与14个输入stat，未读真实金融/源数量载荷。新source-ready：`outputs/stage670_esr_schema_recovery_implementation/source_ready.json`，6,337字节，SHA256 `3d1156da2bab09eab529ddad481ecf3fea2bea682661a7f4abf09a300a54c5a7`。源码差分、RED/GREEN原日志和metadata检查收据均已保留。

历史计数仍563 fit、294完成现金回放及1旧partial；668增加0 fit、0现金。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A（本阶段0现金）。正式版、CTP、邮件、launchd、Git、分支没有操作。

## 反思与后续

运行前后：历史自适应/过拟合风险仍高；此次修复来自真实输入schema而非收益方向，尚未发生数量模型拟合或C/A非零性能选择，不属于失败后调参救分。继续有价值，因为修复后才能真正执行已经冻结的数量机制实验；要区分技术支持不足与经济实验失败。

TODO：665源码GO后root唯一恢复actual执行至terminal，再由665只读新671缓存一次独审方程、预测、政策、未知、支持、CI；不重训、不读原538大载荷。root汇总真实结论，若真实支持下任一七门失败则停止整包，不改时钟/窗口/尺度/符号/模型/品种/年份/风险救分。目标保持active，无PIT、正式晋级、极窄止损或加大投注资格；END固定2026-10-16，无需等今日日线。
