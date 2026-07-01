# Stage002 重建版 C9/15w 目标基准审计

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:06 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读目标拆解与基准缺口审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz、Ooi、Pedersen，`Time Series Momentum`：跨资产期货趋势的价值来自持久趋势与横跨市场的机会集合，不能轻易砍右尾。
  - Hurst、Ooi、Pedersen，`A Century of Evidence on Trend-Following Investing`：趋势跟随长期有效的核心是跨周期、跨市场和右尾分散化。
  - Bailey、Lopez de Prado，`Deflated Sharpe Ratio` 与 PBO/CSCV 框架：多候选、多参数和 winner-picking 会显著放大虚假发现概率。
- 我的判断：用户目标中“每年正收益 + 收益保留 80% + 加鸡蛋 + AI 优化 + 高质量信号加风险”不能直接写成一个共享 topN rerank 或风险倍率补丁。第一步必须量化当前缺口和数据可得性，再设计非泄漏、非挤占的选择器。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_rebuilt_c9_stage002_goal_baseline_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增只读目标审计口径。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage167 曲线，`2018-01` 至 `2026-06-30`，每半年冷启动。
- 账户规模：沿用 Stage167 `150,000`。
- 成本口径：沿用 Stage167 已生成曲线，不重跑。
- 样本过滤：不做额外过滤。
- 策略/归因口径：只读拆解年度收益、产品池和 AI 池状态。

## 目标拆解

- R1：任意起点开始，每一年都正收益。
- R2：全周期收益保留 `80%+`。
- R3：基础品种池加上鸡蛋 `jd.DCE`。
- R4：AI 选品进一步优化。
- R5：能识别超高质量信号。
- R6：对超高质量信号加大风险投入。

## 结果

- 当前 Stage167 年度负收益行：`29`。
- 最差年度行：`2021-07` 起点的 `2022` 年，年度收益 `-16.9640%`。
- 年度问题集中：
  - `2023`：`12` 个窗口中 `10` 个负收益，中位 `-5.2701%`。
  - `2026`：截至 `2026-06-30`，`17` 个窗口中 `16` 个负收益，中位 `-9.1643%`；这是半年度未完成样本，不能和完整年度直接等价，但仍是当前目标缺口。
  - `2022`：`10` 个窗口中 `2` 个负收益，最差 `-16.9640%`。
- 当前 Stage167 中位总收益：`203.6425%`。
- 后续候选按中位总收益的 `80%` 计算，保留线为 `162.9140%`。
- 鸡蛋 `jd.DCE` 在 full-market universe：`PASS`。
- 鸡蛋 `jd.DCE` 在当前 Stage182 AI 池：`FAIL`。
- 鸡蛋 `jd.DCE` 在 Stage167 入场候选：`FAIL`。
- 当前 Stage182 AI 池覆盖 `19` 个产品：`AP/CF/FG/MA/OI/SA/SH/SM/au/cu/fu/hc/jm/lc/lh/rb/ru/si/sp`。
- full-market universe 覆盖 `57` 个产品，包含 `jd.DCE`。

## 鸡蛋历史经验约束

- 旧 Stage407/Stage418 的本地记录已经给出强约束：鸡蛋进入共享 AI rerank/topN 主池时，问题不是鸡蛋本身一定亏，而是它改变原核心池排序、持仓排队、全局连败状态和右尾复利路径。
- 旧结论指向：如果继续鸡蛋，应优先考虑非挤占式 sleeve / 独立风险预算 / 账户级 selector，而不是简单把 `jd.DCE` 放进共享 AI 排名后扫 `topN/maxpos/月/方向/rank`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_report_stage002_rebuilt_c9_goal_baseline_audit_v1.md`
- annual_returns：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_annual_returns_stage002_rebuilt_c9_goal_baseline_audit_v1.csv`
- annual_stats：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_annual_stats_stage002_rebuilt_c9_goal_baseline_audit_v1.csv`
- product_audit：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_product_audit_stage002_rebuilt_c9_goal_baseline_audit_v1.csv`
- requirement_audit：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_requirement_audit_stage002_rebuilt_c9_goal_baseline_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/rebuilt_c9_stage002_goal_baseline_audit_annual_return_heatmap_stage002_rebuilt_c9_goal_baseline_audit_v1.png`

## 结论

- 本阶段结论：当前重建版还没有满足用户目标。年度正收益约束当前失败，`jd.DCE` 数据可用但未进入当前 AI 池和候选，AI 优化与高质量信号加风险尚未开始。
- 是否进入下一步：是。
- 下一步：Stage003 不应直接写交易规则，应做两个只读归因：
  1. 年度负收益行归因，重点 `2022/2023/2026`，查是趋势环境、AI 池、持仓风险、止损重试还是账户层风险预算导致。
  2. 鸡蛋非挤占接入方案设计，先比较“共享 AI rerank”历史反证与“独立风险槽”可行边界。

## 过拟合反思

- 运行前判断：否。只读审计当前基准和数据可得性，不挑参数。
- 运行后判断：否。没有生成候选策略，没有根据结果调整规则。
- 原因：本阶段只是把目标拆解成可验证缺口，避免直接用红框或单年表现反推规则。

## 继续价值反思

- 运行前判断：是。目标很大，必须先固定差距和数据边界。
- 运行后判断：是。当前已确认 `jd.DCE` 数据可用但未入基准，且年度正收益目标当前未满足；下一步归因有明确价值。
- 原因：只有先识别年度负收益和鸡蛋挤占机制，后续才可能构造不破坏核心右尾的 AI selector 或风险槽。

## 合入建议

- 是否更新本线 `LINE.md`：是，补 Stage002 当前状态。
- 是否更新 `research/registry.md`：暂不需要；Stage002 不是重大状态变更。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段未产生正式候选或重要突破。
