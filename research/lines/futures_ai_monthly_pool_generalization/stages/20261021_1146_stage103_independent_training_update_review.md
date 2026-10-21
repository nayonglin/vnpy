# Stage103 固定训练与同标签比较独立审查

- line_id：futures_ai_monthly_pool_generalization
- 记录时间：2026-10-21 11:46 CST；独立审查，不是重要突破；不触发正式A/B/C。
- 工作区：/Users/mac/Desktop/fian；解释器.py311/bin/python；只写本Stage103目录及本唯一阶段记录。

## 调研与判断

读取100冻结方案及其已保存的sklearn官方防泄漏、时序交叉验证说明、GitHub切分源码。没有新网络取数。判断：双时钟严格早于cutoff和train-only scaler符合防泄漏目标；并不消除历史开发、标签两尾选择、非随机缺失和参考执行假设。既有记忆仅用于保持冻结合同及研究/生产边界习惯，本次所有结果来自当前文件的独立复核。

## 本次变更与参数

仅新增独立审查脚本/机读review、分fold核验、8条标签明细、prior/paired年界、非重叠敏感性及README。模型、特征、策略新增/修改/删除参数均0；没有fit、模型搜索、资金账户回测、Git或生产动作。本训练源halfR/retry=False、C2=True；不把本审查当正式资格认证。

## 独立结果

107,346检查、失败0；接受Stage101/102以及Stage104预声明非重叠子集，未解决P0/P1/P2=0/0/0。冻结100输入、各manifest声明及7份新旧joblib全部SHA绑定。

完整19698格、8398 asof、4770条件点值；1374 robust=688正+686负（155月86产品）。旧1366标签保留、新增8与075相同；其中仅2022年2条OI在2023—26各cutoff前成熟，另外6条尚不进入这些年初模型，避免把“总目标+8”错读成“每个fold+8”。

严格双日期train counts为467/579/632/679/734/808/901/1036/1236。2018/19和全部原18保持floor不足跳过。逐fold复算train population mean/scale、样本数与prior；核固定12特征、LogisticRegression(C=.20,l2,lbfgs,max_iter=1000,random_state=42)、coef/intercept元数据、收敛及正则似然梯度。直接载入新joblib预测和独立sigmoid均与4738概率一致到数值容差。2020—22模型文件SHA/概率float64 bits与旧模型完全相同，2023—26每fold仅增加2条训练样本。

评分81月/4738全U，未知未删未当0，最新2026-09-30为77研究品种。对每个未知y分别取0/1，重算三类损失及prior/old减new配对界，逐月全N平均、年度仅成熟月等权，均与101/102一致。工程覆盖合格2020/22/23/24/25；2026只有6成熟月。

| 年度 | 旧loss减新loss的完整N Brier识别界 |
|---|---|
| 2020—22 | [0,0] |
| 2023 | [-0.00290370,0.00303723] |
| 2024 | [-0.00238178,0.00252395] |
| 2025 | [-0.00188177,0.00161909] |
| 2026（6成熟月） | [-0.00179947,0.00144102] |

相对prior的Brier界也全部跨0；2023/24 known-only局部正、2025/26为负，不能代表完整候选池。按既定label_end贪心抽取24非重叠月，其104旧新敏感性每年Brier下界也无正值；不能据此宣布独立forward OOS。损失界是缺失识别外界，非CI，独立枚举可能比真实联合秩约束更宽。

期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A；这是分类模型诊断，无资金回测。

## 结论、置信度与反思

工程计算/保存模型/切分/损失与SHA证据置信度高；跨周期预测或金融有效性证据不足。保留NO_PROMOTION，不替换正式模型。历史开发、目标60日重叠与产品依赖、可识别两尾选择、非随机缺失、静态费用及逻辑daily open/reference时段未PIT/live认证仍限制解释。

开始/结束新增按成绩择参过拟合：均否。原因是100事前冻结且无新参数搜索；不能据此声称上游无过拟合偏差。开始继续价值：是，一次固定更新能检验最近1366训练版本与1374监督集的实际差异。结束继续价值：新来源/独立forward观察是；当前同数据复杂learner、阈值和known-only救分否。

后续由root合入者更新LINE/registry和闭环，本审查不修改。无金融/实盘晋级建议。

输出：outputs/stage103_independent_training_update_review/review.json、review_training.py、README.md；明确SHA绑定见review.json。审查复现命令：`.py311/bin/python research/lines/futures_ai_monthly_pool_generalization/outputs/stage103_independent_training_update_review/review_training.py`。
