# Stage676 2015 延展的独立完整审查

- line_id：`futures_full_market_long_signal_ai`
- 当前模式：现有 COMMON52+统一 K 参考版的历史延展；独立结果审查。
- 记录时间：2026-10-21 14:43 CST。
- 工作区：`/Users/mac/Desktop/fian`；解释器 `.py311/bin/python -B`。
- 阶段性质：只读算术、时间与覆盖审查；不实施新策略。
- 是否重要突破：否。
- 是否触发 A/B：否；沿已冻结 Stage673 原参数复现更早连续账户，不提出候选或晋级。

## 外部调研与判断

- 延展合同已在新结果前由 Stage673 引用 [scikit-learn 时序划分官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html) 与 [官方 GitHub 实现](https://github.com/scikit-learn/scikit-learn/blob/main/sklearn/model_selection/_split.py)。本阶段不开展新的 alpha 选题或参数搜索。
- 独审判断：时间先后本身不足以防止跨截止日的标签泄漏，必须同时限制机会时间 `u_date` 与标签可知时间 `label_known_date`。2015 前自身成熟 closed 条件训练可复验，但不是无删失偏差、全历史首发 PIT 或独立未见 OOS 证明。
- 20 日特征使用平均 TR20，标签/期限信息的 N 使用 Wilder20；COMMON 两个原风险量纲仍为 2N，目标为 `.25N` 压力净 R。这是原冻结合同的差异，未顺手改成新参数。

## 本次变更

- 新增脚本：`tools/stage676_2015_independent_review.py` 与 `tools/test_stage676_2015_independent_review.py`。
- 修改/删除策略、原脚本和参数：无。
- 新增审查参数：唯一 `main2015`／固定 2015、2020、2023 三段模型归属；仅限本次审查入口授权。
- 研究模型与资金账户由 Stage675 产生；本审查不 fit、不解正规方程、不回放策略、不读旧四账、不审旧模型或 held 模型，不做 SQL、下载或旧原始规范重审。
- 首次四个合成边界用例因审查器未实现呈 RED；实现后发现工具目录导入路径缺失，修复审查器后 4/4 GREEN（0.024 秒）。后续实际适配遵照 root 要求未扩大 fixture 或旧 suite 重跑；唯一完整实际审查通过全部真实合同与账本。

## 回测与审查参数

- 数据区间：原 source calendar 首个不早于 `2015-01-01` 的交易日到 `2026-10-16`，共 2,862 个账户日；不是截至 2026-10-21。
- 本金：1,000,000；2015 起各一条连续 base／stress 账户，无年度重置、旧曲线拼接或旧控制重跑。
- 原参数：初始止损 `.25N`，单族计划风险 `0.25%`、总计划风险 `2%`、缓冲保证金上限 `25%`、保证金缓冲 `1.1`、D-1 成交量 `1%` 的往返容量、整数手数与原 base／stress 成本。
- 选择：完整母域保留，原正分选择、同分次序、普通/F 家族优先，D<K；K 为合约月前月首个 source 日。
- 训练：仅 `u_action_eligible=1`、`closed_complete_bar_model`、有限压力目标，且 u、known 均严格早于 2015。只新增一个 Ridge1 main2015；原 main2020／main2023 分数逐值复用。

## 完整独审结果

- 唯一审查 session：`66144`；终态 chunk：`5c5e01`；退出码 0，耗时 168.206791792 秒。
- C/I/M：0/0/0；研究算术接受；0 新 fit／正规方程求解／策略资金回放／SQL／旧账重审／held 模型。
- 模型：91,804 训练行、1,192 日、50 族、30,786 family-u union 组；最大 u `2014-12-30`，最大 known `2014-12-31`。
- 新早段前向分数 345,321 行；完整前向 1,312,061 action、280,476 母行、5,246 所选信号。三段 action 行数 345,321／366,634／600,106，所选 881／2,613／1,752；2020+ 与原 Stage156 的 161,014 母行选择及分数精确重合。
- 保存训练身份、union 权重、train-only scaler、joblib／portable 系数、LHS／RHS 与全部新预测一致。正规方程仅核 `LHS @ beta = RHS`，最大残差 1.3869794202e-09；其余数值核验最大差 1.16415321827e-10。
- K、普通/F、逐信号 native 值和有效 lifecycle 全核；2015 初始账户空仓，不回填 2014 intent；完整旧母域持续决定 canonical anchor。
- 两账合计 6,643 fills、5,724 账户日、9,006 持仓日、10,508 预算／拒绝记录；2,280 个含零 95 族年度格；宽 CSV 的两条 equity 与含初始本金的 drawdown 逐日一致。

| 指标 | base | stress |
| --- | ---: | ---: |
| 期末权益 | 3,213,991.969 | 2,219,976.268 |
| 总收益 | 221.399196900% | 121.997626800% |
| 最大回撤 | -13.602533368% | -11.781810272% |
| Sharpe | 0.864193549 | 0.849097110 |
| 总费用 | 118,438.031 | 156,663.732 |
| 总滑点（已在成交价中） | 332,605.043091 | 395,693.616330 |
| 已闭合交易 | 1,850 | 1,462 |
| 已闭合净胜率 | 12.108108% | 12.448700% |
| fills | 3,703 | 2,940 |
| 历史 stale 账户日 | 9 | 6 |
| 期末开放 / stale 仓 | 2 / 0 | 2 / 0 |
| 容量未知 roots | 50 | 30 |
| 入场执行未知 | 5 | 2 |

## 限制与结论

- 接受新增连续账、保存分数、选择与账本的算术一致性。低净胜率与趋势右尾并存，不能仅因胜率低判定记账错误。
- 两账 `execution_unknown=true`；1% 日线容量、历史缺价、开放仓位及静态费用／保证金快照限制保留。期末 0 stale 不抹除历史缺价或容量未知，不证明可成交、实时 broker 资格或 `.25N` 通用损失上限。
- 早年自然覆盖小于现有完整目录；保留 98 品种／95 族母域不等于每个品种自 2015 同时上市且可交易。未新增数据、不造早年合约。
- 无新 bootstrap、promotion gate、正式启用、生产资格、加注资格或目标完成声明。

## 输出文件

- 源码 GO：`outputs/stage676_2015_extension_review/source_GO.json`，SHA `732a6deb1131df53d6cc78c3e08e1d4fda0029af543e622341c0337984ad66c9`。
- 真实完整 receipt：`outputs/stage676_2015_extension_review/actual_run1/review_receipt.json`，16,475 bytes，SHA `f957165d4d7058efbde922ca6f2b4ed56eb4d9dac3bfe0ec17f2be2fa5e2b8b7`。
- 独审终态：`outputs/stage676_2015_extension_review/actual_run1/actual_terminal.json`。
- 分阶段证据：同目录 `new_model_review.json`、`selection_review.json`、`signals_review.json`、`book_base.json`、`book_stress.json`。

## 过拟合反思

- 运行前：新增收益后调参过拟合否；仅核既定版本的更早时期与记账，有同史择题和反复研究的适应性风险。
- 运行后：未按结果改变模型、特征、目标、K、年份、品种、止损、风险或成本；因此新增调参过拟合否。2015 延展属于条件历史检验，不自动转成真正未见 OOS。

## 继续价值反思

- 运行前：有价值，可揭示 2020 起点未覆盖的早期周期及覆盖差异。
- 运行后：本次有价值且已完成；不需要重复本模型／本账户或扫描早期年份来救成绩。继续全市场高质量做多研究仍有价值，需事前实质不同信息与未见观察。

## 合入建议

- 本阶段仅写独立唯一 stage，未改 `LINE.md`／`research/registry.md`／根 `memory.md`／`back_log.md`；由 root 按线合入。
- TODO：root 展示标准 PNG／HTML 连续资金曲线，记录此审查 receipt；保留全部未知与原关闭研究结论，不正式晋级。
