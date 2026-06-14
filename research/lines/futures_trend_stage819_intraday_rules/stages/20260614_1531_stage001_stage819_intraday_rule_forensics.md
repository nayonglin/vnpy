# Stage001 Stage819候选分钟级规则逐笔法证

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-14 15:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读逐笔法证、分钟K覆盖率检查、入场日分钟图谱与规则形状诊断
- 是否重要突破：否。本阶段只形成证据台账，不升级规则，不改正式版。
- 是否触发A/B：否。所有规则均为 `diagnostic_only_not_promoted`，未达到接入正式候选或第78/Stage372正式基准的条件。

## 外部调研与判断

- 参考资料：
  - GitHub `je-suis-tm/quant-trading` 中的 opening range / London breakout 规则样例。
  - GitHub `yulz008/GOLD_ORB` 中开仓同时放置止损止盈的黄金 ORB 样例。
  - SSRN opening range breakout 相关论文。
  - ResearchGate Timely Opening Range Breakout on Index Futures Markets 论文页。
- 我的判断：
  - 可借鉴的是低自由度的规则形状：开盘区间突破、固定风险止损/止盈、实时止损、收盘前/确认后处理。
  - 不能复制外部参数，也不能围绕 Stage819 的几笔大赢家/大亏损反推分钟阈值。
  - 本阶段只把规则形状映射到候选版逐笔台账，生成下一步 A/C 的候选假设；不把诊断分桶当成真实策略收益。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage825_stage819_intraday_rule_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增研究线：`research/lines/futures_trend_stage819_intraday_rules/LINE.md`
- 新增阶段记录：本文件
- 新增参数：
  - `MODEL_TAG=stage825_stage819_intraday_rule_forensics_v1`
  - `START=2018-01-01`
  - `END=2026-05-29`
  - `CAPITAL=Stage819 30w`
  - `OPENING_RANGE_BARS=15`
  - `FAST_WINDOWS=(15, 30, 60, 120)`
  - `RISK_R_MULTIPLES=(0.5, 1.0, 2.0)`
  - `PER_PAGE=4`
  - `MAX_ATLAS_PAGES=0`，即生成全量图谱页
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2018-01-01 至 2026-05-29
- 账户规模：30万，沿用 Stage819 候选配置
- 成本口径：沿用 Stage819 回测成本口径；本阶段不改手续费/滑点/保证金口径
- 分钟数据来源：
  - `qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv`
  - `qmt_roll_stage498_actual_trade_fill_key_readiness_completed_minute_bars_stage498_actual_trade_fill_key_readiness_v1.csv`
- 样本过滤：Stage819 候选全周期 closed lots，共 341 笔；入场日分钟K覆盖 227 笔，覆盖率 66.57%
- 策略/归因口径：
  - 只读复跑 Stage819 primary official candidate：`official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`
  - 不修改 Stage372/20w 官方正式版
  - 不连接 CTP，不调用下单 API
  - 对每笔 closed lot 计算入场日 MFE/MAE、OR15 突破确认、15/30/60/120分钟窗口、0.5R/1R/2R 先后触发、0.5R 止损后重试穿越次数

## 结果

- 期末权益：26,322,730
- 总收益：8,674.24%
- 最大回撤：-54.75%
- Sharpe：1.436
- 总滑点：2,149,150
- 总交易次数：666
- 胜率：53.11%
- closed lots：341
- 入场日分钟K覆盖：227/341，66.57%
- 新增回测结果：
  - R1 OR15确认后入场：覆盖 188 笔，覆盖样本总PnL 31,693,805，覆盖样本胜率 54.26%；诊断有效但不晋级。
  - R2 30分钟0.5R失败快速止损/重试：覆盖 292 笔，覆盖样本总PnL 35,153,400，剔除样本总PnL -6,981,520；值得进入冻结 A/C。
  - R3 1R目标先于1R止损：覆盖 178 笔，覆盖样本总PnL 39,498,320，胜率 60.11%；是最强的质量过滤证据，但有明显事后标签风险，必须改写为逐分钟实时语义后再测。
  - R4 60分钟内1R确认后追踪：覆盖 56 笔，覆盖样本总PnL 16,204,420，胜率 60.71%；样本少，不能单独推广。
  - R5 0.5R止损后允许重试：覆盖 46 笔，覆盖样本总PnL 1,281,825，胜率 39.13%；单独看价值不足。
