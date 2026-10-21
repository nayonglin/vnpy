# Stage154：用户拓宽目标后的研究brief与执行次序

line_id=futures_trend_triple_screen（沿用既有记录身份收口，不迁移旧材料）；2026-10-18 10:56 CST；本次是目标澄清和有界数据接合，不是新策略实现或回测。已读registry、152盘点和既有失败摘要，使用brainstorming理解新目标；用户已授权自主设计/持续研究，沿该授权推进，不重复形式性审批。

用户目标现为：不断迭代策略，找到更高收益和更低回撤；规则、AI特征和其他方向均可；希望AI识别超高质量信号，用极小止损增加投注博取高收益。原三重滤网不再是总目标的强制形状，旧EMA只作为已冻结、尚未完成金融对照的入场假说，不因已投入工程而优先于更有价值的AI数据证据。

## 可证伪的工作口径

1. 先在固定入口/退出/原风险和成本下证明“识别质量”的真实增量，再分别研究止损与加注。质量评价关注成本后净R分布、左尾/右尾机会成本及跨日期/产品稳定性；不能把高胜率、极窄分母或更大名义仓位等同高质量。
2. 窄止损是独立执行假说：原始成交路径、未成交、噪声止损、跳空、费用/R和更大q后的可成交量都会变。加注在优势和不确定性有证据后才有可检验意义，账户收益/回撤最终由真实组合现金与保证金检验，独立事件PnL不可直接相加。
3. 152确认现存005原生900事件/682日期/19产品、两A各886候选同一事件键集合；不能把两臂视作1772独立样本。318闭合订单根仍非跨roll统一经济mother；未选路径、成熟时刻与风险分母缺失。旧全市场57已知路径缺文件，尚不直接训练。
4. 已派155完成有界的全outer事件去向接合：005潜在事件↔两A候选↔可唯一识别的实际初开/时钟；保留未选/未成/未成熟/未知与歧义状态，不生成任何收益或质量label，不跑新账户。其后再选择一个预先固定的小样本事件路径合同，检查真实native退出/成本/重试/换月；独立反事实环境须披露，不假称未入选的原组合收益可唯一还原。
5. 已看过多次的2020—2026不改名为全新未来OOS。未来拟合只能用u前完全成熟标签，按实际标签区间purge/embargo并以产品/日期/母交易归组；新数据/新信息优势与单次冻结消融应先于换复杂模型。既有Stage236、二期015、连续预算与score-only加风险的反证保留。

## 网页与GitHub调研及判断

本轮已实际读[Risk-Constrained Kelly Gambling](https://web.stanford.edu/~boyd/papers/kelly.html)及作者[cvxgrp/kelly_code](https://github.com/cvxgrp/kelly_code)：论文研究分布假设下增长与回撤概率约束。已实际读[Distributional Robust Kelly Gambling](https://web.stanford.edu/~boyd/papers/robust_kelly.html)及作者[代码](https://github.com/QingyunSun/Distributional-Robust-Kelly-Gambling)：将分布不确定性纳入下注问题。判断：可参考“估计误差和生存约束进入投注”的思想，不能据此证明本策略有预测优势或直接套最优杠杆；未下载、安装或运行外部代码。

官方[mlfinlab cross_validation.py](https://github.com/hudson-and-thames/mlfinlab/blob/master/mlfinlab/cross_validation/cross_validation.py)当前页面多函数主体仅pass，不能称现成完整可运行工具；只参考其标签区间purge合同，不盲目依赖第三方splitter或copy训练架构。

## 当前状态与反思

149/150集中修复、153实际prepare已通过，但新增金融/训练仍0，EMA绩效N/A。155正在生成事件身份/去向证据，原收益更高且回撤更低的目标仍完整保留，financial_ready=false、production_qualified=false。

开始/结束新增过拟合否：本轮先核数据可识别性与已有反证，没有按收益筛样本或调参数；“罕见高分+极窄stop+重注”若直接联合扫描会放大过拟合。继续价值是：小而真实的全机会身份/路径证据，优先于无成熟标签就训练或纯放大风险。目标active，未找到新alpha，不承诺高收益可以实现。
