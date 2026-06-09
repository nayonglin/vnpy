# Stage407 正式版 Stage372 原 AI 池 + 鸡蛋参与 AI 重排 top9 回测

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 11:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前正式版 Stage372/20万扩池纠正实验
- 是否重要突破：否，但完成“鸡蛋真正参与 AI 选品”的定义修正
- 是否触发A/B：是，属于可能接入正式版的品种池/AI gate 候选

## 外部调研与判断

- 参考资料：
  - Man Group `A Trend Following Deep Dive: The Optimal Market Mix for a Trend Follower`：趋势跟踪的市场组合本身会改变机会分布和组合效率，市场选择不是中性操作。
  - Aspect Capital `Diversification in Trend Following`：趋势跟踪依赖跨市场分散机会，但不同市场的流动性、相关性和组合方式会改变风险收益。
  - GitHub `quantiacs/strategy-futures-trend-following`：公开模板强调多市场趋势策略需要先定义可交易市场与指标，不等于盲目扩全市场。
- 我的判断：用户要求“鸡蛋也要参与 AI 选品”是合理的定义修正。本阶段应只把候选集限定为“当月正式 AI 原选中产品 + 鸡蛋”，再用现有 AI 预测分数重排取 `top9`，避免 Stage405 那种 full-market 重排污染原池，也避免 Stage406 那种手工追加鸡蛋。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5.py`
- 修改正式策略：无。
- 删除脚本：无。
- 新增参数：
  - `jd.DCE`
  - `AI_STRATEGY="stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_entry_filter"`
  - `AI_SCORE_TYPE="stage694_original_ai_pool_plus_jd_probability_rerank_top9"`
  - `max_concurrent_positions=5`
- 修改参数：
  - B 分支只把 `maxpos4` 改为 `maxpos5`。
  - C 分支每个有 AI 预测覆盖的 eval_date，把候选集限制为“正式 AI 当月原产品 + `jd.DCE`”，按 full-market AI 概率分数重新排序，只保留 `top9`。
  - 2020-2021 full-market AI 预测未覆盖，C 沿用正式 AI 快照，不强行放行鸡蛋。
- 删除参数：无。
- 正式配置：未修改。
- CTP/下单：未连接 CTP，未调用 order API。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`200,000`
- 成本口径：正常成本、`2x`、`3x` 滑点压力。
- AI 覆盖：生成 eligibility `2019-12-31` 至 `2026-02-27`，2022-01-28 起鸡蛋参与 AI 重排；本次回测数据止于 2026-04-30，故 2026-03/04 继续使用 2026-02-27 快照。
- 策略/归因口径：
  - A：当前正式版 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`
  - B：只放宽并发 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos5`
  - C：原 AI 池 + 鸡蛋参与 AI 重排 top9 + maxpos5 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5`

## 结果

- A 当前正式版：
  - 期末权益 `8,728,285`
  - 总收益 `4264.1425%`
  - 最大回撤 `-38.6713%`
  - Sharpe `1.6279`
  - 总滑点 `506,220`
  - 总交易次数 `633`
  - 胜率 `52.2586%`
  - broker10 峰值 `79.6015%`
  - 强制减仓 `6` 次，`299` 手
- B 仅 maxpos5：
  - 期末权益 `7,511,205`
  - 总收益 `3655.6025%`
  - 最大回撤 `-38.7987%`
  - Sharpe `1.5831`
  - 总滑点 `434,330`
  - 总交易次数 `661`
  - 胜率 `52.2748%`
  - broker10 峰值 `77.3076%`
  - 强制减仓 `15` 次，`474` 手
- C 原 AI 池 + 鸡蛋参与 AI 重排 top9 + maxpos5：
  - 期末权益 `3,284,935`
  - 总收益 `1542.4675%`
  - 最大回撤 `-33.2821%`
  - Sharpe `1.3858`
  - 总滑点 `298,030`
  - 总交易次数 `688`
  - 胜率 `51.7181%`
  - broker10 峰值 `82.6211%`
  - 强制减仓 `14` 次，`361` 手
  - 收益保留 `36.1730%`
