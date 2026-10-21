# Stage628：原52＋K完整准入静态诊断的独立审查

- line_id：`futures_full_market_long_signal_ai`；完成2026-10-21 09:56 CST。先读registry/624/621/623，定向核156/233，完整读冻结625及627新源码、8个新synthetic fixture、source-ready/真实receipt；没有重跑作者fixture或旧suite。非重要突破，不改LINE/registry、正式C9。
- **结论：接受627诊断的数据、逻辑和计算，0 Critical / 0 Important；固定conditional门未过，完整E净R未识别。** 不等于AI全部无用，也不证明稳定全市场优势或财富增量。root唯一实际40692退出0/84.730246s，0fit/0cash/0新标签；累计551fit、290完成cash＋1旧partial不变。

## 预审与实际如何独立

625协议SHA`a9f4363c6069fc95ad7e845e45fb925619ae69b73e256bd12010f67b4c484651`，627源码SHA`90f33f4cc8803ddc5f028554f2dd632afe1cf21a2b1804649cc620aceceae673`；收益前source GO已在`source_go.json`保存。没有从627 daily/stat反推选择：独立解析完整1,933,480 signed score投影、399252母身份和全部选中K原literal，重新算纯K、逐product最大分、普通/F优先、正分赢家与only无赢家fallback，再按固定calendar/原070 indices重建三层统计、年度/全family零机会覆盖、门和unknown。

首遍65938保留14,837,000项/0失败的core日志：E216916、union129851、原main正分4365动作全部保持；全负分普通不能替换原正分F。原main与accepted156逐母/动作/epoch/score/cutoff/anchor对照；held为原规则重建，不冒称存在已验held文件。完整98/95母体、322028适配scope母行及含零机会的1330条family-year覆盖得到核对。未知结果没有筛E，也没有把非primary的政策0塞进可行动域。

65938最终写report时，审查器自己的计时变量被窗口日期遮蔽，权威exit1；同错误使exception footer也未写出最终统计。**这是审查器故障，627和策略没有重跑/修改。** 旧审查源码、原4条progress及失败收据保留。按root授权修timer，fresh77759仅复用首遍已独立逐字段匹配的E_linked补未持久化统计/覆盖尾段，exit0/5.958697s、1,144,011项/0失败；合计可追溯15,981,011项。没有假称原handle仍活跃或第一遍全审已成功。

## 固定口径下的结果

下表是**当日机会数归一化后、完整源u日历等权的潜在一手净R贡献**，不是每笔成交平均R、现金收益或胜率。I域n/k/p完全在同一known集合重算；完整E的未知仍保留。

|scope/window|A_I|AI−均匀的Δ_I|Δ_I描述CI95|未知总数 / 已准入未知|
|---|---:|---:|---|---:|
|main/primary_2020|0.01241990|0.02793380|[0.01098502, 0.04522167]|576 / 30|
|main/cold_2023|0.01526861|0.03578059|[0.01544641, 0.05934765]|302 / 5|
|holdout_0/primary_2020|-0.00087469|0.00922363|[-0.01036028, 0.02927770]|193 / 16|
|holdout_0/cold_2023|-0.00943117|0.01257055|[-0.00267398, 0.03411807]|111 / 6|
|holdout_1/primary_2020|0.02474584|0.05432498|[0.03043103, 0.07825408]|381 / 25|
|holdout_1/cold_2023|0.02855432|0.06031821|[0.03336097, 0.08555169]|194 / 6|

主primary和cold条件差为正，但holdout0后段自身A_I=−0.00943117，固定conditional_support=false；不能只截主样本的正差称泛化通过。全部6窗的完整E净R仍有非零系数未知，full_E_support=inconclusive；未知不补0、不nanmean删日期、条件结论不替代全域门。

Z=1[潜在K净R>0]按配对系数(m−p)/n形成未知[0,1]外界。它的端点均值/各自block描述区间均独立复算，不能叫完整净R界、现金胜率、联合95%带或成功门；没有因部分端点正就救conditional/full门。原2000×source-day索引与252源日循环块逐窗复用，各scope/stat共享，0新seed/随机政策账户。重复月份、同日held与重叠路径不是独立市场样本；固定历史预测与长期适应性择题的CI也不是未触碰样本推断。

## 未知不是只剩最后一天

main全部576未知、30个准入未知，横跨261个源u日：早段274（267 unknown_before_K、7 unknown_on_K；从2020-01-02起），后段302（130 historical unknown_before_K、93 open_K_pending、79在2026-10-16 intent_right_censored）。后段前者最早2023-01-03，不应统称等今天日线即可补齐。各scope/早后段/branch/state/reason和u端点已在小acceptance及完整review保存；均为unresolved原状态，不重造K标签或删尾。

两项源审非阻断限制如实核：`observed_children`实际0/1存在flag，未当子行数；full门额外保守要求Δ均值正，未改变独立full门的inconclusive结论。没有结果后改判或修策略。

## IO、调研与反思

原大score/K载荷由627各一次combined hash+parse；本独审0原载荷重读，完整score投影仅首遍1读，尾审0再读/0重建选择。E/K/母identity/coverage及结果cache第二读、两原070小npy各第二读（约20MB）均披露；这是尾审恢复的额外IO，不洗成0。0原native/模型/COMMON/SQL/网络/金融路径或账户重演。新代码仅628审查器；策略/模型/风险/费用参数及回测财富结果新增/修改/删除0，权益/收益/DD/Sharpe/滑点/成交数/现金胜率均N/A。

本轮收益前真实刷新[SPO原作者摘要](https://arxiv.org/abs/1710.08005)和[作者GitHub README](https://github.com/paulgrigas/SmartPredictThenOptimize/blob/master/README.md?plain=1)，仅支持预测与动作目标需区分；同k均匀精确期望来自边际包含率k/n的直接推导，不借论文声称中国收益、随机因果或缺失识别定理。

开始/结束新增按收益调参过拟合：否，冻结前未看新Y，结果后不调门；长期同史适应性过拟合风险高。继续价值：本次补核心证据有价值且已完成；不能据条件正差自动新fit/cash/加注，也不以本轮失败否认所有AI。目标仍active，历史诊断不依赖今日日线，独立于u20→D21前向账。