- 修改回测结果：无
- 删除回测结果：无

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_report_stage825_stage819_intraday_rule_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_summary_stage825_stage819_intraday_rule_forensics_v1.csv`
- curve：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_curve_stage825_stage819_intraday_rule_forensics_v1.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_trades_stage825_stage819_intraday_rule_forensics_v1.csv`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_closed_lots_stage825_stage819_intraday_rule_forensics_v1.csv`
- intraday_features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_intraday_features_stage825_stage819_intraday_rule_forensics_v1.csv`
- rule_candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_rule_candidates_stage825_stage819_intraday_rule_forensics_v1.csv`
- coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_minute_coverage_stage825_stage819_intraday_rule_forensics_v1.csv`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_atlas_manifest_stage825_stage819_intraday_rule_forensics_v1.csv`
- atlas：86 页 PNG，`qmt_roll_stage825_stage819_intraday_rule_forensics_atlas_page001...086_stage825_stage819_intraday_rule_forensics_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage825_stage819_intraday_rule_forensics_decision_stage825_stage819_intraday_rule_forensics_v1.json`
- 文件数量：本阶段输出 100 个文件，其中图谱 86 页。

## 结论

- 本阶段结论：
  - Stage819 候选相对正式版的进攻性很强，但左尾仍重；分钟级规则有继续研究价值，尤其是“错了实时止损、不死扛”和“确认后再持有趋势”。
  - R2、R3、R4 给出了较强的归因信号，但这些只是历史 closed lot 分桶，不是可执行策略收益。
  - R3 的质量过滤信号最强，同时也最容易过拟合，因为“目标先于止损”天然接近事后判断；下一步必须冻结成分钟逐根可执行的入场/退出规则。
  - 入场日分钟数据覆盖率只有 66.57%，2018/2019 和少部分合约存在缺口；因此图谱已经覆盖全量 closed lots 的索引，但不是每笔都有可视化K线。
- 是否进入下一步：是
- 下一步：
  - Stage002 固定 1-2 个规则，不再扩大特征表：优先 R2 fail-fast/retry 与 R3 的实时化版本。
  - 写真实分钟级 A/C 引擎语义：逐分钟触发、止损即退出、允许有限重试、成本和滑点实际扣除。
  - 先不讨论接入正式版，先看 A/C 是否能同时改善收益、回撤、交易次数和左尾。

## 过拟合反思

- 运行前判断：否。本阶段不是参数搜索，而是用外部常见日内规则形状做只读法证。
- 运行后判断：当前输出本身不是过拟合；但如果继续围绕 15/30/60/120 和 0.5R/1R/2R 微调，就会快速滑向过拟合。
- 原因：
  - 规则形状来自通用交易机制，而非某一年或某几笔交易。
  - 没有把任何分桶结果接入策略，也没有修改正式配置。
  - 主要风险在下一阶段：如果为了抬收益不断调窗口和R倍数，会把分钟噪声当成规律。

## 继续价值反思

- 运行前判断：有。用户目标是分钟级规则类入场出场，Stage819 候选的高进攻性和高回撤正适合做逐笔法证。
- 运行后判断：有，但必须收窄。继续扩大分析表的价值下降，应转向冻结规则 A/C。
- 原因：
  - R2 显示“早期错误不死扛”可能能切掉一批负贡献样本。
  - R3/R4 显示早期顺势确认和后续趋势持有存在结构性差异。
  - 分钟覆盖缺口会限制结论强度，需要在下一阶段明确只对有分钟数据样本做 A/C，或先补齐关键年份数据。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新为 Stage001 已完成、Stage002 待启动。
- 是否更新 `research/registry.md`：否。按并行研究记录纪律，暂不频繁改 registry，由后续合入者统一整理。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是重要突破、正式候选或跨线合并，只保留在线内记录。
