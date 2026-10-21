# Stage041 缺失稳健月度 source 研究设计

- line_id：`futures_ai_monthly_pool_generalization`；2026-10-20 21:50 CST；独立研究设计，非重要突破。仅本协议输出目录/本stage，不改root实现、LINE、registry或生产。
- 结论：支持全域“eval月末flat→future60连续fresh/roll”的新研究目标；120past作为asof产品历史资格，首版特征只用精确AM41价格/量状态，不要求旧120source PNL。不是旧108追加或正式策略替换。fu固定与_F行保留但不进入非fu排名。
- first-open仅daily.open时明示research reference，逻辑bar stamp而非伪造09:00；calendar/session、真实tick顺序、queue、PIT经济、正式身份均不由此认证。缺分钟neither/confirm可条件识别动作，stop_only fill及both继续未知，错误signedR/guard/fee缺失不能填0/删除。连续source即使flat仍须验证窗口内再入场信号，不能复用entry-episode“永久flat后缺bar无碍”结论。
- 数学设计：每产品future累计独立entry episode净unitR，roll不改episode初始currencyR，fresh重入才换R。D60 MTM只计已发生legs+现持仓，不提前计D61pending。对每月全N个asof成员保留目标区间/无界，再以严格less与.5ties推rank上下界；K点值+U未知退化Stage002 r/N..(r+U)/N。K<=N/2则该月无robust已知top/bottom标签（必要非充分）。不known-only重排、不得中点/伪标签。
- 独立有限数学验证：`outputs/stage041_monthly_label_protocol/rank_bound_demonstration.py`实际运行1,159检查0失败；不是金融回测/真实标签或Stage042代码独审。详细规则与限制在同目录README。
- 调研：读取Manski缺失数据partial-identification原论文可访问摘要；scikit-learn官方TimeSeriesSplit/GroupKFold/数据泄漏文档和GitHub维护者源码。判断：panel gap=60不是60交易日；group切分不代替时间，scaler必须train-only。区间排名与本地阈值为自推设计，不冒称论文现成算法。所有原文链接就近列于README。
- 事前pilot工程门槛：训练至少60成熟月/612robust行/两类各100且各跨24月/12产品；OOS块12连续成熟月且两类各24/至少6产品，3年度块后才讨论泛化。这些不是统计保证，不足则继续coverage，不救参。固定L2 Logistic C=.20低复杂度诊断，不增加fit作为进度指标。
- 比较：old18与expanded同新source/同features/full-U target/同时间cut；strict产品组holdout须避免heldout outcome间接进入train的截面rank，train reference统一U\H而test全U并披露label-reference shift。按真实label_end purge60源日历、未来fold不用作过去训练；完整N上报告预测、coverage、Brier/logloss/accuracy与改进外界，known-only分数不得代表全域。
- 当前事实边界：Stage012 152是动作可识别（含51stop_only），不是152收益标签；66neither+35confirm=101也不代表未来完整source可识别率。Stage011 27自然日minute命中不等于session资格。Stage042实际全月coverage将决定是否可fit，不能提前猜测通过。
- 新增/修改/删除模型/alpha参数无；本协议冷启动新target与fixed整数诊断规则必须独立命名，未生产生效。期末权益/收益/最大回撤/Sharpe/总滑点/总交易次数/胜率均N/A，未运行金融回测。fit0、订单0、下载0、生产修改0；formal A/C因已知生产身份缺项仍不跑。
- 开始/结束新增收益调参过拟合：否，事前全域/时序/缺失合同，不依据表现挑参数；新目标不能伪称旧模型等价。继续价值：是，只有量化strict/interval识别与有效OOS覆盖才知道扩数据是否增加学习信息。下一步由root连续推进source与coverage，本reviewer另Stage043独审039/040，不能自审本协议当实现通过。
