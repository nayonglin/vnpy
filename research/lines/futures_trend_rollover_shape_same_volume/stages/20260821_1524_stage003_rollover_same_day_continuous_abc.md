# Stage003 新主力仅当日行情与元数据、连续历史形态 A/B/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-21 15:39 CST`
- 基准提交：`06d1d11ad356330353eed9c6681db24764989eb8`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：用户确认把换月新主力门槛改为“仅要求当日可交易行情和完整合约元数据”，并以点时连续历史计算形态后的完整 A/B/C 重跑
- 是否重要突破：是，属于换月数据语义的结构性修复；首次在完整回测和 2026-08-18/19 真实短历史事件中证明不再依赖新合约 K 线根数，但仍为研究候选、未晋级正式配置
- 是否触发 A/B/C：是；A 为当前正式基线，B 为 Stage002 新合约自身至少 40 根，C 为新主力仅当日行情/元数据 + 连续历史

## 外部调研与判断

- QuantConnect Futures Universe：`https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures`，连续期货用于研究和指标，实际交易使用映射后的具体合约。
- QuantConnect US Futures Security Master：`https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-futures-security-master`，提供 mapped contract 与 backward ratio normalization 的明确区分。
- QuantConnect Futures History：`https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/asset-classes/futures`。
- LEAN futures 数据说明：`https://github.com/QuantConnect/Lean/blob/master/Data/future/readme.md`。
- 我的判断：要求新主力自身积累 40 根才计算同一产品的趋势延续，是把“指标历史”和“可交易合约”错误绑定。合理的点时语义是：指标沿用同一产品截至换月日的连续历史，真实下单标的只要求当日有可交易行情和乘数、最小价位、保证金元数据。不能直接拼接未复权价格，否则换月价差会制造虚假 MA/MACD 信号。

## 本次版本变更

- 新增参数：`rollover_shape_history_mode="target_contract_only"`，默认保留旧语义；Stage003 C 显式使用 `backwards_ratio_continuous`。
- 修改参数：C 保持 `rollover_shape_volume_policy="shrink_to_allowed"`；A/B 作为冻结对照，不修改正式参数。
- 删除参数：无。
- 新增规则：C 的新主力仅要求当前行情批次存在当日日 K、OHLC 为正且自洽、成交量大于 0，并且 contract size、pricetick、margin ratio 都为正。
- 修改规则：C 不读取新主力历史根数作为交易门槛；取旧合约实际可见历史，以 `新主力当日收盘/旧合约最近可见收盘` 做 backward-ratio 平移；旧合约同日有 bar 时替换同日末行，旧合约已提前停止时追加新主力当日真实 OHLCV/OI，再计算 MA5/10/20/40 与 MACD。
- 历史要求边界：新主力没有 40 根要求；指标来源连续历史仍须覆盖 MA40。若旧合约连续历史不足、当日行情不可交易、元数据不完整或复权锚点非法，均 fail closed。
- 当日语义修正：以新主力是否出现在当前 `bars` 行情批次且日期为该批次最新日期为准；不要求旧合约最后一根也在同日，因为旧主力可能在切换日前一天停止提供日 K。
- 手数规则：继续使用 `min(旧仓实际剩余手数, 全部硬风控允许手数)`，允许手数为 0 才不开仓。
- 诊断新增：`history_mode/history_source/history_input_ready`、目标/旧/source K 线数、复权比、当日行情、可交易性、元数据、乘数、最小价位和保证金字段。
- 正式配置/实盘：未修改正式配置和生产 checkout，未连接 CTP，未调用下单或撤单 API；生产数据库专项验收使用 SQLite `mode=ro` 只读连接。

## 回测参数

- 区间：`2018-01-01` 至 `2026-05-29`，共 `2037` 个交易日。
- 账户规模：`150,000`。
- A：`stage003_A_official_live_c9_15w`，正式 C9/15万原样。
- B：`stage003_B_target_history_40_shrink`，新主力自身至少 40 根 + 动态缩手。
- C：`stage003_C_same_day_quote_metadata_continuous_shrink`，新主力仅当日行情/元数据 + 点时连续历史 + 动态缩手。
- 数据/成本：正式 Stage901 C9 分钟 K 注入、正式 AI eligibility、broker10、0.5R stop/retry-once、相同 rates/slippage/size/pricetick。
- 预声明门：A 必须与 Stage002 A 逐日一致，B 必须与 Stage002 C 逐日一致；C 候选诊断数必须等于换月平仓数，且必须实际存在 `target_count<40/source_count>=40` 的绕过样本，不能再以目标 K 线不足判定 `insufficient_indicator_history`。
- 产物发布：全部合同在内存中通过后，使用同文件系统临时目录原子替换 Stage003 产物；失败不覆盖上一轮有效结果。

## 回测结果

| 指标 | A 正式基线 | B 新合约 40 根 | C 当日行情+连续历史 |
| --- | ---: | ---: | ---: |
| 期末权益 | `13,071,214.10` | `13,492,951.90` | `13,338,365.80` |
| 总收益 | `8614.1427%` | `8895.3013%` | `8792.2439%` |
| 最大回撤 | `-56.2069%` | `-57.2674%` | `-56.9876%` |
| Sharpe | `1.3622` | `1.3631` | `1.3627` |
| 总滑点 | `1,525,590` | `1,573,350` | `1,517,200` |
| 总交易次数 | `808` | `811` | `825` |
| 非零日胜率 | `52.5841%` | `52.8745%` | `52.6812%` |

### C 相对 B

