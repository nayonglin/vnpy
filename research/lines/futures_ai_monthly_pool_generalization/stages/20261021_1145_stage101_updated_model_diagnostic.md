# Stage101 最新标签固定模型训练测试

运行时间2026-10-21 11:41，北京时间。非重要突破。按100冻结协议，1374标签替代最近060b使用1366，保持原12特征和LogisticRegression(C=.20,l2,lbfgs,max_iter1000,random_state42)，StandardScaler各train独立拟合。

实际7个年度研究fit（2020—26），无包装重复fit/参数搜索；2018/19不足612跳过，原18最大年度442<612全skip。完整4738测试评分/81月，最新2026-09-30 77品种。新增监督8条中仅2条可进入2023—26训练，前三年份数据相同；2020—22 joblib与060b逐字相同，后四不同，2922预测概率变化。不是从旧正式108特征直接扩到新数据。

训练与测试按eval_date及label_end双重严格早于年度cutoff。覆盖工程合格年度2020/22/23/24/25，2026只有6成熟月；五年覆盖门槛通过不表示预测力有效。完整N Brier对训练prior的稳健正下界年度数0，未证跨周期改善，不晋级。

阶段新增/修改/删除策略或模型参数0；训练数据1366→1374是唯一实验delta。model/prediction/feature_contract/local_reproducibility_manifest已原生成器显式分为model_artifact、decision_asset、feature_contract、qualification_evidence；source_chain_supplement额外绑定093/094/095/097/100，不回写原manifest。103独立审模型/scaler/预测与置信边界。

调研见100保存的[防泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html#data-leakage)与[时间切分GitHub源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)。判断：研究训练可以现在开展，不需要等所有未知补齐；未知必须保留在评价宇宙，不能训练成负类。属于历史pseudo-OOS，非独立前瞻验证，仍有两尾选择/非随机缺失/历史开发/静态经济/参考session风险。

开始/结束新增按成绩择参过拟合否，无新调参；继续一次更新有价值，训练后重复同协议/扫参无价值。资金账户回测未跑，权益、收益、回撤、Sharpe、滑点、交易数、胜率N/A。半R/retry仅训练源False，C2=True；正式源、模型、池、订单与调度均未动。
