# Stage047 新源可学习性诊断事前协议

- 时间：2026-10-20 21:58；重要突破：否。只测试新增研究源的可学习性，不运行或创建正式A/C策略臂，不改变池、订单、production或正式108特征。正式生产身份缺项不因本诊断解除。
- 调研：scikit-learn[泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html)与[GitHub交叉验证源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)支持训练内fit变换和严格时间边界；它们不证明本金融目标可预测。判断：先用低复杂度基线检验信息量，不以复杂模型掩盖来源缺失。缺失非随机与上游策略后验风险不可消除。
- 原理假设：同一结构在过去表现出的趋势强度、路径效率、波动/量/OI状态，可能含未来趋势策略适应性信息；这只是待否证假设，不预设更多品种必然更好。

## 冻结参数与数据合同（先于预测结果）

1. 仅接Stage044已经先于模型结果冻结的12项精确同epoch AM41过去特征，及Stage045完整asof宇宙的robust条件标签；所有行通过product/eval一对一连接。X缺失不能借未来可观测性缩N，asof合规却X缺失则阻断本诊断。
2. Source为Stage041/042/046新目标：monthly-flat未来60日累计episode unit-R、2手研究数量、halfR/retry=False、C2保留、日open逻辑参考、静态经济未历史认证。不是旧正式target/source、真实账户收益或正式策略A/B。
3. 固定StandardScaler + L2 LogisticRegression，C=.20、solver=lbfgs、max_iter=1000、random_state=42；不扫C、不选特征、不class_weight、不样本重采样。收敛失败即报告，不放宽阈值救模型。均值/scale只训练fit。
4. 固定年度截点2018—2026年初；训练eval与label_end均严格早于cutoff。2018/2019若不达Stage041训练floor则跳过。2020以后亦逐折检查同一floor，无后验降低。每年一个模型，测试当年全部asof候选，包括未来标签未知者。2026不足12成熟月只作partial诊断。
5. `expanded`使用所有asof产品的robust训练行；`original18`使用冻结名单的robust训练行，目标仍用同full-U排名，只有同样满足训练floor才fit，否则记录不可比较。`class_prior`为expanded训练标签均值的常数预测，无特征fit。两模型只作独立source诊断，不称正式A/B策略。
6. 所有年都输出全U概率与按概率降序/产品键平局顺序的研究排名，`usable_for_trading=False`。不写正式池或真实委托可消费的路径。缺未来值不影响预测，未知不填负类。
7. 每月等权平均Brier、logloss、accuracy界；已识别标签才作known-subset辅表。未知label逐行取{0,1}损失及两个预测器差的min/max，再按月平均。相对prior改进=`prior_loss-model_loss`，只有下界>0才证明该宽外界下的稳健改进。accuracy阈值固定.5；Top10仅可提供正类数识别界，不作收益测算。
8. 每个test年度须12连续成熟eval月、两类各24条、≥6产品才是工程合格块；至少3块才允许讨论跨周期泛化。已经看到的Stage045覆盖仅2024/2025可能够，不因不足而改要求。另按最早成熟测试eval起，下一eval>=上次label_end固定取非重叠60日目标子样本，汇总同样的全N损失界，不按结果挑月份。即使合格也只是历史pseudo-OOS，上游策略开发已看过这些年份，不冒充前瞻未见数据。
9. 保存固定feature/target/config身份、代码/输入输出SHA、标准化均值/scale、系数/截距与模型文件；仅本地研究，training/live qualification=False。独立review源/特征/标签与模型切分后才能接纳诊断结论。

## 失败与后续

- 不满足训练floor不fit；test块不足不声称泛化；稳健loss改进不能识别则不声称优于prior。模型打分不是收益、价格预测概率或交易胜率。
- 若来源/独审发现P0/P1数值错误，暂停fit，先修并独立重验；provenance P2修复须保留旧产物且解释数值是否不变。
- 金融回测指标（期末权益、总收益、回撤、Sharpe、总滑点、交易次数、胜率）均不适用；本阶段不是账户回测。
- 开始新增按收益选参过拟合：否，参数/特征/切分先固定。来源选择、非随机标签识别和上游历史开发后验风险：是，持续披露。
- 继续价值：是，以固定简单诊断确认数据扩充是否增加可学习信号；若证据不足，结论应是不晋级，下一步针对数据可识别性，不加参数救分。
