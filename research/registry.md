# 研究线总索引

更新时间：2026-06-12 15:49 CST

## 当前研究线

| line_id | 中文名 | 资产/策略 | 当前状态 | 最新关键阶段 | 主要记录目录 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| `futures_trend` | 期货趋势策略 | 商品期货趋势/Stage78历史基准与执行安全资产 | Stage78-1 50万口径从当前实盘默认降级为历史/研究对照；CTP/SimNow daily gate、broker-test/SimNow 1手测试链路、普通 SimNow 开平仓/撤单/断网和执行安全验收作为当前官方实盘流程复用的执行资产 | Stage373/Stage360/Stage295：官方实盘默认口径已从 Stage653 原版切换到 Stage372 20万恢复仓 sleeve；Stage78-1 保留为对照，不再作为实盘默认 signal source | `research/lines/futures_trend/` | 执行安全资产继续复用；后续每日虚拟盘按 skill 读取 current official live config；review 禁止新增开仓，空仓不得发送平仓单；若券商要求 `1010/41407/41415` 评测前置证明，则等该前置稳定后复刻开平仓/撤单/断网 |
| `futures_trend_drawdown30_preserve_return` | 期货趋势回撤30以内保收益线 | 商品期货趋势/当前官方实盘 Stage372 20万 | 当前官方实盘默认仍是 Stage372/20万 `official_live_stage372_20w_recovery_sleeve`；Stage432 月度冷启动审计显示盈利不依赖 `2020-01` 单一起点，但严格 DD30/DD40 与 2x 成本口径仍有尾部失败；Stage653 原版与 Stage372 30万只作历史/研究对照 | Stage432：`2020-01` 至 `2026-04` 共 `76` 个逐月独立起点，`73/76` 正收益；`>=252` 交易日成熟样本 `64/64` 正收益，中位收益 `200.9738%`、最小收益 `17.9975%`，但 DD30 失败 `28/64`、DD40 失败 `1/64`、2x成本 DD40 失败 `6` 个，决策 `official_monthly_start_audit_has_hard_fail` | `research/lines/futures_trend_drawdown30_preserve_return/` | 继续只用 Stage372 20万 current official live config 跑每日影子盘和执行闸门；不要按最差月份/品种/阈值补丁化。若继续研究，优先账户层生存线/出金锁定、成本/TCA、保证金压力治理或独立外生信息源 |
| `futures_trend_2019_data_extension` | 期货趋势2019数据延展线 | 商品期货趋势/Stage819 30万 AM41+OI0.8+旧AI+RSI95锁盈候选 | Stage819 30w 已登记为当前 primary official candidate `official_candidate_stage819_30w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`；Stage813 50w 与 Stage777 50w 保留为对照；当前实盘默认仍是 Stage372 20万 | Stage823：按用户要求登记 Stage819 30w 为官方候选；只改 `account_capital/c3_capital=300000`，继承 Stage813 逻辑。Stage822 月度3年滚动显示 30w 不稳定压过 50w，不能直接切 live default | `research/lines/futures_trend_2019_data_extension/` | 只做 30w 候选 shadow、执行 dry-run、风险复核和 Stage372 20w 公平对照；不继续扫本金、RSI 阈值、OI 倍率、AM 根数、AI topN、训练窗或 horizon |
| `futures_trend_loss_streak_threshold_sweep` | 期货趋势连败阈值扫描线 | 商品期货趋势/当前官方实盘 Stage372 20万 | 独立敏感性研究线；Stage002 已证明阈值 `3` 不是收益普适最优已完全证明，但作为防守闸门有明显价值；不改正式配置 | Stage002：阈值 `3/4/6` 多起点验证完成。阈值 `3` 在 `32` 个窗口收益冠军 `15` 次、回撤冠军 `21` 次；季度收益冠军 `12/25` 未过预设 `13/25`，但季度回撤冠军 `17/25`，弱窗口更稳。Stage001 全周期 `3` 仍最强：`8,728,285/4264.1425%/-38.6713%/Sharpe1.6279` | `research/lines/futures_trend_loss_streak_threshold_sweep/` | 不直接改正式版；停止阈值小数/倍率小数扫描。若继续，只能做预声明高质量机会豁免或 forward watch，不能用红框窗口反推 |
| `futures_trend_loss_streak_risk_floor` | 期货趋势连败风险地板线 | 商品期货趋势/当前官方实盘 Stage372 20万 | 独立敏感性研究线；Stage001-002 已反证把正式连败风险地板从 `0.1` 放宽到 `0.2/0.3/0.4/0.5`，不改正式配置 | Stage002：A 正式 `8,728,285/4264.1425%/-38.6713%/Sharpe1.6279`；C `0.2/0.3/0.4` 分别为 `5,464,445/-46.6202%`、`4,220,145/-51.6497%`、`2,558,700/-57.3563%`，全部 `not_promoted`；Stage001 的 `0.5` 也失败 | `research/lines/futures_trend_loss_streak_risk_floor/` | 停止固定小数风险地板扫描；正式版继续 `1,1,1,0.1 + recovery_sleeve`。若继续，只能做 recovery sleeve 触发结构隔离、账户级 selector、外生特征或 forward watch |
| `futures_trend_quarter_risk_no_streak` | 期货趋势低风险关闭连败机制线 | 商品期货趋势/当前官方实盘 Stage372 20万 | 独立研究线；Stage007 公平 A50 vs C50 反证 C50 正式替代，不改正式配置 | Stage007：A50 只把正式 Stage372 逻辑资金改为50万，C50复用Stage748。C50 全体收益胜出仅 `6/76`、成熟 `3/64`，DD40失败 `5/76` vs A50 `2/76`；A50 相比 A20 收益胜出 `57/76`、成熟 `51/64`，说明50万改善的是共同整数手颗粒度而非C50新alpha，决策 `official_500k_vs_c50_monthly_start_c50_not_promoted` | `research/lines/futures_trend_quarter_risk_no_streak/` | 停止扫风险倍率小数、关闭连败路线和本金放大救参；正式版继续 `1,1,1,0.1 + recovery_sleeve`。若继续低回撤体验，转账户层资金分层、出金/锁盈、生存线或独立 sleeve |
| `futures_trend_cash_reserve_bucket` | 期货趋势现金备用桶线 | 商品期货趋势/当前官方实盘 Stage372 50万研究口径 | 独立资金管理研究线；Stage001 反证 `50万总资金/40万交易桶/10万备用桶` 作为正式增强，不改正式配置 | Stage001：C 全周期 `9,656,610/1831.3220%/-39.0439%/Sharpe1.3532`，A50 `21,371,670/4174.3340%/-39.7236%/Sharpe1.6218`；逐月 `76` 起点 C 收益胜出 `20/76`、回撤胜出 `68/76`、成熟收益胜出 `16/64`、中位收益差 `-70.7835pp`，但 `2022-05` 从 A50 `107.579%` 修复到 C `281.856%` | `research/lines/futures_trend_cash_reserve_bucket/` | 不接正式版；停止扫交易桶/备用桶比例。若继续账户层研究，转向不降低初始交易能力的外层备用资金、出金锁盈或生存线框架 |
| `futures_trend_winner_trade_forensics` | 期货趋势历史赢家逐笔复盘线 | 商品期货趋势/当前官方实盘 Stage372 20万 | 只读法证/候选验证线；内部字段、0.1 豁免、市场广度、账户状态、慢趋势一致性、入场前短影线、入场后确认仓真实加仓、入场后顺畅K线退出延迟均未找到可靠可交易化特征 | Stage024：入场后顺畅K线一次性延迟 `prev2day_stop` 真实 A/C 被反证。C1 `post1_smooth` 触发10次，仅 `6,764,990/3282.4950%/-38.4013%/Sharpe1.5544`；C2 `post5_long60le20` 触发36次，仅 `6,117,135/2958.5675%/-38.3586%/Sharpe1.5374`，均远低于正式 `8,728,285/4264.1425%/-38.6713%/Sharpe1.6279`；`phase_2024_2025` 局部有效但 `phase_2020_2021` 破坏复利底座 | `research/lines/futures_trend_winner_trade_forensics/` | 停止真实确认仓加仓和退出延迟路线；不扫 `post1/post5` 阈值、窗口、倍数、延迟天数、品种、方向或年份救参。入场后顺畅K线只保留为复盘/forward watch 标签；若继续只能换新信息源、账户级 selector 或等待新OOS样本 |
| `futures_trend_profit_lock_exit` | 期货趋势盈利锁定退出线 | 商品期货趋势/Stage78-1退出规则 | Stage279反证“锁盈已激活+趋势仍强时直接跳过prev2day_stop”；正式78-1盈利锁档位和prev2day_stop保持不变 | Stage009：C触发1754次但全周期少775.9万、回撤恶化10.70pp，仅1/6窗口胜出 | `research/lines/futures_trend_profit_lock_exit/` | 停止该形状；若继续只考虑降仓、延迟确认或账户层风控，不做MA阈值补丁 |
| `futures_trend_hot_universe_expansion` | 期货趋势热门缺口扩池线 | 商品期货趋势/Stage78-1基础宇宙扩展候选 | 收束研究线，不改78-1正式池；`y/ag`均不promotion，heat/giveback风险倍率也失败 | Stage005：组合层heat/giveback日级回放全周期好看但弱窗口独立回放失败，停止该overlay形状 | `research/lines/futures_trend_hot_universe_expansion/` | 正式池不变；若继续风险治理，转回`futures_trend_risk_overlay`账户层分层 |
| `futures_trend_risk_overlay` | 期货趋势风险覆盖层 | 商品期货趋势/78-1风险叠加层 | 独立研究线，不改78-1 alpha | Stage238：balanced_tranche已进入日更部署日报 | `research/lines/futures_trend_risk_overlay/` | 接真实账户余额并监控实值与回放偏差 |
| `futures_trend_signal_quality_ai` | 期货趋势信号质量AI | 商品期货趋势/78-1二级信号质量模型 | 暂停/降级，不改78-1默认逻辑 | Stage236：路径标签+purged walk-forward后仍反证，当前特征不足以稳定加注 | `research/lines/futures_trend_signal_quality_ai/` | 等待更长OOS样本、外生特征源或全新不泄漏特征 |
| `futures_range` | 期货震荡策略 | 商品期货震荡/区间回归 | 独立研究线，暂不接第78 | 第198阶段v8长侧可交易性归因 | `research/lines/futures_range/` | 做`cs.DCE short`短侧状态归因 |
| `futures_swing_no_lower_shadow` | 期货无下影线波段策略 | 商品期货波段/开盘惯性 | 独立研究线；B版看大做小弱转正但 Sharpe/滑点敏感不过关，不接第78 | Stage009：周线顺势 + 回撤后第一根 strict 无下影线收益`0.477%`、回撤`-5.1529%`、Sharpe`0.0481`，2倍滑点转负 | `research/lines/futures_swing_no_lower_shadow/` | 暂停主动优化；只做成本敏感、腿部归因、最差年份/品种只读复盘 |
| `stock_range_paper_v1` | 股票震荡paper线 | A股横截面震荡/liquid_q3 paper | paper监控线，黄灯继续观察 | paper monitor suite：权益`2.2225`、回撤`-15.16%`、Sharpe`0.7373` | `research/lines/stock_range_paper_v1/` | 定期补数据、跑paper suite、积累OOS |
| `stock_range_30w_industry_resid_core` | 股票震荡30万industry_resid_core线 | A股30万账户/行业残差核心 | 持有期硬规则被反证，转向组合风险归因 | Stage339未确认退出反证：第4-10日仍为正收益 | `research/lines/stock_range_30w_industry_resid_core/` | 做简单母本日期层/组合层风险归因 |

## 状态定义

- `正式基准`：当前可作为后续研究默认对照。
- `部署候选`：只在特定资金/账户约束下作为候选，不自动替代正式基准。
- `paper监控`：已有固定复跑入口和监控状态，但不能自动实盘。
- `独立研究线`：代码、配置、输出命名必须隔离，不得污染其他线。
- `强线索`：出现有价值结果，但尚未通过稳健性和分段反证。
- `停止/降级`：只保留经验，不继续扫参。

## 合入规则

1. 各研究线日常只改本线目录。
2. `registry.md` 由合入者维护；并行 agent 不应频繁修改。
3. 根目录 `memory.md` / `back_log.md` 只记录跨线结论、重要里程碑和迁移说明。
