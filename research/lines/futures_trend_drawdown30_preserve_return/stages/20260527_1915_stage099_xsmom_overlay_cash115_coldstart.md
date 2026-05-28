# Stage099 Stage079 + xsmom overlay 11.5万现金口径冷启动审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 19:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读诊断；复用 Stage352 固定 `min1_all_no_cap` xsmom 整数手数 overlay，不改 C3/Stage079 交易规则。
- 是否重要突破：否。重要边界确认：全周期强，但新账户多起点冷启动失败。
- 是否触发A/B：是。A 为 Stage079，C 为 `Stage079账户口径 + xsmom min1_all_no_cap overlay`；另含一个不可晋级的 PnL 层自有动量门控诊断。

## 外部调研与判断

- 参考资料：
  - Clare, Seaton, Smith, Thomas, *Trend Following, Risk Parity and Momentum in Commodity Futures*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
- 本轮网络/GitHub 检索关键词：`trend following portfolio overlays combine risk budget with cash sleeve momentum satellite robustness drawdown holding period`、`GitHub trend following portfolio risk budget overlay cash sleeve momentum python backtest`、`managed futures drawdown reduction overlay cross sectional momentum trend following portfolio selection research`。
- 我的判断：
  - 公开研究支持趋势、横截面动量、策略分散和风险预算的组合价值；不支持继续围绕单一入场胜率或失败次数做补丁。
  - Stage051/052 停止的是 `3万现金 + xsmom overlay` 和其附近小数，本阶段不是救 `3万`，而是在当前唯一基准 Stage079 的 `61.5万` 账户口径下复核同一个冻结 overlay。
  - 审计结果显示 xsmom overlay 是真实有价值的低相关线索，但当前 `min1_all_no_cap` 承载对新账户冷启动仍不稳，不能满足“任何时候启动”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart.py`
- 修改脚本：无正式策略默认修改。
- 删除脚本：无。
- 新增候选：
  - `xsmom_overlay_cash115`：C3 50万原路径 + Stage352 `min1_all_no_cap` xsmom overlay + 11.5万现金，账户总资金仍 `61.5万`。
  - `xsmom_overlay_cash115_gate252_diag`：仅当 xsmom overlay 自身过去252交易日 PnL 为正时启用；这是 PnL 层诊断，没有重建逐笔开平仓，不能晋级。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：`61.5万`，不增加资金占用。
- 成本口径：复用 Stage352 C3 与 xsmom 日级 PnL/滑点，做 `1x/2x/3x/5x` 日级滑点压力。
- 样本过滤：无品种过滤，无权重/现金小数扫描。
- 冷启动口径：复用 Stage352 预声明多起点窗口，重新以 `61.5万` 账户启动，检查是否穿30回撤。

## 结果

- 基准 Stage079：
  - 期末权益 `31,040,650`
  - 总收益 `4947.2602%`
  - 最大回撤 `-29.7007%`
  - Sharpe `1.3188`
  - Ulcer `15.0874`
  - 总滑点沿用 Stage079/C3 路径 `1,556,750`
  - 总交易次数沿用 Stage079/C3 路径 `757`
  - 胜率沿用 Stage079/C3 `45.3826%`
- 候选 `xsmom_overlay_cash115` 全周期：
  - 期末权益 `31,909,920`
  - 总收益 `5088.6049%`
  - 最大回撤 `-28.6271%`
  - Sharpe `1.3719`
  - Ulcer `13.9209`
  - 252/504日滚动破30回撤率 `0%/0%`
  - 年度/季度回撤30内通过率 `100%/100%`
- 候选 `xsmom_overlay_cash115` 3个月体验：
  - 5%分位收益 `-10.9495%`，优于 Stage079 `-11.4702%`，但仍未到 `>-8%`。
  - 中位收益 `13.6523%`，正收益率 `75.0563%`，年化低于5%概率 `27.6002%`。
  - 最差期内回撤 `-28.6271%`，破20回撤率 `9.9505%`，破30回撤率 `0%`，Ulcer P95 `15.1175`。
  - 体验分 `148.1141`，改善项 `5/8`。
- 候选 `xsmom_overlay_cash115` 6个月体验：
  - 5%分位收益 `-0.5061%`，中位收益 `34.3752%`，正收益率 `94.7912%`，年化低于5%概率 `7.4613%`。
  - 最差期内回撤 `-28.6271%`，破20回撤率 `27.2173%`，破30回撤率 `0%`，Ulcer P95 `18.8155`。
  - 体验分 `166.0203`，改善项 `6/8`。
- 成本压力：
  - 候选 `1x/2x/3x/5x` 最大回撤为 `-28.6271%/-29.9759%/-31.3966%/-37.9106%`。
  - 同口径 Stage079 为 `-29.7007%/-31.2917%/-33.0035%/-40.1055%`。
  - 日级压力下候选不差于 Stage079。
- 新账户多起点冷启动：
  - `start_2024`：候选收益 `242.7065%`，最大回撤 `-30.8555%`，失败。
  - `start_2025`：候选收益 `201.6089%`，最大回撤 `-31.3537%`，失败。
  - `ytd_2026`：候选收益 `-15.3024%`，最大回撤 `-48.7056%`，失败。
  - 对照 Stage079 在这些窗口分别为 `-28.0544%/-27.1556%/-23.8062%`，均未穿30。
- 诊断 `xsmom_overlay_cash115_gate252_diag`：
  - 全周期 `5080.4878%/-29.1465%/Sharpe1.3601/Ulcer14.1225`，3个月分 `132.3087`，6个月分 `144.7685`。
  - 同样在 `start_2024/start_2025/ytd_2026` 冷启动穿30，且不是逐笔真实门控，因此不晋级。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_report_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_summary_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_horizon_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_score_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_cost_stress_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- fresh start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_fresh_start_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_gate_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_daily_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_decision_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage399_stage079_xsmom_overlay_cash115_coldstart_equity_drawdown_stage399_stage079_xsmom_overlay_cash115_coldstart_v1.png`

