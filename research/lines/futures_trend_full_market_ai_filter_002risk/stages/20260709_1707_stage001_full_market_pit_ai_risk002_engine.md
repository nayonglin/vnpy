# Stage001 全市场 PIT AI 过滤 + 0.02 基础风险真实引擎

- line_id：`futures_trend_full_market_ai_filter_002risk`
- 当前模式：`day`
- 记录时间：`2026-07-09 17:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：独立研究线最小 A/C 真实引擎回测
- 是否重要突破：否，第一关验证
- 是否触发A/B：是，A=官方 C9/15w；C=全市场 PIT AI top8 + risk_ratio_* 0.02

## 外部调研与判断

- 参考资料：Hudson & Thames meta-labeling、AQR managed futures、QuantInsti cross-sectional momentum ML、stefan-jansen/machine-learning-for-trading。
- 我的判断：AI/ML 更适合作为趋势策略外层过滤或排序，不应直接改趋势入场/退出；全市场排序必须 PIT、walk-forward、多起点验证。

## 本次变更

- 新增脚本：`research/lines/futures_trend_full_market_ai_filter_002risk/tools/stage001_full_market_pit_ai_risk002_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`TOP_N=8`、`TARGET_BASE_RISK_RATIO=0.02`、`RECENT_PROFIT_DAYS=126`、`RECENT_LOSS_DAYS=63`、`MIN_HISTORY_DAYS=40`
- 修改参数：候选 C 显式覆盖 `risk_ratio_of_total_assets/breakout/ma_cross/open_interest_surge/open_interest_decline/volume_open_interest_surge=0.02`；`product_universe_csv_path` 改为 full-market 57 品种；AI strategy 改为本阶段 PIT eligibility。
- 删除参数：候选 C 不强制固定 `fu.SHFE` satellite。

## 回测/归因参数

- 数据区间：`2020-01-01` 到 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿用 C9 真实引擎原成本/slippage 配置。
- 样本过滤：当前 full-market eligible 57 品种，月度 PIT top8。
- 策略/归因口径：A 复用 Stage167 官方 C9/15w 曲线；C 新跑真实引擎。

## 结果

- A 期末权益：`5,979,281.00`；总收益 `3886.1873%`；最大回撤 `-55.3701%`；Sharpe `1.3959`
- C 期末权益：`268,976.10`
- C 总收益：`79.3174%`
- C 最大回撤：`-69.1326%`
- C Sharpe：`0.4442`
- C 总滑点：`51,670.00`
- C 总交易次数：`531`
- C 胜率：`50.3356%`，口径为非零交易日胜率，不是逐笔胜率。
- C 最大 broker10 保证金/权益：`113.2057%`
- C 相对 A 收益差：`-3806.8699` 百分点；回撤差：`-13.7624` 百分点。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_report_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_ac_summary_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv`
- eligibility：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_eligibility_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv`
- feature_panel：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_feature_panel_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv.gz`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_candidate_daily_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_full_market_ai_filter_002risk/outputs/stage001_full_market_pit_ai_risk002_engine/full_market_ai002_stage001_full_market_pit_ai_risk002_engine_ai_usage_audit_stage001_full_market_pit_ai_risk002_engine_v2_rankfix.csv`

## 结论

- 本阶段结论：`stage001_stop_or_attribution_before_more_runs`
- 是否进入下一步：不进入逐半年多周期。
- 下一步：停止候选推进，先做只读归因；重点解释全市场 PIT top8 为什么错过官方 C9 的核心右尾、哪些被拦截/放行品种造成损失。

## 独立 Agent Review

- review 时间：`2026-07-09 17:26 CST`
- reviewer 结论：未发现 P0；v2_rankfix 的 PIT、同日使用、rank 方向、eligibility schema、full-market universe 接线、AI filter 接线和 `risk_ratio=0.02` 接线没有发现明显错误。
- reviewer 置信度：中；未重跑引擎，未深审 Stage124 上游 single-product daily 生成链。
- P1：AI usage audit 只能证明过滤器运行时生效，不能证明 AI 选品有正贡献；本阶段结果本身明显失败。
- P2：decision 逻辑把冷启动两个月 `selected_count=0` 也纳入 `min_selected_count`，如果未来结果变好会误判；2026-03 后旧特征缺失，旧特征变为中性 tie-breaker，应在后续报告显式标注。
- review 后决策：不扩展逐半年多周期，不扫 topN/窗口/权重/风险小数；如继续，只做归因。

## 过拟合反思

- 运行前判断：是，有明显风险，因为全市场收益记忆可能追历史赢家。
- 运行后判断：是，继续救参风险高；本阶段没有根据结果调整 topN、窗口、权重或风险小数。
- 原因：全市场 + profit-memory 的结构天然容易追历史赢家，当前结果已经劣于官方，不应继续扫参。

## 继续价值反思

- 运行前判断：有价值，因为它检验用户提出的结构性问题。
- 运行后判断：作为候选推进没有价值；作为归因有价值。
- 原因：C 收益、回撤、Sharpe、broker10 都劣于 A；下一步价值在解释错过核心右尾，不在扩大回测矩阵。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage001 状态。
- 是否更新 `research/registry.md`：本阶段已在建线时新增索引，暂不进一步改。
- 是否追加根目录 `memory.md/back_log.md`：已追加 `back_log.md`，不改 `memory.md`。
