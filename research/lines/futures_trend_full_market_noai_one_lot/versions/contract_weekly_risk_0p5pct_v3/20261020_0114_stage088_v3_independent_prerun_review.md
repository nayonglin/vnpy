# Stage088：v3延期OPEN及真实资金边界独立预审

时间：2026-10-20 01:14（Asia/Shanghai），研究线`futures_trend_full_market_noai_one_lot`。本代理未参与085/086实现，仅只读审查、向实现者/root反馈具体证据、运行合成oracle；未修改实现、旧源、LINE、Git，没有金融回放。

**结论：PASS WITH LIMITS PREFLIGHT V3。最终冻结085/086当前未发现剩余P0/P1，可以开始已授权的新v3一次完整回放。** 这是静态/合成预审，不认证尚未运行的金融结果。v1失败和v2`FAIL_CONTRACT_PENDING_OPEN`保留；v2完整诊断账本不能重新标PASS或用作N绩效比较。

## 原P1与完整延期链

085只保护真实active OPEN、唯一未同步layer、原冻结budget/stop/qty/产品合约/方向/日期和long原周授权均绑定的意向。原有正常新signal首次创建仍由native→068→075生成唯一receipt；fresh必须是该次_open_position确实新建layer及同一个receipt的双对象身份，不能凭日期或孤儿target假造fresh。

对已延期有效意向，native actual0 reconcile不再reset；flat plan过滤该产品，避免新signal覆写原授权；current_pos0原分支不进入真实持仓止损/平仓流程。缺真实bar时rebalance仅给已验证pending加入因果cache用于重新派单，未进入AM/signal/history_data。真实成交仍须原history_data存在、全量V>=qty及原068/075/生命周期闸门；没有cache成交、缩单、1手fallback或改写原stop/budget/receipt。

映射空/他合约、原授权异常、孤儿无真实order、生命周期原截止失效时，完整取消旧OPEN/target/未成交层/诊断/预留并归档，不制造CLOSE/PnL。真实持仓和pending CLOSE不会被意向清理擦除；缺真实成本basis等不可验证状态hard fail，不伪造entry。

## 延期映射的精确时点合同

审查先用真实单日engine.new_bars合成复现：仅on_bars检查映射会晚于撮合，已延期旧单会先fill再因mapping空queue CLOSE。最终EngineMixin现在只对**真实缺bar/低量已延期，或已preserve的同一原receipt身份**在后续_fill之前查当前因果映射和授权；失效先撤单，无actual fill、无假CLOSE。

**普通首次T→T+1 OPEN不新增当前mapping门**，保持原信号合约资格语义。已延期mapflip无fill，与普通first-next-open mapflip仍按原行为fill的完整new_bars对照均通过。该映射源是prev-calendar-session OI/volume next-session effective，当前开盘已知；不是后验取新日close，也没有按收益决定是否加门。

## 资金/cluster/PnL分离

预审额外指出并确证的资金缺口已修，不能只因延期层保留就称风控保留：

- 缺bar但有效pending3手、cache90、size10、margin0.1，旧估计total/reserved/cluster全0；最终完整native on_bars后均保持270，AM不增加该缺bar、实际0/无交易，之后真实bar足量按原receipt成交。
- A实际500已全排平、B有效待开270，同cluster，003原max(layers,actual)仅500；最终资金为**实际全额+valid pending**=770，不能提前扣actual pendingClose。多空×待平0..5矩阵均770；已见证本日ledger不再重复叠加，额外原reserve7仍叠为777。
- 078强减规划上下文继续使用`actual−有效pendingClose+OPEN`的投影；上述矩阵投影始终`(5−pending)×100+270`，退出flag后资金恢复770。没有把规划扣减泄漏给真实资金/保证金。
- 原native把未成交OPEN层的paper浮动算入cluster，还漏掉已queue但未真实平的实际腿。最终cluster真实浮动只由同步余层+pendingClose真实未成交数量及原entry价重建，排除未成交OPEN；矩阵真实±250而非pending产生的paper profit/loss。实际qty与basis覆盖不足hard fail。
- 本次回调已真实创建的fresh rollover新腿，即使旧同产品实际仓仍全pending CLOSE，资金也必须500+270=770。资金事实资格与strict preserve资格分开：strict preserve仍可因旧真实仓冲突取消，资金计算不因该条件丢掉已创建的新意向；不因此授权新实际双合约持仓。

## 独立验证与冻结字节

最终独立完整命令：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl PYTHONPATH=research/lines/futures_trend_full_market_noai_one_lot/tools .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_*.py'
Ran 401 tests in 30.857s — OK
```

单独085/086真实栈定向63项通过；另83项独立oracle使用明确数量×保证金/真实entry PnL算式，不调用实现函数当预期答案，覆盖上述缺bar、混合资金/真实浮动、ledger扣重、078scope、完整映射时序及fresh换月边界，全部GREEN。测试是虚构行情/状态的单会话或少数回调合成验证，不是历史金融回放。

085最终SHA256：`33099a87fbc2d37b2f64d839ae652113d5c47c91eb8eaf03a024fa8066c625c3`。
086最终SHA256：`90ac9d27ef0326eb3a72be1e84e26e186d85e066e95f9eb2462b61aec4ce3bf4`。

068/069/074/075/078与v2冻结代码逐一hash相同。086相对079经济settings和FRACTIONAL_RISK_POLICY完全一致；预算仍0.005、无1手帽、不加仓、原周门/整数全单量门/原运营截止和forced0.95→0.8、1.65、priority/max100不变。v2 manifest `b5357eef7ec6f3ce9a844bfbf680b7eb5fe24e4fb6e91dec6e87f6ea56933635`与withdrawn声明保留。新pending事件、原授权归档及cache causal_quote_asof导出加入源码/manifest绑定，报价asof是export-only注释，不改价/信号/订单。

## 限制、结果与反思

当前尚无v3 manifest，JSON顶层source_manifest_sha256=null，预期`run_20261020_contract_weekly_risk05_v3`。sourcefreeze/预注册后由root一次完整运行，完成或失败都须再独立实际审查；预算/量/原receipt、延期身份与真实fill、取消/forced、每日MTM、分平/残余、deadline及输入/源码全部再核。不能以401项通过保证下一次金融必完成。

延期证据是本单进程私有对象身份与真实order，未认证跨进程恢复、实盘或完整C9。保留日线近似、C2/C9与供需停用、静态费用/保证金/规格非逐历史PIT、研究主力、多源execution-only仅退出估值、V>=qty非盘口/排队/冲击容量边界。0.5%是初始止损计划风险，不保证gap损失或组合回撤上限。

过拟合：**否**，按既定合同修复目标/实际/授权及资金事实，没有收益寻参或品种日期例外；同样本后验修复非样本外。继续价值：**是**，新冻结一次v3可以验证正确延期与多手风险执行。新增/修改/删除金融绩效结果均无，期末权益、收益、回撤、Sharpe、滑点、胜率均不适用。

调研判断沿用[CME仓位/止损风险](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)与[vn.py目标/实际仓位接口](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)：预算、目标、未成交授权与actual事实需分别核实；通用源码/合成验证优先，外部资料不能代替实际账本认证。
