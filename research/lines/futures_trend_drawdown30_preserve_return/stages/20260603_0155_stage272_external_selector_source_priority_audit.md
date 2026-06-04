# Stage272 外生选品来源优先级与数据缺口审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 01:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据资格审计；不生成交易候选，不做收益回测，不修改策略规则。
- 是否重要突破：否，但进一步固化“扩池必须先有 point-in-time selector”的数据边界。
- 是否触发A/B：否。没有形成可接入正式版本的新策略。

## 外部调研与判断

- 参考资料：
  - 商品期货 term structure / basis / carry / inventory 类研究通常把期限结构、库存压力、基差变化作为趋势或风险溢价的候选解释变量。
  - 新闻/舆情类商品策略资料强调事件时间戳、发布源、品种映射和不可回填性；没有真实 `received_at` 的舆情历史，很容易把事后知道的信息误当作当时可交易信息。
  - 多品种 CTA / managed futures 的组合构造资料强调 instrument diversification、相关性估计、risk budget，但分散本身不是 alpha，关键仍是能否在当时识别可抓趋势的品种。
- 我的判断：
  - 用户提出的“减少单笔风险、扩大品种池、避免高相关、选对品种”在第一性原理上成立；但当前不能直接晋级交易版本。
  - 当前最该做的不是继续扫宽池参数，而是给外生数据来源排序，并把阻塞项写成机器可审计闸门。
  - basis / inventory 可以继续做 forward monitor；news/sentiment 目前缺真实账本，不能进入历史回测。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage571_external_selector_source_priority_audit.py`
- 修改脚本：
  - 同一脚本内修正 Stage547 basis 诊断旧列名兼容：兼容 `positive_month_rate_future60_pct` 与 `selected_vs_oracle_capture_ratio_60d`。
- 删除脚本：无。
- 新增参数：
  - 最少合格 forward runs：`20`
  - 最少合格 forward dates：`20`
  - 最少真实 sentiment/news ledger：`1`
  - 单 route 最少 forward-ready 产品：`20`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage549/558/560/561/550 既有输出，不重建 2020-2026 交易回放。
- 账户规模：不适用。本阶段不是策略收益回测。
- 成本口径：不适用。本阶段不生成交易。
- 样本过滤：
  - 同一自然日重复采集不增加 selector 样本深度。
  - 只有同一 `run_id` 内至少 `2` 条 route 各自覆盖 `>=20` 个 forward-ready 产品，才计入合格 forward 样本。
  - 没有真实 point-in-time 历史账本的外生数据，不允许回填进 2020-2026 selector 回测。
- 策略/归因口径：
  - 固定审计来源：Stage549/558/560/561 的 forward external ledger / protocol gates，Stage550 的历史 feature IC，Stage547 的 basis monthly diagnostic。
  - `market_state_guardrail` 只作为风险状态/弱先验，不作为 alpha selector。

## 结果

- 决策：`basis_inventory_forward_monitor_only_sentiment_ledger_missing`
- 数据资格硬闸门：`2/8` 通过。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - basis forward-ready：`28/37`，通过 `>=20` 覆盖闸门。
  - inventory forward-ready：`24/37`，通过 `>=20` 覆盖闸门。
  - member_detail forward-ready：`0/37`，不能作为硬依赖。
  - warehouse forward-ready：`0/37`，不能作为硬依赖。
  - 合格 forward runs：`2/20`，未达标。
  - 合格 forward dates：`2/20`，未达标。
  - 真实 sentiment/news ledger：`0/1`，未达标。
  - history-ready external route：`0`，所以禁止历史回填式选品收益回测。
  - Stage247/547 basis 最好 quarterly-purged 模式：`basis_alignment_family_cap1`，future60 edge `139.9149`，正月份率 `29.4118%`，Oracle capture `18.1791%`，但 `diagnostic_pass=0`，不能作为 standalone selector。

### 来源优先级

| 来源 | 角色 | 当前可用性 | 优先级判断 |
| --- | --- | --- | --- |
| `market_state_guardrail` | 风险状态/弱先验，不是 alpha | 历史特征覆盖完整，但 Stage543/544 未跑出可部署 selector | 可做 guardrail 或 feature prior，不可单独决定扩池 |
| `basis` | 候选外生特征 | `28/37` forward-ready，history-ready `0` | 继续跨日采集；只作为 joint feature / monitor |
| `inventory` | 候选外生特征 | `24/37` forward-ready，history-ready `0` | 继续跨日采集；后续和 basis 联合测试 |
| `member_detail` | 阻塞来源 | `0/37` forward-ready | 暂停作为硬依赖 |
| `warehouse` | 阻塞来源 | `0/37` forward-ready | 暂停作为硬依赖 |
| `sentiment_news_manual_event` | 舆情/政策事件候选 | 真实 ledger `0` | 先建账本，不能回测 |
| `stage256_upper_bound` | 历史上限/目标差距 | 不可部署 | 只能作为 selector 研究目标，不是特征 |

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_chart_stage571_external_selector_source_priority_audit_v1.png`
- 左上图：合格 runs 和 dates 均只有 `2`，距离 `20` 的预测力审计门槛很远；sentiment real ledger 为 `0`，低于 `1` 的最低要求。
- 右上图：basis 和 inventory 的 forward coverage 已超过 `20` 产品线，但 history-ready 全为 `0`；member_detail/warehouse 完全不可用。
- 左下图：`market_state_guardrail` 分数最高但被标注为 risk guardrail，不是 alpha；basis/inventory 分数相同，都是“可继续采集但不可回测”的来源。
- 右下图：`hist_drawdown_120d` 的 mean Spearman IC 为 `0.1214`，只能算弱正先验；`low_core_corr_rank_pct`、`core_corr_252d` 等仅能 monitor。图中没有任何特征达到强先验阈值。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_report_stage571_external_selector_source_priority_audit_v1.md`
- source priority：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_source_priority_stage571_external_selector_source_priority_audit_v1.csv`
- data gaps：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_data_gaps_stage571_external_selector_source_priority_audit_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_gates_stage571_external_selector_source_priority_audit_v1.csv`
- feature prior：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_feature_prior_stage571_external_selector_source_priority_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_decision_stage571_external_selector_source_priority_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_chart_stage571_external_selector_source_priority_audit_v1.png`

