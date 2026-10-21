# Stage216：训练域差异已确认，选择单一loss-domain实验

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 20:12 CST。
- 当前为全市场long-only独立研究，不是正式A/B或生产动作；非重要突破。
- 214唯一actual 10.307906秒，六训练缓存各读一次，215独立核心阻断0。新增fit/cash/SQL/Y值/X/价格读0，累计427fit/230cash。

## 实证结果

| scope | 截止日 | 原训练行 | D<K允许行 | 不允许行 | 不允许旧权重占比 | unknown |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| main | 2020-01-01 | 247,795 | 216,443 | 31,352 | 12.868944% | 0 |
| main | 2023-01-01 | 445,475 | 390,340 | 55,135 | 13.111606% | 0 |
| holdout_0 | 2020-01-01 | 171,712 | 150,511 | 21,201 | 12.469077% | 0 |
| holdout_0 | 2023-01-01 | 297,404 | 261,338 | 36,066 | 12.488113% | 0 |
| holdout_1 | 2020-01-01 | 76,083 | 65,932 | 10,151 | 13.509462% | 0 |
| holdout_1 | 2023-01-01 | 148,071 | 129,002 | 19,069 | 14.044896% | 0 |

原权重在不允许域占12.47%–14.04%；六折允许域均非空，时钟unknown0。fold重叠，不能把1,386,540缓存行总数当独立经验。69year/292family/292product分组和16机械anchors均完成有限独审；未按分组结果挑年份或品种。

## 调研与判断

[Shimodaira2000](https://www.sciencedirect.com/science/article/pii/S0378375800001154)支持训练/使用分布与模型错定可能影响投影，也指出正确指定和有限样本下不保证删样本更优。[SPO作者代码](https://github.com/paulgrigas/SmartPredictThenOptimize)只借预测/决策区别，没有安装或使用其优化器。212方法审查允许盘点，不把数学可能性或份额当收益资格。

我的判断：值得**另冻一次单域loss实验**。理由不是样本“坏”，而是部署已严格排除这些动作，固定线性头仍将约八分之一的旧损失质量分配给此域；这提供明确且有足够支持的不同经验风险最小化问题。限制域也可能丢失有益泛化、增加方差；旧模型不是bug，没有证明这是此前失败原因。

## 下一次实验只允许的改变

- 候选保持原COMMON52、原firstexit stressR、原成熟时钟/两cutoff/两held、原scaler坐标、Ridge alpha1及既有156选择/157现金政策；q包保持关闭。
- 仅训练损失域变为原成熟域内D<K。允许子集保留旧权重相对比例，统一乘原W/允许W_A，固定总loss质量及有效alpha；不重算uniqueness、不重缩放X、不改变原目标或添加新信息。
- 这是训练loss分布干预，不是新alpha源、纯target比较、K重标或组合效用优化。旧130/156/157可作为该完整单干预的基准，不能将其叫同训练域的纯Y比较。
- 另冻217后最多六新模型，原模型/主与held控制选择及四现金均复用。完整主选择若完全相同，因原现金分配不使用score大小，则0新现金并关闭；有实际动作差异才最多四新资金账本。
- 固定收益/DD/四paired CI与两个held/unknown门；失败不换K、日期、family、正则化、scaler、目标、模型、阈值、止损或风险挽救。协议未冻结和精确source复审前不得actual。

## 反思与边界

- 开始/结束过拟合风险：是，历史择题风险；本盘点未解析收益或按成绩救参。
- 继续扩大本盘点价值：否，核心差异和守恒已证；不再扫描旧数据寻找原因。
- 继续一个固定domain-only反证价值：是，有限成本可直接检验当前使用域训练是否改善实际选择及现金，而不是继续弱标量试错。不能保证有效。
- 新/修改/删除金融参数与回测结果均0；权益、收益、DD、Sharpe、滑点、交易和胜率N/A。总体目标active，不加注/晋级/发布；普通阶段不追加根memory/back_log。

## 证据

- [protocol](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage213_training_domain_probe_protocol/protocol.json)
- [manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage214_training_domain_probe/actual_run1/manifest.json)
- [summary](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage214_training_domain_probe/actual_run1/summary.json)
- [review](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage215_training_domain_probe_review/review_receipt.json)
- [method](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage212_training_domain_target_design_review/decision.json)
- [mechanism](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage211_firstexit_K_structural_mechanism/mechanism_design.json)
