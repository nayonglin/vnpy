# Stage012 Reserve50k Implementation Plan

**Goal:** 原C分档风险、空头底20过滤不变，仅比较5万和15万场外备用。

**Spec:** 20261030_stage012_reserve50k_design.md。用户既定参数/起点与隔离要求优先于skill的正式基准和固定1/2/3年默认表；本研究不自动晋级。

**Architecture:** Stage009金融入口和备用类只读基底，新增Stage012独立namespace，仅reserve常量50k。9真实新引擎＋14逐检查耦合证明复用＋23旧对照。报告与金融解耦，E/15万主口径；不混用不同总预算W收益。Python .py311，pandas/numpy/matplotlib，既有vn.py daily-next-open。

## Global Constraints

只写本线Stage012；C-only；原风险6%/6%/2.5%保留；交易150k、备用50k；23starts、cutoff10/29；无加仓/多头新增过滤/MA斜率过滤；最多2金融；零下载/HTTP/生产/CTP/订单/邮件。金融冻结源不得为后处理修复而改变。

## Review Focus

完整actual settings/effective原样；备用余款不可提前进入交易风险；无绑定证明逐信号/现金流/源码而非仅看期末；cap绑定后必须新金融；旧版本只有C_R原风险；E零/负不回退本金恢复购买力；新旧预算不等额不可套同W百分比优胜。

## Tasks

- [ ] 1. 测试先行：stage012_reserve/contract/reuse/runner/coordinator，独立AST证明备用类除常量外不变；复用14逐检查全部验证，超过50k一律禁止复用。
- [ ] 2. 数据/源码入场独审，冻结source commit/hash与9/14名单；2015证明复用＋2016June真实canary，真实账本/资金/风险独审后继续剩余8。
- [ ] 3. 9真实run全部checkpoint与独审；14候选证明复用证据独审；保持实际新跑与复用计数，不伪称23新引擎。
- [ ] 4. 构建46summary/23pairs/70998daily、cohort、五图、离线HTML与23中文逐窗记录，完整亏损/耗尽/风险/收益保留。
- [ ] 5. 独立全表/图文/来源SHA总审、最终封存及本地commit，不推送、不修改旧链或生产。

接口：root负责stage012_report/plots/HTML，runner agent独占reserve/reuse/contract/coordinator/runner及其tests；独审agent仅写stage012_independent_*工具与记录。复用候选source_path仍旧Stage009，method=proven_nonbinding_reuse，保留原entry/交易/PnL/statistics并重建R50字段；新金融输出stage012_C_<start>_attempt001，method=fresh_engine。
