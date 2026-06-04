# Stage263 外生状态跨日采集与质量闸门修复

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 00:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘可执行外生状态 forward 账本采集 + 采集质量闸门修复；不做收益回测，不生成交易候选。
- 是否重要突破：是，属于数据资格闸门的重要修复。今天确认 `2026-06-03` 可以形成第二个合格 `received_at` 样本，同时发现并修复失败 run 会污染样本深度的风险。
- 是否触发A/B：否。未产生新策略版本，也未准备接入第78/Stage079/Stage526 正式候选。

## 外部调研与判断

- 参考资料：
  - [AQR: Demystifying Managed Futures](https://www.aqr.com/Insights/Research/Journal-Article/Demystifying-Managed-Futures)
  - [pysystemtrade](https://github.com/robcarver17/pysystemtrade)
  - point-in-time alternative data / look-ahead bias 相关资料。
- 我的判断：
  - “降低单笔风险 + 扩大品种池 + 避免高相关 + 选对品种”方向成立，但只有在外生/舆情数据有真实 `received_at`、来源、hash 和跨日稳定样本后才可进入预测力审计。
  - 今天最有价值的推进不是历史收益回测，而是把第二个真实跨日样本落账，并修复同日失败/重跑对样本深度的污染。
  - 趋势策略可穿越周期的关键仍是分散化、风险预算、成本/执行纪律和点时化数据；不能把历史赢家或单日外生快照当成 selector。

## 本次变更

- 新增脚本：无。
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage560_forward_collection_run_gate.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage561_selector_predictive_audit_protocol.py`
- 删除脚本：无。
- 新增参数：
  - `MIN_FORWARD_READY_PRODUCTS_PER_ROUTE = 20`
  - Stage560 新增 `RUN_QUALITY_PATH`
- 修改参数：
  - Stage560 的 selector 样本深度从 raw `run_id/received_date` 改为质量闸门计数。
  - 合格 run 定义：同一 `run_id` 内至少 `2` 条 route 各自有 `>=20` 个 forward-ready 产品；同一自然日最多只计入一次合格样本。
  - Stage561 协议层改为优先读取 Stage560 的 `qualified_forward_runs/qualified_forward_dates`，并保留 raw 计数用于审计。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2026-06-02` 至 `2026-06-03` forward received ledger。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：37 个外生状态 applicable 商品；每次 Stage549 snapshot 为 `37 products * 4 routes = 148` 行。
- 策略/归因口径：
  - 不跑交易策略、不读取未来收益、不形成候选。
  - 只审计 basis / inventory / member_detail / warehouse 的 forward-ready 覆盖与点时化采集质量。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 采集前 Stage560：`forward_runs=1/20`、`forward_dates=1/20`，最新接收日 `2026-06-02`，推荐动作 `run_stage549_collect_new_distinct_date`。
  - 沙箱内 Stage549 run：`stage549_20260603_000740`，因 DNS/外网限制导致 basis/inventory/member/warehouse 全部 `0`，决策 `forward_external_ledger_incomplete`。该 run 保留在 master ledger 作为失败证据，但不得计入 selector 样本深度。
  - 外部权限 Stage549 run：`stage549_20260603_000956`，决策 `forward_external_ledger_initialized_not_selector_ready`。
  - 成功 run route 覆盖：
    - basis：`28/37` ok，Oracle6 `4/6` forward-ready。
    - inventory：`24/37` ok，Oracle6 `6/6` forward-ready。
    - member_detail：`0/37` ok。
    - warehouse：`0/37` ok。
  - Stage560 质量闸门修复后：
    - raw：`3` runs、`2` dates。
    - qualified：`2` runs、`2` dates。
    - `extra_qualified_same_day_runs=0`。
    - 剩余：`18` qualified runs、`18` qualified dates。
    - active forward routes：`2/2`。
    - history ready products：`0`。
    - real sentiment/news ledger：`0`。
  - Stage561 协议层复核：
    - 质量闸门计数 `runs=2/20`、`dates=2/20`。
    - raw 账本计数 `runs=3`、`dates=2`。
    - `raw_duplicate_received_dates=1`，但 `extra_qualified_same_day_runs=0`，所以 same-day inflation gate 通过。
    - 决策仍为 `protocol_frozen_predictive_audit_not_ready`。

## 输出文件

- Stage549 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage549_external_state_forward_ledger_decision_stage549_external_state_forward_ledger_v1.json`
- master ledger：`examples/portfolio_backtesting/backtest_outputs/external_state_forward_ledger/external_state_forward_ledger.csv`
- Stage560 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_decision_stage560_forward_collection_run_gate_v1.json`
- Stage560 run quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_run_quality_stage560_forward_collection_run_gate_v1.csv`
- Stage560 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage560_forward_collection_run_gate_chart_stage560_forward_collection_run_gate_v1.png`
- Stage561 decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_decision_stage561_selector_predictive_audit_protocol_v1.json`
- Stage561 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage561_selector_predictive_audit_protocol_chart_stage561_selector_predictive_audit_protocol_v1.png`

## 图表视觉复盘

- Stage560 图表：
  - 左上显示合格样本进度为 `2/20` runs 和 `2/20` dates，而不是 raw `3` runs，说明失败 run 已被质量闸门排除。
  - 右上显示最新 route 健康度只有 basis `28` 和 inventory `24` 两条 route 达标，member_detail/warehouse 仍为 `0`。
  - 左下闸门图中 `enough_forward_runs`、`enough_forward_dates`、`sentiment_real_ledger_exists` 和 `ready_for_predictive_audit` 失败，说明当前仍只能采集/监控，不能做 selector 收益回测。
  - 右下文本显示 duplicate dates 为 `2026-06-03`，但 qualified runs 为 `2`，这正是今天修复的关键风险点。
- Stage561 图表：
  - 数据资格进度同样显示 `2/20`，真实 sentiment 为 `0/1`。
  - `same_day_inflation_absent` 通过，说明协议层已经区分 raw 重跑与合格样本膨胀。
  - route 覆盖图显示 basis/inventory 都超过 `20` 产品线，member_detail/warehouse 不达标，因此未来特征先只能围绕 basis/inventory 和真实舆情账本。

## 结论

- 本阶段结论：
  - `2026-06-03` 第二个合格外生状态样本已落账，basis/inventory 覆盖与 `2026-06-02` 保持一致。
  - 失败采集会真实发生，不能假设外部数据链路稳定；因此 selector 样本深度必须采用质量闸门计数，而不是 raw run/date。
  - 当前“选对品种”路线仍不能进入收益回测：样本只有 `2/20`，真实 sentiment/news ledger 为 `0/1`。
- 是否进入下一步：进入数据采集下一步，不进入策略收益回测。
- 下一步：
  - 等 `2026-06-04` 或之后再采集第三个合格样本。
  - 补一个真实 sentiment/news/manual event ledger，哪怕先是少量高质量人工事件，也必须有 `received_at/source_url/published_at/raw_text_hash/product_mapping/status`。
  - member_detail/warehouse 继续视为不稳定源，不作为硬依赖；basis/inventory 作为当前主 route。

## 过拟合反思

- 运行前判断：否。本阶段不看未来收益、不调交易参数，只做真实接收时间账本和采集闸门。
- 运行后判断：否，并且进一步降低后续过拟合风险。
- 原因：
  - 沙箱失败 run 暴露出真实执行链路风险；质量闸门防止把失败或同日重跑当作样本外证据。
  - Stage561 协议继续禁止用 `future_*`、Oracle6、hindsight top 产品、同日样本膨胀和新闻回填。

## 继续价值反思

- 运行前判断：有价值。Stage258-261 的瓶颈是 forward 样本与舆情账本，今天刚好是可计入的新日期。
- 运行后判断：有价值，但价值在数据工程和实盘可执行性，而不是新的历史回测。
- 原因：
  - basis/inventory 连续两天都能形成合格覆盖，说明外生状态 forward monitor 可继续积累。
  - 同时网络/DNS失败证明采集质量必须被审计；这比继续扫宽池参数更接近实盘问题本质。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage263、质量闸门修复和 `2/20` 进度。
- 是否更新 `research/registry.md`：是，作为当前研究线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段属于数据资格闸门的重要修复。
