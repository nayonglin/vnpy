# Stage063 session missing实际数据依赖诊断

- 时间：2026-10-20 23:04 CST；同线；非收益突破。
- 范围：冻结058成熟unknown3403中first reason恰为continuous_source_session_missing的全部1036窗、79产品，不按收益选择。
- 仅新增本阶段隔离诊断、6个TDD、12固定细节样本和中文证据；039/042/058/正式实现、LINE/registry均不改。新增/修改/删除金融参数无；halfR/retry仅源关闭、C2保留。

## 先行调研与判断

先查[Python官方短路语义](https://docs.python.org/3/reference/expressions.html#boolean-operations)、[LLVM PDG文档](https://www.llvm.org/docs/DependenceGraphs/index.html)、[官方llvm-project依赖图源码](https://github.com/llvm/llvm-project/blob/main/llvm/include/llvm/Analysis/DependenceGraphBuilder.h)。可借鉴控制依赖与数据依赖的区分，不能把unknown当False。旧039有意要求held也fresh显式观察，因此不是可回写旧结果的bug；042将fresh unknown整session丢弃确实耦合了独立held输入。若调整，须新versioned observational contract，不宣称正式多层等价。

## 实跑与数量

23:01:17–31完成全部1036冻结058重放，10360摘要/首日/原因断言一致。捕获首missing前branch，精确补其当日target/held/pending所需独立record，仅在063内partial-evaluate一日pending fill→新entry C2→dailyclose→finish，不调用fresh、不续算新60日标签。

- pre flat980：全部仍需fresh。
- pre held37：30可证明fresh不需，7held精确日记录缺失仍未知。
- pre pending open17：12成功fill/C2/daily后held，fresh不需；其余2错误侧R、2缺C2分钟、1缺entry anchor/bar仍未知。
- pre held+pending reduce2：全平真正fill后flat，正确仍需fresh。
- 总计fresh不需42/1036（4.05%、18产品），fresh仍需982，管理未知12；42当日金融值可计算但没有保存其金额或变成新标签。

42=held30（28hold、2排nextopen reduce）+pendingopen成功12（11hold、1排reduce）。未fill普通退出仍占actual qty，不能当flat。981 target身份已知，55未知；1036 target record均不可用。39原held中32 exact held record可用、7缺失。42 target均已知、无roll due；不能据它们外推due时shape/newanchor缺失可跳。

全部分层、不可恢复原因和12固定状态/record细节见`outputs/stage063_causal_missing_input_audit/`。任意C2stop/full pending close后flat都仍需fresh；roll先旧腿、新腿未知不能回滚或认定成功。所有有限分支全留。

另8首missing恰为D60，7post-flat在本完整下一状态合同仍fresh_required；若将来另定义只关心终点金额、忽略D61 pending，可能另有末日价值依赖精化，但此处未偷换目标或将7加入42。

## 不变性、反思和决策

原4762known覆盖矩阵、1366robust标签矩阵运行前后SHA全部一致，冻结代码/方案/数据SHA见summary与post_run_verification。这里只证明旧产物未动，不冒称未实施v2已通过全known值回归。6隔离函数TDD先红后绿。完整新60日shadow/标签/模型fit/下载/订单/正式修改均0。期末权益/收益/回撤/Sharpe/滑点/交易数/胜率不适用。

开始/结束新增收益调参过拟合：否，选择由缺失原因固定、全部统一审查，不拟合或收益择样。继续诊断有价值，因为区分了真正缺数据和控制依赖；但本轮**不实施source v2**：只42首日可消除fresh依赖，尚不保证任何完整60日识别，改变观察合同的成本/漂移不小。root已决定保留冻结源，转官方历史session证据与剩余分钟数据需求。原模型泛化未证结论保持。
