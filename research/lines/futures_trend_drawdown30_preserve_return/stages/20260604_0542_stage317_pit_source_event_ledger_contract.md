# Stage317 点时化 source/event ledger 合同

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 05:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：基本面/舆情可实盘执行性审计；把 Stage616 P1/P2 监控对象接到点时化 source/event ledger 合同。
- 对应脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage617_pit_source_event_ledger_contract.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_report_stage617_pit_source_event_ledger_contract_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_chart_stage617_pit_source_event_ledger_contract_v1.png`
- 决策：`pit_source_event_contract_ready_selector_not_ready`
- 是否重要突破：否。它推进了基本面/舆情的实盘可执行合同，但没有形成 selector 或交易候选。
- 是否触发 A/B：否。没有 paper selector、交易白名单或正式候选。
- 是否新增回测：否。
- 是否修改策略：否。
- 是否连接 CTP/SimNow：否。
- 是否调用 `send_order`：否。

## 开始前反思

- 是否过拟合：否。本阶段只审计数据接收时间、来源、hash、route 资格和样本深度，不把任何基本面/舆情数据用于收益回测。
- 是否有价值继续：有。目标要求研究基本面/舆情是否能实盘可执行；如果没有点时化 ledger，就会把事后新闻解释误当交易信号。

## 外部调研与判断

- Point-in-time 数据纪律是基本面/舆情路线的核心：`received_at` 和原始 hash 比事后整理的 `published_at` 更重要。
- 官方或授权数据源应优先进入候选；第三方/vendor 数据可以先做 forward monitor，但未证明授权、历史回放稳定性和原始快照前不能成为 history selector。
- 手工新闻/舆情可以辅助人工复盘，但如果没有实时采集、source URL、text hash、品种映射和足够多 forward 样本，不应作为 alpha 特征。
- 本阶段判断：基本面/舆情值得继续做 forward ledger，但当前不能做 selector 回测、paper selector、A/B 或白名单。

参考：

- Point-in-time/look-ahead bias：`https://www.quantrocket.com/docs/#time-date-data-point-in-time`
- CME managed futures / commodity research digest：`https://www.cmegroup.com/education/files/research-digest.pdf`
- Rob Carver `pysystemtrade`：`https://github.com/robcarver17/pysystemtrade`

## 本阶段做了什么

- 读取 Stage616 monitor plan，聚焦 P1/P2 监控对象：
  - `black_ferrous`：`j.DCE/i.DCE`
  - `precious_metals`：`ag.SHFE`
  - `soft_agri`：`CY.CZCE/SR.CZCE`
- 读取现有 forward ledger：
  - `external_state_forward_ledger.csv`
  - `black_ferrous_p1_source_forward_ledger.csv`
  - `sentiment_news_manual_event_forward_ledger_stage572_real_sentiment_event_ledger_bootstrap_v1.csv`
- 新增 Stage617 脚本，生成：
  - product route matrix；
  - family ledger readiness；
  - contract rules；
  - gates；
  - decision JSON；
  - markdown report；
  - 可视化图表。
- 不联网抓新数据，不回填历史新闻，不做收益回测。

## 新增/修改/删除

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage617_pit_source_event_ledger_contract.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `MIN_PIT_DATES_FOR_PREDICTIVE_AUDIT = 20`
  - `MIN_P2_FORWARD_MONTHS = 12`
  - `MIN_INDEPENDENT_TREND_EPISODES = 3`
  - `REQUIRED_LIVE_TCA_SAMPLES = 9`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测结果

本阶段没有新增交易回测，因此以下字段不适用：

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 核心结果

- monitor products：`j.DCE`、`i.DCE`、`ag.SHFE`、`CY.CZCE`、`SR.CZCE`
- monitor families：`black_ferrous`、`precious_metals`、`soft_agri`
- observed monitor routes：`20`
- contract-complete forward-ready routes：`4`
- selector-ready routes：`0`
- event/sentiment-ready P1/P2 products：`0/5`
- min PIT dates among monitor products：`0/20`
- P2 required forward months：`12`
- P2 required independent trend episodes：`3`
- live context：`0/45`
- P0 live TCA：`0/9`
- hard gates：`2/8`
- paper selector：`0`
- trading whitelist：`0`

## 关键解释

