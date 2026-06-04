# Stage327 Source Probe 后独立风险槽再排序审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 07:47 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读风险槽优先级再排序；吸收 Stage625/626 最新 source 证据，不新增收益回测、不改策略规则、不生成 selector/paper/交易白名单、不连接 CTP、不调用订单 API。
- 是否重要突破：否，但把“低单笔风险 + 扩池 + 避免高相关”的下一步从宽池回测进一步收敛成 `P1 + P2 monitor` 的证据闸门。
- 是否触发A/B：否。没有形成可接入正式版本的新交易规则、新风险预算或新白名单。

## 外部调研与判断

- 参考资料：
  - AIMA Managed futures and varying correlations：https://www.aima.org/article/managed-futures-and-varying-correlations.html
  - Man Group trend following market mix：https://www.man.com/insights/trend-following-optimal-market-mix
  - SSRN Trend Following, Risk Parity and Momentum in Commodity Futures：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
  - GitHub risk-parity topic / Riskfolio-Lib / skfolio：https://github.com/topics/risk-parity
- 我的判断：
  - 趋势策略扩池的第一性原则不是“品种越多越好”，而是增加低相关、不同经济驱动、可真实执行的独立风险槽。
  - 风险预算/HRP 类资料有参考价值，但本阶段不引入新优化库，避免把历史协方差优化当成新增 alpha。
  - Stage625 的公开源成功可以提高 `ag/CY/SR` 的 forward monitor 质量，但 source readiness 不是 predictive edge；没有 PIT 深度、趋势 episode、selector 审计和 TCA 前，不能上调为交易预算。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage627_post_source_probe_slot_reprioritization.py`
- 修改正式策略脚本：无。
- 删除脚本：无。
- 新增参数/闸门：
  - `TARGET_EFFECTIVE_SLOTS = 7`
  - `CURRENT_EFFECTIVE_SLOTS = 4`
  - `SLOTS_IF_BLACK_CLOSED = 5`
  - `PREFERRED_SINGLE_SLOT_RISK_PCT = 15.0`
  - `MAX_CORE_CORR_OBSERVE = 0.10`
  - `source_probe_reprioritizes_p2_monitor_no_new_slot_budget`
  - `P2+source`
  - `p2_source_improved_but_not_promoted`
  - `deployable_scenarios_zero`
- 修改参数：
  - Stage626 合并产品路由在产品级汇总时按共享 product token 拆权重，避免 `CY.CZCE/SR.CZCE` 家族层重复计数。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 数据区间：沿用 Stage604/621/625/626 冻结输出。
- 账户规模：不适用；本阶段不生成交易组合。
- 成本口径：不适用。
- 样本过滤：
  - 读取 Stage604 年度捕获和3/6个月持有体验边界。
  - 读取 Stage621 风险槽优先级板。
  - 读取 Stage625 `ag.SHFE/CY.CZCE/SR.CZCE` raw fetch ledger/product summary。
  - 读取 Stage626 CZCE route forensic probe ledger。
- 策略/归因口径：
  - 把 Stage625/626 的 source 证据只映射为监控优先级，不映射为收益权重。
  - `history_selector_rows=0`、`event_signal_ready=0`、`live_tca=0` 时，所有新增风险预算保持 `0%`。

## 结果

- 决策：`source_probe_reprioritizes_p2_monitor_no_new_slot_budget`
- promotion allowed：`false`
- paper selector allowed：`false`
- trading whitelist allowed：`false`
- P1 new-slot families：`1`
  - `black_ferrous(j.DCE/i.DCE)` 仍是唯一 P1 新槽线索，但 source/TCA/live 未闭合。
- P2 source-improved families：`2`
  - `precious_metals(ag.SHFE)`：Stage625 fetched ok rows `1`，event monitor rows `0`，仍缺材料性/episode/selector/TCA。
  - `soft_agri(CY.CZCE/SR.CZCE)`：Stage625 fetched ok rows `4`，event auto monitor rows `4`，但 Stage626 家族层 CZCE route-ready `0`、HTTP `412=28`、HTTP `404=14`；仍缺材料性/episode/selector/TCA。
- deployable new slots now：`0`
- current effective slots：`4`
- slots if black_ferrous closed：`5`
- best hypothetical slots if P2 edge verified：`7`
- single slot risk current：`25.00%`
- single slot risk if black_ferrous closed：`20.00%`
- single slot risk if hypothetical P2 verified：`14.29%`
- hard gates：`8/8`
  - 注意：这里的 `8/8` 是 fail-closed 审计闸门通过，不是晋级闸门通过；含义是“新增预算为0、selector为0、P2未晋级、可部署场景为0”的纪律保持。
- 期末权益：无新增权益曲线。
  - Stage526 参考：`23,369,505`
- 总收益：无新增收益曲线。
  - Stage526 参考：`3699.9195%`
- 最大回撤：无新增收益曲线。
  - Stage526 参考：`-36.2670%`
- Sharpe：无新增收益曲线。
  - Stage526 参考：`1.6385`
- 总滑点：无新增交易。
- 总交易次数：无新增交易。
- 胜率：无新增交易。

## 图表视觉复盘

- 图表：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_chart_stage627_post_source_probe_slot_reprioritization_v1.png`
- 视觉结论：
  - 左上 slot ladder 显示当前 `4` 槽、black closed 后 `5` 槽、black+P2 verified 才到 `7` 槽；三根柱子都是橙色，表示当前没有一个场景可部署。
  - 右上散点显示 `black_ferrous` 低相关且有正贡献，是唯一 P1；`precious_metals/soft_agri` 低相关但当前贡献为负，不能因为 source 变好就上调；`rubber/other` 位于相关性红线右侧，继续拒绝。
  - 左下 evidence matrix 把 source success、event monitor、CZCE blocked、selector ready、live TCA、budget allowed 分开。`soft_agri` 同时有 event monitor 绿块和 CZCE blocked 红块，说明它可以监控但不能交易；所有 selector/TCA/budget 列仍为 `0`。
  - 右下 fail-closed gates 全绿，语义是“锁定纪律保持”：新增预算 `0%`、selector/event signal `0`、deployable scenario `0`、P2 source improved 但 promoted `0`。
  - 第一版右上标签略拥挤、右下标题可能误读为晋级，通过二次修图错开标签并改为 fail-closed 标题后通过。

