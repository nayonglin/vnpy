# Stage656：SLV 数量条件增量的隔离实现与 source-ready

- 时间：2026-10-21 12:54 CST；line_id `futures_full_market_long_signal_ai`。非重要突破；完整读653协议/计划及654交接，沿已接受648/650源与655方法说明。只写本线隔离kernel、薄runner、5类fixture和小ready；不改原源、LINE/registry/根日志/Git/生产。
- 653唯一结果前协议为21,431B，SHA `bf1fbf5d03b51ea3e2abd3e2536b1106435dfdc754b8617623edadc4651ef680`。固定END=2026-10-16，**不等今日日线，也不推进旧watch**。0新现金。

## 调研与实现判断

网上/GitHub与方法判断沿653/655已核原论文、BIS与原作者项目；本实施不再扩源或重新验源，不读新Y选参数。价格/数量分开及保守时钟合理，但没有给SLV alpha或净流量解释背书。Polanyi式直觉仅压为预先冻结的数量×原AI状态交互，不能作为已验证经验。

采用test-driven-development与verification-before-completion：先5个新行为fixture全部断言失败（kernel尚未实现），再实现隔离kernel，最终5/5 GREEN（0.076秒）。只跑必要新行为，不跑旧suite。纯synthetic head solve为2，runner另以2个合成mother/4个child验证九scope/arm原选择，12个选择行；这些不是历史fit或现金回测。

## 冻结行为

1. 保留5160原source行/原9列，稳定日期顺序相邻成pair，不跳缺失或周末。d后2个完整Mon–Fri结束后的次日00纽约作为条件可用时刻，真实zoneinfo/DST；用CN u15:00按<=映射。该规则不是NYSE完整会话或strict PIT。latest invalid pair覆盖旧pair，四个Shares/NAV数须共同正且有限，否则B=C=A。
2. B固定残差raw slopes `[Ahat,P,Ahat*P]`；C只增加 `[Q,Ahat*Q]`。target为原stressR−own Ahat；raw交互先构造，train-only weighted scale，共同三列两臂精确相同。每source-date-pair总训练权重1，原sample_weight仅组内比例；Ridge1、intercept不惩罚。十二新对象上限，原52/标签/stop/risk/scaler全不重建。
3. 保持98历史product/95family、原两个cutoff/main+两held、完整mother与正负score。656.choose_all与538.select_scope/567链完全相同：own-scope child+own mothers →仅换arm score →alias scope=main →原 `stage156_voluntary_choices.select_full_pool(..., audit_sink=lambda _:None)` →还原scope/arm。无新增D<K、direction或epoch筛选。A从已保存own score重建信号选择，不读旧A choices，不做基准fit/现金回放。
4. 同action且own未知时paired差识别为0，同时保留own unknown；不同action任一未知仍NaN；flat明确已知0。源组等权conditional own/pair贡献；每era各一次252源更新圆块、2000次seed20261021，所有scope/arm共用索引，缺组保留NaN且报告coverage，不称fullE。
5. 四项653门不变：两main C−B CI下界正、四held C−B点值正、六C自身条件均值正、两main C自身CI下界正。MSE只诊断，annual含2020—26/partial26与95family零覆盖。失败关闭精确包，不改lag/窗/λ/族/年/风险救分。旧629 conditional false/fullE inconclusive及646关闭不变。

## IO、独审与身份

薄runner只在root唯一actual执行6train各一次、forward一次、mothers一次、SLV/calendar各一次。核心金融压缩预算310,827,226B；大源仅继承已审SHA+绑定stat前后，0独立重hash，不读COMMON/native/model/scaler/旧Achoices。实际同时写6份全域thin train、完整forward/母体、12heads、全部choices、原源literal/pair与calendar、源组/年度/family/未知/MSE、共享bootstrap索引及门/terminal/manifest，供655一次只读新cache独核，不重训。

ready绑定当前655原notes19,155B/SHA `5feaab7329fab4e0827fbda73cc9e989deccaf52a3467a5f072bd79251c96730` 及独立 `protocol_review.json`；actual结束还核protocol/654/655notes/clarification/fixture/ready/GO/reviewer_ready和所有源码小绑定，保持前后SHA一致。异常也写失败terminal/manifest，不自动重试。

- kernel：16,354B，SHA `989af8072dbbef1c21704f6f94c96d43e95eb87856610b750b32596fcf40b578`。
- runner：31,816B，SHA `f4d6ac090f1d0b2be1755b2f5b23958ec25e507352ae5ff251abcdd7fb9a4514`。
- fixture：5,938B，SHA `68b24185b6d3bf4bf48065b7c36bb07d955529aacaa2eb881389849f5c58de3c`。
- fixture_receipt：1,734B，SHA `1f2bd3199e2a0225217c6218ce697083fd43ca196943b885c8de6e53024557f5`。
- source_ready：3,341B，SHA `02cd01cc1ebb12576846201474f3da9858d1e4b3a7010a5609212694304d80dc`；`--check-source`真实exit0，10角色stat及小绑定通过，金融payload/model/scaler/actualfit/cash全0。

生成fixture收据时第一次subprocess误将venv解释器符号链接resolve到系统Python，导致缺numpy；已改为规定的literal `.py311/bin/python` 后生成上述真实GREEN收据，未改模型/协议、未启动历史actual。这是收据命令错误，不隐藏为训练失败或现金回测。

## root唯一actual命令

下面仅是已准备的命令；须待655对精确ready签发source_GO.json后，由root唯一启动并持原exec handle到终态。本作者未执行。

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage656_slv_quantity_runner.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage653_slv_quantity_increment_protocol/protocol.json --protocol-sha256 bf1fbf5d03b51ea3e2abd3e2536b1106435dfdc754b8617623edadc4651ef680 --source-ready research/lines/futures_full_market_long_signal_ai/outputs/stage656_slv_quantity_increment/source_ready.json --source-go research/lines/futures_full_market_long_signal_ai/outputs/stage655_slv_method_clock_pre_review/source_GO.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage656_slv_quantity_increment/actual_run1 --actual
```

## 当前记录与反思

新增策略参数为653已冻的单一时钟、P/Q/AI交互与Ridge残差头、固定conditional门；旧策略参数与旧结果修改/删除0。当前**真实新增fit0、现金0、金融Y/score payload0**，synthetic solves另列，不混入累计。累计551实际fit/294完成cash+1旧partial保持。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A，尚无本轮历史结果/alpha/窄损/加注资格。

开始/结束新增按收益调参过拟合：否，仅执行结果前固定合同，未读新历史收益；长期同史适应风险仍高。继续价值：是，仅一次已冻结的新数量条件检验及独核；重复验源、等待今日收盘或救参数无价值。等待655 sourceGO及root唯一actual，作者不越权启动。
