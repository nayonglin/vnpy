# Stage004B 冻结产物只读分析合同

- 时间：2026-09-05 19:50 CST
- line_id：`futures_trend_xgboost_formal_signal_marginal_utility_v4`
- 当前Stage004原始A已完成、A0/S待完成；不修改原runner、测试、冻结输入、claim或产物。
- Reviewer不启动；本次是读取层修复，不是新候选，不是收益优化。

## 已定位的读取差异

1. A根事件CSV与Stage003文件SHA完全相同，均为`16d2356b33c49b1dc7d893d988d3292fe440aba46358240d8e6523baab33e611`；一侧round_trip、一侧默认浮点解析导致stop_distance_pct唯一值142/116，从而触发qualification字典比较失败。两侧同一解析模式时逐值差0、原10门均通过。
2. 正式build_trades_df序列化Direction/Offset.value，实际为中文多/空、开/平；旧离线终点函数误按Long/Short、Open匹配。A已有真实纸浆开平仓，不能把枚举解析失败称为没有成交。

## 唯一修复边界

- 根特征统一采用原Stage003默认pandas解析；其他账户、交易表保留round_trip精度。额外要求A/Stage003特征原始bytes完全相同。
- 交易枚举按已读取的正式`vnpy/trader/constant.py`原始中文值及本机Direction/Offset.value适配到旧函数内部英文值；正式worker的隔离环境没有父进程英文gettext翻译，故不能只使用父进程枚举。仅接受这两组已证实的值，未知枚举报错，不静默过滤。
- 在内存中适配，绝不重写CSV，不更改目标、事件区间、收益/回撤公式、阈值和原策略。
- 只消费Stage004同一批A/A0/S产物；只在原汇总因已知浮点解析异常失败、三个worker均完整成功且原输入仍完全匹配时执行。
- 复核三个worker所有CSV文件身份、零敏感计数、A0零干预、S恰好一次干预；A/A0七类文件要求bytes相同，曲线重算指标必须等于worker记录。
- 重用原Stage004前缀比较、单事件检查、终点/标签公式；不新增回测，不按S收益选择方向或事件。
- 保存分析源文件、回执、CSV、原claim/freeze等完整文件身份，保留原Stage004失败记录，不改写成原runner通过。

## 反思与后续

- 过拟合：否，本修复只处理已证实的浮点解析和枚举接口差异，不调策略、不按收益修门；历史小样本过拟合风险仍高。
- 继续价值：是，复用已完成的高成本回放，避免因纯读取问题重复计算。
- 成功只说明一个固定事件的标签机制成立，不构成有价值的XGBoost版本，不启动reviewer。
- 若发现其他身份、干预或账户问题，不绕过该检查，不重跑或覆盖本批结果。
