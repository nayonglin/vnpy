# Stage017 五日以内有限合成路径验证协议

- line_id：futures_ai_monthly_pool_generalization；2026-10-20 20:39 CST创建、20:40实现前细化；day。
- 沿用已确认Stage016下一门槛，先验证有限路径合同，不构建完整新策略或真实60日数据集。变更局限本线tools与outputs。
- 用户条件：训练源halfR/retry关闭，C2保留；正式源和配置不改。单品种、单epoch、单层、一次已知entry，固定初始R；无资金竞争、仓位叠加、roll、普通止损、部分平仓或重新入场。以上未实现功能不能解释为正式源已取消。

## 先验合同

1. 明确synthetic_only，最多5个按序合成session。每session的有限备选路径显式列出minute OHLC，备选必须具有相同聚合日OHLC及相同数量的有序抽象minute slots；没有真实timestamp，不认证真实交易所会话。第一session首open等于已知entry。持仓中没有路径是未知，不能填0或跳至下一有行情日；已永久flat时保留已知realized和该日缺数据标记。
2. C2仅入场session激活，源依据当前Stage827 after-open函数，后续session不重新激活。入场日neither后为entry_session_expired，confirm后为confirmed；二者后续都继续持有，此段只做horizon MTM，未实现正式普通退出，不能混为完整策略。
3. 固定signed初始R必须正，不用abs或floor救活；guard tick与fill tick分别提供。若R小于effective guard `max(configured_tick,1e-9)`，按实际C2 guard记为inactive并继续持仓，不改R。每minute先open，随后同minute adverse-first，绑定当前helper SHA。stop后持仓0，无retry；fill用gap或threshold并作不利tick取整，必须在触发minute可达，否则execution_unknown。20:44独审指出原协议文字及实现遗漏该1e-9 guard下限，补回真实源码语义，测试先红后绿；不修改既有R/阈值。
4. 枚举所有显式给定的session alternatives组合（最多256条）；不随机抽、不剪掉坏分支、不合并同仓位历史。达到限制拒绝，不截断。只称finite supplied scenario set，不声称覆盖所有与日线相容的真实分钟路径。
5. 每条保留minute/session选择、逐日realized/unrealized/total gross price-R trace。R分母永远初始距离；stop gap可低于-1R，不截亏。无乘数、费用、滑点、volume或保证金模拟，不称净收益、交易绩效或60日标签。末日close为持仓估值，不模拟强平。
6. 持仓中missing path/不可达fill保留未知行和原因，不能从已知分支的min/max推断整体bounds。即使都已计算，min/max也仅针对给定有限集合，不表示区间每点可达。输入非法则抛错，与合法但执行未知分开。以上subtick/flat细化在实际实现前由独立reviewer指出并纳入，不依据收益结果修改。

## 预声明验证

- 同日相同OHLC、stop-first与confirm-first产生不同后续状态，分别保留；多空镜像；同minute双触adverse政策；open优先于同minute极值；gap亏损超过1R；guard/fill tick区分与不可达fill；C2不跨session；stop后不重入；fixed R归一；missing路径不变0；上限/日期/重复/非法OHLC/首open/不一致alternative拒绝。
- 五日4^5=1024超限必须拒绝，五日2^5=32例全部枚举；独立agent以直接Decimal逻辑复算整个允许集合、trace和未知状态。先测试失败，再实现，再跑有限合成验证，最后独立审查。真实数据回测/fit/下载/订单均0。
- 开始新增按收益选参过拟合：否，例子预先固定只检验机制；继续价值：是，防止把入场日C2误扩到持仓全期及路径未知被伪确定化。历史缺失偏差不由合成测试消除。

## 调研与判断

本轮重新读取[Backtrader执行说明](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)与[VeighNa GitHub组合回测源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)。通用bar撮合假设不能补回分钟先后；本地Stage827函数明确仅`entry_session`。因此选择有限显式路径验证，而非将日bar adverse-first冒充C2真路径，也不为解覆盖擅自关C2。

模型/金融参数新增修改删除均无；金融结果均N/A。后续实际结果另记Stage018，不把协议中的预期当实际结果。
