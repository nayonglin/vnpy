# Stage137 当前 C9 PIT 质量事件单向卫星预声明

- 时间：`2026-07-11 20:30 CST`
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 阶段：`Stage137`
- 设计选择：采用此前推荐方案 1；持续目标模式授权按判断继续。
- 性质：研究 A/B/C；不修改 C9 正式策略、实盘配置、CTP、邮件、launchd 或订单路径。

## 研究问题

Stage010/014 的质量加风险 proxy 明显改善收益和左尾，但 Stage026/028/058 把加风险接回主账户后，仓位、保证金和后续 sizing 反馈改变了 C9 路径，真实引擎结果失败。本阶段只回答一个结构问题：

> 当前 C9 的入场时可见质量事件，若放进不反馈主账户的独立单向卫星，能否在保留至少 70% C9 收益的同时降低最大回撤，特别是 2022 起点路径？

## 外部调研与判断

- AQR 的长期趋势研究强调趋势系统价值来自跨市场趋势右尾，防守结构不能系统性切断核心趋势暴露。
- pysystemtrade 把规则、仓位缩放、组合构建、capital correction 和账户 PnL 分层；额外资本风险应单独核算，避免把卫星盈亏反向污染母策略 sizing。
- vn.py portfolio strategy/backtest 是多合约真实账本的底座；本阶段使用当前仓库 C9 真实 trade/entry-risk/position 输出，不把 closed-lot 期末 PnL 直接塞到退出日。
- 判断：使用单向卫星可以隔离 Stage026/028/058 的账户反馈问题，但质量条件来自历史归因，仍存在选择偏差。因此只允许一个冻结条件、一个冻结比例、四锚点 canary 和 conjunctive gate；失败即关闭，不救参。

参考：

- AQR `A Century of Evidence on Trend-Following Investing`：<https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing>
- pysystemtrade backtesting/capital correction：<https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md>
- vn.py portfolio strategy：<https://github.com/vnpy/vnpy>

## 冻结输入

- A 母本：当前 Stage167 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，资金 `150,000`。
- C9 runner：`analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow._run_live_c9`。
- closed-lot 构造：Stage719 `_build_closed_lots`，仅用于把真实 open/close trade ID、PIT entry fields 和 FIFO 生命周期绑定。
- 日级 MTM：当前 C9 engine 的 `positions` close/pre_close 与真实 trade price；不得把 realized PnL 一次性记到 exit day。
- 产品规格：当前 metadata 的 `size / margin_ratio / slippage / rate`；缺失或非有限值 fail-close。
- AI 字段：open trade 对应 entry-risk/candidate 中已经存在的 `ai_product_pool_allowed / ai_product_pool_rank / selected_volume / entry_context / projected_total_margin_after / estimated_equity`。
- A 身份：每个起点重新运行的 C9 daily equity 必须与冻结 Stage167 curve 同日起点、同终点且最大绝对误差 `<=1e-6`。
- 所有实际输入文件和 producer 脚本写入 size/mtime/SHA256 manifest。

## 冻结质量条件

卫星 open 必须同时满足：

1. C9 真实 trade 为 `Open`；
2. `entry_context == flat_entry`；
3. `layer_kind == base`；
4. `ai_product_pool_allowed == 1`；
5. `1 <= ai_product_pool_rank <= 8`；
6. `selected_volume > 1`；
7. open trade ID、entry-risk 和 candidate 绑定唯一且时间不晚于实际开仓；
8. `satellite_open_volume = floor(original_open_volume * 0.25)`，结果为 0 就不下卫星单。

不增加 RSI、risk multiplier、OI、产品、方向、日期或 2022 专用条件；不改 `25%`，不使用 ceil/min-one。

## 单向卫星账本

- A：冻结 C9。
- B：`150,000 + satellite cumulative net PnL`，只诊断卫星腿。
- C：`A account_equity + satellite cumulative net PnL`，初始分母仍为 `150,000`。
- 卫星盈亏不反馈 C9 equity、风险倍率、AI 池、开仓手数、止损、重试、换月或任何后续信号。
- 同一个 C9 open trade 只建立一个卫星 sleeve lot；closed-lot 被拆成多行时先按 `requested_start_month + open_trade_id` 聚合，禁止重复开仓。
- 部分平仓按 C9 FIFO close 顺序处理：每次平仓后，卫星目标剩余手数为 `floor(base_remaining_volume * 0.25)`；最后一笔必须归零，不能超平。
- 卫星使用 C9 同一笔 entry/exit trade 的真实时间和价格；每次卫星成交按 `abs(delta) * slippage * size * cost_multiplier` 扣成本，并按 metadata rate 计算非零 commission。
- 每日逐段 MTM：上一 close -> 当日每笔真实 trade price -> 当日 close；多笔同日成交按 timezone-aware datetime、trade_id 稳定排序。
- 不允许 exit-day lump-sum、不允许相邻日期价格、不允许缺价格静默归零。

