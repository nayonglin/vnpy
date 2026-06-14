# Stage007 Stage831 C4年度起点稳健性反证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 16:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结 Stage830 参数的候选线内部年度起点稳健性验证；不改正式策略、不连接 CTP、不调用下单。
- 是否重要突破：否；这是重要反证和路线收敛，阻止把 Stage830 单一起点好结果误升为正式候选。
- 是否触发A/B：不触发正式 A/B。已读取 `skills/version-ab-experiment/SKILL.md`，本阶段只是 Stage819 候选内部 A/C4 稳健性，不是与当前正式 Stage372/20w 的 live-default 替代验证。

## 外部调研与判断

- 参考资料：
  - GitHub walk-forward/robustness 相关项目与主题，确认策略晋级前应看跨起点/分段，而不是只看单一路径。
  - Semantic Scholar `Assessing Stop-Loss and Re-Entry Strategies`，强调止损价值必须和再入场规则一起评估。
  - 公开 trend-following position sizing/stop loss 资料，核心观点是止损距离、仓位和账户风险预算是一个系统。
- 我的判断：
  - Stage830 的结构理由仍成立：日内止损释放资金后，必须用账户层预算约束重新开仓。
  - 但 Stage831 证明“flat-entry broker10 100%入口闸门”只约束入场一刻，不能约束持仓后的盯市路径；因此不能把它包装成完整生存线。
  - 下一步如果继续，只能研究全路径持仓保证金生存或释放资金再使用纪律，不能扫 `95/90/85` 这类入口阈值救结果。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage831_stage830_c4_yearly_robustness.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无策略参数；新增验证参数 `YEAR_STARTS=2018-01..2026-01`，`STAGE831_MAX_WORKERS` 仅为运行并发控制。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：每个年度起点从对应 `YYYY-01-01` 跑到 `2026-05-29`。
- 账户规模：Stage819 候选 30万口径。
- 成本口径：沿用 Stage827/Stage819 候选回测成本与滑点口径。
- 样本过滤：无年份、品种、方向、收益标签过滤。
- 策略/归因口径：
  - A：`stage827_stage819_baseline`，Stage819 原始候选复现。
  - C4：`stage830_stage819_c2_broker10_100_cap`，冻结 `1R/1R` 日内止损、`broker_margin_multiplier=1.65`、`projected broker10 margin/equity cap=100%`。

## 结果

- 全部年度起点 `9` 个：
  - C4 收益胜 `8/9`，回撤胜 `5/9`，Sharpe 胜 `8/9`，收益+回撤双胜 `5/9`。
  - C4 正收益 `8/9`，A 正收益 `8/9`。
  - C4 收益差中位 `+225.8113pp`，p10 `+10.4005pp`。
  - C4 回撤差中位 `+1.4188pp`，p10 `-6.7858pp`。
  - A DD40 失败 `4`，C4 DD40 失败 `4`。
  - A DD50 失败 `1`，C4 DD50 失败 `3`。
  - A broker100 失败 `0`，C4 broker100 失败 `4`。
  - A 最差回撤 `-54.7546%`，C4 最差回撤 `-50.8993%`。
- 成熟起点 `2018-01` 到 `2025-01` 共 `8` 个：
  - C4 收益胜 `8/8`，回撤胜 `5/8`，Sharpe 胜 `8/8`，收益+回撤双胜 `5/8`。
  - C4 收益差中位 `+813.1024pp`，p10 `+55.8218pp`。
  - C4 回撤差中位 `+1.6818pp`，p10 `-6.8571pp`。
  - A DD40 失败 `4`，C4 DD40 失败 `4`。
  - A DD50 失败 `1`，C4 DD50 失败 `3`。
  - A broker100 失败 `0`，C4 broker100 失败 `4`。
  - C4 日内止损事件 `262` 次、止损量 `38,941` 手；cap events `147` 次、降手 `3,075` 手。
- 关键逐年结果：
  - `2018-01`：C4 收益 `10074.6369%` vs A `8674.2433%`，回撤 `-50.7900%` vs A `-54.7546%`，broker10 `115.4012%` vs A `90.6200%`。
  - `2019-01`：C4 收益 `11730.3406%` vs A `7497.4750%`，但回撤 `-50.7898%` vs A `-43.4335%`，broker10 `104.9794%`。
  - `2020-01`：C4 收益 `8549.0772%` vs A `6162.5117%`，但回撤 `-50.8993%` vs A `-44.6223%`，broker10 `114.4678%`。
  - `2021-01`：C4 收益 `4468.6333%` vs A `1826.5917%`，但回撤 `-49.4595%` vs A `-42.8163%`，broker10 `108.1240%`。
  - `2026-01`：C4 `-12.9412%` 弱于 A `-11.4000%`，回撤和 Sharpe 也更差。
- 期末权益：
  - `2018-01` 起点 A：`26,322,730`
  - `2018-01` 起点 C4：`30,523,910.8`
  - `2020-01` 起点 A：`18,787,535`
  - `2020-01` 起点 C4：`25,947,231.6`
