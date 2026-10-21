# Stage059 EIA 输入精度修正：在首次拟合之前停止下游

- line_id：`futures_full_market_long_signal_ai`。
- 记录时间：2026-10-18T15:42:37.912801+08:00。
- 当前工作区：`/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`；不新建工作树。
- 性质：数据整体正确性修正，非策略突破、非收益调参，不触发正式晋级 A/B。
- 上一目标轮属于 verified wait：重新轮询已确认活着的原调度 session26165/PID4616 及其每30秒确认的原源进程 PID3442。本轮已产生改变下一步决策的新证据，并停止错误输入的自动放行，属于 progress。

## 调研与判断

- EIA 官方 Table1：<https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf>。页面单位是 Million Barrels；脚注明确“Differences and percent changes are calculated using unrounded numbers.”（差分与百分比使用未舍入值计算）。这直接否定了显示 current-prior 必须精确等于显示 Difference 的假设。
- GitHub <https://github.com/ropensci/eia/issues/11> 说明旧 API v1 已退休。此前选择逐期官方归档小表，而非今日 API 修订史，是正确的来源路线；此问题应修在显示精度核验，不应另换数据系列。
- 060 作者在537期已观察53份因精确等式被拒，2020完整53期只28期known。该缺失系统性集中2020之后，已经超出用户所说可保留的零星小缺口；有必要修正。
- 独立063 reviewer用5份真实拒绝CSV/15行核验，8行残差非0但均落打印精度的独立舍入相容界内。例2016-10-19 crude残差−0.1M、界±0.15M；2020-02-26 distillate残差−0.001M、界±0.0015M。不是策略成绩不佳后的调参；当前没有任何新fit/现金成绩。

## 已采取的行动与边界

- root在2026-10-18 15:39 CST核对PID命令后，只向原下游调度PID4616发送SIGINT；原下载PID3442继续。session26165实际退出130，程序保留失败终态和KeyboardInterrupt；不把主动中止包装为成功。
- 原调度终态 `outputs/stage059_eia_full_market_protocol/orchestration_once/terminal.json` SHA `b1bc2e731f3bf56114efd7540cb7552ac1d0043eda6161083c81f54a171cffb8`。source/fit/cash manifest均null；061/062实际输出目录均不存在；新增拟合0、账户0、原生SQL0。
- 原060源码、测试、actual、progress、原拒绝值及原始下载字节保持原状；没有第二次下载、自动重试或原060重跑。
- 授权作者新写 `stage065_eia_precision_recovery.py` 和新测试，使用已完成060的缓存字节离线生成独立产物；实际065仍需精确SHA授权。063独立编写同一数学规范的核验，不导入作者解析核心。

## 新增数据规范，策略参数不变

- 不可变机器合同：`outputs/stage059_eia_full_market_protocol/precision_input_amendment.json`，3035B，SHA `46946878f76d2b0a134bf274898868e622c4bded4d021a1add62116f8af3e729`。
- 每个字段的量化单位q直接由原文Decimal的打印指数确定。必要相容条件：`abs(current-prior_inline-reported_Difference) <= (q_current+q_prior+q_difference)/2`。没有可调epsilon，不按年份、品种或成绩选择规则。
- 仅恢复原算术等式拒绝、且三个指定库存行所有其他核验通过并在相容界内的报告。官方current、prior-inline与Difference原数保留，只按1000转换单位；不能用显示current−prior重算Difference。
- 日期不符、缺源、无效数、重复行、真正越界继续unknown。完整794周ordinal、已知时钟、原52期lag、past-sham及全family资格不变。逐格保存精度、残差、界、原拒绝原因和恢复决定。
- 新manifest明确绑定原060 actual及新065来源，保持061所需角色接口但标明producer065。打印精度相容不证明未舍入真值，也不证明字节PIT，原归档重建限制保留。
- 原059 Ridge1、10槽、三臂、两cutoff、6fit预算、12现金、两成本、风险/止损、CI/继续标准均不变。

## 结果与后续

- 本轮没有回测。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均为未产生，不能填0或沿用旧包成绩。
- 后续：完成同一个060下载；065新行为先RED/GREEN；独立精度及源码增量预审；root精确授权一次离线规范化；一次新061完整输入预检后首次6fit/12cash；实际账本后唯一063全面独审。
- 原056期限信息包仍为否决，不救参、不复用旧模型。完整目标仍active，窄损/加注和真实盈利资格未证明。

## 反思与记录

- 开始/结束判断新增过拟合：否。本次修正由官方测量精度说明和收益前系统覆盖错误触发，未参考新实验成绩；历史多次研究选择风险仍然存在。
- 本次继续价值：是。恢复正确的外生观测有必要，否则2020后覆盖误差会扭曲实验；仅做这一处影响整体准确性的修正，不追求消灭所有缺口。
- 根memory/back_log不追加；待真实源/拟合/现金/独审完成后一次整理LINE和registry本行。未commit、push、部署、CTP、邮件或委托。
