# 研究线总索引

更新时间：2026-05-28 07:46 CST

## 当前研究线

| line_id | 中文名 | 资产/策略 | 当前状态 | 最新关键阶段 | 主要记录目录 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| `futures_trend` | 期货趋势策略 | 商品期货趋势/第78-1正式基准 | Stage78-1正式基准与50万资金约束；CTP/SimNow daily gate 与 broker-test/SimNow 1手测试链路已固化；普通 SimNow `9999/trading` 已完成1手开仓成交、1手平仓成交、1手撤单回报、程序化断网回调和1.6-1.9执行安全验收；`41407`原生C++路线已能调用报单API但测试单曾被CTP拒绝，评测前置仍需券商确认/恢复 | Stage288：合并普通 SimNow 开平仓/撤单/断网证据，补齐阈值预警、交易指令检查、错误提示和暂停交易验收，16/16通过；执行安全模块已接入Stage250 OrderRequest构造层；外发版HTML已去本机路径、通用中文分章节，并补回脱敏交易细节与控制台关键打印 | `research/lines/futures_trend/` | 后续每日虚拟盘按skill执行；review禁止新增开仓，空仓不得发送平仓单；继续把 `ctp_execution_safety.py` 扩展到最终真实submit adapter；若券商要求 `1010/41407/41415` 评测前置证明，则等该前置稳定后复刻开平仓/撤单/断网 |
| `futures_trend_drawdown30_preserve_return` | 期货趋势回撤30以内保收益线 | 商品期货趋势/第78-1风险压缩 | 独立研究线；Stage079 `50万C3下单+11.5万外部现金` 仍是唯一baseline；多数补丁型方向已被反证；Stage083 确认 `78-1/Stage079/纯C3` 中 Stage079 在当前目标下综合第一；Stage101/102/103 将 xsmom 波动管理承载推进到真实整数手和执行保证金审计；Stage115/116/117 已将股指期货 TSMOM overlay 从强固定路径候选降为高分 paper/研究经验；Stage118/119/120/121 进一步反证商品动量拆腿、期限结构 basis-momentum/rank blend、固定分批启动/风险爬坡与 network momentum overlay，无新晋级；Stage122/123 将长期 value proxy 从研究候选降为研究经验；Stage124 反证固定贵金属避险小腿；Stage125 反证持仓兴趣确认动量 overlay；Stage126-140 多轮晋级/反过拟合/目标缺口审计确认：完整严格3/6个月目标尚未完成；Stage141-161 发现 Stage079/Stage103 对成交模型高度敏感，日线同日收盘、T+1 日线 open、已补齐的 `14:55 VWAP`、三种预收盘分钟语义、只换close/成交价的预收盘口径以及未补全OHLCVOI的一致预收盘bar均不能直接视为安全真实会话可成交口径，Stage103 暂停真实 paper/影子盘晋级；Stage158 证明 Stage156 的 `volume=0` 主要来自滚动未完成K线抽取语义，`completed_previous_row` 可恢复 strict OHLCVOI 数据链路；Stage160 将 completed-row 完整bar扩大到 Stage154 全部 `547` 个缺口span抽样，`2,665/2,665` 目标日 strict ready；Stage161 将最重前 `20` 个span升级为全日期探针，`2,121/2,121` 目标日 strict ready，数据链路晋级但策略候选不晋级 | Stage161：completed-row 预收盘完整bar重缺口全日期探针通过。Stage154 缺口计划前 `20` 个span、`20` 个合约、`2,121` 个目标缺口日期全部 strict ready；已完成分钟K `672,045`、正成交量分钟K `671,253`，失败合约 `0`，首次抽取耗时合计 `611.09` 秒，缓存修复后复验 `cached_raw=20`，决策 `completed_preclose_full_bar_shard_ready_extend_next_shard`。 | `research/lines/futures_trend_drawdown30_preserve_return/` | 下一步继续按 `20` span 左右做全日期 completed-row 回补分片并聚合，覆盖 Stage154 约 `21,475` 个缺口合约日键；全日期OHLCVOI稳定后，再做一致预收盘真实回放和3/6个月体验优化。 |
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
