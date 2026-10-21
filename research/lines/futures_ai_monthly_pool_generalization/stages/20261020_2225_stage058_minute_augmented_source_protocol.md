# Stage058 分钟输入补充后的同源识别扩展协议

- 时间：2026-10-20 22:25；重要突破：待数据结果判定，不预设alpha提升。
- 原理：新增分钟只能收窄既有source的未知执行路径，不得改信号、退出、单位R、数量、费用、目标或asof分母。参数/特征/模型仍冻结；本步骤由数据身份与coverage驱动，不按收益找case。
- 调研判断：继承Stage055所引Backtrader文档/vn.py维护者源码的显式执行假设边界；分钟参考路径不是实际tick事实。Stage054盘点表明只有132/910首阻塞需求位于已声明的2020+旧产品reference-grid范围，不能将剩余778硬套该时间表。

## 固定合同与自动检查

1. 等Stage056统一审核全部132范围内候选以及Stage057独审确认无阻断后，才允许把通过的minute路径接到研究源；多个合法但不同路径全部保留，相同OHLC/时间内容可去重但来源证据不丢。
2. adapter只覆盖Stage042 ProductCases.record返回的minute_paths与minute_evidence_id，并附资格receipt；不得改基础daily bar/history/RSI/MA/economics/guard/tick/extra slippage/逻辑开盘anchor。exact epoch+source_trade_date与当前source daily OHLC/first open再次核对。
3. 原日open anchor仍是logical bar label，不以minute grid伪造实际physical execution_timestamp；roll close-first研究顺序及其限制继续保留。物理session、历史PIT、真实tick先后、broker资格继续False。
4. 复用原信号/管理kernel、原calendar、未来60close MTM、固定2手、每fresh新R/roll不重置episodeR；halfR/retry=False、C2=True。未知不恢复为0，不默认stop，不截断不利分支。超过256 finite-path预算必须unknown/拒绝，不截断挑路径。
5. 所有98×201=19,698原行、asof角色、资格与成熟时钟逐字相同。**原4,508已知条件点值必须保持相同；任何旧known变unknown或金额变更即P1停止。** 只允许旧unknown收窄/首阻塞移至后续未知或仍未知，不更改原产物。
6. 所有仍未知候选继续留完整每月N。重新生成Stage045相同rank识别合同、Stage048原12特征SHA不改、Stage047固定年度模型/612等floor不改；数据收窄后可按原协议重检，但不降低门槛、不加模型、不筛年度、不以合格块数量反选数据。
7. 每个新源运行/模型结果必须另目录、input/code/evidence SHA、参数与版本绑定；独立review后才接纳诊断结果。原042/046b、045b、047b全保留。正式A/C、池、production、CTP、委托与调度均不运行。

## 结果与反思

- 新增金融参数无；修改仅minute输入证据覆盖，不改变已定义source政策。当前无新增fill/label/model结果，实际运行结果另记。
- 期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率均不适用：本线输出source unit-R/标签识别及预测诊断，非账户绩效回测。
- 开始新增按收益选参过拟合：否，统一纳入全部同资格数据；原来源后验、两尾识别、静态费用和未资格会话仍构成限制。
- 继续价值：是，能检验已下载数据的实际增量；若不能恢复足够标签或固定模型仍无稳健证据，应继续不晋级，不能由数据补充自动推导策略改善。
