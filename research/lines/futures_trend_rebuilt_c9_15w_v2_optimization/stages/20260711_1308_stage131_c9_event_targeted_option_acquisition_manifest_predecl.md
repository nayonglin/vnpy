# Stage131 当前 C9 真实事件定向期权采集清单预声明与实施计划

> **执行要求：** 本阶段只冻结采集清单和数据合同，不联网、不下载行情、不回测收益、不修改策略。实现按 TDD 推进，完成后由独立 agent 只读复核。

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：`day`
- 预声明时间：`2026-07-11 13:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：Stage130 后的数据 acquisition manifest；不是策略候选
- 是否重要突破：待清单完整性结果
- 是否触发 A/B：否；Stage132 metadata 覆盖与后续 premium/流动性门通过前禁止 A/B

## 目标

- 把冻结的 Stage847 C9/15w `closed_lots` 全量映射成“合约 + 入场日”的历史期权查询事件，回答下一步需要查询哪些时点、标的、保护方向和数据字段。
- 清单必须覆盖全部基准交易事件，不按盈利/亏损、2022 窗口、品种、方向或 AI 排名筛选。
- 本阶段不声称期权可交易，不选择最终 option symbol，不计算 premium、IV、Greeks、收益或回撤。

## 冻结输入

- closed lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_closed_lots_stage847_stage830_c4_stop_retry_engine_v1.csv`，`405` 行，SHA256 `1bc2771d40fd3f5f1f7c240ab259b1d39e65265cf44d5eb82dc0f742b29581a2`。
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_trades_stage847_stage830_c4_stop_retry_engine_v1.csv`，`793` 行、其中 Open `388` 行，SHA256 `59acf2887778eb5d943f7db70c6bf479b4db4a412f96022338ca6b106bd46c48`。
- entry risk：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage847_stage830_c4_stop_retry_engine_entry_risk_stage847_stage830_c4_stop_retry_engine_v1.csv`，`367` 行，SHA256 `4224a8fb0482cb67ef330c481b0e19df02b82e903df9bfade163bd9b0affa9b7`。
- trading calendar：同源 `qmt_roll_stage847_stage830_c4_stop_retry_engine_curve_stage847_stage830_c4_stop_retry_engine_v1.csv`，`8,148` 行、`2,037` 个唯一交易日，SHA256 `199926a5dac7e21c0381dfd807675235e07cf650429fa0295e2e2705d94cc56d`。只取 date 列，不读取收益/权益。
- 基准快照：`405` 个 lot、`238` 个期货合约、`365` 个唯一 `vt_symbol + entry_date` 查询事件、`332` 个入场日、`19` 个产品。
- 区间：最早入场 `2018-01-15`，最晚退出 `2026-05-07`；不只截取 2020+ 或 2022。
- closed lots 白名单字段：`lot_id/open_trade_id/vt_symbol/direction/entry_date/exit_date/entry_price/volume/size/product/holding_calendar_days/stop_distance/risk_amount`。原文件有 `32` 条缺 risk/stop 扩展字段，禁止删掉；必须用同源 trades+entry_risk 恢复。

## 外部调研与判断

- TqSdk 官方 `query_options` 在 `TqBacktest` 中按历史回放当前时点过滤合约；Stage130 已实测固定历史日使用 `expired=False` 才表示当时 active。
- CME 官方保护性期权示例说明，长 futures 的保护腿是 PUT、短 futures 的保护腿是 CALL；保护保留有利方向，但 premium 会抬高盈亏平衡点。
- Israelov 的 protective-put 研究提醒：持续买保护可能因 premium drag 和时点错配，风险调整后不如简单降风险。本路线因此不能默认“有期权就会改善回撤”。
- 我的判断：先绑定当前 C9 全量真实事件，比下载 19 品种全市场全链更可审计，也比按 2022 亏损品种定向下载更不容易过拟合。Black-Scholes 合成历史 premium 明确禁止。

## 三种方案与裁决

