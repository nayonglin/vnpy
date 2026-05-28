# Stage125 Stage103持仓兴趣确认动量Overlay审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-28 00:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：外部先验驱动的低自由度结构验证；固定 Stage079 与 Stage103，不修改 C3、Stage079、Stage103 交易规则，不增加账户资金。
- 是否重要突破：否。重要边界确认：持仓兴趣确认能改善全周期风险和3/6个月左尾，但不满足“任意启动收益体验”晋级要求。
- 是否触发A/B：是。A=Stage079，C0=Stage103，C1/C2=Stage103 叠加持仓兴趣确认动量 overlay。

## 外部调研与判断

- 参考资料：
  - Hong & Yogo, *What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices?*：https://www.nber.org/papers/w16712
  - GitHub 调研关键词：`commodity futures open interest momentum strategy Python`、`futures open interest trading strategy trend following`。
  - GitHub 参考结果：`quantiacs/strategy-futures-trend-following`、`chrism2671/PyTrendFollow` 等多为通用期货趋势框架，没有发现可直接迁移到本地中国商品池、逐合约持仓兴趣、整数手、保证金闸门和 Stage079 资金口径的 OI 确认实现。
- 我的判断：
  - 持仓兴趣有外部研究先验，含义接近“价格趋势背后是否有新资金/套保需求承诺”，比继续救坏窗口日期或品种更低过拟合。
  - 但 OI 不是方向圣杯；它更可能改善水下/回撤体验，不一定提高任意启动收益胜率。
  - 因此本阶段只测一个固定结构：`63日价格动量` 必须被 `63日总持仓增长` 确认，周频调仓，不扫窗口、不扫阈值。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage425_stage103_open_interest_confirmation_overlay.py`
- 修改脚本：无正式策略默认修改。
- 删除脚本：无。
- 新增参数：
  - `LOOKBACK_DAYS = 63`
  - `REBALANCE_EVERY = 5`
  - `OI_BEST1_VARIANT = stage103_plus_oi_confirm63_best1_weekly_guard`
  - `OI_TOP3_VARIANT = stage103_plus_oi_confirm63_top3_weekly_guard`
  - 每品种 `1` 手，沿用 Stage103 `1.10x` broker 保证金闸门。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：Stage079/Stage103 账户口径 `615,000`，即 `50万C3下单 + 11.5万外部现金`，不增加外部资金。
- 成本口径：正常成本 `1x`，并额外做 `2x/3x/5x` 滑点压力。
- 样本过滤：无品种黑名单、无年份排除、无日期过滤。
- 策略/归因口径：
  - 从原始 TQSDK 逐合约日线汇总每个品种每日总持仓兴趣和成交量。
  - `price_mom_63` 与 `oi_growth_63` 均 shift 一日，只使用入场前已知数据。
  - 仅当 `oi_growth_63 > 0` 时允许该品种进入排名；动量多空按 `price_mom_63 * oi_growth_63` 排序。
  - `best1` 每5个交易日取最强多头和最弱空头各1个品种；`top3` 各3个品种；每品种1手。

## 结果

- Stage079：
  - 期末权益 `31,040,650`
  - 总收益 `4947.2602%`
  - 最大回撤 `-29.7007%`
  - Sharpe `1.3188`
  - Ulcer `15.0874`
  - 总滑点 `1,556,750`
  - 总交易次数 `757`
  - 日度胜率 `36.2924%`
- Stage103：
  - 期末权益 `31,730,915`
  - 总收益 `5059.4984%`
  - 最大回撤 `-28.9792%`
  - Sharpe `1.3681`
  - Ulcer `14.3132`
  - 总滑点 `1,569,265`
  - 总交易次数 `1,217`
  - 日度胜率 `43.0809%`
- `stage103_plus_oi_confirm63_best1_weekly_guard`：
  - 期末权益 `32,157,075`
  - 总收益 `5128.7927%`
  - 最大回撤 `-26.8963%`
  - Sharpe `1.4092`
  - Ulcer `13.5225`
  - 总滑点 `1,582,475`
  - 总交易次数 `1,631`
  - 日度胜率 `50.0000%`
  - 3个月/6个月体验分 `146.4538 / 155.0300`
  - 3个月目标改善 `6/8`，6个月目标改善 `8/8`
  - 多起点回撤30内全部通过。
  - 成本压力：`1x/2x/3x/5x` 最大回撤 `-26.8963%/-28.3111%/-30.1437%/-39.4600%`；`5x` 相对 Stage103 略劣。
  - 相对 Stage103 任意启动收益胜率：`90/180/252/504` 日为 `45.3849%/36.1333%/32.2972%/30.4372%`，中位收益差分别为 `-0.1244pp/-0.3804pp/-0.9026pp/-3.1543pp`。
- `stage103_plus_oi_confirm63_top3_weekly_guard`：
  - 期末权益 `32,287,570`
  - 总收益 `5150.0114%`
  - 最大回撤 `-26.9944%`
  - Sharpe `1.4200`
  - Ulcer `13.3869`
  - 总滑点 `1,600,745`
  - 总交易次数 `2,325`
  - 日度胜率 `50.8486%`
  - 3个月/6个月体验分 `155.0160 / 164.4191`
  - 3个月目标改善 `8/8`，6个月目标改善 `8/8`
  - 失败项：`start_2022` 最大回撤 `-35.4490%`，`start_2024/phase_2024_2025` 最大回撤 `-31.9096%`，冷启动破30。
  - 相对 Stage103 任意启动收益胜率：`90/180/252/504` 日为 `43.2238%/31.1122%/30.5002%/27.7809%`。
- 其他关键指标：
  - `best1` 和 `top3` 的全周期核心指标都优于 Stage079 和 Stage103，且不是由单一最大贡献日支撑；`best1` 剔除最大20个相对 Stage103 贡献日后，收益仍高 Stage103 `17.2740pp`。
  - 但它们的任意启动收益胜率明显不足，说明新增 OI 腿更偏“少数窗口显著改善 + 风险水下体验改善”，不是“任何起点都更容易赚更多”。
  - `top3` 因冷启动破30直接淘汰；`best1` 因 `5x` 成本压力相对 Stage103 略劣且任意启动收益胜率不足，不升执行候选。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_report_stage425_stage103_open_interest_confirmation_overlay_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_summary_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_horizon_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_score_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_gate_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- fresh start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_fresh_start_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_cost_stress_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- pairwise rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_pairwise_rolling_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_daily_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- overlay daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_overlay_daily_stage425_stage103_open_interest_confirmation_overlay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_decision_stage425_stage103_open_interest_confirmation_overlay_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage425_stage103_open_interest_confirmation_overlay_chart_stage425_stage103_open_interest_confirmation_overlay_v1.png`