## 保证金与执行闸门

- 所有卫星平仓永远允许。
- 卫星开仓前使用该 C9 entry-risk 的 `projected_total_margin_after`，它已包含当前 C9 开仓后的计划保证金。
- 卫星已有仓按当前事件前最新 mark，新增仓按本次真实 trade price 计算 margin。
- `proposed_broker10 = (c9_projected_total_margin_after + satellite_margin_after) * 1.10 / previous_combined_equity`。
- `proposed_broker10 > 100%` 时整笔卫星 open 跳过；该 open_trade_id 永久 blocked，不允许以后追价补开。
- 同时输出 EOD aggregate broker10；任一日超过 `100%` 直接判 canary 失败，不事后强平修饰结果。
- `estimated_equity`、前一日组合权益、margin 或规格缺失/非有限时 fail-close，不允许 `_safe_float(..., 0)` 静默放行。

## Canary 起点

- `2020-01`：全样本和主要右尾。
- `2022-01`：2022 前启动路径。
- `2022-07`：已知峰谷窗口附近独立启动。
- `2026-01`：最新短样本，防止只对旧历史有效。
- 统一终点：`2026-06-30`。
- canary 先只跑 `1x` 成本；全部通过后，在同四锚点跑 `2x/3x`；二者再通过才允许扩 13 个逐半年起点。

## Canary 硬闸门

四起点必须全部满足：

- C9 identity `<=1e-6`；
- selected open 绑定唯一、PIT 字段完整、未来时间命中 `0`；
- 重复卫星 open `0`、超平 `0`、末日非零卫星持仓 `0`；
- 缺价/fallback/静默默认 `0`；
- 会计 reconciliation `<=1e-6`；
- proposed 与 EOD aggregate broker10 均 `<=100%`；
- C/B 均未破产；
- 每个起点 C 相对 A 收益保留 `>=70%`；
- `2020-01 / 2022-01 / 2022-07` 的 C 最大回撤均严格优于 A；
- `2026-01` 最大回撤不得比 A 恶化超过 `1.0pp`；
- `2022-01 / 2022-07` 最长水下均不得恶化，且至少一个严格缩短；
- B 累计净 PnL 至少 `3/4` 起点为正，且两个 2022 起点都为正。

任一失败即关闭本路线，不运行成本压力或 full，不调整 selector、25%、锚点、保证金上限或平仓分配。

## Full 闸门

只有 canary 1x/2x/3x 全通过才运行 `2020-01 -> 2026-01` 的 13 个逐半年起点：

- 所有起点收益保留 `>=70%`；
- 跨起点最差最大回撤严格优于 A；
- 两个 2022 起点与跨起点最差最长水下均不劣于 A，且至少一项严格改善；
- 2x/3x 下收益保留仍全部 `>=70%`，最差回撤不劣于对应 A；
- 严格任意 `>365` 天负窗口数量和最差收益必须同时优于 A；
- AI 月度审计 `FAIL=0`；
- broker10、会计、PIT、订单映射和末日清仓全部通过。

full 通过也只允许成为下一阶段完整单体引擎候选，不直接修改正式实盘。

## 输出合同

- base daily、selected open groups、candidate/order ledger、satellite daily、A/B/C summary；
- PIT margin audit、FIFO allocation audit、reconciliation、source manifest、input audit；
- canary/full decision JSON、中文 report、绝对权益/回撤/2022 聚焦图；
- 每次收益回测后必须由独立 agent 从 raw CSV 重算数字、时序、FIFO、保证金、成本、会计和 gate。

## 反思

- 运行前过拟合判断：中等。selector 源于历史 closed-lot 归因，但本阶段不再选择条件或参数，且把 2022、全样本和最新样本一起作为 conjunctive gate。

## 运行前数据合同修正（2026-07-11 22:10 CST）

本修正在任何 Stage137 `audit/canary` 收益运行之前完成，原因是独立代码审查发现：仅从 Stage719 `closed_lots` 构造候选，会用“结束日之后是否发生 close”决定历史 open 是否进入卫星。当前保存证据中，`2026-06-23 rb2610 short 11` 与 `2026-06-24 FG609 short 15` 均在 `2026-06-30` 仍持有，且入场时满足 flat/base、AI allowed、Top8 和 `selected_volume > 1`；静默排除会形成 lookahead。

