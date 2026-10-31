# Stage016 C_R150 原周线 runtime 可移植设计审查

- line_id：`futures_weekly_short_ma_slope_gate`（registry 尚未列入该新线，但现有 LINE.md 已定义；本轮不改索引）。
- 当前模式：day；记录时间：2026-10-31 15:55（北京时间）。
- 工作区/分支：`/Users/mac/.codex/worktrees/weekly19-official-20261031/fian` / `codex/weekly19-official-20261031`。
- 原冻结树：`/Users/mac/.codex/worktrees/weekly-short-ma-slope-20261029/fian`，只读。
- 阶段性质：独立 runtime 设计审查，供 root 统一正式接口；并未实现或资格认证。
- 是否重要突破：否，工程边界澄清；是否触发 A/B：否，按用户已授权 Stage014 原 C 正式迁移，禁止改变 alpha。
- 权限范围：仅新增本阶段记录；未修改原树、正式模块、生产、CTP、邮件、调度、Git index、commit 或远端。

## 外部调研与判断

- 已检索 VeighNa 官方 GitHub 的组合策略模板文档和 OffsetConverter。官方文档明确 target 是持续性状态，并可在同步后恢复；实际持仓和目标不能混为一个字段。参考：<https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md>、<https://github.com/vnpy/vnpy/blob/master/vnpy/trader/converter.py>、<https://github.com/vnpy/vnpy_portfoliostrategy/releases>。
- 判断：可复用原 StrategyTemplate 的实际持仓、订单/成交回报和交易所 offset 转换能力。应保留本地冻结实现及版本，不因网上当前版本存在修复就升级。上游默认 target 持久化不包含本策略全部 ProductState、周线 AM、风险记忆和计划层，不能单独证明本策略可恢复。
- 已按 `skills/futures-live-execution-sop/SKILL.md` 读取 work-type、registry、正式配置、现有正式研究线。用户本次明确授权更换正式策略，旧 SOP 的 C9 默认身份不覆盖该授权；旧生产资格仍不自动适用于新周线语义。

## 原策略构造和固定行为

原入口 `research/lines/futures_weekly_short_ma_slope_gate/tools/run_stage014.py` 实际构造顺序如下：

```text
HistoricalSafety(
  ReserveTopup(
    ShortBottom20(
      daily_addon_strategy_class(base=Stage847C9, enabled=False)
    )
  )
)
```

`daily_addon_strategy_class(..., enabled=False)` 直接返回 `Stage029v2(Stage029v1(ShortCase2(NoMacd(ThreeMa(base)))))`，仅把 research_daily_addon_enabled 置 False；不会安装加仓类的方法、所有权账本或日线加仓逻辑。Stage029v1 又明确关闭 short_case2，因此允许的普通信号是 long_case1a、long_case2、short_case1a。MA5/10/20，41周储存、21完成周 readiness；MACD 禁算、MA40不参与决策；多空 MA 斜率 wrapper 和 long top20 wrapper 均不存在。

原基类继承链为 `Stage847C9 -> Stage830Broker10 -> Stage827C2 -> Stage804LongTighterInitialStop -> Stage772ExactAm -> QmtRollPortfolioStrategy`。Stage847/827 的盘中功能关闭，但 Stage830 broker10 sizing 和 Stage827 的真实 fill 与原信号层匹配仍有作用，不能把基类直接替换为裸 QmtRollPortfolioStrategy。

必须以真实 C 输出的完整 `actual_strategy_settings.json`（而非只选几项参数）为固定配置来源。当前参考：原树 `outputs/stage014_C_20150101_attempt001/actual_strategy_settings.json`、同目录 preflight/effective_parameters/input_manifest；Stage014 冻结 HEAD `688754057ba1dc07caa9edc537ceec486f678372`。实际固定比例为 regular/breakout/MA-cross 0.018、volume+OI surge 0.06、OI surge 0.06、OI decline 0.025；原 min_risk_per_trade=1000、max_risk_per_trade=50000000。以下原有行为也仍在，不应因用户只概括 OI 比例而删除：

- max_concurrent_positions=19，固定原19池；所有加仓、RSI partial exit、reverse、alignment exit 关闭。
- Stage830 broker multiplier 1.65、projected broker margin/equity cap 1.0、95%→80% forced margin deleverage、cluster margin cap 25%、cluster heat deleverage。
- 5交易日 rollover delay、shape same-volume reopen、shrink_to_allowed、target_contract_only、OI确认以及既有方向/量折扣、ATR/range admission。
- 实际 runtime 风险 flags：portfolio volatility 与其 deleverage False；overheat 与其 deleverage False；portfolio drawdown gate/deleverage False；cluster heat gate False；cluster heat deleverage True；cluster margin cap True。

