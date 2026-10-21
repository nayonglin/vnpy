# Stage432 最终52输入的单次固定浅树对照

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 19:22 CST。独立全市场研究，不是正式C9候选合入；沿当前分支，不建worktree。
- 430核实际代码：旧053HGB是2N代表合约53槽，旧094RFF是181序列/代表月NARROW，最终130逐月52与156/157K仍全部Ridge。不能把旧失败概括为最终目标浅树已失败，未测也不保证有价值。
- [Gu/Kelly/Xiu原研究](https://www.nber.org/papers/w25398)、[原tabular benchmark](https://arxiv.org/abs/2207.08815)、[官方HGB文档](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html)及[维护者代码](https://github.com/scikit-learn/scikit-learn/blob/main/benchmarks/bench_hist_gradient_boosting.py)只支持一次非线性交互的学习器比较，不证明国内期货alpha或窄损加注。依version-ab-experiment固定控制与反救参原则，用户独立全市场scope定义本研究A/B，未创建正式C9臂，正式六身份验证留给真正晋级时。
- 所有成熟训练行、原Y、权重、train-only scaler、52列、2cutoff×3scope、K/正分阈值/分配/执行/成本/初损风险固定；只把Ridge换成原053既定depth3/leaf7/100轮/leaf样本100的HGB。不得nativeNaN改输入或顺带重标237K/DOMAIN/q。完整参数/身份/预算/前置后置门见同名输出protocol.json，收益前固定。
- 最多6新fit；主动作改变才4新candidate现金，原157四控制直接复用。heldfirstexitR只是另估计量，不提前冒充K现金否证而省掉所需金融检验；最终泛化门仍明确核held与unknown。旧模型/旧现金重跑、下载、SQL、标签、未来D/原账户修改均0。
- 433拟合与434现金薄包装独立实现、一个小fixture；root绑定最终源后启动，435在实际结果后一次独立核数据/逻辑/置信度/bug，不做重复全审/训练。任何实质失败保留partial，不自动重跑。
- 本阶段尚无新训练/回测结果，权益/收益/回撤/Sharpe/滑点/次数/胜率N/A。未认定重要收益突破；无正式配置/生产/CTP/订单/邮件/调度/Git修改。
- 运行前过拟合：是，历史多次择题和新增模型选择均有风险；本轮不按成绩扫描，不能声称全无过拟合。继续价值：只限一次预先固定的model-only反证；失败关闭此包，不换树参数救参。整体原目标active未完成。
- 431直接cropcondition字段的source-only建议保留下一独立候选；本轮不同时扩报告解析或跑第二个金融假说。
