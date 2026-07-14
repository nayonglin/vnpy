# Stage007 最终独立复核与治理收口

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 记录时间：`2026-07-14 01:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：跨阶段最终决策
- 是否重要突破：是，获得一个数值通过但不可直接晋级的冻结探索规格
- 是否触发A/B：否；本阶段只做独立复核与治理决策

## 最终证据

- Stage003 reviewer `Halley / 019f5c7c-8bb4-7d30-a2fb-e33a5308e797`：`P0/P1/P2/P3=0/0/3/3`，数值可信度 `99.9%`；2021 收益保留 `62.9423%`，硬失败并关闭。
- Stage004 reviewer `Locke / 019f5c80-34af-7800-b361-588720093ce6`：`P0/P1/P2/P3=0/1/2/2`，数值可信度 `99.7%`；唯一 P1 为预声明治理污染，不改变当前数值。
- Stage004 四锚点收益保留 `87.4239%/70.4270%/138.4318%/125.0682%`，回撤改善 `14.1584/13.3491/5.1110/11.5933pp`，数值硬门全部通过。
- 联合测试 `.py311/bin/python -m pytest -q research/lines/futures_trend_tight_stop_quality_sizing/tests`：`42 passed`；`py_compile`、`git diff --check` 与现有 manifest 哈希复核通过。

## 最终决策

- 决策：`CLOSE_HISTORICAL_TUNING_KEEP_STAGE004_FROZEN_EXPLORATORY_NO_ORDER_SHADOW_ONLY`。
- Stage004 不晋级正式版，也不进入可报单 shadow；正式策略、AI 月池、CTP、邮件和 launchd 均不变。
- 允许的唯一后续是补齐治理记录和依赖闭包后，以当前代码、参数和输入哈希做无报单前瞻 shadow；禁止修改阈值、权重、年份、品种或起点。
- 不扩逐半年回测。四锚点高度重叠，继续增加重叠起点只会制造虚假样本量，不能消除 Stage004 的后验选择偏差。

## 统计口径说明

- 本线没有输出统一闭合机会胜率；不使用非零日胜率冒充交易胜率。
- Stage005 旧结果和 Stage006 未完成结果均不进入最终统计。
- 回测期末权益、收益、最大回撤、Sharpe、滑点和交易数以 Stage003/004 修复后 summary 为唯一有效来源。

## 过拟合反思

- 运行前判断：高风险。
- 运行后判断：是，高风险。
- 原因：阈值来自同一历史样本，Stage004 又由错误中间结果启发，四锚点共享大量交易；数值守恒只能证明“算对了”，不能证明“样本外有效”。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：历史优化无继续价值；无报单前瞻观察有有限价值。
- 原因：水下降风险是透明、可证伪的机制，但只有新的未见数据能增加可信度。