## 结论

- 本阶段结论：`no_new_promotion`。OI 确认动量是有信息的研究线索，尤其能改善左尾和水下体验；但不值得升级为 Stage103 后继执行候选。
- 是否进入下一步：不继续围绕 OI 确认主动优化。
- 下一步：
  - 主执行相对候选仍是 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
  - `best1` 可作为 paper/诊断观察项保存，但不接入当前执行准备。
  - 禁止继续扫 `21/42/84/126` OI窗口、OI增长阈值、成交量阈值、top_n、再平衡频率、日期或品种过滤救援。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合；如果继续调 OI 窗口、阈值或品种过滤救 `best1/top3`，会转为过拟合。
- 原因：本阶段来自外部文献先验和固定低自由度结构；失败后主动停止，没有按 `start_2022/start_2024` 或 `5x` 成本压力去补丁。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：OI 子路线继续主动优化价值低；总目标仍有价值，但当前更应该回到 Stage103 工程化复跑、paper/影子盘和真实券商保证金接入，或寻找样本更充分、保证金更轻、风险源更不同的外生收益腿。
- 原因：OI 确认已经证明能改善风险体验，但任意启动收益胜率不足，这和“任何时候启动、启动多久都更舒服”的核心要求冲突。继续救它大概率会变成窗口和路径拟合。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage125 边界。
- 是否更新 `research/registry.md`：是，最新阶段更新为 Stage125。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 OI 确认路线停止摘要。
