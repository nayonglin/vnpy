# Stage267 严格月度样本统计工具边界验收

- line_id：`futures_trend_rollover_shape_same_volume`
- 记录时间：2026-10-17 19:57 CST；工作区 `/Users/mac/Desktop/fian`，分支 `codex/ai-training-data-expansion`。
- 阶段性质：独立实现月度样本统计工具；真实策略 source 由 root 单独构建和复核，本 agent 不回放、不训练、不改生产、Stage266、LINE/registry。
- 是否重要突破：工程合同落实，不是 alpha、训练或实盘资格突破。不触发 A/B。

## 调研与判断

- 先读取 registry、LINE、`stage262_ai_sample_contract.py`、原月度入口及 Stage263 的扩样诊断/失败记录。
- [Microsoft Qlib RollingGen 源码](https://github.com/microsoft/qlib/blob/main/qlib/workflow/task/gen.py)明确用 `trunc_days` 截断防未来信息泄漏；[scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)强调按时间顺序划分。这里使用真实来源交易日与 `label_end`，不照搬按行 gap。
- 判断：保留原 108 列计算函数，但原未来收益函数允许 30 日 partial 标签，不能当作完整 60 日目标。缺覆盖不能用原填零逻辑宣称有效；没有来源排序信息的全零/全同月份须单列。

## 本次变更与冻结

- 新增 `tools/stage267_build_monthly_samples.py`，SHA256 `e7932ba5b0669c80a1449da63487e3be909792d62571d3427880e959f48b2ccf`。
- 新增 `tools/test_stage267_build_monthly_samples.py`，SHA256 `0de9bae4553a17b68f6624beeb9d38de5b4616231f9261205e3b1581173eab9e`。
- 无修改/删除原策略、清洗器、读取器、Stage262/263/266。经济参数变更 0。
- CLI：`--positions --entries --coverage --calendar --output-dir`，可选 `--baseline-samples --asof`。调用原 `build_product_daily/add_rolling_features`，临时路径在 finally 恢复；原月度代码 SHA 与 Stage262 窗口代码 SHA 均固定，108 列以 Stage263 冻结清单核对并输出新特征合同。

## 严格合同

1. 固定原 18 产品，无自动扩池或产品别名。position 经济列必须存在且有限；相同 `(date,vt_symbol)` 不得重复计账。coverage 布尔须显式 True/False/1/0，重复键拒绝，observed=true 必须有对应源 PNL 产品日。
2. 以显式 source_calendar 决定真正月末，不把截至 10/14 的不完整月份当月末。最后被截断的日历月不获认证。
3. 历史为含 eval 当日的 120 个来源交易日，标签为 eval 后第 1 至第 60 个来源交易日；保留 `feature_start/end`、`label_start/end`、真实覆盖计数与完整标记。60 日 target 重新严格求和，30–59 日 legacy partial 值仅作审计，不能作为有效标签。
4. 对产品逐行资格过滤后重算截面，至少 8 个产品。完整数据层 qualified 与有排序信息层 informative 分开：全零、全同非零月份分别计数，信息层剔除；这些月份 qualified 的 rank/target/weight 保持空值，不造可训练标签。
5. 原 CSV 开盘 OI 与 `legacy108_row_usable` 不是月度 108 的必要条件，工具不要求这些字段。月度特征来自策略 PNL 与候选/信号统计，不直接读取开盘 OI。
6. 同一新 source 下统计全历史、eval>=2020、eval<2020 的 qualified/informative 以及同 asof 成熟样本，不重新回放、不重置窗口、不改变共同特征/标签/权重。与 Stage263 只比较精确产品月键的新增/丢失及年份分布，不能称扩样因果效果。

## 测试与独立复核

- 已先观测缺实现的 RED，再实现；新增重复 position PNL 测试先确认失败，随后增加 guard；新增同源时间拆分要求亦先失败再实现。
- 最终 20 项边界测试通过，包括：108 列不变、120/60 边界、59 日 partial 无效、排除 eval 和第 61 日、缺历史/未来覆盖、过滤后截面不足 8、全零/常数目标、显式 False、重复 coverage/日历/PnL、固定 18、无开盘 OI、未来改动不污染 eval 日 108 特征、文件端到端、缺 turnover 拒绝、空候选文件不造事件、同源时间拆分。
- 空候选文件原函数只返回键列；工具只补与原非空候选文件无事件日相同的 0/neutral1 聚合 schema，不伪造候选或经济观察。
- 测试只生成临时合成 CSV、计算原特征并计数；无模型拟合、行情请求、财务回放或主库写入。合成 fixture 的 72 行/4 月只供边界检查，不是实际市场样本结果。
- root 指派 DCE agent 独立 review；其发现的重复 PNL 防护缺项已用最终 guard 修复，当前最终版供独立复测。真实 source 的小 census 由 root 在本版冻结后重新生成到新目录，不能将旧执行版冒充新 SHA。

## 输出与使用

- 工具验证收据：`outputs/stage267_monthly_tool_validation/tool_validation.json`，测试日志 `boundary_tests.log`。
- 真实执行将生成 `all_sample_contract.csv`、`qualified_samples.csv`、`informative_samples.csv`、`monthly_counts.csv`、`annual_sample_counts.csv`、`feature_contract.json`、`sample_summary.json`；输入/原函数/窗口代码/特征清单/产物 SHA 与数值运行时均保留。
- 本记录只接受工具边界，真实最终样本数量以 root 的最终目录与独立复核为准。本 agent 未自动运行真实 census；金融回放由 root 的已授权独立 source 任务记录。
- root 随后通知最终小 census 已完成于 `outputs/stage267_monthly_samples_final`，并 fresh 重跑 20 测试通过；实现继续冻结，独立结果审查由 DCE agent 负责，本记录不冒称本 agent 已独立复验该真实结果。
- 期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率不适用。本 agent 财务回放/模型拟合/订单/主库写入均 0。

## 反思

- 运行前/后过拟合判断：否。固定 108/120/60 与截面>=8，未依据收益、早期信息数量或最终样本数量调整门槛；保留全零/全同月份，而非隐藏它们。
- 运行前/后继续价值判断：是。真实历史覆盖改善后需要重新区分数据完整性、标签成熟度和排序信息；月份之间 60 日标签仍重叠，不能把行数当独立样本量。
- 后验上游 pairwise/固定 Floor35 source 不因此成为 PIT/OOS 或可实盘证据。后续若训练，应另外冻结模型实验和检验合同；本阶段不执行模型、不重跑 Stage263。
- 不改 LINE/registry，由 root 合并登记本记录。
