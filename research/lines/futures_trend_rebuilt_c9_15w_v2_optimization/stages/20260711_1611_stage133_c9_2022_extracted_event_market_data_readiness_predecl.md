# Stage133 C9 2022 已覆盖真实事件期权行情可读性探针预声明

> **执行要求：** 本阶段只回答 4 个固定真实事件的历史期权 premium、买卖一、成交量、持仓量和时间字段能否被当前 vendor 读取。不得计算保护收益，不得扫描 strike/DTE/比例，不得以任何结果解锁全量采集或策略 A/B。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 预声明时间：`2026-07-11 16:11 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage132 覆盖硬失败后的有限 data-readiness；不是策略候选
- 是否重要突破：否；无论结果如何都不能改变 Stage132 的全量覆盖裁决
- 是否触发 A/B：否；固定 `ready_for_option_strategy_ab=false`

## 外部调研与判断

- TqSdk 官方 `TqApi.get_kline_serial` 文档定义 1 分钟线包含 OHLC、volume、open_oi、close_oi；`get_tick_serial` 定义 tick 包含 last_price、bid/ask price1、bid/ask volume1、volume 和 open_interest。
- Stage130 已验证本机 `tqsdk=3.9.4` 在固定历史回放中可读取商品期权日线；Stage132 已证明当前 vendor 的全事件 metadata 覆盖只有 `123/365=33.6986%`，2022 核心窗口原风险覆盖只有 `26.461965%`。
- 我的判断：在 123 个 extracted 子集上做策略收益必然有强选择偏差，但在固定的 4 个 2022 核心事件上验证行情字段是否可读，仍能回答是否值得寻找覆盖更完整的同类数据源。

## 方案比较与裁决

1. **每事件一张机械 ATM 保护类别期权 + 分钟/tick（采用）**：请求规模最小，同时覆盖 premium、盘口、成交和 OI；结果只作字段可读性证据。
2. **四事件全链分钟/tick（否决）**：约 298 个期权序列，成本和超时风险显著增加，对“接口能否读取”没有必要。
3. **直接进入保护收益回测（硬拒绝）**：Stage132 对年份、交易所和产品的覆盖严重偏斜，任何收益结果都无法代表完整 C9 事件全集。

## 冻结输入与样本

- Stage132 terminal ledger SHA256：`c8361cbfb38007fda953730bdfff2a868a765b4ab114422ab853b963917f4b05`。
- Stage131 acquisition requirements SHA256：`13a01cd1a7b88d6b66fabc137cad73f19b01a9a0a6e335edbe1fe68f5f6089bf`。
- Stage131 entry-risk links SHA256：`22e397ffe8a3c00e5da1614db12deecc134b7c884edaecd25297a845a2891e7e`。
- 样本选择规则：取 Stage132 在预先定义的 2022 核心回撤窗口 `2022-03-09 -> 2022-06-29` 中全部 `terminal_status=extracted && cacheable=true` 的事件，必须精确得到以下 4 个，不允许删换：
  - `2424ec63fd31887211f99761200188b2ad2a0afb482997c9d8ad65a4081f3d39`，`MA209.CZCE`，`2022-04-26`，short/CALL，entry `2698`。
  - `9df8755883c082095fd03b87ab99734546df9b375453c82e1f2088871f20db98`，`au2206.SHFE`，`2022-05-10`，long/PUT，entry `403.56`。
  - `d90db2cbffbbe58a48be41bdeb736aa0056f404709d2bb47230eab9a25805cb8`，`MA209.CZCE`，`2022-05-13`，short/CALL，entry `2716`；该 event 对应 2 lots，但只请求一次行情。
  - `bb6d3275a518d933758ae3dfec300685616b6f48ae86c11e5d61e41c7e40c9c3`，`MA209.CZCE`，`2022-06-13`，long/PUT，entry `2916`；该 event 对应 2 lots，但只请求一次行情。
- 四份 Stage132 normalized metadata SHA256 依上列 event 顺序分别为：
  - `8abaab130972e6c137132372e9243b4661ea0e1a2abdd9532af336ea1e7285a8`
  - `505f55ee5cb479082f6b3737f91470d12b35f2439ed75cdba3c6d16a6908a038`
  - `7d552cb7f365101991f45753c4c5011927743f47b67e67756fce9a949e5fd03f`
  - `caf2e7c60d5ee08307fdd78b273f6fa98197a3f75d8590a02ddaab47f5666538`

## 固定机械选券规则

- protection class 完全由 Stage131 冻结方向决定：long -> PUT，short -> CALL；同 event 若方向不唯一则 fail-close。
- 只允许 expiry `> entry_date 23:59:59 Asia/Shanghai`；先选最早 expiry，不扫描 DTE。
- 在该 expiry 和 protection class 内，按 `(abs(strike-entry_price), strike, option_symbol)` 升序取第一张；不读取 option premium、volume、OI、spread 或未来收益参与选择。
- 预期固定结果必须为：
  - `2022-04-26 MA209` -> `CZCE.MA209C2700`
  - `2022-05-10 au2206` -> `SHFE.au2206P400`
  - `2022-05-13 MA209` -> `CZCE.MA209C2700`
  - `2022-06-13 MA209` -> `CZCE.MA209P2900`
- 任一输入 SHA、四事件集合、方向、entry price、metadata SHA 或机械选择结果不一致，联网前停止。

## 历史行情请求与时间口径

- 每事件独立 `TqApi(TqSim(), TqBacktest)`，禁止共享跨事件状态；本机版本固定 `tqsdk=3.9.4`。
- 回放窗口固定为北京时间前一自然日 `20:00:00` 到 entry_date `16:00:00`，覆盖夜盘与日盘；结果另保留原始纳秒时间戳和 Asia/Shanghai 规范化时间。
- 请求标的与选中期权的 1 分钟线，各 `data_length=2000`；请求选中期权 tick，`data_length=5000`。若 SDK 最大长度或历史数据不足，原样记录，不扩大窗口、不换合约。
- 每事件最长 `180s`，包含 `api.close()`；先只运行第一条 MA canary，独立审查通过后才允许剩余 3 条。
- 禁止调用订单、持仓、账户、CTP、邮件、launchd 或实盘接口；凭证只从既有环境读取，任何输出不得包含凭证值。

## 原始数据、审计和 fail-close

- 每事件原子 attempt 目录至少包含：`request.json`、选券审计、raw underlying minute、raw option minute、raw option tick、字段 schema、status、manifest 和 detached checksum。
- raw DataFrame 全列原样保存；规范化表只能增加 `datetime_beijing` 和 session-window 标识，不得删除或修改原列。
- 完整性硬门：event/input/metadata/producer SHA 全匹配；raw 文件 bytes/hash 闭合；原始行数和规范化行数一致；时间戳可解析且不重复；OHLC 合法；volume/OI/盘口量不得为负。
- premium 可读：session 内至少 1 条 option minute `close>0`。
- OI 可读：session 内至少 1 条 finite `open_oi` 或 `close_oi` 且非负。
- tick 可读：session 内至少 1 条 finite `last_price>0`。
- 双边盘口可读：session 内至少 1 条 `bid_price1>0 && ask_price1>0 && ask_price1>=bid_price1`；盘口量同时要求非负。
- 正成交可见：session 内 option minute 或 tick 至少一条增量/区间成交量大于 0。tick 的 `volume` 是日累计量，不得直接求和冒充成交量。
- 每个字段分别报告 observed/total 和时间覆盖，不允许把“有 premium”写成“可成交”，也不设人为收益相关阈值。
- `authentication_failed/timeout/query_failed/integrity_failed` 均 fail-close；失败不换事件、不换 option、不缩字段。

## 准入裁决

- `stage133_data_readiness_observed` 仅表示固定 4 个事件中相关历史字段可读；`stage133_data_readiness_not_observed` 表示当前接口对该小样本也不足。
- 无论 4/4 是否通过，固定：
  - `ready_for_full_premium_acquisition=false`
  - `ready_for_option_strategy_ab=false`
  - `ready_for_live=false`
- 只有未来获得对 365 事件，尤其 2018-2022 与 `fu/jm/FG/SM/hc` 覆盖充分的授权数据源，才允许另开覆盖阶段；Stage133 不能替代该门。

## TDD 与执行计划

- [ ] RED：输入 SHA、四事件全集、metadata SHA、方向/entry 唯一性或固定选券结果漂移必须 fail-close。
- [ ] RED：时间戳秒/ns 混淆、重复时间、OHLC 错误、负 volume/OI/盘口量必须被审计发现。
- [ ] RED：只有 last price 没有双边盘口时，不得误判 spread 可读；tick 累计 volume 不得求和。
- [ ] 实现纯函数选券、时间规范化、字段审计、原子 attempt 和 manifest；先 plan-only。
- [ ] 只跑固定第一条 canary，拉独立 agent 审查 P0/P1；未清零不得继续。
- [ ] canary 通过后只跑剩余 3 条，再做全量独立终审。
- [ ] 记录结果；不产生资金曲线、不做任何策略参数实验。

## 运行前反思

- 过拟合：数据接口探针本身否，因为 4 个事件是目标窗口内全部 extracted 事件，选券规则不读行情结果；但样本由 vendor 覆盖形成，任何策略外推都会是严重选择偏差。
- 继续价值：有限但有。它能判定当前接口是否至少提供真实事件级 premium/盘口/OI，从而决定未来是否值得寻找覆盖更完整的同类 vendor；它不能直接推进“收益保留70%且降低回撤”的策略目标。
- 停止边界：Stage133 结束后不允许在这 4 条上计算保护损益或调参；若只得到局部可读性证据，仍优先数据源覆盖而非策略优化。
