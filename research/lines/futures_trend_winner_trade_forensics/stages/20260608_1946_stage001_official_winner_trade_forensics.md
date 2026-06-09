# Stage001 正式版历史赢家逐笔法证复盘首版

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-08 19:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：从当前官方实盘 Stage372/20万重跑全周期，只读导出逐笔成交、入场诊断、候选快照和 closed-lot 法证表。
- 是否重要突破：否；属于首版证据表和线索筛查。
- 是否触发A/B：否。本阶段是只读归因，不是候选策略接入；若后续交易化，必须另走 A/B 或 A/C。

## 外部调研与判断

- 参考资料：
  - R-multiple/expectancy：`https://vantharpinstitute.com/tharp-think-trading-concepts/`
  - R-multiple trade journaling：`https://crosstrade.io/learn/performance-metrics/r-multiple`
  - MFE/MAE trade replay/review：`https://www.tradesviz.com/trade-replay/`
  - Python backtest/trade stats参考：`https://github.com/arman-bd/tradepruf`
- 我的判断：赢家逐笔复盘必须用 R、MFE、MAE、退出效率和跨年份稳定性，而不是只找历史赢家共同点。趋势系统天然依赖少数右尾，单纯提高胜率不是核心；更重要的是识别哪些入场状态更容易产生右尾，同时确认这些状态不会只在单一年份/品种有效。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage719_official_winner_trade_forensics.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `BIG_WINNER_QUANTILE=0.80`
  - `MIN_FEATURE_COUNT=8`
  - `quality_winner = winner & MFE>=2R & MAE<=1.2R & exit_efficiency>=0.35`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：当前 official Stage372 全周期，`2020-01-01~2026-04-30` 口径。
- 账户规模：`200,000`。
- 成本口径：策略正式版成本照常用于回测；closed-lot 表中的 `realized_pnl` 是 FIFO 配对后的逐笔 gross PnL，不直接等同账户净权益。
- 样本过滤：不按年份、品种、方向、红框窗口筛选；特征桶样本数小于 `8` 不进入 feature quality 表。
- 策略/归因口径：当前官方实盘 `official_live_stage372_20w_recovery_sleeve` / `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`；只读导出 `trades`、`entry_risk`、`entry_candidates`、`trade_events`、`positions`，并用真实成交 FIFO 配对开平。

## 结果

- 正式版账户参考结果：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
- Stage719 closed-lot 法证结果：
  - closed lots `320`
  - raw trades `633`
  - entry risk diagnostics `315`
  - entry candidates `1,082`
  - winner lots `145`
  - winner rate `45.3125%`
  - big winner lots `28`
  - big winner threshold `3.8908R`
  - quality winner lots `63`
  - gross realized PnL `8,866,465`
  - avg R `0.4971`
  - median R `-0.1818`
  - p90 R `3.7177`
  - p10 R `-1.7117`
  - median MFE `1.4905R`
  - median MAE `0.8642R`
- 初步正向线索：
  - `loss_streak_1_2`：`118` 笔，胜率 `53.3898%`，big winner rate `13.5593%`，avg R `1.8309`，total gross PnL `6,317,280`，年份正贡献 `6/7`。这是目前最像“相对可靠”的账户状态线索。
  - `risk_normal`：`262` 笔，胜率 `49.6183%`，big winner rate `10.3053%`，avg R `0.7473`，total gross PnL `9,180,510`，年份正贡献 `6/7`。赢家主要来自正常风险档，不是 0.1 档。
  - `rollover_reopen`：`22` 笔，胜率 `54.5455%`，big winner rate `13.6364%`，avg R `1.0836`，年份正贡献 `6/6`。样本较小，但值得继续复核。
  - `stop_1_2pct`：`106` 笔，胜率 `50.9434%`，big winner rate `11.3208%`，avg R `1.0187`，年份正贡献 `5/7`。止损距离过近或过远都不稳。
  - `active_0`：`83` 笔，胜率 `49.3976%`，avg R `1.0679`，total gross PnL `5,510,850`，年份正贡献 `5/7`。空仓/低并发入场可能更干净。
  - `long_rsi_60_70`：`67` 笔，avg R `1.0547`，quality winner rate `26.8657%`，年份正贡献 `5/7`。长侧强但不过热可能有线索。
- 明确反证：
  - `risk_floor_01`：`51` 笔，胜率 `19.6078%`，big winner rate `1.9608%`，avg R `-0.7885`，年份正贡献 `1/7`。
  - `loss_streak_ge3`：`64` 笔，胜率 `21.8750%`，big winner rate `1.5625%`，avg R `-1.3237`，年份正贡献 `1/7`。
  - `recovery`：`13` 笔，胜率 `30.7692%`，big winner rate `0%`，avg R `-3.4233`，年份正贡献 `1/5`。
  - AI rank 不单调：`rank_7_9` 的 avg R `0.8970`，`rank_1_3` 为 `0.4645`，`rank_4_6` 为 `0.3028`，`rank_gt9` 接近 `0.0070`。不能直接用 AI rank top 更高来解释赢家。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_report_stage719_official_winner_trade_forensics_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_chart_stage719_official_winner_trade_forensics_v1.png`
- closed lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_closed_lots_stage719_official_winner_trade_forensics_v1.csv`
- feature quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_feature_quality_stage719_official_winner_trade_forensics_v1.csv`
- top winners：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_top_winners_stage719_official_winner_trade_forensics_v1.csv`
- year stability：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_year_stability_stage719_official_winner_trade_forensics_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_trades_stage719_official_winner_trade_forensics_v1.csv`
- entry risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_entry_risk_stage719_official_winner_trade_forensics_v1.csv`
- entry candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_entry_candidates_stage719_official_winner_trade_forensics_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage719_official_winner_trade_forensics_decision_stage719_official_winner_trade_forensics_v1.json`

## 结论

- 本阶段结论：`winner_forensics_readonly_first_pass_no_promotion`。首版已经能看到一些相对可靠的账户状态线索：赢家更集中在正常风险、连败 `1~2`、低并发/空仓、合理止损距离、部分 rollover reopen；而连败 `>=3`、`0.1` 风险档、recovery sleeve 自身并不是赢家来源。
- 是否进入下一步：是。
- 下一步：把候选线索做 walk-forward/留一年验证。不要直接交易化；先检验 `loss_streak_1_2`、`risk_normal`、`active_0`、`stop_1_2pct`、`long_rsi_60_70`、`rollover_reopen` 是否能在训练窗口识别未来大赢家，同时控制误杀率。

## 过拟合反思

- 运行前判断：过拟合风险高。赢家复盘天然容易把历史右尾包装成规则。
- 运行后判断：仍有过拟合风险，但本阶段保持只读，风险可控；目前最有价值的是反证而非正向规则。
- 原因：正向特征如 `short_rsi_30_40` 样本只有 `19` 笔且年份正贡献 `4/7`，不能直接用；更稳的 `loss_streak_1_2/risk_normal` 是账户状态层线索，但也需要 walk-forward 验证。

## 继续价值反思

- 运行前判断：有价值。此前连败阈值研究说明我们需要识别高质量机会，但不能红框倒推。
- 运行后判断：有价值继续。Stage719 给出了候选特征和反证特征，下一步可以转成预声明 selector 验证。
- 原因：`loss_streak_ge3/risk_floor_01/recovery` 明确偏弱，能解释为什么 0.1 档很难产生右尾；`loss_streak_1_2/risk_normal/active_0/stop_1_2pct` 具备一定跨年稳定性，值得进一步验证。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：已在新建研究线时登记。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选合入。
