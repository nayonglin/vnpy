# Stage681 单品种1%风险预算独立审查

- line_id：`futures_full_market_long_signal_ai`
- 当前模式：独立只读审查；不运行策略、fit、solve、SQL或旧账回放
- 记录时间：2026-10-21 15:13 CST
- 工作区：`/Users/mac/Desktop/fian`
- 阶段性质：Stage679固定合同、Stage680两新账的源码与保存产物审查
- 是否重要突破：否；风险敏感性研究的真实性与会计约束验证
- 是否触发A/B：沿用Stage679研究基准A(.25%)与C(1%)单点比较，不触发正式策略晋级

## 外部调研与判断

- 沿用Stage679已冻结的[CME仓位规模材料](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)及[backtesting.py资金/保证金源码](https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py)，不额外寻参。
- 判断：单笔比例提高四倍不等于手数、收益或亏损同比四倍；同一u权益的组合2%风险、25%缓冲保证金、整数手、容量及次日自身分配约束都必须同时存在。1%来自用户固定指示，不把文献中的建议比例当成生产资格。

## 本次变更

- 新增：`tools/stage681_onepct_independent_review.py`、`tools/test_stage681_onepct_independent_review.py`。
- 修改原策略、原账本、原模型、原source：无。
- 新增参数：仅审查器固定对照 `.01/.02/.25/1.1`；不新增研究参数。
- 修改/删除研究参数与结果：无。

## Source GO（15:13）

- 冻结Stage679协议SHA：`818b178f1653e8b074dca7bf31801f8bce9e95c64055532deb5a6bb54c23d170`。
- 实际070 `reserve_batch` 持有其自身globals，单改131的常量不会改变原始目标。本次680为070 reserve、131 capped reserve、131 run三个私有函数命名空间，旧code/defaults保持相同；旧070/131风险常量仍为`.0025`，旧globals前后相同。
- 5个真实私有reserve函数的纯合成实效例：单候选原始风险10,000；三个候选共同scale=2/3、总预留20,000；已有风险15,000只余5,000；保证金预留受250,000限制；容量截断后手数`[1,2,2]`，无剩余资金再分配。
- 10项独立预算小样例通过；包括旧`.0025`目标、次日加量、错误u权益的反向变异必须被拒绝。
- Source GO输出：`outputs/stage681_single_risk_review/source_ready1/source_ready.json`，bytes=20383，SHA=`613b4124b1892d2026a9c8fa457394766cfecbfeccc0f3f6d44dd942de82cbeb`。完整作者与审查器source bundle在该文件中。
- 至本节点：大payload读取0，真实cash运行0，fit/solve/SQL/下载0；尚未审阅真实两新账结果。

### 最终Source GO2

- 作者源稳定前的输出守卫改动使GO1仅可追溯，不作为最终实际授权：680 runner从26250B/`3cf24b...`转为26507B/`514ec1988c7e11bc51180afc9ec70a05b5cd2200353be0c4010182054f3b50a4`；test从8011B/`094d93...`转为8675B/`63fba0084dc26f9233e2379b3e732747b820cdc3e7e296de1e58be99f102e3d3`。
- 仅差异：完成回执改独立`cash_completed_NN.json`避免同名独占写；缺失或非有限Sharpe不能判为描述性占优；新增两个输出守卫小样例。未改kernel、模型、信号、预算或交易逻辑，其余16个依赖源绑定不变。
- 最终私有三层与5个纯合成reserve例证再次通过，仍为0大payload/0实际cash。
- 最终GO2：`outputs/stage681_single_risk_review/source_ready2/source_ready.json`，bytes20383，SHA=`e829310a255892e61aad8c51853671af4d47f9b545240f5f8d985089554485b2`。
- 最终差异回执：`outputs/stage681_single_risk_review/source_ready2/final_delta_GO.json`，bytes1931，SHA=`0604b8b05332c40536537b66d6b8a685b8de1b34a5addae91def46fa203281ca`。

## 终态独审计划与预算

- 仅root确认680终态后，凭精确manifest、审查器source bundle与一次性root authorization，执行一次完整两新账审查。
- 独立102十进制报价与费用算法核u原始目标`.01*E/R`、2%/25%共同scale、先floor再固定cap、D自身分配只减量；保留既有风险冻结与次日降仓。
- 对保存fills做独立现金重建，对保存positions核数量、估值、保证金与风险；核全部日线、closed/open、fees/slippage、stale与execution_unknown、摘要、年度和95族零网格。
- 原675两账只读原summary/daily/annual作为身份与四曲线对照，不读取旧fills/positions/reservations，也不复审旧模型或旧4/2账。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：本节点未读取结果，待终态授权独审后填写。本阶段自身新增研究回测0。

## 过拟合与继续价值反思