## 周信号、保护和成交时点

1. `WeeklyArrayManager` 只接收正量、正且有限 OHLC；完整周要求该物理合约存在本周所有权威交易日的实 K，不填缺日。周 close/OI 为最后交易日，volume/turnover 求和，OHLC 为该周真实聚合。跨复用合约显示名超过366日真实bar间隔时 reset inner AM；physical epoch 还需独立 fail-closed 验证。
2. 指标信号只在 `am.fresh=True` 的完成周最后交易日生成；非 fresh 日保留 alignment/RSI 风险输入，但清空 signal/breakout，不能重复下同一周信号。21个完成周 ready，roll shape 自身要求20周目标合约 observed history。
3. `completed_weeks(calendar)` 的 terminal 周仅当末日是 Friday 才认完成；节假日周可能周四已经结束，runtime 应传至少延伸至下一 ISO 周的权威交易日历，同时真实行情仍截止目标日，不能用未来行情补周。
4. 原模型为日线下一交易日开盘，未验证盘口、队列、滑点或可成交容量。周五完成周信号对应下一 trading_date，夜盘产品可能周五21:00就执行；不能统一写成周一09:00。实际执行必须使用经验证 session 与真实报价，不把 daily open 模型冒称为实盘成交价。
5. 初始保护计算使用最近完成周 OHLC 和周 history，相对计划日的真实 daily close 做方向准入：long `max(weekly_close*0.98, weekly_low)`（Stage804 tighter），short `min(weekly_high, weekly_close*1.02, 最近3完成周high的max)`。有限正价但位于错误方向，029v2在预算、目标和保证金 reservation 之前拒绝；非有限或非正保护价硬失败，不能修正价格救仓。
6. 动态 stop 仅 fresh 完成周更新周 high/low 和基于周收盘的 max_profit_pct。原利润锁档为 2%→0.1%、3%→1%、5%→3%、10%→8%、20%→15%、30%→20%，选择最高已达档且只收紧。周 ATR14 条件 `abs(close_t-close_t-1)>=2*ATR` 时，使用本周 `(high+low)/2` 收紧。giveback 默认 False；trailing_stop_pct=0。
7. 前2周保护须入场后已接受至少2个完整周；排除当前周的此前两周 low min/high max，long 逐次 max、short 逐次 min；当周 close <= long stop 或 >= short stop 才退出。MA20退出比较前一完成周 MA20；layer stop、MA20、前2周等全部受 fresh 周 close 确认门控制。
8. 所有以上价格技术保护均为完成周 close 确认后的下个交易日 open 模型委托，盘中触价不会退出。Stage904 以 tick 触价执行旧 C9 保护会改变策略，不能原样使用。
9. 每日账户/cluster/强平风险和换月仍运行，不能只每周五调用 `on_bars`。原循环优先次序为 rollover；持仓动态保护→前2周→layer→cluster heat→portfolio margin→其他日级 deleverage→RSI（关）→MA20。正式 adapter 应保留调用次序。

## short 全历史 bottom20

`RangeHistory` 按 `(vt_symbol, contract_epoch_id)` 对所有 available 正量 physical daily bars 做累积 low min、高点 max，包括信号日；阈值 `low+0.2*(high-low)`，signal daily close <= 阈值拒绝，flat range拒绝。只用于 short_case1a 的 flat_entry/env_probe/reverse_entry；不应用 rollover_reopen，也不移植 long top filter。`_open_position` 再检查一次，避免绕过。

这是“全部已获准可用同物理epoch历史”，原独审没有证明从上市首日起完整；正式材料不能把它升级称为完整上市历史。必须携带 physical epoch、history_start/end/bar_count、low/high/threshold 与数据 receipt。新增当前行情时要延长同一因果表，不以滑动20日或跨主力拼接近似。

## 换月精确行为

mapping 目标与实际合约不同时，首次发现差异的日为 elapsed=0；每个之后新交易日 +1，>=5 才到期；目标再次变化重置。等待期间继续管理原仓，不开普通新仓。到期要求旧/新当日真实bar与元数据；旧仓先产生 flat target，随后按目标合约自己的完成周 history 的3MA形态考虑续仓。不使用旧正式策略的 backward-ratio continuous history，不要求新合约 fresh crossover，MACD 无参与。