1. **真实事件定向 manifest（采用）**：覆盖全部 405 lots，按 365 个唯一历史事件查询同标的 active chain；数据量可控、与基准路径闭合。
2. **19 品种 2018-2026 全链下载（暂不采用）**：覆盖最全，但在未证明事件级可用率前会引入大量无关 strike/date，下载和质量审计成本过高。
3. **理论期权价格代理（否决）**：无法复原真实 skew、流动性、涨跌停、成交空洞和 premium，不能支撑目标结论。

## 固定事件语义

- 查询键：`event_id = sha256(vt_symbol|entry_date)`；同一合约同一入场日的多个 lot 合并为一个 query event，但保留 `lot_count/lot_ids/total_volume/total_original_risk_amount`。
- TqSdk 标的：vn.py `symbol.EXCHANGE` 机械转换为 `EXCHANGE.symbol`，不改合约月份或大小写。
- 历史查询：Stage132 每个 event 必须在 `entry_date 00:00:00 -> 23:59:59` 的独立 `TqBacktest` 上执行 `query_options(underlying, expired=False)`；不允许长回放异步推进后猜测查询时点。
- 保护方向：`long -> PUT`，`short -> CALL`；若同一合约同日同时有多空，拆为两个 acquisition requirement，但 metadata query 仍只执行一次。
- 原策略止损锚：直接使用同源 `entry_risk.stop_price`，不从成交价和旧 `stop_distance` 反推。当前基准有 `13` 条成交价已跨过原止损价，反推公式会改变真实语义。
- 原风险金额：逐 lot 使用同源 `entry_risk.risk_per_contract × lot volume`；已有 `373` 条 closed-lot `risk_amount` 只用于逐行复核，缺失 `32` 条由该公式恢复。`abs(fill-stop) × size × volume` 只作为成交偏离诊断，禁止用于保护规模或 coverage 权重。
- entry-risk 关联顺序冻结为：风险记录只能关联到同源曲线的**下一个交易日**；同合约+方向+同手数按 FIFO 直接关联；同日 stop-retry 必须存在中间 Close 后继承前一笔关联；剩余只允许同一风险日对应的下一个交易日、同合约+方向的唯一 volume-mismatch 关联。独立预审计确认 `388/388` 都满足 next-trading-date，方法数固定为 `360/23/5`；删除旧 `5/10` 自然日参数。
- 查询结果必须保存 untouched API metadata 与 normalized metadata 两份；不得把归一化文件称为 raw。

## Stage132/后续数据合同

- untouched metadata：完整源字段、原始 epoch、SDK 版本、历史 query timestamp、请求参数、response 行数和文件 SHA256。
- normalized metadata：`option_symbol/underlying_symbol/option_class/expire_datetime/last_exercise_datetime/strike_price/expired/volume_multiple/price_tick`。
- premium/流动性阶段至少要求：标的与候选期权的日线 OHLC、volume、OI；入场/退出日分钟 OHLCV；能取得时保存 bid/ask，不得用当前 quote 回填历史。
- PIT：metadata query timestamp 必须等于 event entry_date；最终选择只能使用 entry_date 当时已返回且当日已有行情的数据。
- 完整性：每个 request 都要有终态；成功、无期权、权限失败、超时和异常分别记录，不允许静默丢行。
- hash：source、tool、test、predecl、每个 raw/normalized batch、汇总均写 bytes + SHA256；manifest 排除自身与 checksum 文件，并另写 detached SHA256，避免自引用循环。凭证只记录存在性，值不得落盘。

## 本阶段成功门

