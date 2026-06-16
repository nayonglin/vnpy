# Stage072 Stage897 C9 Jan/Jun 1年滚动测试

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 17:28`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：C9 多起点独立回放、1年窗口冷启动审计。
- 是否重要突破：否。它修正了“C9 每年都正收益”的直觉。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - Interactive Brokers Campus walk-forward analysis：https://www.interactivebrokers.com/campus/ibkr-quant-news/the-future-of-backtesting-a-deep-dive-into-walk-forward-analysis/
  - vn.py GitHub portfolio strategy 说明：https://github.com/vnpy/vnpy/blob/master/README_ENG.md
- 我的判断：外部资料只确认 rolling/walk-forward 的方法论，即用多个预声明窗口检验策略稳健性。C9 有权益、持仓、重试、保证金路径依赖，不能用全周期净值切片替代真实冷启动；本次继续复用仓库 vn.py portfolio engine 做每个窗口独立回放。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage897_c9_janjun_rolling1y.py`
- 修改脚本：无。
- 删除脚本：移除了未保留的临时 `stage897_c9_vs_official_janjun_rolling1y` 对比入口；原因是当前正式版 Stage372/20w 在 `2018-01` 起点返回空结果，不能覆盖用户要求的 2018 起点。
- 新增参数：
  - `DATA_START=2018-01-01`
  - `DATA_END=2026-05-29`
  - 用户请求今天：`2026-06-15`；本地最新可回测日期：`2026-05-29`
  - `ROLL_YEARS=1`
  - 起点月份：`1月` 与 `6月`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 起，到本地最新可用 `2026-05-29`。
- 账户规模：C9 `300000`。
- 成本口径：沿用 C9 引擎的手续费、滑点、合约乘数与 broker10 保证金口径。
- 样本过滤：完整 1 年窗口 `15` 个作为主判断；`2025-06 -> 2026-05-29` 与 `2026-01 -> 2026-05-29` 为 partial，仅作观察。
- 策略/归因口径：C9 `stage847_stage819_c4_05r_stop_retry_once`，即 C4 + `0.5R` 实时止损 + 原入场价重试一次；不改 R 倍数、不改重试次数、不改分钟窗口。

## 结果

- 主决策：`stage897_c9_rolling1y_has_negative_windows_not_annual_all_positive`
- 完整 1 年窗口：
  - 窗口数：`15`
  - 正收益：`12/15 = 80.00%`
  - 负收益窗口：
    - `2018-01 -> 2018-12`：收益 `-20.6533%`，最大回撤 `-23.3137%`，Sharpe `-1.2228`。
    - `2018-06 -> 2019-05`：收益 `-20.8667%`，最大回撤 `-22.2047%`，Sharpe `-1.0444`。
    - `2022-01 -> 2022-12`：收益 `-0.6999%`，最大回撤 `-38.4414%`，Sharpe `0.2123`。
  - 期末权益：完整窗口 raw 值范围约 `237,400 -> 1,798,491`，以收益率为主判断。
  - 总收益：中位 `60.7455%`，p10 `-12.6720%`，最小 `-20.8667%`，最大 `499.4970%`。
  - 最大回撤：中位 `-22.2047%`，最差 `-42.5759%`。
  - Sharpe：中位 `1.1503`，p10 `-0.5417`，最小 `-1.2228`。
  - 总滑点：`267,580`
  - 总交易次数：`1,329`
  - 胜率：非零日胜率中位 `52.4194%`，最低 `39.8058%`，最高 `59.7884%`。
  - 其他关键指标：DD30 失败 `4`，DD40 失败 `1`，DD50 失败 `0`，broker100 失败 `0`，peak broker10 `91.9780%`。
- partial：
  - `2025-06 -> 2026-05-29`：收益 `75.6652%`，最大回撤 `-17.1754%`，Sharpe `1.6789`。
  - `2026-01 -> 2026-05-29`：收益 `-8.6838%`，最大回撤 `-12.0280%`，Sharpe `-1.0230`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_report_stage897_c9_janjun_rolling1y_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_summary_stage897_c9_janjun_rolling1y_v1.csv`
- orders：无。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_curves_stage897_c9_janjun_rolling1y_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_decision_stage897_c9_janjun_rolling1y_v1.json`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage897_c9_janjun_rolling1y_aggregate_stage897_c9_janjun_rolling1y_v1.csv`

## 结论

- 本阶段结论：C9 不能说“每个 1 年周期都正收益”。按用户指定的 2018 起、每年 1月/6月起点、1年窗口，完整窗口中 `3/15` 为负收益，其中两个 2018 起点约 `-20%`，2022-01 起点小负 `-0.6999%`。但 C9 的年度级风险尾部比 3 年窗口温和：DD50 与 broker100 都为 `0`，最差 broker10 `91.9780%`，说明它不是年度层面爆仓式失败，而是早期冷启动和 2022 弱窗口收益稳定性不足。
- 是否进入下一步：不进入 A/B，不作为正式替代。可以继续做 2018 起点与 2022-01 起点的只读归因。
- 下一步：若继续，应先解释 2018 两个负窗口是否来自旧数据阶段的品种池/AI可用性/趋势环境，和 2022-01 小负是否与后续 DD38 的同一压力机制相关；不要按 2018 年份、单品种、方向、R 倍数或重试次数做补丁。

## 过拟合反思

- 运行前判断：否。用户固定 `1年窗口 + 1月/6月起点 + 2018起`，本次不调参。
- 运行后判断：对“每年都正收益”这个推广表述，是。完整 1 年冷启动显示 `3` 个负窗口，说明仅看 3 年窗口或图形右尾会高估年度稳定性。
- 原因：C9 的右尾足以拉平多数年度窗口，但 2018 早期和 2022-01 仍有收益不足；年度窗口更容易暴露入场时点和市场环境的短周期脆弱性。

## 继续价值反思

- 运行前判断：有价值。它能直接验证 C9 年度正收益直觉。
- 运行后判断：有价值但范围收窄。继续价值在归因负窗口，而不是推广 C9 或继续扫参数。
- 原因：`12/15` 正收益和无 broker100 说明 C9 年度冷启动并不差；但负窗口足以否定“年度全正”的强表述。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage072 摘要。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，不是正式候选晋级或重要突破。
