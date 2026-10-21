# Stage372 一次最新成熟样本训练协议

- line_id：`futures_full_market_long_signal_ai`；记录：2026-10-20 04:38 CST。训练前科学协议，非收益突破、非正式候选晋级；尚未读482MB实体或训练。
- [精确协议](../outputs/stage372_latest_mature_training_protocol/protocol.json)：7908B，SHA `d854a77e3935f290c554399718f51f8bb775849372d39e8ecd88b9cd72c85001`。依据371小记录/130与071训练数学制定，未看新模型或未来行情。

## 唯一命题与判断

[scikit-learn时间序列文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)支持按时间扩展训练；[维护者交叉验证说明](https://github.com/scikit-learn/scikit-learn/blob/main/doc/modules/cross_validation.rst)强调未见评价与学习分开。推论：原2023 cutoff估计不必永久不更新，按相同规则吸收后来成熟经验有有限价值，但不保证优势、不能消除长期历史择题偏差，旧曝光区间不能再当盲测。

新版本`PURE52_LATEST_MATURE_20261020`只问“扩大成熟训练历史后的估计能否改善后续决策”。不新增特征、学习器、seed、标签、持有期、风险或成本；不查看旧金融收益选版本。原2023参考及359 T0、370双空态均不改。此阶段不是与正式C9组合或晋级的A/B/C，不调用生产身份流程。

## 固定设置

- 训练cutoff=`2026-10-20`，仅main一次；实际底料为接受129快照，标签只至2026-10-16，不假定19/20已成熟。
- 原eligible、closed_complete_bar_model、有限net_R_stress、非空label_known，u与label_known均严格<cutoff；unknown/open/censored/取消诊断0不转成目标。完整输入1552456动作保留，训练排除逐项计数。
- old cutoff2023同门只计旧/新增成熟数量，参考旧main445475，不重训/预测旧模型。若无新增成熟，0fit停止，不换窗口。
- 新成熟全集重算原130 family-u区间并集、并发uniqueness、组内均分、等u、均值1权重；原071加权finite scaler、26值+26missing列序、原目标单位不改。Ridge alpha1/intercept/cholesky/thread1完全固定。
- source为现成actions334909637B与common146877351B，无下载、SQL、mothers、旧nativecache、原经济投影或重标。原130入口强制6fit和历史预测，不改cutoff硬跑；373只抽原训练数学，准备auth后root才actual。

## 预算与证据

- 最多1次实际fit/1个模型；训练fixture另记，不算实际拟合。0旧历史预测/选择/held/现金/生产/Git；失败保留，不切换solver/参数救参。
- actual每个必要实体只作所需读一次，并结合精确SHA；独审可另各读一次必要训练实体，不能重跑旧资格。保存训练身份/权重/分组、scaler/portable、方程、最大成熟日期、source/runtime/terminal；不复制规范化X大矩阵或原行情。
- 374独审完整训练门、权重/scaler/方程/模型/bug与置信边界，0reviewer fit/旧金融。root375在接受并保存后另以真实事件签T1，不拿训练截止或文件时间代替冻结；赶不上u20完成就不追认u20。
- 未来新模型只能在T1之后完成的新输入上另评估。未来报告终点/共同比较范围须在新模型首次未来评分前固定；不得借原2023账户或未出资seal，不据短期优劣换赢家。

本阶段期末权益/收益/DD/Sharpe/滑点/交易次数/胜率全N/A，新增fit/cash0。开始/结束新增按成绩选参过拟合否，历史研究偏差及增加一个训练版本的自由度仍在；继续单次有限训练价值是，新增样本不等于新增信息或窄损/加注资格。完整目标active。