因此在未查看 Stage137 收益结果的前提下，冻结以下替代合同：

1. 候选全集必须从 base `Open trades + PIT entry-risk/opened candidate` 构造；`closed_lots` 只负责绑定截至结束日已经发生的 FIFO close，不再决定 open 是否存在。
2. 所有入场时满足冻结质量条件的 open 必须进入 coverage audit；`missing_selected_open_count == 0`。
3. 结束日尚未平仓的合格 open 必须建立卫星仓并逐日 MTM 到 `2026-06-30`，不使用 7 月 close、不虚构结束日强平、也不扣虚假平仓成本。
4. 原“末日非零卫星持仓为 0”闸门废止，替换为：已平仓生命周期末仓为 0；terminal-open 生命周期的卫星末仓等于 `floor(base_remaining_volume * 0.25)`；`unexpected_terminal_position_count == 0`，terminal position/margin/PnL reconciliation `<=1e-6`。
5. audit 必须输出 `eligible_open_count / selected_open_count / missing_selected_open_count / open_at_end_count / expected_terminal_position_count / unexpected_terminal_position_count`，不能在 coverage 缺失时宣称 PASS。

该修正改变的是结束日统计合同，不改变 selector、25%、方向、品种、成本倍率、四锚点或收益/回撤门槛；不是根据表现救参。

## 运行前数据合同修正 2（2026-07-11 23:15 CST）

本修正在任何 Stage137 `audit/canary` 收益运行之前完成。独立 Task3 review-3 发现，eligible-only 的五日贪心映射仍可能先消费 synthetic retry/rollover Open，并可能把未映射 source 静默丢弃后让 coverage 自证通过。主线程随后只读核对旧 Stage847 保存形态：`388` 个 actual Open 包含 `23` 个 synthetic retry；`367` 个 risk 包含 `12` 个 rollover。严格五个日历日会漏掉春节/国庆后的下一交易日，严格 risk volume 还会漏掉被 margin deleverage 缩量后的 actual Open。

因此在未查看任何 Stage137 收益结果的前提下，冻结以下替代数据合同：

1. 先生成完整 PIT risk source ledger，包含 flat/base、rollover/non-flat 以及质量是否合格；再把全部 non-retry actual Open 一对一映射到 source；最后才提取质量合格且确有 actual Open 的 eligible actual Open。不得从 eligible-only source 直接贪心消费 trades。
2. `.stage847_c9.` synthetic retry 必须在任何 source 映射前排除并单独分类；rollover/non-flat risk 必须先绑定自己的 actual Open，禁止被 flat/base quality source 占用。
3. source 的预期执行日固定为其本地 risk date 之后、fresh base daily calendar 中的第一条交易日。该定义覆盖春节、国庆和周末，不再使用固定五个日历日。
4. 同一预期执行日、合约和方向先要求唯一 exact-volume；若没有 exact-volume 且只有一个 actual Open，允许实际成交量因执行/保证金约束小于 source volume，但必须显式记录 `volume_drift`。多候选、source/trade 复用、未来绑定或未分类 non-retry actual Open 一律 fail-close。
5. opened PIT diagnostics 没有 actual Open 时保留 `no_actual_open` 状态和数量；它不满足冻结条件第 1 条“C9 真实 trade 为 Open”，因此不计入 `eligible_open_count`，但不得静默删除或伪报为已映射。
6. coverage 必须满足：eligible actual Open 数 = mapped eligible 数 = selected lifecycle 数；missing/unexpected selected、future binding、未分类 non-retry actual Open 均为 `0`。所有计数必须来自显式 mapping audit，禁止缺列默认 `0`。
7. 最小输出新增 `pit_source_ledger.csv` 和 `actual_open_audit.csv`；source manifest 覆盖实际加载的本地 Stage901/847/513/719 producer、策略依赖和数据源，只哈希引用，不复制大文件。
8. 静态 `audit` 不运行收益账本，因此只允许输出 expected terminal coverage，不得伪造 terminal position/margin/PnL reconciliation；三项实际 reconciliation 继续只在 canary 中强制并进入硬闸门。

