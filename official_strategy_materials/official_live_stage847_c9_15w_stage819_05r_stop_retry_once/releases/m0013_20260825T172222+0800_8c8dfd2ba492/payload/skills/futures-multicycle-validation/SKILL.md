---
name: futures-multicycle-validation
description: Use when a vn.py futures candidate needs fixed multicycle validation against the active official baseline, including full-period and independent 1/2/3-year January and June starts, five standard images, and a promotion verdict. Do not use for single-window, attribution-only, or existing-curve requests.
---

# 期货多周期验证

## 基线预检

**REQUIRED SUB-SKILL:** 涉及正式候选比较时使用 `version-ab-experiment`。

构造任何 arm 前，读取活动 `official_strategy_materials/CURRENT.json` 并运行 `assert_official_checkout_matches_active_material()`。A 组声明必须与返回的 `strategy_version`、`ruleset_version`、`material_release_id`、`source_commit` 完全一致，并与远端 master、稳定生产身份一致；任一不匹配立即停止，不运行回测。Stage78/Stage372 只有用户明确点名时才作为历史对照，不能替代 A。

提交冻结的数据截止日、arms、成本、窗口、指标和门禁后才能生成结果。运行前明确过拟合和继续价值判断。

## 固定窗口

| 组别 | 必需的独立运行 |
| --- | --- |
| 全周期 | 从共同有效起点到冻结截止日的一次 A/候选比较 |
| 1 年 | 每个能完整覆盖 1 年的 1 月 1 日和 6 月 1 日起点 |
| 2 年 | 每个能完整覆盖 2 年的 1 月 1 日和 6 月 1 日起点 |
| 3 年 | 每个能完整覆盖 3 年的 1 月 1 日和 6 月 1 日起点 |

每个周期至少要有一个完整 1 月起点和一个完整 6 月起点，否则返回 `insufficient_multicycle_coverage`。

每个窗口必须重新创建引擎、资金、持仓和账户状态。warm-up 只能使用点时可见历史；禁止把全周期曲线切片冒充独立窗口。临近完整的终端窗口可以用 `*` 展示，但只观察、不投票。

每窗记录期末权益、收益、最大回撤、Sharpe、滑点、交易数、胜率、生存状态和适用的保证金门禁。缺失、非有限、重复或 arm/window 不匹配都 fail closed。

## 简单运行安全

1. 先运行并验证全周期所有 arms，再开始 1/2/3 年窗口。
2. 全周期 IDs、日期、计数和状态必须完全一致；CSV 浮点采用有文档的尺度容差或 canonical CSV round trip，并测试“序列化微扰通过、实质漂移失败”。
3. 每个 arm-window 成功后写临时 checkpoint，键包含冻结 commit、数据截止、arm 和窗口。
4. 重试只复用键和文件都重新校验通过的 checkpoint。
5. 最终发布保持原子性；checkpoint 只是续跑缓存，不是最终报告。
6. 若出现漏窗、arm 计数不一致或摘要漂移，先定位并修复生成流程，再完整重验；不得把失败的首次结果当成最终多周期报告。

## 固定报告格式

先给晋级结论，再按以下顺序输出：

1. 已验证的活动正式 A 身份与候选身份。
2. 全周期指标对比。
3. 1/2/3 年表格；每个周期都分别给 `combined`、`January`、`June`。
4. 最弱收益、回撤、Sharpe、成本和生存窗口。
5. 五张图片，严格按此顺序：
   - 全周期正式版与候选资金曲线；
   - 1 年独立滚动资金曲线网格；
   - 2 年独立滚动资金曲线网格；
   - 3 年独立滚动资金曲线网格；
   - 多周期聚合摘要。
6. 结果 CSV、decision 和中文 stage 记录链接。
7. reviewer/tests，以及 production/CTP/order 的明确安全边界。
8. 运行前后过拟合与继续价值判断。

所有网格按年份排序，同年先 1 月、后 6 月。标题显示精确起始日和周期。颜色、图例、单位保持一致，`*` 只解释一次。

## 决策纪律

全周期或单一周期的优势不能覆盖任何失败的周期、1 月 cohort 或 6 月 cohort。只用完整窗口投票。结果出来后不得通过改变起点、周期、品种、参数、阈值或图表筛选来救失败。

任何产生回测结果的多周期运行必须按仓库 AGENTS 要求写当前研究线 stage 文件，并拉独立 reviewer；无回测时明确写未运行。

## 常见错误

| 错误格式 | 必需格式 |
| --- | --- |
| 最近 1/2/3 年 trailing snapshot | 每年 1 月与 6 月独立冷启动 |
| 每月起点 | 固定半年起点 |
| 每周期只有 combined | combined + January + June |
| 全曲线切片 | 每窗 fresh engine |
| 每次实验自定义图 | 固定五图和顺序 |
| 滚动窗全跑完才查身份 | 全周期前先做活动基线预检 |
| 完成窗只留内存 | 校验后 checkpoint 并可恢复 |
