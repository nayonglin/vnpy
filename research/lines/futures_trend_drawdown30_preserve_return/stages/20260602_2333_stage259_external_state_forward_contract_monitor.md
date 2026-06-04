# Stage259 外生状态 Forward 契约监控

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:33 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据契约和监控审计；不做收益回测，不生成交易候选。
- 是否重要突破：否；但把 Stage258 的“外生/舆情要先有 forward 账本”落成了可复跑契约和舆情模板。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档：本地已使用 `futures_spot_price`、`futures_inventory_em`、会员持仓和仓单接口，适合做自动/半自动 forward 采集。
  - AQR managed futures / trend-following 资料：趋势策略的长期稳健性来自多市场分散、风险预算和跨资产低相关，不是简单放大历史赢家。
  - `pysystemtrade`：多品种趋势组合强调 instrument diversification、相关性和风险预算，和本线“低单笔风险 + 扩池 + 避高相关”方向一致。
  - Point-in-time / look-ahead bias 资料：系统化研究必须记录数据在当时是否可得，`received_at`、版本和原始hash是避免未来函数的关键。
- 我的判断：Stage258 后不能再做选品收益回测；正确下一步是把外生/舆情数据契约固化，并持续积累 forward 样本。舆情数据尤其危险，必须先有 `received_at/source_url/raw_hash/product_mapping`，否则只能做解释材料。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage559_external_state_forward_contract_monitor.py`
- 新增输出：
  - source contract CSV。
  - contract gates CSV。
  - sentiment/news schema CSV。
  - sentiment/news forward ledger template CSV。
  - decision JSON、report、chart。
- 修改脚本：运行后修正图表显示，让失败闸门显式标出 `FAIL`，并把样本深度改为当前/要求并列柱，避免视觉误读。
- 删除脚本：无。
- 新增参数/闸门：
  - `MIN_FORWARD_RUNS_FOR_SELECTOR_AUDIT=20`
  - `MIN_FORWARD_DATES_FOR_SELECTOR_AUDIT=20`
  - `MIN_ACTIVE_FORWARD_ROUTES=2`
  - `CORE_LEDGER_COLUMNS`：外生状态总账硬字段。
  - `SENTIMENT_SCHEMA`：舆情/新闻硬字段，其中必填字段 `25` 个。
- 修改参数：无交易参数修改。
- 删除参数：无。

## 结果

- 决策：`forward_contract_created_selector_still_not_ready`
- Contract gates：`6/9` 通过。
- 通过项：
  - core ledger schema ok：核心字段完整。
  - point in time rule present：所有行写明 `received_at` 规则。
  - ok rows have raw hash：`52` 条 ok 行 raw hash 覆盖达标。
  - active forward routes：当前已有 `2` 条可用 forward route。
  - history selector disabled until ready：history selector 产品数仍为 `0`，符合当前纪律。
  - sentiment template created：舆情/新闻模板已创建。
- 失败项：
  - enough forward runs：当前 `1`，要求 `>=20`。
  - enough forward dates：当前 `1`，要求 `>=20`。
  - sentiment forward ledger exists：当前 `0`，要求 `>=1`。
- Source contract：
  - basis：`28/37` forward-ready，history-ready `0`，自动探针，继续每日/每周积累。
  - inventory：`24/37` forward-ready，history-ready `0`，自动探针，继续每日/每周积累。
  - member_detail：`0/37` forward-ready，当前 not live ready，需要修源或换 provider。
  - warehouse：`0/37` forward-ready，当前 not live ready，需要修源或换 provider。
  - sentiment_news：schema template only，必须先建结构化账本。
  - manual_event：schema template only，人工事件必须先落盘，且多品种事件拆多行。

## 回测指标

- 期末权益：不适用，本阶段不做收益回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_chart_stage559_external_state_forward_contract_monitor_v1.png`
- 左上 source coverage 显示只有 basis 和 inventory 有蓝色 forward-ready 柱，member_detail、warehouse、sentiment_news、manual_event 都是 `0`；紫色 history selector 产品全为 `0`，说明所有外生状态仍禁止历史 selector。
- 右上 gates 图显示失败项集中在 forward 样本数、forward 日期数和真实舆情账本；契约本身已建立，但预测力审计条件未满足。
- 左下 sample depth 显示当前 `1` run / `1` date 与 `20/20` 要求差距很大，不能用同日多跑替代跨日样本。
- 右下 sentiment contract 显示舆情/新闻必填字段分布，classification 和 audit 字段最多，说明舆情路线的重点不是“情绪打分”，而是可追溯、可复核、可映射。

## 输出文件

- source contract：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_source_contract_stage559_external_state_forward_contract_monitor_v1.csv`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_contract_gates_stage559_external_state_forward_contract_monitor_v1.csv`
- sentiment template：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger/sentiment_news_forward_ledger_template_stage559_external_state_forward_contract_monitor_v1.csv`
- sentiment schema：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_sentiment_schema_stage559_external_state_forward_contract_monitor_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_decision_stage559_external_state_forward_contract_monitor_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_report_stage559_external_state_forward_contract_monitor_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage559_external_state_forward_contract_monitor_chart_stage559_external_state_forward_contract_monitor_v1.png`

## 结论

- Stage259 不是策略晋级，而是实盘可执行数据纪律推进。
- basis/inventory 可以作为自动 forward monitor 主线；member_detail/warehouse 暂不能当硬依赖。
- 舆情/新闻已具备模板和 schema，但没有真实账本；不得用于回测、不得用于交易筛选。
- 下一步如果继续外生状态路线，应优先做可复跑采集/监控：每天或每周追加 Stage549 账本，并开始按 Stage559 模板记录人工/新闻事件。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段不使用收益标签、不调交易规则，只做数据契约。
- 运行后判断：不是过拟合，且降低后续过拟合风险。原因是本阶段把 `history selector disabled` 和舆情硬字段写成机器可审计输出，防止用解释性新闻或单次外生数据历史回填。

## 继续价值反思

- 运行前判断：有价值。Stage258 已经确认最大短板是 forward 样本和舆情账本。
- 运行后判断：仍有价值，但继续方向不是收益回测，而是采集/监控自动化。
- 下一步 TODO：
  - 定期运行 Stage549 追加外生状态账本，累计至少 `20` 个跨日样本。
  - 用 Stage559 模板记录真实舆情/新闻/manual event，先 paper，不交易。
  - 修复或替换 member_detail/warehouse 源；在当前 `0/37` 状态下不得作为实盘硬闸门。
  - 样本达标后，再做一次固定预测力审计，目标是未来 3/6 个月品种趋势收益排序，而不是直接调仓。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为外生/舆情数据契约边界。
