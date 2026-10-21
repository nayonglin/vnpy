# Stage062 自主连续迭代结果：数据扩充有效，模型不晋级

- 整合时间：2026-10-20T22:47+08:00；重要突破：数据与可复现工程里程碑，非alpha突破。
- 用户已明确“你一直继续吧，不要一直打断”，本轮连续完成源重建、全域输入、训练、独审、已有分钟复用、再训练和同集比较，各阶段不等待“继续”。正式交易/发布闸门仍按原约束保持。
- 最终决策：**NO_PROMOTION**。正式模型、池、止损、订单、CTP和定时任务均未变。14个既有formal/current source SHA与Stage005绑定一致；用户仅授权本次训练源halfR与耦合retry=False，C2始终保留。

## 调研与判断

[scikit-learn泄漏说明](https://scikit-learn.org/stable/common_pitfalls.html)与[维护者时间切分源码](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)支持训练内拟合变换和明确的时序隔离；本项目按源label_end而非panel行数隔离未来60日目标。[Backtrader执行文档](https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/)及[vn.py维护者源码](https://github.com/vnpy/vnpy_portfoliostrategy/blob/main/vnpy_portfoliostrategy/backtesting.py)提供显式bar执行假设参考，不证明本数据真实tick/session或盈利。

判断：新增资料确实增加了监督信息，但样本数、工程覆盖和模型优势是不同问题。不能从更多行直接推出更强预测，更不能把本研究分数当交易胜率。

## 本轮实际完成

| 项目 | 补分钟前 | 补分钟后 |
|---|---:|---:|
| 保留的产品月格 | 19,698 | 19,698 |
| asof竞争候选 | 8,398 | 8,398 |
| 成熟候选 | 8,165 | 8,165 |
| 已识别条件参考点值 | 4,508 | 4,762（+254） |
| 完整N下可识别前/后半标签 | 1,026 | 1,366（+340） |
| 正/负标签 | 519 / 507 | 685 / 681 |
| 有robust标签的月份 | 137 | 155 |
| 满足测试工程floor且有拟合的年度块 | 2024/2025 | 2020/2022/2023/2024/2025 |
| 固定年度模型数 | 7 | 7 |
| 全U预测行 / 月份 | 4,738 / 81 | 4,738 / 81 |
| 最新研究eval / 品种数 | 2026-09-30 / 77 | 2026-09-30 / 77 |

1. 98个历史产品域与201个月原行全部保留；fixed fu与_F不参与竞争，不能把98个历史域称为当下98个可交易品种。角色只按asof决定，未来未知留在每月N。
2. 新source是月末flat冷启动、未来60源交易日close MTM的累计episode unit-R：普通fresh重新固定R，roll沿用episode分母，固定2手研究数量，halfR/retry关，C2保留。排除了原账户资金/槽位/组合heat等路径。这不是旧正式账户source或原108特征的追加。
3. 冻结12项方向对称AM41技术特征与StandardScaler+L2 LogisticRegression(C=.20)。每年label_end严格早于cutoff，scaler只训练fit，不扫C、窗口、特征或TopN。原18在同一新source总robust标签480，年度训练最多440，均低于612同一floor，因此不fit，不能声称胜过旧18或正式108。
4. 052独立提取2209个成熟首C2未知窗口，落到910个精确epoch×source_trade_date；其中34窗held并非当日代表、63窗涉及roll新开。无猜合约、自然日替代或09:00伪造。
5. 既有reference grid明确支持的132需求统一核428小缓存（约332MB）与SQLite；117需求通过输入审核，128来源成员去重成117条数据路径，所有冲突/拒绝与778范围外需求保留。未读取221MB大CSV，无下载，无provider拼接或按收益择源。
6. 117条参考路径接回同一source后，全19,698身份/asof/角色/时钟不变，原4,508点值四项float64 bits全部不变；287个首阻塞发生变化，其中254整窗得到条件点值，33仍因后续缺日/C2/signedR未知。未把它们归零或删除。
7. 原1,026个robust类别全部保留同类，旧known的排名界只收窄；新增340标签不是删未知后的重排。

## 模型结果

同一全N下相对同训练标签prior的Brier改进界（prior_loss-model_loss）所有年度下界都不大于0。数据扩充前后模型再统一用**同一新标签识别集**比较，old_model_loss-new_model_loss如下；均不是置信区间、R或账户收益。

| 年 | 扩证模型相对旧模型的全N Brier改进界 |
|---|---|
| 2020 | [0, 0]（训练结束日早于2020，未受2020+分钟增量影响） |
| 2021 | [-0.007251, 0.006961] |
| 2022 | [-0.011004, 0.011655] |
| 2023 | [-0.015345, 0.015747] |
| 2024 | [-0.017166, 0.017110] |
| 2025 | [-0.021562, 0.018825] |
| 2026 | [-0.030070, 0.026383]（仅6成熟月） |

- 所有改进界均未证实稳健提升。known-only在2021—2024略好，2025/2026反为负，不能宣传跨周期稳定改善。
- 5块工程覆盖满足讨论的最低数据跨度，`test_coverage_block_gate_pass=True`仅这一含义；`cross_cycle_predictive_validated=False`，不能称模型泛化通过。源策略开发已看过历史年份，这仍是历史pseudo-OOS。
- 4,762已知值中2,077为零，但1,366robust标签没有零值，仍为收益正负两尾识别样本；不能校准全U适应性概率。未来缺失非随机假设未成立，不能用known-only AUC/精度代替全N证据。
- 非重叠60日的24个固定子窗口也独立核验；不能把行数当独立经验。

## 证据与复现

- 源/全域/标签：Stage043独审303,199检查；首轮特征模型Stage049 56,700检查。
- 精确需求Stage053 63,364检查；分钟输入Stage057 8,377检查；扩证源/标签Stage059 139,569检查。
- 最终模型与同集比较Stage061 23,179检查。上述各阶段0失败，无剩余P0/P1/P2。检查数是工程核验次数，不是独立金融样本数。
- 本线完整181项测试通过；未因最终未改善增加模型或降低floor。
- 共28次市场model fit：两个数据版本各7个固定年度模型，每个再作一次只规范资产/语义字段的字节复现。不是28组参数搜索；每组复现6份CSV、7个joblib逐字相同。
- 明示四类AI研究资产、reproducibility_required、输入/代码/源链review SHA、包版本及source快照；未git add/commit/push或发布正式物料。
- 主产物：`outputs/stage060_targets_augmented/`、`outputs/stage060b_final_model_diagnostic/`、`outputs/stage060b_paired_data_expansion_comparison/`；源证据`outputs/stage058_minute_augmented_source/`，独审`outputs/stage059_independent_augmented_source_review/`和`outputs/stage061_independent_model_expansion_review/`。
- 旧run、修复前输入/收据、失败pilot与勘误均保留。部分源码是run后仍匹配hash的捕获或明确标注的反向重构，不冒称pre-run捕获。

## 参数、财务口径与后续

- 新增：12特征研究合同、完整源/数据证据与固定模型诊断。修改：仅本研究源halfR/retry=False（用户授权）及分钟证据覆盖；正式策略/费用/风险参数未改。删除参数/结果：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：均不适用。没有运行账户绩效回测，不能把累计unit-R转为资金曲线或编造这些指标。
- 正式AI仍有原108字段合同，本研究12字段模型不能直接替换；正式A/C和晋级还受生产身份缺项及未来正式验证约束。本次不请求发布或交易确认，因为没有满足晋级的结果。
- 开始/结束新增按成绩选参过拟合：否；参数/输入规则先冻结，未因失败换C、复杂learner、窗口或名单。上游历史开发、收益两尾选择、静态经济与参考会话偏差仍在，不能声称无过拟合风险。
- 继续复杂模型搜索价值：当前否。继续统一数据可识别性价值：是。本轮已将可可靠复用的首阻塞资料落实；下一优先级是3,403成熟未知的来源/历史session与未来日级输入，不按收益挑事件，不把wrong-side signedR或tick不合规强行修成交易。
