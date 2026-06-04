# Stage261 选品预测力审计协议冻结

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:48 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：未来外生/舆情 selector 预测力审计预注册；不做收益回测，不生成交易候选。
- 是否重要突破：否；但冻结了未来 `20` 个跨日样本到位后的审计协议，防止事后按结果倒调。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AQR `Demystifying Managed Futures` / managed futures 资料：趋势收益来自多市场、多周期和风险预算，分散有效但不能替代真实 alpha。
  - `pysystemtrade` 文档：多品种系统要重视 instrument diversification、相关性和风险预算，适合作为“扩池但不高相关”的工程先验。
  - Bailey / Lopez de Prado 关于 backtest overfitting、purged/embargoed validation 的资料：金融时间序列标签会跨期重叠，必须防止信息泄漏、样本重叠和多重试验。
  - Point-in-time / look-ahead bias 资料：外生/舆情数据必须使用真实 `received_at`，不能用后来整理出的发布时间或新闻解释回填历史。
- 我的判断：当前继续研究“选对品种”有价值，但在数据到位前先冻结审计协议，比继续写收益回测更重要。否则等 `20` 个样本到位后，最容易发生的错误是临时换窗口、调 TopN、改情绪映射或用 hindsight 产品池。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage561_selector_predictive_audit_protocol.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增输出：
  - protocol JSON。
  - decision JSON。
  - gates CSV。
  - feature spec CSV。
  - label spec CSV。
  - test plan CSV。
  - report。
  - chart。
- 新增参数/闸门：
  - `MIN_FORWARD_RUNS=20`
  - `MIN_FORWARD_DATES=20`
  - `MIN_ACTIVE_ROUTES=2`
  - `MIN_PRODUCTS_PER_ROUTE=20`
  - `MIN_REAL_SENTIMENT_LEDGERS=1`
  - `MIN_EVAL_DATES_FOR_IC=20`
  - `MIN_MEAN_SPEARMAN_IC=0.05`
  - `MIN_POSITIVE_IC_RATE_PCT=60.0`
  - `MAX_SELECTOR_TRIALS_BEFORE_REVIEW=6`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：当前外生 forward ledger，截至 `2026-06-02`；Stage558 历史先验仅作为参考，不作为新收益回测。
- 账户规模：不适用，本阶段不做收益回测。
- 成本口径：不适用。
- 样本过滤：只读取 `external_state_forward_ledger.csv`、Stage560 decision、Stage558 feature prior、Stage559 舆情模板状态。
- 策略/归因口径：预测力审计协议冻结；不训练模型、不形成交易 selector。

## 结果

- 决策：`protocol_frozen_predictive_audit_not_ready`
- 当前进度：
  - forward runs：`1/20`
  - forward dates：`1/20`
  - latest received date：`2026-06-02`
  - next eligible collection date：`2026-06-03`
  - duplicate received dates：`0`
  - active routes：`2/2`
  - real sentiment/news ledgers：`0/1`
  - sentiment templates：`1`
  - history selector ready products：`0`
- Gates：`6/9` 通过。
- 通过项：
  - protocol file created。
  - same day inflation absent。
  - active routes ready：basis/inventory 均至少 `20` 个 latest forward-ready 产品。
  - history selector disabled。
  - label protocol frozen：固定 `63d/126d`。
  - max trials predeclared：最多 `6` 个 selector 试验形状后必须复盘，不允许无限扫。
- 失败项：
  - forward runs ready：`1 < 20`。
  - forward dates ready：`1 < 20`。
  - sentiment real ledger ready：`0 < 1`。
- 固定标签：
  - `future_product_trend_pnl_63d`：3个月持有体验，`63` 个交易日。
  - `future_product_trend_pnl_126d`：6个月持有体验，`126` 个交易日。
  - 标签必须等 `label_end_date <= available_market_data_last_date` 后才能评估。
  - OOS IC 日期需要按 `63/126` 天不重叠或按月/季度 purged grouping。
- 固定特征：
  - `basis`：`dom_basis_rate/near_basis_rate/dom_basis/source_age_days/status` 等，只能用 `received_at_local <= selector_eval_time` 且 forward-ready 的行。
  - `inventory`：库存 level/change 字段，只能用 point-in-time 行。
  - `sentiment_news/manual_event`：必须有真实 ledger、`source_url/raw_text_hash/product_mapping/status`，不能回填重标。
  - `market_state_guardrail`：只作为风险/容量约束，除非单独审计，否则不算 alpha。
  - `forbidden_hindsight`：Stage541/543 的 `future_*`、`oracle6`、hindsight top 产品禁止作为特征。
