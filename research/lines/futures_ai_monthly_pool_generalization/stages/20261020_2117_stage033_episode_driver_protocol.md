# Stage033 固定时钟逐日episode driver协议

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 21:17 CST；结果前协议。
- 范围：将已验收C2、冻结日终adapter与actual-fill经济组件接成单次初始entry及其roll延续的逐日研究driver。不新增普通平仓后的fresh entry；因此是entry episode参考，不是旧Stage183连续资金策略或全市场月度标签完整源。halfR/retry关闭，C2保留，账户heat/forced/streak/capital排除为已声明研究delta。

## 时钟、执行与未知

1. 输入完整共同source calendar、固定signal/eval日期、observed_through、horizon（正常60）。D1为signal后第1source day，D60永远由该切片决定；entry缺失/roll不重设标签窗口。首entry正常age1，roll新entry重置signal-age，初始episode currency-R不重置。
2. 每日先处理此前pending：要求绑定本session首open参考anchor，不能用daily.open自动补。actual数量仅成功fill后变化；RSI partial_done只在该请求成功fill后commit。然后处理新entry的C2，再在完整日线收盘做日级退出；partial close不是新entry，不重新启动C2。
3. C2按当前helper：若有显式完整有限路径，逐路径单独深拷贝账本/状态并全部保留；超256拒绝不截断。若无minute而已知首open、完整日OHLC且neither/confirm-only，可条件识别动作；stop-only/both不能造fill，保留trajectory_unknown。缺bar/anchor/minute或不可达fill同样unknown，不填0/跳日或删除分支。
4. 每日target必须显式给定asof值。不同target按冻结Stage037 delay5与shape helper处理：首次target日elapsed0，第6个distinct day为5、目标改变重置；等待期继续旧约普通退出。due时旧close优先，新约shape/数据条件决定是否请求重开。旧实际close后newopen缺失须保留已成交旧腿及unknown，不能整日回滚。
5. 本driver只支持旧close→newopen同session首时间不逆序的参考roll，tie显式close-first。这是单在持合约经济组件的研究限制；若实际anchor新先旧后，显式unsupported，不能声称完整源事件队列等价。新entry C2按新entry−newstop重新算R；所有利润锁仍沿entry百分比，episode净R分母保持首次currency-R。
6. 日级adapter的proposed stop/最高最低等收盘状态可被保留；requested qty/RSI flag不等于actualfill。来源history严格41共同源日截至本日，不接受未来窗口。显式qty为诊断研究输入，尚未确定完整新源最终数量政策；整数RSI floor不改。

## 终点

- `mtm`：D60 close估值，不强平、不收虚构exit fee；D60pending仍单独保留，D61不影响此目标。
- `exit_next_open`：D60持仓提出全平，D61首open实际参考成交后才是该目标，费用计D61；缺D61/anchor未成熟或执行unknown，不以D60close顶替。该horizon退出是显式研究目标，与原策略普通退出规则不同；不保留D60 roll reopen到窗口之外。
- 即使早已flat且经济值已知，也须observed_through达到固定D60才标成熟时钟；缺未来bar不抹去永久flat已知经济腿。未知执行或pendingroll不得因book暂flat冒称完整路径已知。
- 费用未知则net未知、静态经济则conditional；调用方证据/validated标志不授予真实成交或PIT资格。所有结果training_eligible=False，不能把参考episode值当成熟全市场月度标签。

## 实验与复核

先TDD测试pending次开、RSI奇数手、C2不跨日/partial不重开、gap、分支独立、roll新R/旧分母、oldclose后new缺失、缺成本、D60/D61成熟、早flat与日历不足。实际后独立agent手写oracle/边界/绑定复核。

真实诊断仅固定JM/AU历史条件见证及Stage032找到的后续首open来源；source_id/逐来源冲突限制保留。提供固定60source-day clock与静态经济输入，结果只可称条件episode参考金额；不作模型拟合、池调整、绩效外推或正式发布。

调研与判断：本轮重读[VeighNa官方回测源码](https://raw.githubusercontent.com/vnpy/vnpy_portfoliostrategy/main/vnpy_portfoliostrategy/backtesting.py)与[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)，实际生命周期以本地绑定调用链为准；pending/actual与成本时点分离，不能从通用撮合假设补历史证据。开始新增真实收益选参过拟合否，继续价值是；终点/未知/roll错误会系统扭曲标签。
