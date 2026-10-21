# SLV数量信息增量实验 Implementation Plan

> 执行：按既有用户自主研究授权采用subagent-driven-development；656实现，655独立复核，root唯一actual及657结案。无新worktree/分支/Git/生产操作。

**Goal:** 在同源NAV与原AI状态控制外，检验SLV数量包对完整98/95做多母体的增量。
**Architecture:** 复用538/539六份成熟训练/完整前向投影及冻结A，12个小Ridge残差头；一次流扫同时保存独审薄缓存；0资金回测。
**Tech Stack:** .py311/bin/python，现有numpy/pandas/zoneinfo，不安装依赖。
**Spec:** [完整结果前协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage653_slv_quantity_increment_protocol/protocol.json)，SHAbf1fbf5d03b51ea3e2abd3e2536b1106435dfdc754b8617623edadc4651ef680。

## 固定约束和判断

- 时间：2026-10-21 12:43 CST；line_id=futures_full_market_long_signal_ai；重要突破否，尚无本轮结果。
- 沿654与655输入/方法，新量仅Q及Ahat*Q；B共同Ahat/P/AhatP，Ahat固定offset。保留原H stressR、成熟cutoff、原选择、风险/stop与全部95family，不能解释为纯因果flow。
- 单一two-full-NY-weekdays假设：d后2个完整Mon–Fri日结束，次日00NY可用；CN u15点asof<=，DST真zoneinfo。不是NYSE会话/逐日首发保证；原相邻行缺失B=C=A，不回找旧有效pair。
- 每source更新总训练权重1，原sampleweight仅作为组内比例，不mean1到复制行。train-onlyscale/common列完全同，Ridge1不penalty intercept，12实际fit/0A重训/0cash。
- 主C−B两main era CI下界正、4held点估计正、6C自身条件均值正及两main自身CI下界正才conditional_signal_candidate；否则关闭此精确包。未知另列，旧629不改，不等今天日线。
- 阅读/写实现前网上与GitHub已看原ETF信息分解论文、BIS WP952与原作者ETF flow项目：支持价格/数量与时钟控制，不能移植其收益或机构分类；本轮不照搬未来套利解释量。
- 开始是否新增按结果过拟合：否，收益前固定单包；长期同史选择风险高。继续价值是，检验真实新信息；没有收益/加注资格。

## Review Focus

1. Fri/Mon/DST及当日15点边界不提前；测试真实UTC阈值。
2. 原相邻missing和周末条目不跳过；两臂同mask与A fallback。
3. source复制不弱化Ridge：组sumw1、复制数据拟合不变；common列scale一致。
4. 原scope/known maturity/fullmother保持；同未知动作paired0但ownunknown不抹，异动作unknown不填0。
5. 一次读/0重训A/12fit计数与新薄缓存独审，不因等待观察超时重启actual。

## Tasks

- [ ] 656写上述必要新行为fixtures，先RED；实现隔离kernel/runner，再GREEN，记录syntheticfits另计，不跑旧suite。
- [ ] 656冻结三源码/fixture receipt/source_ready与准确CLI，0历史payload/actual；655一次完整sourceGO，提前准备不重训的独审。
- [ ] root唯一actual：6train各一流、1forward、1mothers、SLV/calendar各一读，最大12fit；记录终态/未知/新薄缓存，不动源。
- [ ] 655只读新缓存一次独立核12模型/scales/weight/maturity/所有预测/选择/统计/CI/unknown/覆盖，不再重放训练或旧源。
- [ ] root657实读最终小收据/结果并记录中文财务N/A或真实后续范围；更新LINE/registry一次，goal保持active直到完整目标真达。

当前新增权益/收益/DD/Sharpe/滑点/笔数/胜率N/A；累计551fit/294cash+1旧partial，结果前协议一经给作者不按结果修参数。