旧 Stage847 形态验证只用于修正数据绑定语义：按上述“完整 source + 下一 base 交易日 + retry 预排除”规则，可解释全部 `365` 个 non-retry actual Open，另显式留下 `2` 个无 actual Open 的 diagnostics。它不是 Stage137 收益结果，也没有改变 selector、`25%`、方向、品种、锚点、成本或绩效门槛。

## 运行前数据合同修正 3（2026-07-11 23:45 CST）

本修正仍发生在任何 Stage137 `audit/canary` 收益运行之前。独立 Task3 review-4 证明：同一预期交易日、合约和方向下存在多条 rollover/eligible source 与多笔 actual Open 时，按 volume exact/唯一 drift 仍可能交叉绑定且通过数量 gate。审查同时发现正向扩量、opened candidate without risk 和运行时动态 CSV 输入尚未 fail-close 或进入 manifest。

因此冻结以下最终身份与证据合同：

1. 同一 `(expected_execution_date, contract, direction)` 内，PIT source 按 `risk_datetime + entry_index + raw risk row index` 的 producer 顺序编号；non-retry actual Open 按 `trade_datetime + raw trade row index` 的 producer 顺序编号。身份一律按双方 sequence 一对一，不再以 volume 决定 source 类型。
2. 只要该 key 存在 actual Open，source 与 actual 数量必须相等；source/actual 任一多出、顺序不可唯一、复用或未来命中都 fail-close。只有整个 key 没有 actual Open 时，source 才可保留为 `no_actual`。
3. 每个映射必须落盘 source/actual 原始 row index、双方 sequence 和 `source_order_match=1`。rollover/non-flat/eligible 的 actual classification 由 producer order 继承，禁止事后按 volume 重排。
4. volume 只作执行审计：`actual_volume == risk_volume` 为 exact；`actual_volume < risk_volume` 为允许的执行/保证金缩量；`actual_volume > risk_volume` 是未声明扩量，立即 fail-close。
5. 输出必须对每条 raw risk、每条 raw Open、每条 raw candidate 保留最小投影。candidate 明确分为 opened/skipped，以及 matched risk/opened without risk；`opened_candidate_without_risk_count` 必须为 `0` 并进入 static/canary gate。
6. static/canary 同时验证 risk source ledger、actual Open audit、candidate audit 的 raw input row-count 恒等式，以及 source-order mismatch、正向 volume drift、opened candidate without risk 均为 `0`。
7. fresh C9 运行期间实际通过 `pandas.read_csv` 访问的本地文件必须被捕获并加入 source manifest，包括 Stage149 execution detail 和实际命中的 raw execution fallback minute 文件；捕获器异常时必须恢复原函数。未访问的整个 raw 目录不复制、不伪报为输入。

该修正只提高 source 身份和输入血缘的可证明性。它没有使用 Stage137 收益，也没有改变 selector、`25%`、品种、方向、锚点、成本、保证金或绩效门槛。

## 运行前数据合同修正 4（2026-07-12 00:14 CST）

本修正仍在任何 Stage137 `audit/canary` 收益运行之前。第三位独立 reviewer 发现，candidate 状态、静态 terminal 字段、raw trade price、重复索引、retry 改名和 CSV 读后变化仍有 fail-close 缺口。

冻结以下输入安全边界：

1. raw candidate status 仅允许 `opened` 或 `skipped`；空值、拼写错误和未来新增但未声明的状态立即失败。raw `entry_index` 与 `candidate_index` 必须非空且各自在完整输入 frame 内全局唯一。
2. static audit 只保存 `open_at_end_count` 与 `expected_terminal_position_count`，不得写入或默认 `unexpected_terminal_position_count`、terminal position/margin/PnL error。上述 actual 字段只能由 canary replay 产生。
3. 所有 raw trades 的 price 在 static audit 阶段就必须有限且严格正，volume 必须为正整数；不能因 eligible 为空而跳过验证。
4. 当前冻结 Stage847 producer 的计划 non-retry Open 必须发生在本地 `00:00`；`.stage847_c9.` synthetic retry 必须发生在非 `00:00`。任何非 `00:00` 且无 marker 的 Open、或 `00:00` 却带 marker 的 Open 都视为 retry 身份漂移并 fail-close，不允许进入普通 source sequence。
5. runtime 每次成功读取本地 CSV 后立即冻结 path/size/mtime/SHA256；同一路径重复读取发生变化、读取前后 stat 变化，或最终 manifest 落盘前与读时快照不一致，均 fail-close。reader 必须在成功或异常路径无条件恢复。

这些规则冻结的是当前 producer 的输入协议。未来正式 producer 若有明确的新 candidate 状态、retry 命名或成交时点，必须新开数据合同审查，不能在本阶段静默兼容。

