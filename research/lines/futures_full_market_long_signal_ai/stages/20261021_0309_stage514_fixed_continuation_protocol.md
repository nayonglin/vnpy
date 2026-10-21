# Stage514 固定低容量续持模型及真实资金实验协议

时间：2026-10-21 03:09 CST；非重要突破，研究线futures_full_market_long_signal_ai。

上一513完成原现金语义单位状态及独审，是progress。本轮原目标仍完整：全市场高质量做多、更高收益/更低回撤、极小止损可承受后加注，独立正式C9。模型只测试退出模块，不能用它替代完整入场质量目标。

A为157 OWN四冻结VOLUNTARY_RESELECT账（不误用其131B refs），C保留A所有入场与.25N/SL0/K/风险，仅当前自由close预测为负请求下一可用开盘退出。所有强退、缺价、真实账户减仓优先，C按自己的真实持仓score，不复制单位退出日；旧A不回放。

收益前冻结六头（2020/2023×main/两held补集）、六mechanistic数值+六missingflag、weightedRidge1/sumw1/intercept不罚。X为(mark−SL0)/R0、(mark−Bnext)/R0、return1/R0、Nt/R0、持有source天龄、到min(source target,K target)的日历日。训练均值/std仅本fold observed加权，missing填mean标准化0并留flag，不做裁剪/搜参/年度族dummy。

Y为stress下原policy终端SELL净值−请求退出SELL净值，除原R0×mult；BUY已沉没抵消，fill已含滑点不再扣。事前K_date<cutoff先划cohort，再要求u/t/两SELL可得日期严格早于cutoff及D已知stressentry支持；unknown/cohort全保留，不训练未知Y，不声称无删失偏差。不按eventualτ/closed/明日有效性筛riskset。日期等权、日内族等权、族日内候选状态均分，sum1，不再X去重或目标聚类。

按t_date更新退出head，0/unknown hold。实际仅515四新表联流一次，存compact后六fit/pred/独审复用，不重扫旧metadata/native/129/COMMON/score。候选四C资金独立核算，2020/2023冷启动×base/stress，对A own四账一次比较，沿用100w/.25%/2%风险/25%保证金、1.1buffer/1%容量，绝不加注。

门：四C收益为正，主2020stress收益/DD严格改善，其余三不劣，primary日对数增长配对CI下界>0；两heldstress增量非负且至少一正为泛化诊断，未知保持未知。全指标期末权益/收益/DD/Sharpe/滑点/交易次数/胜率、年度/95family/同账2025与独审必须记录。失败关闭固定包，不扫alpha/窗口/特征/阈值/风险、不排品种或2026救分。

调研：[Ridge官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html)确认alpha与加权损失语义；[作者mlOSP](https://github.com/mludkov/mlOSP/)只提供继续/停止方法，不是期货盈利证据。

开始过拟合风险是（同史适应性择题/held已披露），继续一次固定实验价值是（不同持仓决策对象与真实资金验证）。本协议阶段0fit/0cash，金融指标N/A；累计505fit/274完成cash+1旧partial。后续actual须root精确source/协议授权，失败保留不自动重启。

协议：/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage514_continuation_model_protocol/protocol.json；SHA256 d90a160e62ae460a16dabb867e2a7495aceda59ebbd6b5e7487d5ee1084bb32a。

静审前数学补充：观测列加权population variance ddof0；权重在本fold最终known可训练集计算，未知cohort独立报告，无参数新增。