- 期末权益：`-154,586.10`。
- 总收益：`-103.0574pp`。
- 最大回撤：改善 `+0.2797pp`。
- Sharpe：`-0.0004`，近似持平。
- 总滑点：`-56,150`。
- 总交易次数：`+14`。
- 非零日胜率：`-0.1933pp`。

### C 相对 A

- 期末权益：`+267,151.70`。
- 总收益：`+178.1011pp`。
- 最大回撤：恶化 `-0.7807pp`。
- Sharpe：`+0.0004`，近似持平。
- 总滑点：`-8,390`。
- 总交易次数：`+17`。
- 非零日胜率：`+0.0971pp`。

### 换月事件合同

- A：换月平仓 `23` 次，无候选诊断。
- B：诊断 `23` 次，续开并成交 `14` 次；原手数 `13`、缩手 `1`、不开仓 `9`。
- C：诊断 `23` 次，全部完成形态评估并续开成交；原手数 `20`、缩手 `3`、不开仓 `0`、未成交 `0`。
- C 中有 `5` 次 `target_observed_bar_count=1`、`source_observed_bar_count=41` 的真实短历史绕过样本，全部 `same_day_bar_ready/market_data_ready/metadata_ready=1`，没有目标 K 线长度过滤。
- 5 次样本：`SM809->SM901`、`jm1901->jm1905`、`hc1905->hc1910`、`AP905->AP910`、`CF909->CF001`；其中 3 次原手数、2 次缩手。
- `volume_contract_pass=1`、`history_contract_pass=1`、`stage002_curve_identity_pass=1`。

### 近期真实换月专项验收

- 数据源：`/Users/bytedance/Desktop/person/vnpy_production_live/.vntrader/database.db`，SQLite 只读；不作为正式激活或订单证据，只用于验证本次数据语义。
- `2026-08-18 si2609.GFEX -> si2611.GFEX`：新主力仅 `2` 根、旧连续来源 `41` 根；旧合约最后 bar 在前一日，因此追加新主力当日 bar 后指标序列 `42` 根；当日成交量 `222,722`，size `5`、pricetick `5`、margin `0.12`；多头排布、MACD histogram `77.7742>0`，形态允许，目标历史门槛绕过通过。
- `2026-08-19 jm2609.DCE -> jm2701.DCE`：新主力仅 `2` 根、旧连续来源 `41` 根；当日成交量 `881,425`，size `60`、pricetick `0.5`、margin `0.20`；多头排布、MACD histogram `37.7962>0`，形态允许，目标历史门槛绕过通过。
- Si 旧合约最后日 K 为 `2026-08-17`、新主力当日 K 为 `2026-08-18`，证明“以当前行情批次判断新主力当日可交易”比强行要求旧新 bar 同日更符合真实换月数据。

## 输出文件

- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_abc_summary.csv`
- comparison：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_abc_comparison.csv`
- daily：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_abc_curve.csv`
- trades：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_trades.csv`
- trade events：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_trade_events.csv`
- quality：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_rollover_shape_diagnostics.csv`
- recent acceptance：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_recent_rollover_acceptance.csv`
- decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage003/stage003_decision.json`
- 最终生成时间：`2026-08-21T15:39:18+08:00`。

## 结论

- 决策：`stage003_same_day_continuous_history_semantics_verified_research_only`。
- 工程判断：通过。新主力 K 线根数已从 C 的交易门槛中删除，换月日只验可交易行情和元数据；指标仍有足够点时连续历史且无未来数据。
- 性能判断：不把 C 晋级为正式 alpha。C 相对 B 少赚 `154,586.10`，虽然回撤改善 `0.2797pp`、滑点减少 `56,150`，但 Sharpe 基本不变；23 个换月、5 个短历史事件不足以证明长期优越。
- 用户语义判断：已满足。近期两次仅 2 根的新主力，在新规则下都会进入形态评估且多头形态通过，不会再因 40/41 根门槛只平不开。
- 是否进入下一步：保留为研究候选并做固定规则 forward shadow；不扫描 MA、MACD、复权方式、日期、品种或缩手比例，不修改正式配置、不激活实盘。
- TODO：后续若用户明确要求晋级，需另做正式物料冻结、生产支持链回归、独立复审和激活门禁；本阶段本身不授权生产变更。
- 最终回归：`66 tests passed`；另有完整 A/B/C 四次成功重跑、5 个短历史门禁样本和 2 个近期数据库专项样本通过。

## 过拟合反思

- 运行前判断：否。变更来自同一产品换月的数据语义，不按盈亏、品种、年份或单个事件调参数。
- 运行后判断：规则层面低，结论层面中等。连续历史 + 当日可交易合约是结构设计，但完整历史只有 23 次换月、短历史只有 5 次，不能把收益差视为稳定 alpha。
- 原因：C 的自由度没有增加，但事件数量少；据当前结果继续挑复权方式、MA/MACD 或只保留盈利事件会迅速过拟合。

## 继续价值反思

- 运行前判断：有。旧逻辑把同一产品趋势所需历史错误地强加到刚切换的新合约，真实造成只平不开。
- 运行后判断：有，工程价值明确、主动调参价值低。
- 原因：完整回测 5 次和近期 2 次真实事件都证明新合约历史门槛被移除；下一步价值在固定规则 forward shadow 和生产工程审查，不在继续回测救收益。

## 合入建议

- 是否更新本线 `LINE.md`：是，冻结 Stage003 新数据合同和研究结论。
- 是否更新 `research/registry.md`：否；同一研究线继续推进，待最终合入者统一更新。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，因为这是换月数据合同的重要结构修复和完整 A/B/C；不追加 `memory.md`，尚未成为正式策略政策。