## 运行前数据合同修正 5（2026-07-12 00:44 CST）

第一次真实 static audit 在任何卫星收益账本运行前 fail-close：官方 `build_static18_plus_fu_universe()` 会在 metadata 与策略初始化阶段各执行一次，并每次把同一内容重写到同一路径。验证显示重写前后 size 均为 `6,272` bytes、SHA256 均为 `72c5ca576bfe8aebe12da1e750d9eac980633a43ab9944479a77a7e824a71e34`，只有 mtime 变化。

因此冻结以下内容身份语义：

1. 实际输入身份由 `path + size + SHA256` 决定；size 或 SHA256 任一变化仍立即 fail-close。
2. 同一路径被 producer 重写但 size/SHA 完全一致时允许继续；manifest 必须额外记录 first read mtime、last read mtime、final mtime、same-content rewrite count 和 post-read same-content rewrite 标志。
3. mtime 仍作为血缘证据保留，但不再单独把“确定性同字节重写”误判为数据内容漂移。

本修正来自 static audit 的输入 producer 行为，不涉及任何 Stage137 收益、selector、仓位或绩效门槛。

## 运行前数据合同修正 6（2026-07-12 13:36 CST）

第二次真实 static audit 在第一个 `2020-01` anchor、卫星收益账本运行前 fail-close。旧 gate 要求 fresh current C9 与 `2026-07-01` 冻结 Stage167 曲线逐日相等，但两者实际使用的 AI 快照不同：Stage167 为 `477` 行、`52` 个 eval_date、SHA256 `8f54218d5c1922ebd4e0a2a16ef6d80c4f4392d1aa6c8cddd3f6127ffca574e3`；当前 official AI 为 `504` 行、`55` 个 eval_date、SHA256 `fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc`。主线程复跑证明 fresh current C9 与 `2026-07-09` current-AI Stage006 A0 在 `1,571` 日逐日一致；独立 reviewer 以 `97%` 置信度批准该根因，同时否决简单删除 identity gate。

因此在仍未查看任何 Stage137 卫星收益的前提下，冻结以下替代身份合同：

1. 本 Stage137 固定当前 official AI snapshot：路径必须是 official config 指向的 Stage182 combined eligibility；SHA256 必须为 `fc50e035cd66b65e94261ef70476747daa94ae73071d0f4d7206ff7b644271fc`，行数 `504`，eval_date 数 `55`，范围 `2019-12-31 -> 2026-06-30`。任何后续月更都必须新开阶段，不得在本阶段静默吸收。
2. 固定 Stage006 current-AI A0 为独立 golden：当前 AI 与 Stage006 A0 eligibility 的 `(eval_date, product_vt_symbol, score, score_rank, top_n)` 必须逐行一致；只允许 `strategy/score_type` 标签不同。`2020-01` fresh base 的 date/account_equity/net_pnl/total_margin_exact 必须与 Stage006 A0 daily 在 `1e-6` 内一致。
3. 每个 anchor 必须由两个独立 subprocess 从头加载 Python 模块、metadata、minute cache 和 current C9，禁止用同进程全局 cache 充当重复验证。两次 worker 的实际 source manifest 必须 path 集合和 size/SHA 一致；mtime-only 同内容重写仍按修正 5 审计。
4. 两个 worker 的 `base_daily / positions / trades / entry_risk / entry_candidates / closed_lots` 必须按显式 canonical schema、dtype、时区、NaN 和稳定行序做内容身份比较。身份字段和数量精确比较；golden daily 的三个派生浮点字段单独使用 `1e-6` 容差。
5. 主进程分别从两份独立 raw frames 派生 `pit_source_ledger / pit_candidate_audit / actual_open_audit / pit_binding_audit / selected_lifecycle / candidate_orders / price_audit / contract specs`，上述派生产物也必须 canonical 内容一致，不能只比较最终权益。
6. worker manifest 必须覆盖实际 runtime 读取的 CSV、当前 AI、golden eligibility/daily、full-minute、mapping、repo `.vntrader/database.db`、`vt_setting.json` 和本地 producer/策略源码；同时记录 Python/pandas/numpy、时区和关键 locale 环境。主进程在落盘前再按 size/SHA 复核一次。
7. static/canary audit 以 `current_ai_snapshot_pass / current_ai_golden_membership_pass / current_ai_golden_curve_pass / current_c9_repeat_identity_pass / repeat_source_manifest_pass` 取代旧 `stage167_identity_pass`。`2020-01` 是唯一 golden-curve applicable anchor；四锚点 repeat identity 必须全通过。
8. 任一 worker、manifest、golden 或 canonical identity 失败时，在独立 failure 目录写入不含绩效结果的结构化 diagnostic，并保持正式 Stage137 output 目录不变。

