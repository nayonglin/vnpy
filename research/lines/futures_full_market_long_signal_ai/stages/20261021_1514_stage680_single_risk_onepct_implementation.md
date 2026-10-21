# Stage680 单族计划风险1%隔离实现（尚未运行actual）

- line_id：`futures_full_market_long_signal_ai`
- 当前模式：冻结679协议后的实现与纯合成fixture；root独占actual运行权。
- 记录时间：2026-10-21 15:14
- 阶段性质：同一COMMON52+K策略、同一2015连续历史上，仅修改单族计划风险预算。
- 是否重要突破：否；尚无新财务结果。
- 是否触发A/B：研究基线A(.25%)与C(1%)单点资金预算敏感性；不接入正式策略。

## 外部调研与判断

- 已采用冻结679中root调研结论：[CME按风险和止损定仓](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)、[backtesting.py原资金/保证金约束](https://github.com/kernc/backtesting.py/blob/master/backtesting/backtesting.py)。未下载或引入任何外部实现。
- 我的判断：提高单品种预算不等于成交数或收益四倍；组合2%风险、25%保证金、整数手、容量及D开盘价格会共同约束。必须在真正调用的070.reserve_batch修改私有常量，单改131的模块名义常量无效。

## 本次变更

- 新增脚本：`tools/stage680_single_risk_onepct.py`、`tools/test_stage680_single_risk_onepct.py`。
- 修改/删除旧脚本：无。旧042/070/131/157/675及其globals全部保留。
- 修改参数：仅私有070.reserve_batch的`SINGLE_RISK=.0025→.01`。
- 新增/删除策略参数：无。
- 三层FunctionType适配：私有070预算函数复制globals，仅改SINGLE_RISK；私有131 reserve_capped仅接入该预算函数；私有131 cash循环仅接入该reserve_capped。原code/defaults、共同scale先容量、D仅减量、存量仓冻结entry risk、次日减仓函数保持原语义。
- 实际输入只允许679的16绑定；信号直接复用675，不读取actions/COMMON/scores/模型；完整129 mothers保留canonical reference和95族；原132缓存单次恢复供两账共享；数据库仅stat核验，0 SQL。
- 输出：两新账9个ledger/summary/daily/diagnostics，四账年度，新增两账95族零格，描述性配对comparison，风险预算约束敏感性、四账逐日风险占用、四曲线宽CSV、参数生效和源IO收据。旧账只读已绑定summary/daily/annual/diagnostics，不重跑、不额外读旧reservations或族归因表。

## 回测/归因参数

- 数据区间：2015-01-01—2026-10-16；首个实际源日2015-01-05；2862交易源日。
- 初始权益：1,000,000；新账`all_2015_onepct_base/stress`；连续、不按年重置。
- 固定：TOTAL_RISK=2%、MARGIN_CAP=25%、MARGIN_BUFFER=1.1、初始止损=.25N、原容量1%及往返half cap、原成本base/stress、原COMMON52信号/持久anchor/K/生命周期。
- 预算：0新fit、2新cash、0旧fit/旧cash、0新labels/scores/下载/SQL/bootstrap/扫参。仅root在source_ready与681 source_GO后运行唯一`actual_run1`，失败保留且不自动重试。

## 结果

- 实际回测：未运行。新增期末权益、收益、回撤、Sharpe、滑点、交易数、胜率均暂无。
- 合成测试：42项通过，其中680为10项，依赖070/131/157/675为32项。先观察实现缺失导致8项红测；随后发现fixture小N导致margin先绑定、平低价触发原stop，将fixture改为明确risk主导和单执行日，未修改策略逻辑。
- 实效证据：单信号未受约束时raw预算4倍；三族仍由2%共同scale约束；capacity在scale之后且余量不重分配；已有风险/保证金先扣除；D只减量；真实合成cash循环的新预算传入并增加成交；seeded存量超额占用的整个减仓book与旧函数一致；原全局变量未改。
- 置信范围：以上证明实现和隔离语义，不构成新历史收益、PIT/OOS、实盘加注资格或策略晋升。

## 输出文件

- source_ready：`outputs/stage680_single_risk_onepct/source_ready.json`
- root actual：`outputs/stage680_single_risk_onepct/actual_run1`（尚不存在）。

## 过拟合反思

- 运行前：本次单点1%来自用户，固定全部其他条件，且先冻结协议，不是在新增结果上扫参；不新增结果后调参。
- 运行后：仅fixture完成，尚无新收益；历史策略选择本身的高适应风险继续保留，不能将单次更高收益解释为可推广最优仓位。

## 继续价值反思

- 运行前：有价值；明确资金约束如何使单族4倍意图转成非线性成交与账户路径。
- 运行后：有价值进入已授权的2cash及独审；本实现阶段停止改参数，等待root运行。无论正负结果均保留，不据结果继续扫小数或调整总风险、保证金、止损、模型救参。

## 合入建议与TODO

- 681先完成source_GO；root创建精确源码/输入/输出授权并运行2cash；681在终态后一次独立审查；682生成图表并实测HTML/PNG。
- 本agent只写唯一Stage680记录，不修改LINE.md、registry.md、根memory.md/back_log.md；合入由root统一整理。
