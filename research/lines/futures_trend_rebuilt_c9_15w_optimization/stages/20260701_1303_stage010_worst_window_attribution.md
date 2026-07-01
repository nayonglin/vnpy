# Stage010 最差窗口左尾归因

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 13:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读归因；不改策略、不扫参数、不连接 CTP、不调用下单。
- 是否重要突破：是。确认 Stage009 严格窗口失败的主因不在 Stage008 高质量加风险标签，而在账户层持仓/日级 PnL 左尾。
- 是否触发A/B：否。

## 外部调研与判断

- 参考资料：
  - AQR/Hurst-Ooi-Pedersen, `A Century of Evidence on Trend-Following Investing`：趋势跟随长期价值来自跨市场分散和右尾复利。
  - Bailey/Borwein/Lopez de Prado/Zhu, `The Probability of Backtest Overfitting`：围绕单个坏窗口扫阈值容易产生样本内赢家。
  - Hood/Raughtigan, `Volatility Targeting Is Trendy`：波动管理不能在商品期货上直接假定产生 alpha，必须在真实路径里验证。
- 我的判断：Stage010 不应直接生成“砍品种/砍方向/调阈值”的规则；应该先定位账户权益损失来自已平仓实现亏损、持仓浮亏、保证金压力还是日级风险暴露。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage010_worst_window_attribution.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：`FOCUS_VARIANT=proxy_stage008`，焦点窗口自动取 Stage009 proxy 最差窗口。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage009 最差 proxy 窗口 `2022-07-15` 到 `2023-07-17`。
- 账户规模：沿用 Stage167/Stage006/Stage008 的 C9/15w 曲线与 Stage008 proxy。
- 成本口径：沿用 Stage006 重跑曲线；Stage010 不重新撮合、不改滑点。
- 样本过滤：覆盖该焦点窗口的 `10` 个冷启动账户。
- 策略/归因口径：账户曲线、Stage007 质量标签、Stage008 proxy lot delta、窗口内已平仓 lot 贡献。

## 结果

- 期末权益：不适用，本阶段不是新增完整回测。
- 总收益：最差 source `2018-01` 的 proxy 窗口收益 `-54.2509%`；base 同窗口 `-55.2146%`。
- 最大回撤：最差 source `2018-01` 的 proxy 窗口内最大回撤 `-55.2574%`；base `-56.2069%`。
- Sharpe：不适用。
- 总滑点：不适用，沿用基准曲线。
- 总交易次数：窗口内已平仓 lot 贡献样本 `309`。
- 胜率：窗口内各 source 已平仓 lot 胜率约 `21.43%` 到 `35.00%`。
- 其他关键指标：
  - 覆盖冷启动账户数：`10`。
  - proxy 窗口权益变动合计：`-18,629,920`。
  - base 窗口权益变动合计：`-19,235,925`。
  - Stage008 高质量加风险在窗口内 proxy delta 合计：`+606,005`，方向是缓冲不是放大。
  - 窗口内已平仓 lot 净实现盈亏：`-10,575`。
  - `base_change_cash - closed_lot_realized_pnl` 残差：`-19,225,350`，说明主问题在窗口内持仓浮亏/日级 holding_pnl，而不是仅靠已平仓 lot 可解释。
  - 闭合 lot 层面最大拖累品种/方向：`SM.CZCE short`，`-2,711,300`。
  - 质量桶最大正贡献：`ai4_6_entry_or_first_aligned`，realized `+2,424,020`，proxy delta `+606,005`。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage010_worst_window_attribution/rebuilt_c9_stage010_worst_window_attribution_report_stage010_worst_window_attribution_v1.md`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage010_worst_window_attribution/rebuilt_c9_stage010_worst_window_attribution_window_metrics_stage010_worst_window_attribution_v1.csv`
- orders：不适用。
- daily：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage010_worst_window_attribution/rebuilt_c9_stage010_worst_window_attribution_focus_windows_stage010_worst_window_attribution_v1.csv`
- quality：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage010_worst_window_attribution/rebuilt_c9_stage010_worst_window_attribution_tag_contributions_stage010_worst_window_attribution_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage010_worst_window_attribution/rebuilt_c9_stage010_worst_window_attribution_chart_stage010_worst_window_attribution_v1.png`

## 结论

- 本阶段结论：Stage008 的高质量加风险标签不是 Stage009 左尾失败主因；它在焦点窗口整体贡献 `+606,005` 的缓冲。真正需要追的是窗口内持仓浮亏/日级 holding_pnl 与账户层风险暴露。
- 是否进入下一步：是。
- 下一步：Stage011 复用旧 Stage331/837/885 持仓路径归因方法，拆解 `2022-07-15` 到 `2023-07-17` 的日级 holding_pnl、active positions、保证金压力和持仓穿越窗口来源；若确认是账户层风险暴露，再设计不砍右尾的生存线/动态风险真实引擎。

## 过拟合反思

- 运行前判断：否。只解释 Stage009 暴露的最差窗口，不新增规则、不选参数。
- 运行后判断：否。没有用坏窗口反推阈值或黑名单。
- 原因：输出只做归因；即使 `SM.CZCE short` 在闭合 lot 层面最差，也不直接形成单品种/方向过滤规则，因为账户损失主要来自未拆开的日级持仓 PnL。

## 继续价值反思

- 运行前判断：是。严格任意结束日目标失败集中在同一左尾区间，归因价值高。
- 运行后判断：有。已经排除“高质量加风险是主因”的路径，下一步能更聚焦账户层保护。
- 原因：如果不拆 holding_pnl，后续容易错误地按闭合 lot 结果做品种黑名单，这是明显过拟合风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage010 结论和 Stage011 方向。
- 是否更新 `research/registry.md`：是，最新关键阶段更新到 Stage010。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段仍是本研究线内部归因，不是正式候选或跨线里程碑。
