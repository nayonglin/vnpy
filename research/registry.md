# 研究线总索引

更新时间：2026-06-02 02:14 CST

## 当前研究线

| line_id | 中文名 | 资产/策略 | 当前状态 | 最新关键阶段 | 主要记录目录 | 下一步 |
| --- | --- | --- | --- | --- | --- | --- |
| `futures_trend` | 期货趋势策略 | 商品期货趋势/第78-1正式基准 | Stage78-1正式基准与50万资金约束；CTP/SimNow daily gate 与 broker-test/SimNow 1手测试链路已固化；普通 SimNow `9999/trading` 已完成1手开仓成交、1手平仓成交、1手撤单回报、程序化断网回调和1.6-1.9执行安全验收；`41407`原生C++路线已能调用报单API但测试单曾被CTP拒绝，评测前置仍需券商确认/恢复 | Stage288：合并普通 SimNow 开平仓/撤单/断网证据，补齐阈值预警、交易指令检查、错误提示和暂停交易验收，16/16通过；执行安全模块已接入Stage250 OrderRequest构造层；外发版HTML已去本机路径、通用中文分章节，并补回脱敏交易细节与控制台关键打印 | `research/lines/futures_trend/` | 后续每日虚拟盘按skill执行；review禁止新增开仓，空仓不得发送平仓单；继续把 `ctp_execution_safety.py` 扩展到最终真实submit adapter；若券商要求 `1010/41407/41415` 评测前置证明，则等该前置稳定后复刻开平仓/撤单/断网 |
| `futures_trend_drawdown30_preserve_return` | 期货趋势回撤30以内保收益线 | 商品期货趋势/第78-1风险压缩 | 独立研究线；Stage079 `50万C3下单+11.5万外部现金` 仍是原始日线baseline，但不能作为实盘收益/回撤承诺；Stage202 建立完整日K确认后全订单下一真实窗口基准，收益仍在但回撤失控；Stage208/209 完成 xsmom 真实成交承载并清零 fallback；Stage214/215 确认 exact position margin 是硬闸门；Stage224-228 找到 `cap25 + maxpos4` 新主研究候选；Stage231-237 反证退出开关、相关性小数、入场代理和早期不利退出；Stage238 完成晋级边界审计；Stage239/240 反证朴素扩池和当前 new5 sleeve；Stage241/242 证明“选对非核心品种”有上限空间；Stage243-245 反证当前价格/账本/AI适应度/产品族状态特征不足以事前复刻 Oracle6；Stage246-249 证明外生源可 forward 监控但不能历史 selector；Stage250-252 将年度延续选品落到真实 sleeve 与连续动态宇宙，出现小幅研究级候选。 | Stage252：决策 `dynamic_annual_selector_promotion_candidate_found`，但只进入下一验证阶段，不直接替代 Stage526。`dynamic_prevtop6_r050_pc15_maxpos3` 为 `23,422,160/3708.4813%/-36.0822%/Sharpe1.6432/Ulcer14.3839`，broker10 最大 `98.7159%`、穿100 `0`，2x/3x成本回撤 `-38.8577%/-41.8410%`，卫星PnL `52,655`，63/126日p05改善 `0.2678pp/0.2852pp`。图表显示 edge 不依赖 2026 `lu`，但整体改善很窄；`prev_year_positive` 扩太宽后失败。 | `research/lines/futures_trend_drawdown30_preserve_return/` | Stage526 仍是正常成本主候选；年度动态 top6/r050 是下一层 paper/验证候选。下一步只做剔除最大贡献产品/年份、白名单生效时点、持仓连续性、产品族暴露和部署材料性复核；禁止继续扫 `TopN/risk/cap` 小数或接入 Oracle/hindsight 产品池。 |
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