## 输出文件

- script：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage627_post_source_probe_slot_reprioritization.py`
- family reprioritization：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_family_reprioritization_stage627_post_source_probe_slot_reprioritization_v1.csv`
- source delta：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_source_delta_stage627_post_source_probe_slot_reprioritization_v1.csv`
- slot scenarios：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_slot_scenarios_stage627_post_source_probe_slot_reprioritization_v1.csv`
- gates：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_gates_stage627_post_source_probe_slot_reprioritization_v1.csv`
- decision：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_decision_stage627_post_source_probe_slot_reprioritization_v1.json`
- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_report_stage627_post_source_probe_slot_reprioritization_v1.md`
- chart：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage627_post_source_probe_slot_reprioritization_chart_stage627_post_source_probe_slot_reprioritization_v1.png`

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分趋势，同时避免高相关风险”方向仍成立，但当前只能推进为独立风险槽监控，不应推进成宽池交易。
  - Stage625/626 后，`ag/CY/SR` 的监控质量提高，`precious_metals/soft_agri` 可以记为 `P2+source`，但不能晋级为 P1 或给预算。
  - 理论上，如果 `black_ferrous + precious_metals + soft_agri` 都成为真实独立槽，槽数可到 `7`、单槽风险约 `14.29%`；但当前只有 `black_ferrous` 是 P1 线索，且还没闭合，P2 仍缺材料性趋势 episode、selector 预测力和真实 TCA。
- 是否进入下一步：
  - 是，但下一步不是宽池收益回测。下一步应设计 `P2+source` 的 forward episode 协议：至少 `12` 个月 PIT raw hash、至少 `3` 个独立趋势 episode、再做固定协议 selector IC/左尾持有体验/TCA 审计。
- 下一步：
  - `black_ferrous`：继续授权/官方 source + live TCA；闭合后也只是第5槽。
  - `soft_agri`：继续 USDA/ESMIS/ERS raw hash monitor，CZCE 降级为浏览器/CDP或授权替代源；先收 PIT episode，不做交易。
  - `precious_metals`：补事件/库存/会员数据 monitor，不因 SHFE daily page 可抓就上调。
  - 另找至少 `2` 个非高相关、source 可执行、容量合格、能证明材料性趋势 episode 的新独立驱动。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有按历史收益选择新白名单，也没有调参数；只是把最新 source 可执行证据并入预声明的风险槽准入框架。
  - 结论反而保持 fail-closed：source 变好只提升监控，不直接提升交易预算。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - 该方向从“扩池”转成了更可验证的“独立风险槽 + source/TCA/episode 闸门”，更接近真实可成交结构。
  - 当前价值在于继续积累 P2 PIT 证据和寻找两个新独立驱动，而不是继续做宽池历史收益扫描。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage327 结论。
- 是否更新 `research/registry.md`：是，把最新关键阶段推进到 Stage327。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重大突破、路线废弃或跨线合并。
