# 研究线总索引

更新时间：2026-06-04 11:34 CST

## 当前研究线

| line_id | 中文名 | 资产/策略 | 当前状态 | 最新关键阶段 | 主要记录目录 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| `futures_trend` | 期货趋势策略 | 商品期货趋势/第78-1正式基准 | Stage78-1正式基准与50万资金约束；CTP/SimNow daily gate 与 broker-test/SimNow 1手测试链路已固化；普通 SimNow `9999/trading` 已完成1手开仓成交、1手平仓成交、1手撤单回报、程序化断网回调和1.6-1.9执行安全验收；`41407`原生C++路线已能调用报单API但测试单曾被CTP拒绝，评测前置仍需券商确认/恢复 | Stage288：合并普通 SimNow 开平仓/撤单/断网证据，补齐阈值预警、交易指令检查、错误提示和暂停交易验收，16/16通过；执行安全模块已接入Stage250 OrderRequest构造层；外发版HTML已去本机路径、通用中文分章节，并补回脱敏交易细节与控制台关键打印 | `research/lines/futures_trend/` | 后续每日虚拟盘按skill执行；review禁止新增开仓，空仓不得发送平仓单；继续把 `ctp_execution_safety.py` 扩展到最终真实submit adapter；若券商要求 `1010/41407/41415` 评测前置证明，则等该前置稳定后复刻开平仓/撤单/断网 |
| `futures_trend_drawdown30_preserve_return` | 期货趋势回撤30以内保收益线 | 商品期货趋势/第78-1风险压缩 | 独立研究线；Stage079 `50万C3下单+11.5万外部现金` 仍是原始日线baseline，但不能作为实盘收益/回撤承诺；Stage224-228 找到 `cap25 + maxpos4` 正常成本主研究候选 Stage526；Stage305-315 把执行无偏差链路推进到 TCA/live context 合同；Stage316-349 将扩池/source 路线固化为 forward monitor、PIT source/event ledger、公开源 raw-text/hash、master PIT append gate、event seed/episode 合同、20/63/126 outcome schedule、全本地品种独立风险槽相关性地图、watch 线产品 source contract、`lh.DCE` 官方月度源 active fetch probe/master PIT/rerun 去重闸门、年度独立趋势风险槽审计、年度赢家经济驱动 source gap board、`base_metals` LME/SHFE 官方源 active fetch 探针、SHFE 当前仓单 route forensic、低单笔风险扩池决策板、`base_metals` 授权 source fallback、贵金属官方源合同决策板、`CJ.CZCE` 官方仓单源 active fetch 探针、CJ 仓单 master PIT append gate、`ec.INE`/SCFIS 第二独立槽 source probe、SCFIS master PIT append gate，以及 `ec.INE` 期货代理新鲜度取证；selector 仍锁定，paper/交易白名单仍为 `0`。 | Stage349：`ec.INE` futures proxy freshness forensic，决策 `ec_ine_futures_proxy_stale_due_missing_revised_contracts_selector_locked`。结果：本地 EC 合约文件 `12`、官方 2026-06-03 活跃 EC 合约 `8`、当前官方活跃合约本地覆盖率 `0.00%`、本地 EC 最新可交易日 `2026-02-09`、本地 INE dump 最新可交易日 `2026-04-15`、到官方参考日缺口 `114` 天、Stage633 `days_behind_latest_tradable=67`、官方活跃 `ec2606/ec2607/ec2608/ec2609/ec2610/ec2611/ec2612/ec2703` 全部缺失，其中 `7` 个在本地 dump 最新日期前已上市仍缺失；Stage633 `data_pass/watch_corr_pass/low_corr_pass` 均为 `0`，max abs corr `0.1634`、rolling p75 `0.2175`、tail corr 缺失，SCFIS master rows/PIT dates `1/1`、hard gates `4/9`。结论：`ec.INE` 当前阻塞是 EC 挂牌结构变化后的合约清单/下载覆盖缺失，不是 alpha 已被反证；下一步必须先做只读 EC 合约发现 + 日线修复 collector 后重算相关性。 | `research/lines/futures_trend_drawdown30_preserve_return/` | 第一优先级仍是执行无偏差：用户确认测试环境和 read-only 动作后，用 Stage608 wrapper 显式 `--connect --wait-seconds 90` 刷新当前/未来 submit plan 的 read-only tick snapshot，再输入 Stage612/606/607 validator；随后仅在用户明确确认测试环境和 submit 动作后，做 exact `vt_orderid` writer 与 `EVENT_ORDER/EVENT_TRADE/EVENT_TICK` TCA reducer。扩池/选品侧停止宽池 `risk/cap/corr/maxpos` 小数调参；继续累计 `lh.DCE`、`CJ.CZCE` 和 `ec.INE/SCFIS` 新自然日 collection PIT；下一步先实现 `ec.INE` 只读官方合约发现 + 日线修复 collector，补齐 `ec2606/ec2607/ec2608/ec2609/ec2610/ec2612/ec2703` 后重跑 tail/rolling corr，未有可事前识别、低相关、足量 PIT 和真实 TCA 前，继续禁止 selector、paper、A/B 和交易白名单。 |
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
