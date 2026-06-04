# Stage273 真实舆情/事件账本最小闭环

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 02:04 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据工程与可执行性审计；不生成交易候选，不做收益回测，不修改策略规则。
- 是否重要突破：否，但把 Stage272 的真实 sentiment/news/manual event ledger 缺口从 `0/1` 推进到 `1/1` 的最小闭环。
- 是否触发A/B：否。没有形成可接入正式版本的新策略。

## 外部调研与判断

- 参考资料：
  - USDA/NASS `Crop Progress` 是官方周度报告，ESMIS 页面显示该报告为 weekly，`2026-06-01 4:00 PM` 为最新 release；官方 txt 文件 `prog2226.txt` 明确为 `2026-06-01` 发布。
  - 官方文本给出 2026-05-31 当周美国玉米、黄豆进度和首次作物评级：玉米 planted `93%`、emerged `76%`、good/excellent `67%`；黄豆 planted `87%`、emerged `65%`、good/excellent `66%`。
- 我的判断：
  - 这类报告适合做农产品链的 forward manual_event / sentiment_news 账本样本，因为来源稳定、发布时间明确、能映射到交易品种。
  - 但它不是 alpha 结论：一个样本无法证明预测力，也不能回填进历史 selector。
  - 对本线最有用的是建立 `received_at/source_url/published_at/raw_text_hash/product_mapping/status` 的可审计流程。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage572_real_sentiment_event_ledger_bootstrap.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `usable_for_forward_monitor=1`
  - `usable_for_history_selector=0`
  - `POINT_IN_TIME_RULE`：只能使用 `received_at_local <= selector_eval_time` 前已落盘的记录，禁止历史回填。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用。本阶段不是收益回测。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只记录本次真实接收时间：`received_at_local=2026-06-03 02:03 CST` 附近。
  - source claimed time 使用 `published_at=2026-06-01T16:00:00-04:00`，不得替代 `received_at`。
  - 所有行 `usable_for_history_selector=0`。
- 策略/归因口径：
  - 来源：USDA NASS Crop Progress 官方 txt。
  - route：`manual_event`。
  - 映射方法：`keyword_manual_usda_crop_to_cn_futures`。
  - 映射产品：`c.DCE`、`m.DCE`、`y.DCE`。

## 结果

- 决策：`real_event_ledger_started_predictive_audit_still_blocked`
- 总闸门：`12/15`
- ledger qualification：`12/12`
- predictive readiness：`0/3`
- 真实 ledger rows：`3`
- 映射产品数：`3`
- history selector 可用行数：`0`
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - `c.DCE`：corn progress/condition，sentiment_score `-0.25`，relevance `0.65`。
  - `m.DCE`：soybean-chain supply monitor，sentiment_score `-0.20`，relevance `0.50`。
  - `y.DCE`：soybean-chain supply monitor，sentiment_score `-0.20`，relevance `0.50`。
  - Stage561 样本深度仍为 runs `2/20`、dates `2/20`，所以 selector predictive audit 仍阻塞。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_chart_stage572_real_sentiment_event_ledger_bootstrap_v1.png`
- 左上：`manual_event/ok` 共有 `3` 行，说明这次不是模板空壳，而是真实映射后的事件账本。
- 右上：`c.DCE/m.DCE/y.DCE` 的 sentiment_score 均为负，符合“美国作物进度和状态偏供给宽松”的人工方向标记；但这只是事件语义，不是交易信号。
- 左下：`c.DCE` 相关性最高 `0.65`，`m/y` 为 `0.50`，反映玉米是直接映射，豆粕/豆油是黄豆链映射，质量低一档。
- 右下：ledger qualification 全绿，但 predictive readiness 三项红色，视觉上明确保留边界：账本已启动，预测力审计仍不允许。

## 输出文件

- real ledger：`examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger/sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv`
- event summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_event_summary_stage572_real_sentiment_event_ledger_bootstrap_v1.csv`
- product summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_product_summary_stage572_real_sentiment_event_ledger_bootstrap_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_gates_stage572_real_sentiment_event_ledger_bootstrap_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_decision_stage572_real_sentiment_event_ledger_bootstrap_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_report_stage572_real_sentiment_event_ledger_bootstrap_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_chart_stage572_real_sentiment_event_ledger_bootstrap_v1.png`

## 结论

- 本阶段结论：
  - Stage272 的 `sentiment/news/manual event ledger` 最小缺口已启动：现在有真实 `received_at`、source URL、published_at、hash 和产品映射。
  - 但该账本只能进入 forward monitor，不能进入历史 selector，也不能用于收益回测。
  - 当前路线仍然卡在样本深度：`2/20` runs、`2/20` dates。
- 是否进入下一步：是，但仍是数据累计和 paper monitor。
- 下一步：
  - 每个新自然日继续累计 Stage549 basis/inventory forward snapshot。
  - 同步累计真实事件账本，优先来源：USDA/NASS 农产品、EIA 能源、交易所公告、国内产业/库存官方或准官方源。
  - 达到 `20/20` 后，按 Stage561 固定协议做 `63/126` 日 product trend PnL 的 IC/bucket/paper sleeve 审计。

## 过拟合反思

- 运行前判断：不是过拟合。目标是补真实前视事件账本，不使用未来收益。
- 运行后判断：不是过拟合。所有行强制 `usable_for_history_selector=0`，预测闸门仍保持失败。
- 原因：
  - 没有修改交易逻辑。
  - 没有根据历史收益挑事件或挑品种。
  - 映射结果只允许 forward monitor。

## 继续价值反思

- 运行前判断：有价值。Stage272 明确 sentiment/news ledger 是硬缺口，补上最小闭环后才有资格继续观测。
- 运行后判断：有价值，但不能扩大解释。
- 原因：
  - 已经把“舆情路线只有模板”推进到“有真实可审计样本”。
  - 但样本仍只有一个发布日期和三条产品行，离预测力审计差很远。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage572_real_sentiment_event_ledger_bootstrap.py`：通过。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage572_real_sentiment_event_ledger_bootstrap.py`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage572_real_sentiment_event_ledger_bootstrap_decision_stage572_real_sentiment_event_ledger_bootstrap_v1.json`：通过。
- 图表已视觉检查，并修正失败闸门 0 宽度不可见的问题。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是数据资格推进，不是策略突破。
