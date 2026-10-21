# Stage667：冻结 ESR 数量增量实验实现与合成边界验证

- 时间：2026-10-21 13:43 CST。
- 研究线：`futures_full_market_long_signal_ai`。
- 是否重要突破：否；这是冻结协议的实现交付，还没有实际历史训练或回测结果。
- 唯一行为合同：Stage666 `protocol.json`，28,281字节，SHA256 `309ee986d238be65845f5ac2f6672c9e44784ed10d92a2ba94b913707a23d459`。
- 既有计数不变：563次历史 fit、294次完成现金回放、1次旧 partial。

## 本次改动

新增本线工具 `stage667_esr_quantity_kernel.py`、六类合成 fixture 与 `stage668_esr_quantity_runner.py`。kernel 导入无输入读取；runner 只有 root 使用 `--actual` 时才读取真实输入。源码、fixture、映射、方法审查与精确 CLI 均绑定到 `outputs/stage667_esr_quantity_implementation/source_ready.json`，5,236字节，SHA256 `ba757cd50528a7664868db1b53fd868027b76803971fbdef8be410c415163494`。

五个已有真实经济对应族、三个经济组、原有主组与两个家族留出组、2020和2023两个冻结cutoff全部沿用666。保留98品种/95家族所有母体；90个未映射族逐位返回原A，不把零增量当成迁移成功。经济迁移只训练新残差头，排除完整被留经济组的结果；原A与无监督源单位已见该组的限制保留。

新增参数均已在666见Y前冻结：固定14日00纽约可用性假设、四段period黑窗、原MY起月与365/366相位、季节控制B的五个raw列、C额外签名asinh净销售Q及A×Q、source-prefix medianabs单位、Ridge1/未惩罚截距、每周总权1的经济组→源→原sampleweight层级、52周循环块/2000次/固定seed。没有修改、删除原A模型、风险、止损、标签或原选择器参数；没有补充D<K等新训练筛选。

runner 精确委托 `stage538.select_scope -> stage156.select_full_pool`，只替换score；完整普通/F家族优先级、正分阈值、calendar身份与tie规则保持原逻辑。sourcevalid只限制新头拟合和预测，政策统计保留无源、黑窗、flat与unknown母体。相同未知action的配对差为代数零，自身结果仍未知；不同未知action不补零。政策按全母体周均值，训练与MSE按合同层级，所有arm/case共用周事件grid和bootstrap索引。

原始五源9755行与六train全白名单、完整1933480行forward、原母体只在唯一actual中读取并保存新薄缓存。迁移预测仅在原main对应行增加两列，避免复制三份forward。14个输入各单流一次，旧金融压缩预算310,827,226字节；不另重hash旧金融流，不读旧Achoices/models/scalers/COMMON/native，不用SQL或网络。每个无支持头明确unsupported、无solve、回A、门失败，最多24个新拟合；0现金授权。

## 必要验证

六类合成测试先观察到RED（实现缺失，6 failures），随后GREEN（6 tests，0 failures，0 errors，0.050秒）。仅验证本次新行为：

1. 14日纽约时钟/DST、最新无效期不可回旧有效源。
2. 同period多个MYCO全部保留但共同无效、黑窗、真实闰年MY相位与签名原literal。
3. 源前缀严格小于cutoff，medianabs不看未来，零尺度unsupported。
4. 每周经济组/源等权和旧权比例，经济组排除先于权重。
5. raw交互先构造、B/C共同scaler、完整Ridge方程、逐位A回退、迁移缺余组unsupported。
6. 同未知action配对零不改变own未知、不同未知保留未知、共享52周bootstrap与整周缺失。

唯一 `--check-source` 通过，读取只有小JSON、源码与14个文件stat，0真实金融或源数量载荷、0历史fit/cash、0网络/SQL。没有执行旧suite、没有actual，也没有重跑历史策略。合成方程solve不计历史fit。

## 结果与资格边界

本阶段没有新增、修改或删除历史回测结果。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均为N/A（0现金回放）；不得从合成测试或source-ready推断盈利。正式版本、CTP、邮件、launchd、分支与Git均未操作。strict PIT、fullE、生产、极窄止损和加大投注资格均未获得。

运行前后反思：历史自适应/过拟合风险仍高；本次没有见新结果调参，而是锁定已声明合同一次证伪。继续有价值，因为美国净销售的签名数量信息与季节/原AI控制可以在真实经济组迁移中被明确否定；若七合取门任一失败，则停止整包，不扫时钟、窗口、尺度、符号、模型、品种、年份或风险参数。

TODO：665一次源码GO后由root唯一执行冻结actual至terminal；665只用新薄缓存一次独立全审方程、预测、选择、支持、未知和CI，不重训、不回读旧大表；root再汇总真实结果与更新研究线状态。无需等今天日线，END固定2026-10-16。
