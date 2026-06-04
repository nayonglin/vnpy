# Stage328 P2 Forward Episode 协议审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：P2+source forward episode 协议和当前缺口审计；不新增收益回测、不改策略规则、不生成 selector/paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否，但把 `precious_metals/soft_agri` 从“source 变好”推进为明确、可复验、fail-closed 的未来晋级协议。
- 是否触发A/B：否。没有形成可接入正式版本的新策略或风险预算。

## 外部调研与判断

- 参考资料：
  - Look-ahead bias / point-in-time data：https://www.pfolio.io/academy/look-ahead-bias
  - CPCV / purged cross-validation：https://ml4trading.io/docs/diagnostic/methods/cpcv/
  - Walk-forward validation：https://docs.skelfresearch.com/sigc/backtesting/walk-forward/
  - Aspect Capital trend-following diversification：https://www.aspectcapital.com/insight/diversification-trend-following/
  - Commodity trend-following diversification paper：https://papers.ssrn.com/sol3/Delivery.cfm/4871376.pdf?abstractid=4871376
- 我的判断：
  - 基本面/舆情数据最容易出现“历史回填”和“发布时间泄漏”；必须先有 point-in-time `received_at/source_url/raw_hash`，再谈历史检验。
  - P2 的正确晋级单位不是单日 source 成功，而是非重叠、可复验的独立趋势 episode。
  - 事件定义、方向映射、持有窗口、purge/embargo、3/6个月左尾、TCA 样本，都必须在评分前冻结；否则就是把研究自由度转成过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage628_p2_forward_episode_protocol.py`
- 修改正式策略脚本：无。
- 删除脚本：无。
- 新增参数/闸门：
  - `REQUIRED_PIT_DATES = 20`
  - `REQUIRED_PIT_MONTHS = 12`
  - `REQUIRED_EPISODES_PER_FAMILY = 3`
  - `REQUIRED_LIVE_TCA_PER_PRODUCT = 3`
  - `REQUIRED_WALK_FORWARD_SPLITS = 3`
  - `REQUIRED_LEFT_TAIL_WINDOWS = 2`
  - `pit_source_integrity`
  - `independent_trend_episode`
  - `fixed_protocol_before_signal`
  - `purged_walk_forward_selector`
  - `holding_experience_left_tail`
  - `live_tca_samples`
  - `fail_closed_budget`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 数据区间：沿用 Stage625/627 冻结输出；本阶段只做协议和缺口审计。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - 只覆盖 Stage327 标为 `P2+source` 的产品族：`precious_metals(ag.SHFE)`、`soft_agri(CY.CZCE/SR.CZCE)`。
  - 只读取 Stage625 raw fetch ledger/product summary 与 Stage627 source delta/family reprioritization。
- 策略/归因口径：
  - source row 不进入 history selector。
  - event row 不等于 event signal。
  - 当前没有任何 paper、A/B 或风险预算资格。

## 结果

- 决策：`p2_forward_episode_protocol_ready_current_evidence_insufficient`
- promotion allowed：`false`
- paper selector allowed：`false`
- trading whitelist allowed：`false`
- protocol products：`3`
  - `ag.SHFE`
  - `CY.CZCE`
  - `SR.CZCE`
- protocol families：`2`
  - `precious_metals`
  - `soft_agri`
- promotion ready families now：`0`
- deployable budget now：`0.00%`
- hard gates：`3/8`
  - 通过的是 fail-closed 纪律：`selector rows still zero`、`promotion ready families zero now`、`incremental budget zero now`。
  - 未通过的是晋级证据：PIT 日期、PIT 月份、全产品 event monitor、独立 episode、live TCA。
- 产品缺口：
  - `ag.SHFE`：fetched ok rows `1`，event auto monitor rows `0`，PIT dates `1/20`，PIT months `1/12`，episodes `0/3`，live TCA `0/3`，protocol progress `1.6667%`。
  - `CY.CZCE`：fetched ok rows `3`，event auto monitor rows `3`，PIT dates `1/20`，PIT months `1/12`，CZCE blocked rows `21`，episodes `0/3`，live TCA `0/3`，protocol progress `14.1667%`。
  - `SR.CZCE`：fetched ok rows `1`，event auto monitor rows `1`，PIT dates `1/20`，PIT months `1/12`，CZCE blocked rows `21`，episodes `0/3`，live TCA `0/3`，protocol progress `14.1667%`。
- 家族缺口：
  - `precious_metals`：family progress `1.6667%`，低相关但 source/event/episode/TCA 未闭合。
  - `soft_agri`：family progress `14.1667%`，source/event monitor 较好但 CZCE route blocker 和 episode/TCA 缺口仍大。
- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增收益曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增收益曲线。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易。
- 总交易次数：无新增交易。
- 胜率：无新增交易。

## 图表视觉复盘

- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_chart_stage628_p2_forward_episode_protocol_v1.png`
- 视觉结论：
  - 左上产品热力图显示：三个产品 PIT 日期只有 `5%`、PIT 月份只有 `8%`；`CY/SR` 的 event monitor 是 `100%`，但 episode、selector、live TCA 全是 `0%`；`ag` 连 event monitor 也为 `0%`。
  - 右上 family progress 显示 `soft_agri` 只有 `14.2%`、`precious_metals` 只有 `1.7%`，离 100% 很远，避免把 source 成功误读为可晋级。
  - 左下 source health 显示 `CY/SR` 的抓取和事件行存在，但 CZCE blocked rows 明显高；`ag` 只有 fetched ok，没有 event monitor。
  - 右下 promotion gates 显示红色集中在真实晋级证据：PIT、event monitor、episode、TCA；绿色只是锁定纪律保持。
  - 图表无明显标签遮挡；红绿语义通过标题标明，避免把绿色锁定纪律误读为交易通过。

