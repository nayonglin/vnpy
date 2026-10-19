# Stage042：原生风险预算一手上限修复独立预审

时间：2026-10-19 18:21（Asia/Shanghai）。研究线：`futures_trend_full_market_noai_one_lot`。重要突破：否，是恢复用户原合同和真实开盘预算检查。

**结论：PREFLIGHT PASS。** 当前Stage039/040/041未发现必须阻塞下一次冻结金融运行的P0/P1。允许按下列hash冻结启动一次新运行；不是金融结果PASS，没有认领任何新权益/收益。本代理没有金融回放、改运行代码、源账本或LINE。实际运行完成或失败后仍需独立结果审查。

## 当前证据

独立执行全线113项合成/展示适配测试，113通过，11.675秒；其中Stage039真实native定仓11项、Stage041纯函数及真实engine16项均通过。另用真实Stage039 `_calculate_entry_sizing` 与 `_open_position` 生成frozen dataclass，贯通Stage040/041：信号close100、stop98、size10、budget20时，open100真实成交1手；open100.01拒绝且实际pos0、layer/order均清理。该额外验证避免只使用手写dict造成字段名集成遗漏。

实际构造Stage040完整build_settings并与旧v2协议全量比较，唯一参数变化为fixed_size 1→0，其它参数一致。有效策略MRO包含Lifecycle→NativeRiskBudgetSizingMixin→原native完整风险层；有效engine先经过OpeningRiskBudgetMixin→Lifecycle→CleanExecution。未改cluster映射、阈值或排除2024品种。

## 已修复的问题与边界

首轮审查发现041短factor字段与039长字段不一致，receipt身份未显式核验，以及layer=None模糊拒单留下假pending状态。曾独立合成复现RED：actual0但两个未成交layer与pending_active_product仍存。当前长字段已经对齐，contract/product/direction/signal/date/id检查已经加入；actual0且纯unsynced的模糊状态拒单后重置，真实仓位和synced layer保留。新的真实engine回归独立GREEN。

诊断取消当前移除整个(vt,side) pending索引，历史行保留并标拒。在“每产品最多一层、无加仓、无其它合法同contract方向pending”合同下接受此行为；未来放开多层时必须改为严格intent级移除，不能泛化复用。

Stage039恢复risk_budget后，完整native定仓/筛选/资金门先运行，最终仅能向下cap1；一手stop风险超过原final risk_amount则0。`_open_position`额外阻止0进入native max(1,volume)。真实填单预算冻结原signal因子与货币min/max，以真实open和有效stop重算一手风险，并取signal授权与当前因果资金预算较小值。资金采用开盘权益减已真实发生成本、实际保证金加其它唯一未成交layer预留；没有把pending close当实际释放，不对native reserved重复乘broker1.65。

换月路径从native `_handle_rollover` 调用同一 `_calculate_entry_sizing` 与 `_open_position`，带old risk mode和rollover_reopen context的新budget receipt，再由同一个实际OPEN闸门检查。volume政策先拒selected0，未见绕预算恢复旧手数的路径。旧actual仓仍由产品级close-first/actual margin floor保护，只有真实平仓后才释放。

041每次OPEN记录预算审计，成交后对真实price=open核验并写入trade预算/risk/snapshot；040导出对应CSV、统计与拒单计数，账户核验沿已验证日MTM路径。当前没有看到新收益统计错误。模块inspect局部导入遮蔽风险已修，起始hash/snapshot已覆盖列举的继承策略与engine MRO源码，进一步缩小此前只绑定直接文件的复现限度。

## 冻结代码绑定

- `stage039_risk_budget_candidate.py`：`583da051b2be119e195ed9e0531bd4a5e3c4e3606b9825bc783768030bec57df`
- `stage040_run.py`：`bda26ecd4a2d099a939ca571b7274afdbed66c5d96cc64fb1d8a5b864967b696`
- `stage041_open_risk.py`：`9ed9840bb9188543842d9322755a1a57091afcc32a9cddc4cc0c4a3ff8eddd47`

此预审只对上述代码版本和当前配置成立。JSON source_manifest_sha256=null是因为尚无新金融运行manifest，不能用预审替代实际结果绑定。

开始与结束反思：不是收益优化或针对2024救参，而是恢复“原预算内最多1手，超预算不开”的明确合同；信号/cluster/阈值未据亏损变更，未见过拟合操作。继续有价值，但同一历史上修复不构成样本外alpha证据。日线近似、静态费用规格与真实退出跳空限制仍保留，stop距离预算不是保证实际亏损上限。
