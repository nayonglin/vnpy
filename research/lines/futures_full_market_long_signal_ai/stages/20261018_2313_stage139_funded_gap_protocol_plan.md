# Stage139 已接受账本资金差归因 Implementation Plan

> 本轮 root inline 实施140，独立agent审141；使用 executing-plans。用户已持续授权自主研究与自行决定设计；本次按其既有授权推进，不再请求重复许可。不创建工作树/分支/Git提交。

时间 2026-10-18 23:13 CST；非重要突破；研究线 futures_full_market_long_signal_ai。上一goal轮为progress：84现金和独审已完成、有效改变下一决策；完整目标未达成，goal active。

**Goal**：解释同一AI准入正分月池内，AI资金增长差记在参与、初始风险份额及每风险单位实际贡献哪一层。
**Architecture**：复用133已接受root公式与88账本绑定，不import有执行副作用的133；新140只做父事件会计桥，141用fills及closed/open独立重建新增数学，142中文决策/记录。
**Tech Stack**：现有.py311/bin/python、pandas/numpy/标准库，不安装依赖。
**Spec**：[冻结139协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage139_funded_gap_protocol/protocol.json)，SHA 7d07e65db4dd4287b0245b535c19af76d6a23ffc9e9896defab7f1b278b2057d。

## Global Constraints

0新fit/SQL/label/cash/下载/native缓存读取/整库hash；原风险/stop/参数/模型/资金路径不改。4917完整sourceB selected母域保留每book与pair；current全161014父本引用保留，不称只入场交集为全体。初开风险F=initial_qty*risk_per_lot，Y=C/F；风险项/单位项/单边参与项逐母回加ΔC。成本只扣一次，未知/open/stale不剔除；CNY对账不替换138原log CI。

## Review Focus

- cold起点start−1预留：用源5587日calendar索引窗口，不用u>=start。
- 拒绝行无母id/budget_kind：仅排existing reductions，child映母；无BUY不得伪造单位收益。
- open已有部分减仓：贡献必须含realized-fees+unrealized，初始数量不是末端qty。
- 同action不同资金路径：签名只描述分数化fills及终态，不强设同Y，不宣称因果。
- 20均值：先逐对再均CNY，保留全部20，不均F/Y后乘、不挑seed或重估CI。

## Task1：140有限数学行为及一次实际派生

文件 tools/stage140_funded_gap.py / test_stage140_funded_gap.py。接口root_contribution(row,closed)、decompose(CA,CB,FA,FB,enteredA,enteredB)、window_opportunity(u,start,end)。先写RED，再最小GREEN，覆盖open减仓/费用只扣一次、风险资金分解、单边不伪造Y、双方未入场、cold预留及非法风险。主体加载exact协议/manifest绑定，通过所有实际账本和父域对账后只写新stage140目录，终态保留不自动重启。源码/test和输入先root精确签发，actual一次。

## Task2：141独立新增归因审查

文件 tools/stage141_funded_gap_review.py及有限fixtures；不import140数学自审。读取已接受绑定与140结果，fills独算账本净贡献、parent grids/84pair/FY分量和20均值、分层/未知/尾部表，核0新fit/SQL/cash。复用原137接受资格，不重跑88资金路径/native。结束给中文独审stage/receipt/terminal。

## Task3：142决策与本地资产引用

root读actual/独审，报告8组CNY bridge、主归因分量/参与/同月路径、未知及集中度，明确非因果；引用88旧指标，不产生新回测。保存必要新产物及原输入exact本地引用，更新本线LINE/registry，常规记录不写根总账。

新增策略参数/修改/删除均无；本轮没有新回测，旧期末权益、收益、回撤、Sharpe、滑点、胜率与交易数均不改变。开始过拟合调参否，历史择题风险有；继续价值是，限一次机制会计解释，禁止因分量正负救参或加注。