## 输出文件

- script：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage628_p2_forward_episode_protocol.py`
- product protocol：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_product_protocol_stage628_p2_forward_episode_protocol_v1.csv`
- family protocol：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_family_protocol_stage628_p2_forward_episode_protocol_v1.csv`
- episode rules：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_episode_rules_stage628_p2_forward_episode_protocol_v1.csv`
- promotion gates：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_promotion_gates_stage628_p2_forward_episode_protocol_v1.csv`
- decision：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_decision_stage628_p2_forward_episode_protocol_v1.json`
- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_report_stage628_p2_forward_episode_protocol_v1.md`
- chart：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage628_p2_forward_episode_protocol_chart_stage628_p2_forward_episode_protocol_v1.png`

## 结论

- 本阶段结论：
  - P2+source 的未来晋级协议已经明确，但当前证据远远不足。
  - `soft_agri` 可以继续作为公开源事件 monitor，不能成为交易 selector；`precious_metals` 还缺事件 monitor，优先级低于 `soft_agri`。
  - 扩池低单笔风险方向仍成立，但必须先让 P2 通过 forward episode 协议，而不是继续做宽池历史收益扫描。
- 是否进入下一步：
  - 是。下一步应把 Stage625 的 raw fetch probe 改成可重复 monitor run，定期累积 `received_at` 和 raw hash；同时定义 episode ledger 字段，但在 `20` 个 PIT 日期和 `12` 个月跨度前禁止预测力审计。
- 下一步：
  - `soft_agri`：继续 ESMIS/WASDE/Crop Progress/ERS raw hash monitor；CZCE 路由转浏览器/CDP或授权替代源，不阻塞 USDA 监控。
  - `precious_metals`：补 SHFE/公开新闻/库存/会员类事件 monitor，而不是只抓 daily page。
  - 所有 P2：等 `20` PIT 日期、`12` 月、`3` episode、`3` walk-forward split、`3` TCA 样本后，再申请 P1 review。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有看历史收益后调阈值，也没有把 source 成功接成交易规则；相反，是在评分前冻结未来证据协议。
  - 要求 PIT 日期、月份跨度、非重叠 episode、purged walk-forward 和 live TCA，都是为了抑制过拟合和回填偏差。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - 该协议让“低单笔风险扩池”从主观判断变成可执行的证据管线。
  - 当前不能晋级，但继续 monitor 有价值；如果未来 P2 真能提供两个独立槽，组合可从 `5` 槽走向 `7` 槽，单槽风险才可能接近 `14.29%`。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage328 结论。
- 是否更新 `research/registry.md`：是，把最新关键阶段推进到 Stage328。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重大突破、路线废弃或跨线合并。