- 四个输入 SHA 与冻结值一致；405/793/367/8148、Open 388、交易日2037、238/365/332/19 各项基准计数全部一致。
- `lot_id` 唯一，closed-lot 必需字段无缺失；entry/exit 顺序合法；entry_price/volume/size 为正；direction 仅 long/short。
- `388/388` Open trade 均关联 entry risk，且交易日全部等于风险日后的下一交易日；已有 `373` 条 non-null stop_distance 与关联结果最大误差 `0`，缺失 `32/32` 全部恢复；关联方法计数必须为 `360/23/5`。
- 已有 `373` 条 closed-lot `risk_amount` 与 `entry_risk.risk_per_contract × lot volume` 最大绝对误差不超过 `1e-8`，缺失 `32/32` 全部恢复，405 条恢复后原风险金额均严格为正。
- 所有 405 lot 恰好映射到一个 query event 和一个 acquisition requirement；同日同合约重复只在 query 层合并，不丢 lot/risk/volume。
- 365 query event 的 `event_id` 唯一且可由键重算；Tq symbol 机械可逆。
- long/short 对应 PUT/CALL，保护锚逐行等于关联的原 `stop_price`；不得出现收益、winner、2022 选择条件。
- decision 只有全部本地门通过才为 `stage131_event_targeted_option_acquisition_manifest_ready_for_metadata_batches`。
- 任一门失败即 `stage131_event_targeted_option_acquisition_manifest_not_ready_close`；不得删掉失败品种或日期救清单。

## 文件与接口计划

- 新增工具：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage131_c9_event_targeted_option_acquisition_manifest.py`
- 新增测试：`tests/test_rebuilt_c9_v2_stage131_c9_event_targeted_option_acquisition_manifest.py`
- 输出目录：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage131_c9_event_targeted_option_acquisition_manifest/`
- `load_frozen_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]`：返回 lots、trades、entry_risk、trading_calendar、source_inventory，并校验四个输入 SHA、schema 和基础数值。
- `build_entry_risk_links(trades: pd.DataFrame, entry_risk: pd.DataFrame, trading_dates: pd.Series) -> tuple[pd.DataFrame, dict[str, Any]]`：按冻结 next-trading-date 三层规则关联全部 Open trade。
- `enrich_lots_with_entry_risk(lots: pd.DataFrame, links: pd.DataFrame) -> pd.DataFrame`：按 open_trade_id 恢复原 stop_price/risk 字段并保留 link method。
- `to_tqsdk_underlying(vt_symbol: str) -> str`：机械转换标的格式。
- `build_query_events(lots: pd.DataFrame) -> pd.DataFrame`：按合约+入场日聚合 query event。
- `build_acquisition_requirements(lots: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame`：生成每 lot 的保护方向和止损锚。
- `audit_manifest(lots, events, requirements) -> dict[str, Any]`：执行闭合、唯一性、方向、公式和禁止筛选审计。

## TDD 实施步骤

- [x] 写失败测试：输入 schema/数值/日期错误必须 fail-close，合法最小样本通过。
- [x] 运行单测确认 RED，原因必须是 Stage131 模块或接口缺失。
- [x] 写失败测试：next-trading-date exact、同日 stop-retry 继承和 next-trading-date volume-mismatch 三类关联全部可复算，非下一交易日或歧义必须 fail-close。
- [x] 最小实现输入加载、entry-risk 关联/enrich 与 `to_tqsdk_underlying`，运行 focused test 变绿。
- [x] 写失败测试：同合约同日两 lot 合并为一个 query event，风险/手数/lot 映射守恒；不同方向保留两条 requirement。
- [x] 最小实现 `build_query_events/build_acquisition_requirements`，运行 focused tests。
- [x] 写失败测试：long/short 的 PUT/CALL 和止损锚公式；event_id 可重算；任何 lot 丢失或重复映射均 fail。
- [x] 最小实现 `audit_manifest` 和机械 decision。
- [x] 生成 lot/query/requirement/data-contract/audit/decision/lineage/manifest/report，不联网。
- [ ] 运行 Stage130+131 和相关 TqSdk 回归；机械复算 405/238/365/332/19、hash、凭证和订单/CTP 隔离。
- [x] 拉独立 agent 只读复核；P0/P1 必须修复，P2 记录到下一阶段。

## 运行前反思

- 过拟合：否。清单覆盖冻结基准的全部事件，不使用结果标签，也不按 2022、盈利品种或 option 返回结果删样本。
- 继续价值：有。Stage130 已证明单点历史链可读，Stage131 能把下一步网络工作从模糊“下载期权”收敛成可复核的 365 个历史请求。
- 停止边界：本阶段不下载 metadata/bar、不选择 strike/DTE、不计算保护比例、不回测收益；这些工作不得借“顺手”进入 Stage131。