- 运行前：本次固定风险敏感性核验不是结果驱动寻参；旧研究历史适应性选择风险仍高，不能声称真正未见OOS或PIT。
- Source GO后：判断不变；本节点未读取真实结果，不存在据结果调整风险、成本、模型或样本。
- 继续价值：有；必须确认用户指定1%确实进入真实预算路径，并辨明更高名义风险在组合上限下的实际资金效果。
- 后续：待两新账终态后完成一次产物独审；不据失败回扫风险小数、放宽组合上限或救参。

## 实际完整独审与小表续审最终结果

- 最终记录时间：2026-10-21 15:26 CST。
- root唯一Stage680实际运行完成后，按精确manifest `6014a0eb3cc13d8144d9aed4a41651141d3bd78ea7c3fade6d8318bf73776474` 签发一次完整独审；两新账均完成完整预算、独立现金会计、原生价格/持仓边界、容量、费用滑点、摘要、年度、95族零网格与新曲线检查，并分别保存`actual_run1/book_base.json`和`book_stress.json`。
- 完整独审耗时：`123.48480108403601`秒。最后在旧年度表的字符串全等断言处退出，`actual_run1/actual_terminal.json`保留failed状态，未把失败当成通过。
- 根因：合并annual时pandas把同一个浮点数改为另一种等值十进制表示。最终结构化核验为**57格**文本差异，旧24行×12列全部身份相同，5个财务数值字段逐格Python float**精确相等**，最大数值差`0`；其他字段逐字相同。早期口头及续审回执静态原因句中的58是计数误报，应以`metadata_checks.annual_exact_numeric_equivalence.serialization_only_cells=57`为准。
- root另行授权一次metadata-only续审，复用两book精确绑定检查点，仅核小表与未完成的旧对照/描述性比较，不重新审两账或读取native/actions/features/models。续审命令wall=`0.22836925`秒，退出0。
- 修正后的审查器额外3项小样例（纯浮点表示接受、非零金额差拒绝、source_days变化拒绝）与原10项均通过；此后遵root指示停止新增测试/审查。
- 最终`metadata_continuation1/review_receipt.json`：bytes28432，SHA=`246502b1a5c04da52ec6199c96b96932e74f9e49eab0ab2b1c3b0d2a1f442b09`；`completed=true`、`research_arithmetic_accepted=true`、`C/I/M=0/0/0`。原failed terminal与完整检查点均被精确绑定保留。

### 两新账经独审的财务结果

| 指标 | 基础成本1% | 压力成本1% |
| --- | ---: | ---: |
| 期末权益 | 3,885,311.8425 | 2,213,776.4915 |
| 总收益 | 288.53118425% | 121.37764915% |
| 最大回撤 | -31.41450401% | -15.99718277% |
| Sharpe | 0.71748345 | 0.62276120 |
| 总费用 | 206,773.1575 | 205,548.5085 |
| 总滑点 | 579,071.60147144 | 501,333.99525085 |
| 已平完整交易 | 1,831 | 1,411 |
| 总成交条数 | 3,683 | 2,854 |
| 已平净盈利胜率 | 12.45221191% | 12.89865344% |
| 末端未平仓 | 2 | 2 |
| 日线 | 2,862 | 2,862 |

### 参数实效与不确定性

- 原始单候选风险比例最大浮点值均为`0.010000000000000002`，独立公式核对为1%。基础账2739个新预留，2626个受共同风险/保证金限制、113个未缩放；压力账3279个新预留，3246个受共同限制、33个未缩放。
- 总风险上限仍为2%，缓冲保证金上限25%、缓冲系数1.1；分别23/40个既有持仓降仓记录核过。容量截断442/200个候选，没有截断后再分配或次日增加手数。
- 基础账：容量未知成交56条、55根，入场缺报价未知4条，历史stale 9天；压力账：容量未知成交29条、29根，入场缺报价未知2条，历史stale 7天。两账`execution_unknown=true`，末端stale仓均0，末端真实未平仓均2。
- 独立资金会计、全部成本和slippage已进入现金/成交价；没有把unknown归零或隐藏，原675仅summary/daily/annual对照，旧fills/positions/reservations未读、旧模型未审。
- 四条连续曲线与逐日权益/DD、48个年度切片和描述性财务差值均核对，`same_history_point_dominance=false`。0新增研究fit、0新增研究cash、0SQL、0solve、0策略重放、0旧账完整重审。

### 最终判断与反思

- 独立审查认可保存账本的研究算术与预算实效，不认定1%占优或可实盘加注。基础成本收益提高伴随回撤明显扩大，压力成本收益略低于原.25%基准且回撤更差。
- 运行后过拟合判断：本次固定1%单点没有根据新结果调参；原历史适应性选择风险仍高，本次也不是真正未见OOS/PIT。不得以本结果再扫风险小数救参。
- 继续价值判断：本次核验价值已完成；继续调整相同历史风险比例的价值不足，不建议据本次结果修改组合风险、保证金、止损或正式策略。后续保留结果与不确定性，由root向用户交付。

## 合入建议

- 不修改本线`LINE.md`、`research/registry.md`或根目录`memory.md/back_log.md`；由root统一汇总。