## 结论

- 本阶段结论：`xsmom_overlay_cash115` 是当前最强的全周期诊断线索之一，硬指标、3个月分、6个月分和日级成本压力都明显优于 Stage079；但它不能通过新账户多起点冷启动，尤其 `2026YTD` 回撤 `-48.7056%`，因此不能晋级。
- 我的非硬目标判断：如果允许“不按当前硬目标晋级”，它值得晋级为独立承载/forward paper重点线索，而不是正式 Stage079 替代版。理由是全周期收益源明显有效，失败点集中在冷启动承载稳定性；这说明问题更像“怎么承载 xsmom”，不是“xsmom 没价值”。
- 是否进入下一步：当前承载形状不继续。xsmom 理论线索保留，但 `min1_all_no_cap` overlay 与简单自身252日门控都停止。
- 下一步：若继续 xsmom，只能换真实承载结构，例如更低杠杆/更低保证金离散度的工具、非期货化指数/基金承载、或先做独立 OOS paper 监控；不能继续调 `min1_all_no_cap`、现金数额、252日门控窗口或2024/2025/2026修补条件。

## 过拟合反思

- 运行前判断：不是过拟合。候选来自既有冻结 overlay 与 Stage079 固定账户口径，不新增品种/阈值/权重扫描。
- 运行后判断：本阶段不是过拟合，但如果继续围绕 2024/2025/2026 冷启动失败去调门控窗口、禁用月份或品种，就是过拟合。
- 原因：全周期已经足够好，失败来自独立冷启动路径；继续救局部窗口会把一个有价值的独立收益源线索变成数据拟合补丁。

## 继续价值反思

- 运行前判断：有价值。目标要求提升3个月/6个月体验，而 xsmom 是少数具备低相关收益和收益增强能力的线索。
- 运行后判断：xsmom 方向仍有研究价值，但当前承载形状继续价值低；总目标仍有价值。
- 原因：结果说明收益源可能是真的，问题在于承载和冷启动稳定性，不是 Stage079 本体的入场规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage099 边界。
- 是否更新 `research/registry.md`：否，未形成正式候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；`memory.md` 暂不更新。
