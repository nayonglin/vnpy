# Stage037 开仓分钟价格回放审计

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 00:54 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读数据工程审计；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否；这是 Stage036 之后的必要证据边界收窄，不是可接入候选。
- 是否触发A/B：否，`candidate_ready=0`，`ab_triggered=0`。

## 外部调研与判断

- 参考资料：
  - vn.py `BacktestingEngine.cross_limit_order` 源码显示 BAR 模式下限价单用 bar high/low 判断穿越，并用 bar open 作为 best price 参与成交价计算：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py
  - Backtrader order execution 文档强调当前 bar 已经发生，Market 单只能在下一根 bar 的 open 成交，Limit/Stop 只能用下一根 OHLC 做穿越推断：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - NautilusTrader 文档强调 bar 执行必须明确 `ts_init`/`ts_event` 时间戳语义，否则会产生 look-ahead；bar-only 模式需把 OHLC 转成事件序列撮合：https://nautilustrader.io/docs/latest/concepts/backtesting/
  - Zipline slippage/matching 源码体现订单撮合应作为独立 slippage/order processing 层处理，而不是从成交结果倒推开仓分钟：https://github.com/quantopian/zipline/blob/master/zipline/finance/slippage.py
- 我的判断：主流回测框架都要求先定义订单产生时间、下一可交易 bar、bar 时间戳语义和撮合规则，再生成成交；不能用历史成交价在分钟K里事后找“相同价格”来恢复真实开仓时间。Stage037 因此只做价格匹配可恢复性审计，不把任何匹配状态交易化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage037_open_timestamp_price_replay_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；审计固定 `PRICE_TOL_REL=1e-10`，仅用于浮点价格相等判断。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：复用 Stage010 官方 C9/15w 路径与 Stage861 full minute 源，覆盖官方 closed lots 样本。
- 账户规模：`150,000`
- 成本口径：复用官方 C9/15w 成本口径。
- 样本过滤：不过滤产品、方向、年份、月份；所有 official open trades 与 closed lots 均纳入。
- 策略/归因口径：用 Stage861 entry-day 分钟K机械匹配 official open price，固定分为 `first_bar_open_exact`、`single_later_exact_price`、`multi_exact_price_ambiguous`、`no_exact_price_on_entry_day`、`missing_stage861_day`。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26,017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot `36.0902%`
- 其他关键指标：
  - open trade rows：`387`
  - closed lots：`399`
  - 首根 open 精确匹配 open trades：`99`
  - 单一后续精确价格 open trades：`26`
  - 多重精确价格 ambiguous open trades：`129`
  - 当日无精确价格 open trades：`131`
  - Stage861 缺失日 open trades：`2`
  - 首根 open 精确匹配率：`25.5814%`
  - 可唯一定位 open trades：`125`
  - ambiguous 或 missing open trades：`262`
  - `no_exact_price_on_entry_day` closed-lot 净 PnL：`24,671,820.30`，占总净 PnL `57.3035%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_report_stage037_open_timestamp_price_replay_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_summary_stage037_open_timestamp_price_replay_audit_v1.csv`
- orders：不适用；本阶段未生成订单。
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_contribution_curve_stage037_open_timestamp_price_replay_audit_v1.csv`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_status_summary_stage037_open_timestamp_price_replay_audit_v1.csv`
- 视觉：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_replay_status_path_chart_stage037_open_timestamp_price_replay_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_replay_status_summary_chart_stage037_open_timestamp_price_replay_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_price_match_scatter_stage037_open_timestamp_price_replay_audit_v1.png`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage037_open_timestamp_price_replay_audit/qmt_roll_stage037_c9_minrisk_open_timestamp_price_replay_audit_atlas_page001_stage037_open_timestamp_price_replay_audit_v1.png`

## 视觉观察

- path chart 显示 `no_exact_price_on_entry_day` 组承担最大右尾台阶，净 PnL 占比 `57.3035%`，说明“只保留可匹配开仓分钟”会直接砍掉官方 C9 右尾底座。
- status summary chart 显示多重精确价格和无精确价格合计占 open trades 大多数；`multi_exact_price_ambiguous` 中位精确命中数 `7`，不能解释为唯一成交时点。
- scatter 显示 first-bar delta 与 first exact match index 混杂，正负 PnL 同时分布在可匹配和不可匹配区域，没有形成可交易单调关系。
- atlas page001 显示即使 `first_bar_open_exact`，也可能出现多次同价命中且样本正负混杂；首根/同价线索只能做审计，不足以做规则。

## 结论

- 本阶段结论：`stage037_price_replay_partial_ambiguous_no_trade_rule`。Stage861 价格匹配只能部分定位 official open price，且大多数开仓要么多重命中、要么当日无精确价，不能作为真实初始开仓分钟账本。
- 是否进入下一步：进入数据工程下一步，但不进入候选、不进入 A/B。
- 下一步：构建订单事件回放原型，先从日线信号/官方 entry candidates 生成独立 replay orders，再按 Stage861 分钟 bar 顺序撮合 open、C9 `0.5R stop/retry`、C2 intraday stop，输出 replay trades 与官方 ledger 的价格/盈亏/事件一致性审计。

## 过拟合反思

- 运行前判断：否，但风险很高。原因是本阶段若把“可匹配价格”当成好坏标签，会直接滑向事后数据修补。
- 运行后判断：否。
- 原因：本阶段没有新增交易参数、没有筛产品/年份/方向/月度，也没有用最终 PnL 选择规则；结论是拒绝 price-match 交易化，反而降低了后续过拟合风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只能沿数据工程推进。
- 原因：Stage036/037 已证明当前 official artifacts 无法给出真实开仓分钟，价格匹配也不足以替代。若要继续分钟级进出场，必须先建立可复验的订单事件回放账本；否则所有基于首根/clock/session 的规则都会建立在伪时间戳上。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage037 并把下一步收敛到 order-event replay prototype。
- 是否更新 `research/registry.md`：否，本阶段不是跨线重大突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线数据工程审计，不属于重要突破、路线废弃、正式候选、跨线合并或记录体系迁移。