- 总收益：
  - `2018-01` 起点 A：`8674.24%`
  - `2018-01` 起点 C4：`10074.64%`
  - `2020-01` 起点 A：`6162.51%`
  - `2020-01` 起点 C4：`8549.08%`
- 最大回撤：
  - `2018-01` 起点 A：`-54.75%`
  - `2018-01` 起点 C4：`-50.79%`
  - `2020-01` 起点 A：`-44.62%`
  - `2020-01` 起点 C4：`-50.90%`
- Sharpe：
  - `2018-01` 起点 A：`1.436`
  - `2018-01` 起点 C4：`1.452`
  - `2020-01` 起点 A：`1.594`
  - `2020-01` 起点 C4：`1.622`
- 总滑点：
  - `2018-01` 起点 A：`2,149,150`
  - `2018-01` 起点 C4：`2,079,430`
  - `2020-01` 起点 A：`1,489,460`
  - `2020-01` 起点 C4：`1,779,890`
- 总交易次数：
  - `2018-01` 起点 A：`666`
  - `2018-01` 起点 C4：`677`
  - `2020-01` 起点 A：`529`
  - `2020-01` 起点 C4：`534`
- 胜率：
  - 全部年度起点 A 胜率中位 `53.11%`，范围 `44.83%` 到 `54.75%`。
  - 全部年度起点 C4 胜率中位 `53.85%`，范围 `48.15%` 到 `55.00%`。
  - `2018-01` 起点 A：`53.11%`
  - `2018-01` 起点 C4：`53.63%`
  - `2020-01` 起点 A：`54.75%`
  - `2020-01` 起点 C4：`54.44%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_report_stage831_stage830_c4_yearly_robustness_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_summary_stage831_stage830_c4_yearly_robustness_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_comparison_stage831_stage830_c4_yearly_robustness_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_aggregate_stage831_stage830_c4_yearly_robustness_v1.csv`
- daily/curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_curves_stage831_stage830_c4_yearly_robustness_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_decision_stage831_stage830_c4_yearly_robustness_v1.json`
- metric chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_metric_chart_stage831_stage830_c4_yearly_robustness_v1.png`
- selected curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage831_stage830_c4_yearly_robustness_selected_curves_stage831_stage830_c4_yearly_robustness_v1.png`

## 结论

- 本阶段结论：
  - C4 不能晋级。它的收益和 Sharpe 优势广泛存在，尤其 `2018-2025` 成熟起点收益胜 `8/8`，但风险路径不过关。
  - C4 的问题集中在 `2019/2020/2021` 起点：收益显著变大，但最大回撤也恶化到接近或超过 `-50%`，并触发 broker100 超限。
  - Stage830 的入口 broker10 闸门证明了“账户层预算方向”有价值，但 Stage831 证明它不是完整的生存线。它限制开仓瞬间，不限制持仓后盯市、权益下跌和保证金占用共同作用。
- 是否进入下一步：可以继续研究，但不能沿 C4 直接晋级。
- 下一步：
  - Stage008 应做 C4 broker100/DD50 超限日的只读归因，定位是持仓后价格波动、同日多开、同风险簇复用，还是权益下跌导致分母塌缩。
  - 只允许研究 full-path holding margin survival 或释放资金再使用纪律；禁止把入口 cap 从 `100%` 扫到 `95/90/85` 来救结果。
  - 只有出现不增加 DD50/broker100 的结构性规则后，才重新讨论 Stage819 候选内部晋级；在此之前不与官方 Stage372 做正式替代 A/B。

## 过拟合反思

- 运行前判断：不是明显过拟合，但存在“从 2018 单一起点 Stage830 好结果出发继续验证”的选择偏差。
- 运行后判断：Stage831 本身没有新增过拟合；它反而揭示 Stage830 不够稳健。
- 原因：
  - 年度起点网格、`1R/1R`、`1.65` broker multiplier 和 `100%` 入口 cap 都是冻结的。
  - 没有按失败起点、品种、方向或年份增加过滤条件。
  - 结果显示 C4 同时有真实收益优势和真实尾部风险，不能为了收益优势忽略 DD50/broker100。

## 继续价值反思

- 运行前判断：有价值继续，因为 Stage830 单起点同时提高收益和降低最大回撤，值得跨起点验证。
- 运行后判断：仍有价值继续，但方向必须从“入口闸门”转为“持仓路径生存”，不能继续优化 C4 本身。
- 原因：
  - C4 成熟起点收益胜 `8/8`、Sharpe 胜 `8/8`，说明 C2 日内止损和释放资金机制确有进攻价值。
  - 但 C4 DD50 失败 `3` vs A `1`、broker100 失败 `4` vs A `0`，说明继续推进的核心不是提高收益，而是约束释放资金后的路径暴露。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage007 反证和下一步方向。
- 是否更新 `research/registry.md`：否，当前不晋级、不合入总索引。
- 是否追加根目录 `memory.md/back_log.md`：否。正式 A/B 未触发，且本阶段是候选线内部反证；按并行研究记录规则留在本线 stage 文件中。