## 结论

- 本阶段结论：
  - 扩池路线继续保留，但当前只能做数据工程和 forward monitor，不能做收益回测或晋级交易候选。
  - basis / inventory 是当前最值得保留的外生来源，但都必须等 `20/20` 合格跨日样本后，再按 Stage561 固定协议做 IC、bucket、paper sleeve replay。
  - news/sentiment 的第一步不是 NLP 模型，而是真实 `received_at/source_url/published_at/raw_text_hash/product_mapping/status` 账本。
  - member_detail / warehouse 当前覆盖为 `0/37`，不能成为 selector 硬依赖。
- 是否进入下一步：是，但只进入数据资格与真实 forward 采集，不进入交易回测。
- 下一步：
  - 继续累计 Stage549 合格跨日样本到 `20/20`。
  - 建立真实 sentiment/news/manual event ledger。
  - 到达样本门槛后，固定做 `63/126` 日 product trend PnL 的 IC/bucket/paper sleeve 审计。
  - 未达标前，不再扫宽池 `risk/cap/corr/maxpos` 参数。

## 过拟合反思

- 运行前判断：不是过拟合。目标是检查数据资格、样本深度和 point-in-time 约束，不用未来收益选择品种。
- 运行后判断：不是过拟合。结果明确阻止了使用 history-backfill 或 hindsight 白名单做收益回测。
- 原因：
  - 本阶段没有新增交易规则。
  - 没有调阈值追求收益。
  - 反而把 Stage256 upper 继续标记为不可部署上限。

## 继续价值反思

- 运行前判断：有价值。Stage271 已证明如果能选对品种，扩池有上限收益；需要判断哪些外生来源值得投入。
- 运行后判断：有价值，但方向进一步收窄。
- 原因：
  - basis / inventory 已有可采集覆盖，值得继续 forward monitor。
  - sentiment/news 缺口清晰，可以转为工程任务。
  - 当前样本 `2/20` 太少，继续做收益回测只会制造伪结论。

## 验证

- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage571_external_selector_source_priority_audit.py`：通过。
- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage571_external_selector_source_priority_audit.py`：通过。
- `.py311/bin/python -m json.tool examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage571_external_selector_source_priority_audit_decision_stage571_external_selector_source_priority_audit_v1.json`：通过。
- 图表已视觉检查。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段延续 Stage270/271 的路线边界。
