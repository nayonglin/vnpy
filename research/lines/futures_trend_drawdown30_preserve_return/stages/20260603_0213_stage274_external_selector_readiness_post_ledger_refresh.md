# Stage274 外生选品账本识别修正与来源优先级刷新

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 02:13 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据资格与审计口径修正；不修改交易策略，不新增交易版本，不做收益回测。
- 是否重要突破：否；但修正了后续“选对品种”路线的数据闸门口径。
- 是否触发A/B：否。没有形成可接入正式版本的新策略。

## 外部调研与判断

- 本阶段未新增网络调研，沿用 Stage273 已确认的官方来源：USDA/NASS Crop Progress 官方页面与 `2026-06-01` 官方 txt。
- 参考来源：
  - https://esmis.nal.usda.gov/publication/crop-progress
  - https://esmis.nal.usda.gov/sites/default/release-files/795928/prog2226.txt
- 我的判断：
  - 真实事件账本必须以 `received_at/source_url/published_at/raw_text_hash/product_mapping/status` 为核心，不允许用事后新闻回填历史 selector。
  - Stage273 后，舆情/事件路线不再是“账本为 0”，而是“账本刚起步、样本深度不足”；继续阻止选品收益回测是正确的，但阻止理由必须改准确。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage558_external_state_selector_readiness_audit.py`
    - 收紧 sentiment ledger 扫描：排除 template/schema/自身输出，只把字段完整、非空、`received_at_local` 可解析、`source_url` 存在、`product_vt_symbol` 映射存在、`raw_text_hash` 为 64 位 hash 的 CSV 计为候选账本。
    - 增加 `rows/schema_complete/received_at_parseable/source_url_present/product_mapping_present/raw_hash_present/is_template_or_schema` 审计列。
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage561_selector_predictive_audit_protocol.py`
    - 把 `sentiment_news_manual_event_forward_ledger*.csv` 纳入真实 sentiment ledger glob。
    - 使用同样的字段完整性与点时化校验，避免把模板或报告误计为真实账本。
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage571_external_selector_source_priority_audit.py`
    - 修正硬编码的 `sentiment ledger missing` 决策与报告文字。
    - 增加真实账本产品数/行数/接收日期统计；Stage573 之前的来源优先级现在能识别 Stage572 真实账本。
- 新增脚本：无。
- 删除脚本：无。
- 新增/修改交易参数：无。

## 结果

### Stage558 readiness

- 决策：`opportunity_exists_but_selector_data_not_ready`
- 闸门：`6/9` 通过。
- forward runs：`3`
- received dates：`2`
- forward-ready products：`32`
- history-ready products：`0`
- sentiment candidate ledgers：`1`
- best feature IC：`0.1548695641`

### Stage561 protocol

- 决策：`protocol_frozen_predictive_audit_not_ready`
- forward runs：`2/20`
- forward dates：`2/20`
- raw forward runs/dates：`3/2`
- active routes：`2`
- real sentiment ledgers：`1`
- history-ready products：`0`
- 下一次可计入 selector 样本深度日期：`2026-06-04`

### Stage571 source priority

- 决策：`basis_inventory_sentiment_forward_monitor_sample_depth_blocked`
- 闸门：`3/8` 通过。
- 通过项：
  - basis forward usable：`28/37`
  - inventory forward usable：`24/37`
  - sentiment real ledger ready：`1/1`
- 失败项：
  - enough forward runs：`2/20`
  - enough forward dates：`2/20`
  - history backfill allowed：`0 history-ready routes`
  - basis standalone selector pass：`0`
  - ready for predictive audit：`0`
- 来源优先级：
  - market_state_guardrail：`35.0`
  - basis：`27.0`
  - inventory：`27.0`
  - sentiment_news_manual_event：`12.0`
  - member_detail / warehouse：`0.0`

## 图表视觉复盘

- Stage558 图表：readiness gates 显示 sentiment ledger 已通过，但 `enough_forward_observations/history_selector_ready/prior_historical_selector_passed` 仍失败；route coverage 中 basis/inventory 有 forward 覆盖，history selector 全为 0。
- Stage561 图表：左上 hard gates 中 `sentiment_real_ledger_ready` 已为 PASS；右上数据资格明确显示 runs/dates 仍为 `2/20`，sentiment 为 `1/1`。
- Stage571 图表：hard blockers 中 sentiment 当前值等于 required，真正红灯是 runs/dates；source priority 中 sentiment_news_manual_event 已有低优先级 forward monitor 分数，而不是 0 分缺失。

## 结论

- Stage273 的真实事件账本已经被 Stage558/561/571 三个审计链路识别。
- 当前不能做选品收益回测的原因不是“缺真实 sentiment ledger”，而是：
  - 合格跨日样本只有 `2/20`；
  - history selector 仍必须禁用；
  - basis standalone 诊断没有通过；
  - sentiment/manual event 只有 `1` 个接收日期、`3` 个映射产品，仍只是 forward monitor。
- 因此，“低单笔风险 + 扩池 + 避高相关 + 选对品种”路线继续保留，但下一步应继续累计点时化外生/事件样本，不允许把单次 USDA 事件直接变成交易筛选规则。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只修正数据资格识别与报告口径，不读取未来收益，不改变交易规则。
- 运行后判断：不是过拟合。修正后的结论反而更严格：承认真实账本存在，但继续禁止收益回测，避免把一个事件账本误当 alpha。
- 风险：如果后续把 `c/m/y` 因本次 USDA 映射直接加入或剔除交易池，就是过拟合和事件后验解释。

## 继续价值反思

- 运行前判断：有价值。若审计链路仍把真实账本识别为 0，后续 selector 路线会被错误阻断。
- 运行后判断：有价值但不适合继续交易回测。现在正确阻塞点已经明确为样本深度，下一步价值在继续 forward collection，而不是继续改选品阈值。
- 后续规划：
  - `2026-06-04` 之后继续追加第 3 个合格跨日外生状态样本。
  - 继续记录 USDA/NASS、EIA、交易所公告、产业库存/基差/仓单事件的真实 `received_at`。
  - 达到 `20/20` 后，再按 Stage561 冻结协议做 `63/126` 日 IC、bucket 和 paper sleeve 审计。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage558_external_state_selector_readiness_audit.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage561_selector_predictive_audit_protocol.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage571_external_selector_source_priority_audit.py`：通过。
- `.py311/bin/python -m py_compile` 三个脚本：通过。
- `.py311/bin/python -m json.tool` Stage571 decision：通过。
- Stage558 / Stage561 / Stage571 图表已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段不是新候选或正式突破。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是口径修正和数据资格刷新。
