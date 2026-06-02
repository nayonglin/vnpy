# Stage238 Stage526晋级边界审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 22:51 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读晋级闸门审计；不改策略、不重跑参数、不新增交易规则。
- 是否重要突破：是。把 Stage526 从“主研究候选”推进为“正常成本候选评审”，同时明确不能宣称 3x 成本压力也通过。
- 是否触发A/B：是，属于候选晋级边界审计。A=Stage079/既有真实可成交基准，C=Stage526 `r080_pc25_maxpos4`；本阶段不新增 B 独立策略。

## 外部调研与判断

- 参考资料：继续参考趋势跟随/回测稳健性常见框架：walk-forward/多起点、交易成本压力、回测过拟合控制、贡献集中度和风险预算审计；本阶段没有新增 alpha 搜索。
- 我的判断：这是反过拟合审计，不是过拟合。因为所有闸门在看结果前已从 Stage526-537 的已有证据拼接，不根据失败项继续调参数；继续有价值，因为需要明确候选的可宣传边界和下一步工作重心。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage538_stage526_promotion_boundary.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：晋级闸门表，包括正常成本 DD40、broker100、收益保留70%、Sharpe、2x成本DD40、冷启动、63/126日DD40、edge集中度、xsmom fallback、入场代理反证、早退反证、成本脆弱性识别、外生数据可执行性。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage526-537 的 2020-2026 全周期输出。
- 账户规模：Stage526 `50万C3下单 + 11.5万现金/组合口径`，候选初始权益口径同前序报告。
- 成本口径：正常成本、2x成本、3x成本压力。
- 样本过滤：无新增过滤；仅读取既有 Stage526-537 输出。
- 策略/归因口径：`r080_pc25_maxpos4 = risk0.80 + product cap25% + max active products 4`。

## 结果

- 期末权益：`23,369,505`
- 总收益：`3699.9195%`
- 最大回撤：`-36.2670%`
- Sharpe：`1.6385`
- Ulcer：`14.4691`
- 总滑点：`1,342,190`
- 总交易次数：`905`
- 胜率：非零日胜率 `53.6330%`
- 其他关键指标：
  - 必要闸门：`13/13` 通过。
  - 正常成本 broker10 最大：`99.7299%`，穿 `100%` 天数 `0`。
  - 相对 Stage079 收益保留：`74.7872%`。
  - 2x 成本：最大回撤 `-39.0565%`，收益保留 `70.3759%`；但 broker10 压力口径最大 `105.4038%`，穿 `100%` 天数 `2`，作为安全垫预警。
  - 3x 成本：最大回撤 `-42.0555%`，失败；不能宣称高滑点极端压力下也稳。
  - 冷启动：月/季/年 DD40 与 broker100 通过率均 `100%`。
  - 3/6个月持有体验：63日 p05 `-18.2169%`，126日 p05 `-10.9700%`；短持有左尾仍需披露，但 63/126日 DD40 破例均为 `0`。
  - edge 集中度：相对 `r080_pc25_u75` top5 正贡献占比 `10.4406%`，最大年度贡献占比 `38.5876%`，leave-one-year 全部为正。

## 图表视觉复盘

- 晋级闸门图显示 `PASS=13`、`WARN=3`、`FAIL=1`，说明正常晋级证据完整，但压力披露不可省略。
- 成本压力图呈单调恶化：1x `-36.3%`、2x `-39.1%`、3x `-42.1%`，3x 刚好穿过 DD40 线，问题不是收益消失，而是成本把同一条长回撤路径推深。
- 任意启动持有体验图显示 21/63/126日 p05 仍为负，252/504日明显转正；该版本适合中长期承载，不适合承诺短持有总是舒服。
- 权益/水下图显示 2021-2022 水下是主要风险段，2023 后权益恢复并继续创新高；这与 Stage536 的成本脆弱性归因一致。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage538_stage526_promotion_boundary_report_stage538_stage526_promotion_boundary_v1.md`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage538_stage526_promotion_boundary_gates_stage538_stage526_promotion_boundary_v1.csv`
- boundary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage538_stage526_promotion_boundary_boundary_stage538_stage526_promotion_boundary_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage538_stage526_promotion_boundary_decision_stage538_stage526_promotion_boundary_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage538_stage526_promotion_boundary_chart_stage538_stage526_promotion_boundary_v1.png`

## 结论

- 本阶段结论：决策 `promote_stage526_normal_cost_candidate_with_3x_stress_warning`。Stage526 可以晋级为正常成本口径下的主候选/执行评审候选：DD40、broker100、收益保留、2x成本DD40、冷启动、edge集中度和 xsmom fallback 闸门均通过。
- 是否进入下一步：进入，但只进入“正常成本候选评审/监控准备”，不进入“3x成本也安全的最终实盘版”。
- 下一步：不再围绕 T+1旧问题、入场代理、早期退出、简单 cooldown 或产品黑名单打转。下一条更值得做的结构是“降低单笔风险 + 扩大品种池 + 相关性预算/品种选择”，目标是提高年度抓到趋势的概率，同时不提高同向相关性和保证金峰值。

## 过拟合反思

- 运行前判断：否。只读审计既有候选，不根据失败项改规则。
- 运行后判断：否。13个必要闸门来自独立前序证据，且主动保留 3x 成本失败和短持有左尾警告。
- 原因：没有新增交易参数、没有扫小数、没有按 2022 坏窗口补丁，也没有把产品亏损归因变成黑名单。

## 继续价值反思

- 运行前判断：有价值。Stage526 已经接近可执行边界，需要明确是否值得继续。
- 运行后判断：有价值但方向改变。继续改 Stage526 交易规则价值低；继续做执行监控和更底层的低单笔风险扩池结构有价值。
- 原因：当前版本的主要未完成项是 3x 成本与短持有左尾，不是简单信号错位；扩池若能用相关性预算降低单品种依赖，可能比继续修早退更接近第一性原理。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与下一步。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不更新 `memory.md`。
