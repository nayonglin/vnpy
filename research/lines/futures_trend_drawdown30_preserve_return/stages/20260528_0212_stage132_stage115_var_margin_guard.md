# Stage132 Stage115 VAR保证金闸门审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 02:12 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：固定结构 A/B/C 审计；不改 Stage079/Stage103，不扫窗口、不扫阈值、不扫保证金小数。
- 是否重要突破：否。重要反证：即使给 Stage115 加入事前亏损准备金闸门，也不能把它修成可执行晋级版本。
- 是否触发A/B：是。已遵循 `skills/version-ab-experiment/SKILL.md`。A=Stage079；C0=Stage103；C1=Stage115 best1；C2=Stage115 best1 + VAR99 亏损准备金闸门。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen 的 Time Series Momentum 研究显示期货 TSMOM 有跨资产先验，但收益和风险预算不能分开看。
  - CME 的 time-series momentum 改进资料和公开期货风险管理资料都强调 position sizing、波动/保证金预算对落地结果有决定性影响。
  - GitHub/公开实现中仍未找到可直接迁移到中国期货、整数手、真实保证金、Stage079 资金口径的现成更优方案。
- 我的判断：
  - Stage115 的主要问题不是“多加一点保证金小数”能解决，而是收益优势与少数贡献日、冷启动路径和保证金占用强相关。
  - 因此本阶段只测试一个低自由度、可点时化的风险预算原则：使用上一日已知 Stage103 基础路径滚动252交易日 99% 单日亏损准备金。
  - 如果该原则失败，就不应继续救 Stage115 的窗口、日期、单指数、贡献日或保证金小数。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage432_stage115_var_margin_guard.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `index_tsmom_best1_var99`：仍在 IF/IH/IC/IM 60日 TSMOM 中每天取绝对动量最强1手。
  - `loss_reserve_var99_252d`：上一日已知的 Stage103 基础路径滚动252交易日 99% 单日亏损准备金。
  - 闸门：`(C3保证金 + xsmom保证金 + 股指overlay保证金) * 1.10 + loss_reserve_var99_252d <= 上一日权益`。
- 修改参数：无。
- 删除参数：无。
- 修改正式策略默认：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-05-25`，并复用研究线内多起点窗口。
- 账户规模：`615,000` 账户口径，即 Stage079 的 `50万C3下单 + 11.5万外部现金`。
- 成本口径：沿用当前真实整数手日度滑点口径，并补 `1x/2x/3x/5x` 成本压力。
- 样本过滤：无新增样本过滤。
- 策略/归因口径：只读重构 Stage079、Stage103、Stage115 best1、Stage115 VAR99；不修改 C3、xsmom、股指 TSMOM 信号。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 非零日胜率 | 3个月分 | 6个月分 | 判断 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 | `31,040,650` | `4947.2602%` | `-29.7007%` | `1.3188` | `15.0874` | `1,556,750` | `757` | `48.3478%` | `100.0000` | `100.0000` | baseline |
| Stage103 | `31,730,915` | `5059.4984%` | `-28.9792%` | `1.3681` | `14.3132` | `1,569,265` | `1,217` | `50.3432%` | `121.2041` | `134.4513` | 当前主候选 |
| Stage115 best1 | `33,607,695` | `5364.6659%` | `-23.5184%` | `1.4810` | `12.0786` | `1,594,705` | `1,719` | `53.8102%` | `183.4601` | `210.3930` | 高分paper，但绝对保证金不过 |
| Stage115 VAR99 | `33,622,095` | `5367.0073%` | `-23.4609%` | `1.4850` | `12.0495` | `1,594,585` | `1,717` | `53.8102%` | `183.5582` | `210.4541` | 全周期漂亮，但冷启动/保证金失败 |

## 关键反证

- VAR99 全周期略高于 Stage115 best1，但这不是晋级证据：
  - `start_2024` 与 `phase_2024_2025` 最大回撤均为 `-41.8333%`，硬破 Stage079 目标。
  - `start_2024/phase_2024_2025` 的 1.10x 最大保证金/权益为 `116.2860%`，有 `3` 天穿线，需要额外约 `97,427.10` 元。
  - `start_2022` 回撤为 `-33.4730%`，虽无保证金穿线，但“任何时候启动”体验失败。
- 贡献日脆弱性仍未解决：
  - Stage115 best1 相对 Stage103 剔除最大 `1` 个正贡献日后，总收益差转为 `-13.4193pp`。
  - Stage115 VAR99 剔除最大 `1` 个正贡献日后，总收益差仍为 `-9.9211pp`。
- 准备金尺度过大且路径依赖强：
  - `loss_reserve_var99_252d` 中位数约 `230,306`，90%分位约 `962,837`，99%分位约 `2,186,294`，最大约 `2,235,652`。
  - 这会让新起点在某些年份大量跳过股指腿，反而错过恢复段并放大冷启动回撤。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_report_stage432_stage115_var_margin_guard_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_summary_stage432_stage115_var_margin_guard_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_horizon_stage432_stage115_var_margin_guard_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_score_stage432_stage115_var_margin_guard_v1.csv`
- margin：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_margin_audit_stage432_stage115_var_margin_guard_v1.csv`
- reserve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_base_loss_reserve_stage432_stage115_var_margin_guard_v1.csv`
- topday：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_top_edge_day_ablation_stage432_stage115_var_margin_guard_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_daily_stage432_stage115_var_margin_guard_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_chart_stage432_stage115_var_margin_guard_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage432_stage115_var_margin_guard_decision_stage432_stage115_var_margin_guard_v1.json`

## 结论

- 本阶段结论：决策 `no_var99_promotion`。Stage115 VAR99 不晋级。
- 是否进入下一步：否。Stage115 救援路线到此封止。
- 下一步：主执行相对候选维持 Stage103；后续若继续主动研究，只允许全新低自由度风险源或工程化/paper/真实券商保证金接入，不继续救 Stage115 股指 TSMOM 内部形状。

## 过拟合反思

- 运行前判断：不是过拟合。只测试一个事前固定的风险预算原则，没有扫描分位数、窗口、保证金倍数或日期。
- 运行后判断：不是过拟合。失败后没有继续调参救结果，反而将该子路线封止。
- 原因：全周期指标更好但多起点失败，说明不能按漂亮总收益倒推晋级。

## 继续价值反思

- 运行前判断：有价值。Stage115 的收益和回撤优势太强，值得最后确认是否只是缺少亏损准备金。
- 运行后判断：Stage115 救援路线继续价值低；总目标仍有价值。
- 原因：VAR99 没解决冷启动和贡献日集中，继续救只会转向更细的历史路径补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage132 执行约束。
- 是否更新 `research/registry.md`：否，未产生新主候选。
- 是否追加根目录 `memory.md/back_log.md`：是。Stage115 救援路线正式封止，属于重要路线废弃摘要。
