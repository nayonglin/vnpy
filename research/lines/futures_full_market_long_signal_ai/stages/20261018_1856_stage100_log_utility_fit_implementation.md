# Stage100 固定同单位L/G模型与整候选目标域实现冻结

- line_id：futures_full_market_long_signal_ai；2026-10-18 18:56 CST。重要突破：否。本阶段为099既定科学合同的实现，不是新增收益证据。
- 唯一当前目标仍为国内全市场全品种long-only、高质量做多、窄止损、成本后更高收益且更低回撤；正式版、生产、CTP均不在范围。
- 当前累计研究账本沿099记357fit/86cash；本阶段新增actual fit/SQL/cash/label/download均0。唯一actual runner为root，仍须最终源码、协议、输入与新目录的精确授权。

## 判断与边界

调研判断沿098与099冻结结论：[Kelly原始期刊记录](https://onlinelibrary.wiley.com/doi/abs/10.1002/j.1538-7305.1956.tb03809.x)、[风险约束Kelly作者论文](https://web.stanford.edu/~boyd/papers/kelly.html)及[作者代码](https://github.com/cvxgrp/kelly_code)、[SPO原论文](https://arxiv.org/abs/1710.08005)及[作者代码](https://github.com/paulgrigas/SmartPredictThenOptimize)只支持经济偏好与决策目标需要对齐，不保证本线收益。此次未复制新库、模型或优化器。L/G不新增市场信息；孤立u预算代理不等于重叠持仓的真实组合财富log，更不等于最大回撤约束。

已见此前registry披露、086留组诊断等上下文，不称盲研究。本包按099在收益前冻结，未读新100/101实际结果；当前不存在本包actual输出。没有按任何收益改变目标、window、模型或风险。

## 实现

新增唯一执行源`tools/stage100_log_utility_fit.py`与对应小fixture测试。只pure import已接受071的自身成熟切片、权重、有限值总体统计、Ridge、score动作及序列化工具；不调用其旧actual入口，不读取旧模型或旧金融输出。源码bundle绑定新源、新测试与071原源。

COMMON26标准化与26缺失位共52项，两臂同一训练矩阵、统计、权重、身份及intercept。无RFF、外部标量/缺失槽、序列、OI或额外COMMON选手。训练仍为自身NARROW closed、u<cutoff、非空known<cutoff；权重沿071 family并发唯一性→u等质量→mean1。统计只取本fold成熟训练有限值，缺值填训练均值。2020/2023两cutoff各L/G，共最多4fit；完整预测包含notready/noref/unknown，每臂161014，总322028；动作仅原ready20和score>0，不增加成本/目标域动作门。

目标逐行保存原y、c、a、z、L、G、reference wealth与域状态：`a=1/(1+8c)`、`z=a*y`、`L=z`、`G=log1p(.0025*z)/.0025`。任何当前成熟行的c负或无效、a不在(0,1]、y/z/wealth/log非有限，或wealth<=0，整候选停止；不删行、clip、epsilon、置零或改f。先验证本fold成熟域，再调用071既定finite-y切片以核身份一致。避免在加载时调用071全母体finite-y断言，防止提前扫描未来域。

完整4fit及322028预测落盘后，才计算2020起、closed且known<=end的未来域。未来域失败保留全预测并停止cash；未来域不参与训练/预测/入场资格。未知、open、取消等状态保留原标签及null目标。后一个cutoff训练失败则保留前fold模型和分数，禁止自动修复重启。

保存每fold训练IDs/权重/两目标、scaler、完整预测身份，最多4份joblib/portable/53×53含intercept正规方程，完整main预测、全母体后验域投影、年度及全family含零机会统计、明确asset roles与全部输入引用。不保存重复52项head大缓存；头可由bound COMMON与fold scaler重建。MSE只作各自目标的描述，不作为现金收益或第三臂证据。

## 终态和101接口

- `manifest.json`：schema=`stage100_log_utility_fit_v1`。正常为status=`completed`、domain_pass/cash_eligible=true、4fit与322028预测；绑定protocol、source_bundle、四input_bindings、terminal、predictions_main、domain_report、domain_projection、fit_records及各artifact角色。
- 科学域失败为status=`domain_failure`，completed=false、execution_completed=true、exit_code=0，cash_eligible=false。训练失败可0/2已完成fit，predictions_main=null并保留已有partial_predictions_main；后验域失败为4fit与完整predictions_main。真实异常则terminal=`failed`、exit_code=1并抛出，留现场，不自动重启。
- `domain_report.json`：schema=`stage100_log_utility_domain_v1`；正常status=`valid`、domain_pass/cash_eligible/oos_checked=true；失败status=`domain_failure`且cashfalse，记录training_folds、oos_domain及精确已保存预测binding。101必须整候选hard拒绝失败域。
- `predictions_main.csv.gz`：原7身份列、policy=NARROW、arm=L/G、cutoff、history_ready20、selected、score、scope=main；无held、无额外缺失列。训练前后目标域不删除预测行。101仅消费正常完整main。

## 新fixture验证与冻结

先观察源缺失时7项测试RED，再实现后执行：`.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p 'test_stage100_log_utility_fit.py'`，7 tests / 1.021s / OK。只含内存4行fixture，其中2次小Ridge调用明确不是research actual，未读取真实COMMON/labels。覆盖公式及同单位控制、无效c/a/y、严格wealth零边界、极小值log1p、同52项与训练统计不看未来、成熟域失败0fit保留行、两fixture模型后未来域失败且全预测仍在。未跑旧suite。

最终SHA及最小四参数CLI/精确auth形状见本阶段`outputs/stage100_log_utility_fit/implementation_receipt.json`。等待102一次有限代码预审及root最终精确授权；本作者不启动actual。

交易参数新增/修改/删除0。新增实验目标仅099的同单位L/G曲率；模型容量、阈值、stop、风险、成本、窗口均不变。新增/修改/删除回测结果均无；权益、收益、最大回撤、Sharpe、滑点、交易数、胜率全部N/A，不能把工程测试记为金融进步。

## 反思

此次按本包结果选择参数：否，0actual且目标、模型与停止边界均先冻结。历史多轮研究选择导致过拟合风险：是；换偏好不能声称新增信息。继续价值：有，但仅限这个已冻结的小型反证包，目标域失败即整候选停止，不能转向新的效用、f或阈值救参。通过域也不是经济目标完成，更没有真实组合增长、跨周期或正式资格保证。
