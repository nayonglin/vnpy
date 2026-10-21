# Stage085 自主数据迭代收束：增加8条研究标签，正式模型保持

- line_id：`futures_ai_monthly_pool_generalization`；整合时间：2026-10-20T23:32:01.507380+08:00。
- 本轮按用户授权连续推进，不等待逐阶段“继续”。未发布/交易/修改正式池；本次是研究数据可靠性迭代，不是alpha突破或正式A/B。
- 决策：**NO_PROMOTION**。模型跨年度增益仍未证实，不更换正式模型，不靠降低floor、扩learner或缩时段救数据。

## 调研与判断

[交易所历史时段问答](https://www.shfe.com.cn/content/lxjy/f18-3.html)、[上线与变更历史](https://www.shfe.com.cn/content/lxjy/main.html)、郑商所/大商所原始规则及原署名通知分别保存于066/069/070；[RQAlpha维护者时钟](https://github.com/ricequant/rqalpha/blob/master/rqalpha/data/trading_dates_mixin.py)及[changelog](https://github.com/ricequant/rqalpha/blob/master/CHANGELOG.rst)显示自然时刻映射与实际品种交易时段需分开。当前时段表不能整体倒推历史；早期夜盘有150分钟、240分钟等不同版本。暂未取到原始通知、回顾性资料与直接证据分层保留。

[scikit-learn评价说明](https://scikit-learn.org/stable/modules/calibration.html)与[维护者损失源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/metrics/_classification.py)支持固定概率损失核验，不支持把Brier小幅下降直接解释成校准、交易盈利或模型已有效。

判断：新数据确实能补监督信息；现阶段最有价值的是准确数据和标签，不是增加模型复杂度。本轮先固定证据/规则/样本范围，再读实际payload与回放，不按C2结果/收益选择provider。

## 实际结果

| 项目 | 上轮062 | 当前已审版本 |
|---|---:|---:|
| 原产品月格 | 19,698 | 19,698 |
| asof竞争成员 / 成熟成员 | 8,398 / 8,165 | 8,398 / 8,165 |
| 已知条件点值 | 4,762 | 4,767（+5） |
| 成熟未知 | 3,403 | 3,398 |
| 完整N下可识别研究标签 | 1,366 | 1,374（+8） |
| top / bottom | 685 / 681 | 688 / 686 |
| 有标签月份 | 155 | 155 |
| 原18新目标robust / 最大年度训练 | 480 / 440 | 486 / 442，仍小于612 |
| 新增模型fit / 最新研究评分品种 | — / 77 | 0 / 77（原060b冻结概率） |

1. 两条新后续分钟事件OI202301@2022-08-29、SH202605@2026-03-16通过统一输入审核和独立复核，各345分钟；原117与新增2的review和manifest分别精确SHA绑定。119输入回到同一冻结source后，5整窗变条件已知。原4762金额四项float64 bits和status/path/episodes全部不变。
2. 旧1366标签全同类、旧known rank区间只收窄，所有月N/角色/成熟时钟不变。未知没有删池或置0。2077个known零值仍无robust标签，收益两尾识别偏差保留。
3. 继续审计35个CZCE历史事件：80CSV约48.63MB和1SQLite投影，101组件=93无目标会话行、6分钟残缺、2日OHLC冲突，0合格。事前24文档支持/11额外证据缺口的分组未因结果变化，不缩375分钟成225分钟。
4. 其余SHFE/DCE27事件的27CSV约15.95MB先做精确日期/identity预检：22有行、5无行。20个额外证据缺口仅敏感性候选；不能把broad OHLC冲突一概称exact-grid拒绝。对7个doc候选另作必要条件证明：全部11provider链接中10个连superset分钟数都不足，余M一个恰345但源OHLC不同，故7事件均无法同时满足完整格+源OHLC。无provider拼接或额外假设注入。
5. 1036个会话缺失窗的控制依赖审计只有42个在首缺日不需要fresh，982仍需要，12管理本身未知。42不等于完整60日恢复；冻结正式逻辑也有前置target AM门控，故本轮不为少数首日机会修改observability合同或称旧代码bugfix。
6. 原060b的4738概率/81月和7个joblib全部冻结；仅接075的8个新识别target，成熟月等权重评fullN损失。2020—2026各年度Brier相对原训练prior改善区间仍跨0，正的稳健下界年度数0；2026只有6成熟月。这不是用1374标签重训、真实forward OOS或置信区间。

## 复核、修正与边界

- 210项本线测试全部通过，8份本轮主要独审收据P0/P1/P2均0。源074含22窗44次独立新旧回放；冻结评价078按每row直接枚举0/1复算；071/079独审重读实际raw payload。检查数不是独立金融样本。
- 058继承模板的Stage057-only文字由073独立erratum更正为旧057117+新0722，原receipt保留；权威append receipt精确绑定两父review。
- 077近似分钟常量改为实际系统时钟并保留初快照，三CSV逐字不变、0fit。辅助原18筛选最初错用token导致无效0统计已保留invalid，改为048实际`old18`并断言18域/3618行，080独审486/442；未影响源/标签/模型。
- 14个formal/current source SHA仍与005的current绑定相同。用户halfR/retry=False只在本训练源，C2=True；正式半R、池、策略、CTP、调度未动。生产身份缺项并未被研究目录补证或绕过。
- 新目标仍是单品种flat冷启动、固定2手、日open逻辑T00、静态经济、未来60源交易日累计episode unitR；不是原账户108特征或完整正式C9。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A，未运行资金组合绩效回测。

## 下一数据工作与反思

已生成793个精确epoch×交易日/价格状态需求，对应当前1926首C2缺口窗、83历史产品域。其余1472成熟未知另外保留。来源064状态只按073五known变化做子集，日期/原因和旧状态逐字段一致，084独审通过；未冒称又回放，未下载/调用外部API。793尚未全部历史session资格认证，也不保证取得数据即可恢复整段60日。

开始/结束新增按成绩选参过拟合：**否**；参数、来源范围与证据分层冻结，所有负结果保留。但历史开发、缺失非随机、静态费用和参考会话假设仍有风险。

继续补精确数据价值：**是**。继续重扫这批已审缓存、堆复杂模型或放松门槛价值：**否**。下一轮应基于精确缺口取得真正新增资料或新未来观察，维持完整N和独立复核；不会因想扩池就直接替换正式模型。

- 当前目标：`outputs/stage075_targets_followup_augmented/`。
- 当前源：`outputs/stage073_union_augmented_source/`。
- 冻结评价：`outputs/stage077_frozen_score_reassessment/`。
- 精确数据需求：`outputs/stage083_next_exact_minute_intake/`。
- 闭环与全部资产SHA：`outputs/stage085_final_iteration_closure/`。
