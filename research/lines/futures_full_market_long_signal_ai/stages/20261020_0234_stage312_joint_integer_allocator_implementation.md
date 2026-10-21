# Stage312：私有联合整数预算核实现，3组tiny通过、0actual

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 02:34 CST；非重要突破、非正式晋级。
- 全文读311冻结协议，SHA `f97b23b7732a9ff97272cd793e4ed6c42dc60df6377543d0ab8bcfee527e1259`。调研/独立判断继承303/310/311的一手资料和SciPy维护者文档：原核不是先到先得bug，本次只检验固定联合整数政策；未重复外网、未读306/307新成绩。

## 实现与接口

新增`tools/stage312_joint_integer_allocator.py`及同名test，不改131/070或原模块globals。API精确为：

```text
run_cash_account(signals,market,dates,economics,scenario,account_id,start,end,
 initial=1e6,prepared=None,*,policy='NARROW',base_kernel=None)
```

313必须传已配置`v.kernel`，base_kernel缺失即拒绝，不独立import131。使用同一个原run代码对象复制FunctionType及私有globals，只替换reserve_capped；保留defaults/kwdefaults/closure。每account新callback实例，按prepare callindex映射start−1至end−1（start0则从0），非空u必须一致，empty也审计，最终核调用数。

先在同状态调用原reserve_capped。仅至少2 accepted family且原scale严格<1时新分配；不预删UB0变量。原target/prefloor/jointscale/originalqty等诊断保留，只改qty_cap、allocated风险/保证金/fee、budget_state并标mode。D继续原run代码内的原execution_quantity，整数冻结改变旧实数缓冲的代价不隐藏。

格网顺序唯一：先取原float r/m/d/score及原float cap，再Decimal(str(value))；L在Decimal乘。资源ceil，caps floor，目标`Decimal(L)*Decimal(str(score))*Decimal(str(d))/δ` half-even，δ=1e−6。无额外float系数乘积、不二扣目标费滑。原上限与F0不变，2^50可能和、整数可行性、原Decimal/最终float资源均核；最终float自身上限过一ulp也整候选fail-stop，不削量修复。

每primary/lex阶段记录完整问题、prefix、raw x/rounded k、fun/dual/gap/nodes/options/time及Python整数证据，共享10秒/100000nodes。relative gap不硬比0，以绝对整数bound差[0,.5)和可行性为核心；并列固定canonical lex最大k。非负C且全上界联合可行才解析shortcut。任何失败不fallback/retry，exception挂完整allocation_audit/diagnostics。

book增加`allocation_audit`（全部批次u快照、old_rows/actual_rows/problem/solution/solver_stages）和`allocation_diagnostics`（batch_calls/triggered/qty与freeze改变/solver_calls/analytic等）；D变化仍在原budgets，不反写u快照。所有audit为JSON兼容数值/字符串，Decimal只用于计算。313/314已收到最终接口。

## 必要tiny与冻结

先因新模块缺失获得3个预期FAIL，再实现GREEN；最终3组`Ran 3 tests in 0.017s, OK`，py_compile exit0，API inspect符合。三组覆盖穷举oracle/lot手数/净目标不二扣费/两资源贪心反例、并列排列/ceil-floor/零可行/负C不错误shortcut、私有code/global隔离/空批次/原F0/原D函数对旧实数与新整数缓冲的差别/失败证据。另在同一precision组先RED证明float单family边界漏检，再修复GREEN；未修改冻结政策。

- source：17418B，SHA `f8113be2f68a45875dcf35d6624fe56d3f0008c32dbd0b50af8507e27a14898a`。
- test：8836B，SHA `ec794ca2072a56bad6929313890a1c42a772923a5a3339e0f92143f44784efbf`。
- 314已接最终source/test作唯一静审；313负责新四cash薄封装/exactbundle，作者不执行actual。

本轮仅合成MILP和合成函数接口测试；真实signal/native/动作/训练/标签/现金读取、SQL、actual fit/cash、安装/下载均0，未跑旧suite。实际参数/回测结果新增修改删除0，权益/收益/DD/Sharpe/滑点/交易/胜率N/A；不改LINE/registry/旧工具。

开始/结束判断：没有按新金融结果调参；同史研究过拟合风险仍是。落实已冻单次机制反证有价值，扩大目标/风险/精度/solver搜索无价值。数值证据不冒充数学exact或金融支持；无窄损/加注/PIT/生产资格，完整目标未完成。