- `black_ferrous(j/i)` 有 basis 与 inventory 两类合同完整的 third-party forward routes，但 member_detail、warehouse、event/sentiment 仍缺失；这些 route 只能 monitor，不能 history selector。
- `ag/CY/SR` 有可观测的 basis/inventory 等记录，但早期外生 ledger 缺 `source_url` 或授权 endpoint 字段，因此在 Stage617 中被标为 `OBS`，不是 `OK`。
- 真实 sentiment/manual event ledger 当前只覆盖 `grains_oilseeds`，未覆盖本阶段 P1/P2 目标族，所以 P1/P2 event/sentiment coverage 为 `0/5`。
- 第三方或手工数据可做 forward monitor，但没有官方/授权路由、`received_at/source_url/raw_hash`、跨日样本和 live TCA 前，不能进交易选择器。

## 图表视觉复盘

- 左上图使用三态：`OK` 表示合同完整可 monitor，`OBS` 表示有观测但合同字段不完整，`MISS` 表示无有效观测。`j/i` 的 basis/inventory 为 OK；`ag` 的 basis/inventory 为 OBS；`CY/SR` 的 basis 为 OBS。
- 右上图显示 observed PIT dates 只有 `2-3`，contract PIT dates 只有 `0-1`，远低于 `20` 日预测力审计门槛；selector-ready routes 全为 `0`。
- 左下图显示 monitor-only 占主导：P2 主要是“观测但合同不完整”，`black_ferrous` 有第三方合同完整 route，但没有官方/授权 selector route。
- 右下图显示只有 `pit_source_rows_exist` 和 `paper_or_whitelist_allowed=0` 通过；source完整性、PIT深度、selector route、event/sentiment覆盖、P2月数、live TCA 全部阻塞。
- 视觉结论：图表明确区分“能观察”和“能交易”，没有把基本面/舆情观测误画成 alpha 候选。

## 结论

- 基本面/舆情方向可以继续做，但当前只能是 forward ledger 和 route repair。
- 当前不能做历史 selector 回测、paper selector、A/B 或交易白名单。
- 下一步有价值的不是回填旧新闻，而是：
  - 给 P2 `ag/CY/SR` 的外生 ledger 补 `source_url` 或授权 endpoint 字段；
  - 为 P1/P2 建真实 event/sentiment 路由；
  - 累计至少 `20` 个 PIT 日期；
  - P2 至少连续 `12` 个月观察并记录 `3` 个独立趋势 episode；
  - 同步闭合 live context/TCA。

## 结束后反思

- 是否过拟合：否。脚本没有使用收益标签和历史窗口，不做新闻回填，不把 `published_at` 当作可交易时间，只把数据资格缺口画出来。
- 是否有价值继续：有，但价值方向是数据工程和真实监控，不是策略收益扫描。继续用未点时化基本面/舆情做历史回测价值低且过拟合风险高。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage617_pit_source_event_ledger_contract.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage617_pit_source_event_ledger_contract.py`：通过。
- `rg -n "send_order\\(|connect\\(|subscribe\\(|cancel_order\\(" examples/portfolio_backtesting/analyze_qmt_roll_stage617_pit_source_event_ledger_contract.py`：无命中。
- 图表视觉检查：已发现并修正 P2 route 状态误读，最终三态图通过。
- decision JSON 复读：通过。

## 输出文件

- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_decision_stage617_pit_source_event_ledger_contract_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_report_stage617_pit_source_event_ledger_contract_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_chart_stage617_pit_source_event_ledger_contract_v1.png`
- product route matrix：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_product_route_matrix_stage617_pit_source_event_ledger_contract_v1.csv`
- family readiness：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_family_ledger_readiness_stage617_pit_source_event_ledger_contract_v1.csv`
- contract rules：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_contract_rules_stage617_pit_source_event_ledger_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage617_pit_source_event_ledger_contract_gates_stage617_pit_source_event_ledger_contract_v1.csv`

## TODO

- P2 source repair：补 `ag/CY/SR` 外生 ledger 的 `source_url` 或授权 endpoint 字段，避免只有观察值没有来源合同。
- P1 source repair：继续解决 DCE `j/i` official/member/warehouse route，或找可授权替代源。
- Event/sentiment：为 `black_ferrous/precious_metals/soft_agri` 建真实 `received_at/source_url/raw_text_hash/product_mapping` 事件账本。
- 样本深度：累计至少 `20` 个 PIT 日期后，才能按冻结协议做 63/126 日预测力审计。
- 执行证据：继续等待用户确认测试环境和 read-only/submit 动作后，闭合 live context 和 TCA。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态和下一步。
- 是否更新 `research/registry.md`：是，最新阶段更新到 Stage317。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合入。