- C 相对 B：
  - 期末权益 `-4,226,270`
  - 总收益 `-2113.1350pp`
  - 最大回撤改善 `+5.5166pp`
  - Sharpe `-0.1973`
  - 交易 `+27`
  - 2x/3x 成本 DD 改善 `+5.6634pp/+5.8045pp`
- C 相对 A：
  - 期末权益 `-5,443,350`
  - 总收益 `-2721.6750pp`
  - 最大回撤改善 `+5.3892pp`
  - Sharpe `-0.2421`
  - 交易 `+55`
  - 2x/3x 成本 DD 改善 `+5.5393pp/+5.6832pp`
- 成本压力：
  - C `2x/3x` 成本 DD 为 `-35.1162%/-37.0817%`，风险路径优于 A，但收益大幅不足。
- AI 审计：
  - 鸡蛋进入 AI top9 `46/51` 个 eval_date，选择率 `90.1961%`。
  - 2022-01-28 起有预测覆盖的月份中，鸡蛋多数进入 top9；例如 2025-04-30、2025-09-30 排名第 `1`。
- 产品归因：
  - 鸡蛋自身净 PnL `+21,990`
  - C 相对 A 主要改善：`ma +355,040`、`ap +277,200`、`hc +225,320`、`sp +45,940`、`sh +26,280`、`jd +21,990`
  - C 相对 A 主要恶化：`jm -2,214,690`、`fu -848,070`、`lc -700,480`、`lh -542,560`、`si -536,025`、`oi -521,420`、`au -282,400`
- 年度 C：
  - 2020：`356,965`，收益 `78.4825%`，DD `-17.5900%`
  - 2021：`885,805`，收益 `135.9630%`，DD `-24.1702%`
  - 2022：`1,063,365`，收益 `19.9854%`，DD `-33.2821%`
  - 2023：`2,062,415`，收益 `82.5639%`，DD `-14.1329%`
  - 2024：`2,730,780`，收益 `32.5805%`，DD `-25.0580%`
  - 2025：`2,877,140`，收益 `8.8408%`，DD `-18.3199%`
  - 2026：`3,284,935`，收益 `12.9993%`，DD `-17.1338%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_report_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_summary_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_daily_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1.csv`
- product_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_product_delta_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_chart_stage694_official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_v1.png`

## 结论

- 本阶段结论：`official_stage372_original_ai_plus_jd_ai_rerank_top9_maxpos5_rejected`
- 是否进入下一步：不进入正式版，不继续围绕 topN/maxpos 救援。
- 核心判断：
  - 鸡蛋这次确实参与 AI 选品，且进入 top9 的频率很高，说明“鸡蛋没参与 AI”已经被修正。
  - 但结果比 Stage406 手工追加鸡蛋差得多。鸡蛋自身只贡献 `+21,990`，不是主要收益源；AI 重排把原正式右尾中的 `jm/fu/lc/lh/si/oi` 等贡献显著压低。
  - 因此问题不是鸡蛋能不能被 AI 选中，而是当前 AI 重排分数在这个受限小池里不具备替代正式原池排序的泛化能力。
- 下一步：
  - 不把 Stage407 替换正式版。
  - 不扫 `top8/top10`、`maxpos6` 或鸡蛋月份补丁。
  - 若继续研究鸡蛋，优先走 Stage406 类型的独立防守 sleeve / 非挤占式风险槽，而不是让它进入主 AI 排名挤占核心右尾。

## 过拟合反思

- 运行前判断：不是过拟合；这是对实验定义的必要修正，限制候选集为“原池 + 鸡蛋”，不是全市场扫描。
- 运行后判断：本阶段本身不是过拟合，但结果提示继续用 topN/maxpos 救它会变成过拟合。
- 原因：失败来自核心右尾品种被 AI 重排挤出或路径压低，不是某一个小阈值问题。

## 继续价值反思

- 运行前判断：有价值；它直接回答“鸡蛋是否真正参与 AI 选品”。
- 运行后判断：作为主策略候选没有继续价值；作为 AI gate 归因和鸡蛋独立 sleeve 的证据仍有价值。
- 原因：鸡蛋被 AI 高频选中但组合收益大幅下降，说明当前 AI 排名不应在小池里替代正式排序；后续价值在解释 AI 选品机制和设计非挤占式结构。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage407 纠正结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：是，属于正式候选纠正反证。
