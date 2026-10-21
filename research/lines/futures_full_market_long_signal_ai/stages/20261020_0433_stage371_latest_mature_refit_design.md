# Stage371：同规则最新成熟历史扩展训练的有限价值判断

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 04:33 CST；只读设计，非重要突破。先核registry及130/129小manifest、128合同和必要源码；未读X/Y、大缓存、行情或成绩。
- **有条件GO：值得另立仅未来评估的训练版本。** 吸收2023后合法成熟资料不等于新alpha；不在曝光历史上择优。实施/actual预算0。

## 一个实质问题

原130 `main/2023-01-01`训练445475动作、3139日期、77 family；小`fit_records.json`最大u为2022-12-29、label_known为2022-12-30。**固定学习规则不要求永远固定2022年底的估计。** 唯一问题是较新完整训练估计是否更适用于随后市场，不增加特征、模型、seed、fold、标签或风险选择。

我的判断：扩展资料可能降低估计噪声、纳入后来经验，有有限价值；expanding保留旧周期，也可能稀释新状态，不自动追踪regime。旧52若缺相关信息，更多资料不能创造信息，更不能授予窄损加注资格。

## 已有实体与成熟边界

只核小binding及大实体stat，字节匹配；未读内容/重hash：

| 实体（本线outputs下） | 现状 |
| --- | --- |
| `stage129_contract_choice_dataset/actual_run1/actions.csv.gz` | 已在，334909637B，1552456动作及状态/成熟日期/原目标 |
| 同目录`common26.npz` | 已存在，146877351B，与动作同序的原26列 |
| 同目录`mothers.csv.gz` | 已在，19551936B；训练无需历史预测母表 |
| 130六fold绑定 | 仅main/held0/held1×2020/2023；没有latest成熟训练子集/scaler/模型现成绑定 |

限定链路中，底料已在，**最新训练实体未形成**；新增成熟行数/最大日期未知，不把预测行或全体closed数当新增训练数，不作全库不存在证明。

接受129范围终止2026-10-16。`simulate_action`只遍历至end，退出记`label_known_date=exit_date`、phase=`after_all_source_close`；130 `fold_slices`门为原u_action_eligible、closed_complete_bar_model、有限net_R_stress，且u与非空label_known_date均严格<cutoff。取消诊断0、open、unknown、右删失不进目标。

可支持**在接受129快照上按cutoff=2026-10-20筛成熟**，实际label_known上界≤16日；不是已补到19日。晚取u19及未来u20观察无闭合新标签，不纳入。16日open不能因今天已晚而假定成熟，不重放价格补标签。

## 同规则究竟保持什么

沿130在**新成熟全集**重算family-u区间并集、同family concurrency/uniqueness、组内均分、等u及均值1权重；用新训练集加权finite统计重算scaler，仍非有限标准化置0＋26 missing共52列，Ridge alpha1/intercept/cholesky不变。first-exit stress目标及0.25N/20low/K/成本/预算不动。

同规则不等于同数值：新增区间改变旧组uniqueness，总样本归一和scaler均会变化；应保存，不按系数方向调整。冻结旧scaler只改系数是另一臂，本371不添加。

成本有限但非零：约482MB压缩actions+common，解压/区间权重/52维矩阵有内存成本；无需下载、SQL、新特征或重标。130 CLI强制六fit及旧史预测/选择/held诊断，且要求非空pred；cutoff超过end，**不能直接改CUTOFFS重跑**。以后若授权，需只复用训练数学、保存成熟身份/权重/scaler/模型/方程的薄入口；本文不实现或签预算。

## 未来评价与文献判断

[scikit-learn官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)支持时间有序扩展训练，不证明必胜；通用等间距split不能直接套重叠动作/可变成熟。[维护者文档](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)区分学习与未见评价，反复按test调设置会污染评价。两query/两正文页，不安装升级。

原2023参考、359/360/T0与368初始化不变。新模型另记完成/冻结T1；仅T1后完成且及时收到的新u可算其forward，赶不上u20就不追认，原参考u20不受影响。不跑旧现金择优，不按旧收益选截止/版本，不以几天收益宣布胜者；未来评估终点尚未冻结。

**曝光过的2023—26可训练，不能恢复为未见检验。** 新fit不抹去52/标签/风险的历史偏差，新增版本也增加自由度。价值在固定更新、接受未来反证；若机械筛选没有新增成熟样本，就停止，不换窗口。

## 结果与反思

- 仅增本文；实现/参数/回测结果变更0，fit/cash/预测/测试/API/下载/SQL/Git全0；权益/收益/DD/Sharpe/滑点/交易次数/胜率N/A，无生产/加注资格。
- 开始/结束过拟合：本轮按新成绩调参否，继承择题偏差是。继续价值：核时效及单一未来候选有条件是，旧史择优否。完整目标active；不改LINE/registry/初态，不重开368。
