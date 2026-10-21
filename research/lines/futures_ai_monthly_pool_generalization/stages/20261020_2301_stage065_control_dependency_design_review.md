# Stage065 控制依赖独立设计审查

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 23:01 CST；仅设计审查/小合成反例，未改core/063/064/LINE/registry。
- 结论：只在post-fill/C2/daily-management后实际flat且无pending时索取fresh，对isolated only-flat-fresh意图合理；但039代码/协议显式held也要求fresh、042 unknown时直接丢整个session，所以应新source version，不能回写旧receipt称完整合同未改的bugfix。它既是冗余依赖设计缺陷修正，也是已冻结数据可观察性合同修订。
- 冻结完整C9同样在持仓分支前检查target AM.inited并生成signal，故新设计不能声称完整正式源等价。当前研究关闭reverse/alignment/add并剥离账户功能，才允许单独分析fresh控制依赖。

关键边界：held/pending下fresh不用不代表其他资料不用。必须先原样处理pending fill、新open C2各分支、held AM41/日级退出、target mapping和roll，再按实际状态gate。收盘仅queued全平仍held；早盘已fullclose或C2 stop实际flat当天fresh必须known；partial仍held不用fresh；未知pending/C2/held/target不可被新gate救回。unknown不能写known None，session envelope存在也不能冒充行情已资格。D60流程不顺手特殊化。

建议split evidence slots与consulted/unused日志，独立保留held/pending/target records及fresh未知原因。共同完整域动作应非干扰等价；只有确实未控制后续动作的缺项可恢复，不预设1036全恢复。全19698身份/asof/clock不变，旧058 4762已知金额float64 bits、path/status/episodes等逐key不变，旧1366 robust标签单调保留/边界收窄；不满足即P1停，不按收益好坏豁免。

已查VeighNa primary GitHub的actual pos/target区分、Backtrader官方pending/position控制示例、sklearn泄漏说明。判断是因果状态机可审，但仍需新version/全域统一/独审，不增加learner或降低612floor。详细链接、11类反例和7项验收门在outputs/stage065_control_dependency_design/README.md。

实际只做11个控制反例/17断言0失败，确认当前_fresh在held/pending缺fresh均先报unknown，AST证实042未知即continue；039/042/034前后SHA不变。未实现建议source、未读收益择case，模型fit/金融回放/生产修改0。权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。开始/结束新增收益择参过拟合否；继续价值是，但未证明额外数据或模型收益改善。待063事实分层后由root决定新source版本。
