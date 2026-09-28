# Stage006 事件终点截断回放等价合同

- 时间：2026-09-05 20:12 CST；line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`。
- 目的：减少全量反事实标签回放的无关未来计算和磁盘占用，不改变策略或标签。
- Reviewer关闭；不是XGBoost候选或重要突破。

## 唯一执行

- 固定沿用首事件candidate_index=241，纸浆2022-02-08决策、2022-03-15闭合。
- 两个冷worker：A原始、S仅跳过该根；起点仍2020-01-02，只把回放终点设为2022-03-15。
- 与Stage004完整A/S各自截至2022-03-15的前缀比较，七类表逐值必须完全相等；不改变正式资本15万、AI、成本、仓位、特征或数据源。
- 事件研究身份仍属于原2020-01-02至2026-08-28合同；额外记录实际execution_end，不能把不同回放期限混为同一绩效。
- 该事件的两个标签必须与Stage004B逐值一致；不通过就不把截断方式应用到其他标签。
- 新回放仅2次，可以两个独立进程并行；worker网络/CTP/订单/新模型训练等禁止操作保持0。
- 复用Stage004已经验证的worker函数和Stage003冻结LR推理限制，通过独立研究模块配置回放终点；不修改旧文件或生产。

## 存档

- 空闲磁盘约11GiB；未来159份原始回放可能超出容量。因此本阶段同时验证gzip无损存档。
- 每个新生成CSV压缩后重新解压计算原始bytes SHA/大小，与原回执完全一致才删除本阶段自己的未压缩副本。
- 压缩文件、压缩身份、原始身份及worker原始回执全部保留；Stage004参考CSV绝不删除或修改。
- 前后验证所有冻结输入；summary分别记录两个实际回放指标、前缀比较和标签等价，不把短区间指标当成全周期模型效果。

## 后续模型形状预先固定

- 全量标签尚未生成。在此提前固定下一模型形状，避免看到标签分布后再扫参数：两个XGBRegressor分别预测接受减跳过收益、回撤。
- 12项特征沿用Stage003；objective=reg:squarederror、n_estimators=80、max_depth=2、learning_rate=0.05、min_child_weight=20、reg_lambda=10、reg_alpha=1、subsample=1、colsample_bytree=1、tree_method=hist、n_jobs=1、random_state=20260905。
- 参数参考XGBoost官方parameter文档对深度/正则化的含义，不声称这些数值最优，不进行网格搜索或依据历史结果改符号。
- 以月初为训练/预测边界，扩展训练窗；训练根决策时间和标签成熟时间均严格早于月初，至少60个成熟根才训练，否则保留正式A动作。
- 仅两个回归预测都严格小于0才允许skip；每月模型冻结，不能用本月未来标签重新拟合。
- 历史只有开发证据；当前主线没有达成收益提升且回撤下降。真正有价值候选还需跨阶段和成本反证，通过后才拉reviewer。

## 调研与反思

- https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-of-time-series-data ：时序必须前推验证；本线按标签成熟时间排除未来交叠。
- https://xgboost.readthedocs.io/en/stable/parameter.html ：通过浅树与正则化限制复杂度，不靠添加深度拟合少量事件。
- 过拟合判断：否，本阶段是同一事件同一结果的执行等价验证，不改经济机制；模型开发的小样本风险仍高。
- 继续价值：是，成功后可对159成熟事件生成可复验的账户标签，复用首事件并保留2个删失行。
