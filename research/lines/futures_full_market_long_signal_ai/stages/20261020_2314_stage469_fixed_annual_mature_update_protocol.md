# Stage469：固定年度吸收成熟经验的单项协议

- line_id：`futures_full_market_long_signal_ai`；冻结时间：2026-10-20 23:14 CST；非重要突破；当前只是协议，未运行新fit/cash。
- 结构假说：原COMMON52两cutoff设计使较新已成熟经验延迟进入估计。固定自然年年度扩窗更新，测试及时吸收经验是否改善成本后连续现金与回撤；不是增加Con4或生存标签，不宣称必然适应市场。
- 使用brainstorming/writing-plans/dispatching-parallel-agents流程处理这一有限研究问题；用户已授权自主持续迭代，在独立研究线执行，不要求再次批准例行本地计算。version-ab技能分类：独立全市场long信号研究对照，非当前正式C9整合/晋级；不得把研究A157叫正式A。

## 固定设计与实施计划

1. 读取已绑定129/actions/COMMON/母体与130旧模型。复用2020/2023六个模型/当年分数；新增2021/22/24/25/26五cutoff×三scope，最多15新fit。52坐标、Ridge(alpha1/intercept/cholesky)、原first-exit stressY不变。
2. 每年训练只用u<Jan1且label_known<Jan1的原合格闭合有限目标；未知/未平/取消不造Y。holdout_j训练排除本组，测试取本组；普通/F共享family。按原算法重算当年成熟集权重/scaler，不能借latest/全数据统计。模型在整个部署年冻结，2026结束仍2026-10-16，不混入之后前瞻事实。
3. 年度选品拼成完整连续信号流，training_cutoff与原deployment_fold_cutoff分列，保持全部原action/mother身份、共同K/原family优先级/正分准入；旧2020/2023同年选择必须与原156对齐。原位持仓不在年度边界清空。
4. 原四A157自身控制直接复用，绝不误用其baseline_references旧131B。最多四C新账=2020连续/2023冷启动×base/stress；100万、风险/保证金/容量/成本/退出完全沿原现金合同。若所有main实际分配所用选择与score优先次序都未改，则省掉cash，以原账身份复用并判严格增量未通过。
5. 原157全四正财富/收益、收益不低/DD不深，主2020stress严格收益/DD改善与252日2000次原配对CI下端>0门沿用；完整年/家族/held/unknown均披露，不挑赢家。失败停止annual包，不再比较月/季/滑窗/decay或小数。仅可报告研究证据，不自行晋级/加注。
6. 实现仅做新增成熟边界、年度映射、held成员及持仓连续性的最小必要检查；一实际流水有checkpoint，完成phase不因排版重跑。实际结果后一次独立审查模型、数据、选择、四账逻辑/置信度；审查器不fit或重放现金。中文stage记全指标/参数/失败与计数。

完整精确输入bindings、旧六model/scaler、四控制书/费用及bootstrap绑定、执行预算、闸门、限制均在 `outputs/stage469_annual_mature_update_protocol/protocol.json`。无新数据下载、SQL、正式物料/CTP/邮件/launchd或原前瞻账户变更。

## 调研判断与反思

[微软Qlib RollingGen](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py)展示扩窗更新与截断泄漏边界；[sklearn时间分割](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)要求按时间顺序。这里只借方法，不复制默认step/窗口/资产表现；原交易label_known严格门比固定行gap更贴合变长退出。

新增参数：固定annual Jan1更新；修改：部署更新clock从原2020/2023两次变为每自然年；删除参数0。特征/目标/权重规则/scaler规则/风险/成本/阈值不改，数值估计随当时训练集改变。新增/修改/删除回测结果均0；当前权益/收益/DD/Sharpe/滑点/交易数/胜率N/A。累计466fit/254cash及1旧partial不变。

开始/结束按本包结果调参过拟合否（尚未见结果）；长期同史择题风险是。继续一次严格固定的成熟更新对照有条件价值，但它不能修复信息不足、跳空或生产资格。完整goalactive未完成，未启动本协议实际。