- 固定通过线：
  - IC 审计：mean Spearman IC `>=0.05` 且 positive IC rate `>=60%`。
  - 桶审计：63d 和 126d top bucket edge 均 `>0`，且不能由单日期/单产品主导。
  - 纸面 sleeve：只有 IC/bucket 都过后，才允许一次冻结低风险 sleeve replay；必须改善 3/6个月左尾，且不能显著劣化 Stage526 DD/成本闸门。
- Stage558 历史先验参考：
  - `hist_drawdown_120d` 在 `120d` horizon 的 mean IC `0.1549`、positive IC rate `78.2609%`，是当前最强历史先验。
  - `core_corr_252d` 在 `120d` horizon 的 mean IC `0.1408`、positive IC rate `71.7391%`。
  - 这些先验不能直接转为交易规则，只能作为未来 feature family 的优先级参考。

## 回测指标

- 期末权益：不适用，本阶段不做收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：`runs=1/20`、`dates=1/20`、`sentiment ledger=0/1`、`active routes=2/2`、固定标签 `63d/126d`。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_chart_stage561_selector_predictive_audit_protocol_v1.png`
- 左上闸门图显示协议本身、同日去重、active routes、history selector disabled、标签冻结都通过，但 runs/dates/sentiment 三个核心数据资格失败。
- 右上进度图显示 `runs=1/20`、`dates=1/20`、`sentiment=0/1`，最短板不是 route 覆盖，而是样本深度和真实舆情账本。
- 左下 route 覆盖图显示 basis `28`、inventory `24` 均超过 `20` 产品线，warehouse/member_detail 为 `0`，说明未来协议可以先围绕 basis/inventory 做，但不能依赖会员/仓单。
- 右下图清楚显示固定标签为 `3m=63 trading days`、`6m=126 trading days`，允许特征组为 basis、inventory、sentiment_news、market_state_guardrail，并声明最大 selector 试验数为 `6`。首次视觉检查发现 `3个月/6个月` 等宽字体乱码，已修正为 `3m/6m` 后重跑，最终图无乱码、无遮挡。

## 输出文件

- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_decision_stage561_selector_predictive_audit_protocol_v1.json`
- protocol：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_protocol_stage561_selector_predictive_audit_protocol_v1.json`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_gates_stage561_selector_predictive_audit_protocol_v1.csv`
- feature spec：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_feature_spec_stage561_selector_predictive_audit_protocol_v1.csv`
- label spec：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_label_spec_stage561_selector_predictive_audit_protocol_v1.csv`
- test plan：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_test_plan_stage561_selector_predictive_audit_protocol_v1.csv`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_report_stage561_selector_predictive_audit_protocol_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_chart_stage561_selector_predictive_audit_protocol_v1.png`

## 结论

- 本阶段结论：Stage261 冻结了未来选品预测力审计协议，但当前数据仍不允许启动预测力审计，更不允许形成交易 selector。
- 是否进入下一步：进入采集/账本累计下一步，不进入收益回测或 A/B。
- 下一步：
  - 等新自然日继续 Stage549 跨日采集，累计 `20` runs / `20` dates。
  - 真实记录 sentiment/news/manual event ledger。
  - 等 `63/126` 交易日标签成熟后，只按 Stage261 协议做一次固定 IC/bucket/paper sleeve 审计。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段在未来结果出现前冻结协议，不读取新收益标签，不调交易参数。
- 运行后判断：不是过拟合，且降低未来过拟合风险。
- 原因：协议明确禁止同日样本膨胀、新闻回填、hindsight 产品池和 TopN/阈值事后救援；这正是防止“选对品种”路线被历史结果污染的关键。

## 继续价值反思

- 运行前判断：有价值。Stage257 证明简单宽池失败，Stage258-260 证明外生方向卡在数据资格。
- 运行后判断：仍有价值，但下一步仍不是收益回测，而是跨日采集、真实舆情账本和标签成熟后的一次固定审计。
- 原因：用户的第一性原理判断“选对品种是关键”仍成立，但必须先让“选对”变成可验证的、非 hindsight 的预测力。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为未来外生/舆情 selector 的审计协议边界。