续仓最多 `min(原实际剩余手数, 原全部风险门允许的整数手数)`；容量零不重开。029v2仍要求其 weekly initial stop 相对当日计划价方向有效。short bottom20不约束此换月续仓。

实盘委托是异步的；不能在旧仓尚未真实平掉时就把其资金释放视为可用。决策可保留原 planned rollover，但执行 adapter 必须把新仓 send 依赖于旧仓 confirmed fills 与 fresh available cash；这是执行约束，不得把新旧同时持仓写成已完成换月。部分成交、撤拒、跨session和重启应使用同一 signal/order identity 恢复。

## 建议可移植接口（供 root 定稿，尚未实现）

```python
build_weekly19_runtime(
    settings_asset, metadata, session_calendar, physical_epoch_daily,
    broker_snapshot, durable_state, confirmed_cash_state,
) -> Runtime

runtime.process_completed_day(
    trading_date, real_daily_bars, data_receipt,
    broker_snapshot, confirmed_cash_state,
) -> Decision  # targets, intents, weekly_protection, funding_requests, state_hash

runtime.apply_order_update(order_event) -> StateReceipt
runtime.apply_broker_fill(fill, signal_identity) -> StateReceipt
runtime.reconcile_broker_snapshot(snapshot, confirmed_cash_state) -> Reconciliation
```

- 用原工厂组装到 range/historical 语义，资金部分替换为真实资金 wrapper；不安装回测 `ReserveTopup` 的自动转账。
- 决策阶段的 engine facade 提供原 StrategyTemplate 用到的 get_size/get_pricetick、send_order/cancel/日志等接口，send/cancel只收集 intent，不触发真实订单。实盘执行由根统一的授权/风控消费者接管。broker_fill才改变实际 `pos_data`，计划层和 target 属于 pending 计划，不能伪造 filled。
- 真实 fill 须携带 `signal_datetime`、`signal_order_id`、`trading_date`。Stage827 `_sync_open_trade` 已能按 signal_datetime 匹配周五计划层、处理下周和分批成交；若缺该字段，会退回成交日匹配并可能失配。真实 execution datetime 与 trading_date不能混用。
- 每个 day/receipt 和 fill ID 幂等。决策含 before/after state hash；原 on_bars 只有一次成功 apply，不应重复推进 bars_since_entry、rollover elapsed、AM completed 或风险记忆。未执行 intent 的计划层和保证金 reservation 必须按订单终态撤回/保留可证状态，不能在重启后自动重发。
- 周末邮件收集本周固定信号、eligible funding need 与真实余额；发送不证明入金。实际 E、Available、broker snapshot 与确认现金 receipt 才能开放 send。

## 真实 broker 持仓和现金初始化/更新

1. 冷启动必须从 fresh broker snapshot 得到实仓和可用资金；历史回测/影子仓位不能替代。confirmed-flat才允许空状态启动。若 broker 有持仓，必须有当前策略同一 release 与 fill ledger 可恢复的完整 ProductState/PositionLayer；否则只读/close/reduce/reconcile，不能追入历史理论仓。
2. ProductState全字段（含入场日期、risk_mode、prev2week止损、roll delay四字段、bars_since_entry）、PositionLayer全字段（成本、保护价、high/low、max_profit、entry_price_synced、giveback标记）、pending close/open ownership、目标与未终结订单须完整持久化。仅 broker均价不能恢复周线保护历史。
3. 原 `_reconcile_state_with_position` 在实仓非零但 layers空时会用当日 close、simple 2% stop造层；Stage029 audit明确 `reconciliation_rebuilt_layer_count=0`。正式初始化必须提前拒绝该分支，不能把其视为合格实盘恢复。
4. AM与range可从截至target的已签收历史重建；重建不得让真实策略历史on_bars产生理论仓位。可以纯指标 warmup，或序列化 AM inner/pending/completed/epoch/cursor；需要用 fixture验证二者相同。已存在资金路径风险记忆须恢复，不能每次影子运行重置连败/风险状态。
5. 交易权益 E只认 fresh broker账户权益或确认结算基准+真实成交/已知mark的可核对桥。不能把账户 Available当E；Available 是额外执行上限。场外15万与邮件建议金额均不能增加E或Available。
6. 原 `_refresh_risk_state` 会调用 `_estimate_equity`，on_bars末又把 estimated写入settled，update_trade另加 `_trade_to_close_pnl`。若注入broker权益后仍走原累计MTM，会重复记账；资金 adapter应明确 broker观测/E估值为唯一权威，阻止历史PNL和入金再加。confirmed transfer应有唯一receipt并与broker变化核对，不能仅 `settled_balance += T`。
7. E<=0要显式阻止新开。原多处 `estimated_equity or base_capital` 可把0回退15万，回测reserve只在其wrapper加了guard；删除自动转账wrapper后仍必须保留非正E保护。风险减少与平仓路径继续可用。
8. 每个新开send之前再核 fresh broker position/orders/Available、quote、metadata和cash receipt，按真实已用/冻结保证金加执行上限；不能通过改变原alpha比例来掩盖资金不足。资金不足给出blocked与funding request，等确认到账后重新验证当前仍有效intent。

