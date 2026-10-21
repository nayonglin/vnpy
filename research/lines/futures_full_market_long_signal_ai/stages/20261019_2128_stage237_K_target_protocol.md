# Stage237：固定同样本、同权重、仅替换K收益目标

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 21:28 CST；非重要突破；原goal active。
- 上轮归类：实质进展。233/234一次实测与独审确认少量尾部训练收益不同，235接受对象测量；不是alpha或旧目标bug。当前没有存活进程需要重复等待或重跑。
- 开始反思：本轮按新收益调参数否；同史反复研究的适应性过拟合风险是。继续一次固定target-only反证有价值；不重开失败DOMAIN52包、不承诺盈利或加注。

## 事前固定合同

候选`K_TARGET52`与`DOMAIN52`控制相比，只替换stress训练Y；52坐标、六原scaler、S样本、精确218权重/总loss质量、alpha1/有intercept/cholesky、所有K选择执行保持。另必须同时比较原`COMMON52+K`基准，防止只胜失败控制。对原基准的差异不单归因Y，因为原训练域也不同。

先读取六份已接受218 support NPZ（合计9,335,898B），不再读六份130旧训练CSV（138,791,254B）或129原actions。233标签恢复已接受原alias，按旧状态/旧Y及旧时钟重建原T并与support.sequence逐值一致；S=T[原mask]且mask与原primary完全一致。直接使用new_weight[mask]，不再乘因子、不重算uniqueness。所有S行新Kstress finite/known、phase收盘、tK≤t0<cutoff，六fold全部C=S及X/权重资格通过后才允许最多6实际fit。失败正常0fit结案，不删失败行或自动重训控制。

原Y沿legacy解析；候选先Y0.copy，K前copy逐值保持旧浮点值，仅真实K报价替换为233新值roundtrip。没有1e-12阈值裁剪或float32。744新增known和其他旧Y未成熟但K成熟行不进训练。全1,933,480前向child、main161,014/held合计161,014母体身份保留，无新duration、q、权重、缩放或模型。

held采用相同严格Kstress payoff，两个family组×2020—2022/2023—末日部署段×两个控制共8格，每格known等u增量均值严格>0、distinct unknown=0且有日期。未选与已知政策取消为policy0；selected丢标签或非主域是矛盾，不能伪作0；同action差值0且未知另披露，不同action任一未知保留未知。普通/F先按实际赢家聚合family-u，再对完整u等权，不仅取已交易/closed交集。任一格失败0cash。main完整动作/selected/anchor与任一必要控制相同，也0cash结案。

本237仅资格、最多6fit和新预测/选择/held，**资金回测预算0**。门全过且239独审接受后，才另冻236预结果设计的最多4个候选自有现金账本与双控制收益/DD/CI门；已知执行未知不能靠名义正收益冲掉。没有生产或增加投注资格。

## 调研、执行与审查

本轮实际核对[SPO原文](https://arxiv.org/html/1710.08005v5)、[作者GitHub](https://github.com/paulgrigas/SmartPredictThenOptimize)及[官方Ridge文档](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)。判断：对齐政策目标值得，但论文不证明必须换学习器、原均值预测错误或收益会改善。权重尺度会影响相对正则化，故保持精确旧w/alpha，而不把重算权重混进target。local sklearn仍1.6.1、numpy/pandas2.2.3、scipy1.17.1；在线文档版本不构成升级理由，无安装或复制外部算法。

238作者实施4项新tiny，继承已接受218 Ridge核，不重跑旧suite或原算法测试；239独立3—4tiny，不重复作者测试。独审不fit，复用已接受218 H/r只算目标差Δrhs并核新解、全部新score/choices/held/身份/计数/bug与置信度。大输入只各必要读取一次及stat前后比，继承已接受SHA，不再hash旧大文件。只有root精确源/协议授权才唯一actual，保留每个已完成模型和失败终态，不自动重试。

新增/修改/删除交易参数：无。当前新增fit/cash均0，累计433/234；本轮权益/收益/DD/Sharpe/总滑点/交易/胜率N/A。新源码和结果写本线；不改旧策略、根账本、Git、生产、CTP、邮件、定时任务或分钟资料。

机器协议SHA：`8aad5f5b6afefec4b078ba7a32f48b806119977156ade22da04eb4e433885c06`。后续238、239、root240分别记录真实运行及裁决，不用计划代替结果。继续原目标价值是；停止条件见协议，不救参。