该修正只改变基准正确性和可复现性合同，不改变 selector、`25%` floor、方向、品种、四锚点、成本、保证金或任何收益/回撤闸门；不是根据 Stage137 表现救参。

## 运行前数据合同修正 7（2026-07-12 15:26 CST）

第三次真实 static audit 完成四锚点双 worker 后，在 `final_source_manifest` 汇总阶段 fail-close。每个锚点内部的两 worker 已先通过 path/size/SHA 完全一致；最终错误来自把 `2020-01 worker-a` 当作所有锚点的完整路径 baseline。不同历史起点按区间自然读取不同的合约日线/分钟文件，跨锚点全路径相等不是原预声明语义。独立 reviewer 以 `98%` 总体置信度确认两处 P1，并批准在不查看 Stage137 收益的前提下修正。

因此冻结以下替代 source manifest 合同：

1. 每个锚点内部两个独立 worker 的路径集合、size 和 SHA256 仍必须完全一致；任何 left-only/right-only、size 或 SHA 漂移继续 fail-close。
2. 不同锚点允许拥有不同路径子集；跨锚点只对重叠路径要求 size/SHA 完全一致。
3. final source manifest 路径集合必须恰好等于四锚点路径并集；每个锚点路径必须是 final 子集，禁止 final 缺项或额外项。
4. final 对并集中的每个路径逐字节重哈希，并与所有出现过该路径的 worker 记录比较；不能只与第一个锚点比较。
5. mtime 只保留为 same-content rewrite 血缘证据；同 size/SHA 的 mtime-only 变化允许通过。
6. writer 在 chart 后、atomic swap 前重新验证锚点子集、四锚点并集、重叠内容身份、final bytes 和四锚点 environment SHA 一致性。
7. TDD 必须覆盖合法不同子集、锚点内路径漂移、跨锚点重叠 SHA 漂移、final 缺项、final 多项、锚点非子集、并集不等和最终字节篡改。

该修正只纠正不同执行区间的输入集合语义，不改变 current-AI snapshot、golden、selector、`25%`、方向、品种、锚点、成本、保证金或任何绩效闸门；本次仍未产生任何 Stage137 收益结果，不属于表现救参。

## 运行前证据合同修正 8（2026-07-12 16:26 CST）

第四次 static audit 首次通过，独立 reviewer 重算全部 raw evidence 后以 `99%` 置信度认可内容门禁，并允许进入 1x canary；但同时发现三个 P2 持久化证据问题。主线程选择在任何卫星收益可见前先修复，冻结以下合同：

1. `first_read_mtime_ns / last_read_mtime_ns` 等纳秒时间戳必须全程使用精确 nullable/int64，禁止经 float round-trip；未被 runtime reader 直接访问的静态 source 以 manifest snapshot mtime 填充 first/last，并由 `observed_read=0` 明确区分。
2. final `post_read_same_content_rewrite` 必须由精确整数计算。当前 `294` 个标志属于 `-127ns -> +128ns` 浮点误差假阳性；真实 post-read rewrite 为 `0`，worker 内 same-content rewrite 为 universe 文件共 `8` 次。
3. audit 模式未运行的 `satellite_daily.csv` 和 `replayed_orders.csv` 也必须输出固定 schema 的零行表，保证标准 `pd.read_csv` 可读；不得用无表头空文件表示“未运行”。
4. `price_audit` 每行必须包含 `requested_start_month`，并把该字段纳入 repeat artifact key；跨锚点重复价格允许存在，但每一行必须能直接追溯到所属锚点。
5. 修复后必须重跑四锚点 static audit，并由新的独立 reviewer 验证：mtime 假阳性为 `0`、两个静态空表可读、price 行数按锚点为 `1129/320/384/48`、内容/AI/PIT/FIFO/source 门禁不回退。通过前不得运行 canary。

该修正只提高血缘统计精度和发布证据可读性，不修改任何交易计算、selector、`25%`、成本、锚点、保证金或绩效门槛；仍未查看任何 Stage137 卫星收益。
- 运行前继续价值判断：有。它是 Stage010/014 proxy 与 Stage026/028/058 主账户反馈失败之间尚未验证的结构差异；失败后该差异就应关闭。