## 源码/资产闭包与复用判断

直接保留原类最稳妥，88个本地静态import模块的历史报告依赖不是88个alpha模块，但直接import Stage847会全部带入。正式release应纳入实际动态import闭包和hash；若抽取最小类模块，必须逐方法AST/hash对照，不能用“功能类似”替代。以下策略层文件需原样：

- `research/lines/futures_weekly_formal_no_half_r/tools/weekly_adapter.py`
- 同目录 `stage008_three_ma.py`、`stage014_no_macd.py`、`stage018_short_case2.py`、`stage029_week_close_exits.py`、`stage029_week_close_exits_v2.py`、`stage032_daily_addon.py`（False工厂）、`stage022_historical_safety.py`、`stage020_no_position_cap.py`、`stage012_ai_selection_off.py`。
- `research/lines/futures_weekly_short_ma_slope_gate/tools/stage005_short_bottom20.py`。
- `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`、Stage772/804/827/830/847基类及其actual import依赖、`main_contract_mapping.py`、`contract_metadata.py`、`qmt_roll_intraday_execution.py`、固定vn.py/portfoliostrategy本地版本。
- `stage014_reserve.py` 只作冻结会计/资金意图依据，不能直接作为生产资金变更实现。Stage847/840/827回测engine和stage011 daily-open helper只作原模型验证，不作为broker成交引擎。

资产必需：固定实际settings/effective参数、原19池CSV、current+历史mapping、合约size/tick/margin/slippage metadata、physical_epoch_daily/range源、日线SQLite或相同schema的签收行情、权威交易日/session日历、源数据receipt、release身份和策略source hash。Stage001两个runtime CSV分别是 structural prefilter 和 portfolio eligibility（源hash固定），虽AI关闭仍可能被构造路径读取，删除前必须证明加载不可达。AI模型和monthly pool消费者应禁用；供需信号原路径明确空且不存在，正式迁移不能意外读取某台旧机器已有信号文件。

能复用：CTP broker snapshot/contract查询、order/trade回报、OffsetConverter、幂等订单治理、只读gate、真实账户风控、签收manifest/qualification/activation架构、邮件发送机制（由root统一改语义）。

不能直接复用：Stage901从历史资本冷启动的C9理论持仓当真实仓位、Stage904 tick stop、旧C9 retry/C2合成成交、AI月更signal/material identity、Stage941旧保护解释、旧capital profile/生产资格或把旧15万cold-start日期当新周线起点。旧组件是否适配的具体代码由root处理，本记录不宣称它们已改完。

## 本轮变更、验证和结果

- 新增脚本：无；修改脚本：无；删除脚本：无；新增/修改/删除策略参数：无。
- 新增文件：本阶段设计审查记录。未改LINE.md、registry、根memory/back_log。
- 验证：只读源码、静态AST导入闭包（88本地模块）、原C实际设置/preflight、冻结源hash和最新独审记录。没有运行金融引擎或任何新回测。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：本轮N/A，没有新增或覆盖回测指标。Stage014原结果保持其独审结论与限制，operator授权不替代经济/生产证据。
- 运行前/后过拟合判断：本轮否；原因是固定规则工程语义核对，不筛参数、不比较新收益。此前多起点仍重叠且非独立OOS，本轮不提升其统计置信度。
- 运行前/后继续价值：是；原因是周收盘保护、真实资金和异步broker状态边界若未澄清，会直接改变策略或产生无资金开仓；价值仅在按固定规则完成可审核迁移，不做同历史救参。
- 结论：原策略可以通过原factory薄适配迁移，但必须先统一真实cash/position/fill与周保护消费者；本轮产物是设计审查，`production_qualified=false`。等待root明确接口任务后实施。
