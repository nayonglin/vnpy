# Stage333 独立风险槽相关性地图审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:39 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：低单笔风险扩池的价格结构、流动性与相关性资格审计
- 是否重要突破：否；没有新增可部署风险槽
- 是否触发A/B：否；没有策略版本进入正式候选、paper 或交易白名单

## 外部调研与判断

- 参考资料：
  - Managed futures diversification overview: https://clearingcustody.fidelity.com/insights/topics/investing-ideas/managed-futures-as-a-powerful-portfolio-diversifier
  - Hierarchical Risk Parity overview: https://en.wikipedia.org/wiki/Hierarchical_Risk_Parity
  - pyhrp implementation: https://github.com/tschm/pyhrp
  - ClusterPortfolios implementation: https://github.com/jpfitzinger/ClusterPortfolios
  - PyTrendFollow futures trend following implementation: https://github.com/chrism2671/PyTrendFollow
- 我的判断：
  - 扩池的第一性原理不是增加品种数量，而是增加低相关、可交易、可监控、可 TCA 验证的独立风险来源。
  - HRP/HERC/cluster risk parity 一类方法的共同点是先识别相关结构，再分配风险；趋势跟随的长期分散价值也来自跨市场低相关趋势，而不是同一宏观/商品链条下的重复暴露。
  - 因此本阶段只审计本地全品种价格覆盖、流动性代理、与 P0 结构槽相关性、尾部相关性和趋势机会代理，不使用策略收益排名生成白名单。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage633_independent_risk_slot_correlation_map.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 本地价格源：`examples/portfolio_backtesting/downloaded_futures/tqsdk_daily_2010_2026_04/`
  - strict low corr：`max_abs_corr_to_p0 <= 0.10`、`tail_abs_corr_to_p0_composite <= 0.15`、`rolling_abs_corr_p75_to_p0 <= 0.20`
  - watch corr：`max_abs_corr_to_p0 <= 0.15`、`tail_abs_corr_to_p0_composite <= 0.20`
  - 数据覆盖：`tradable_rows >= 900`、`recent_tradable_days >= 40`、`last_tradable_date` 距全局最新不超过 `45` 天
  - 流动性代理：最近 60 个可交易代理日 `median_volume >= 1000`
  - 趋势机会代理：年度最大 `abs(63d log return) / 63d realized vol` 至少 `1.25`，且至少 `3` 年满足
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：本地 TQSDK 日线，按各产品可用区间自动覆盖，最新本地可交易代理日约为 `2026-04-15`
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：
  - 读取本地 `86` 个产品根、`4044` 个合约日线文件
  - 每个产品按交易日选 `tradable_proxy=1`、成交量优先、持仓量次优的合约行作为产品级价格代理
  - `CFFEX` 金融期货标为当前商品期货范围外，不纳入新增商品风险槽
- 策略/归因口径：
  - 不重放策略、不看策略收益排名、不改交易规则、不生成 selector、paper 或交易白名单
  - P0 参考产品来自 Stage604/611：`lu.INE/v.DCE/y.DCE/c.DCE/ao.SHFE`，其中 `y/c` 仍视为同一 grains_oilseeds 结构槽

## 结果

- 期末权益：不适用；本阶段不是收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - decision：`risk_slot_correlation_map_built_no_new_deployable_slot`
  - local product roots：`86`
  - data pass products：`62`
  - liquidity pass products：`70`
  - strict low corr pass products：`2`
  - watch corr pass products：`6`
  - trend opportunity pass products：`73`
  - new structural monitor products：`0`
  - new structural monitor families：`0`
  - p1 worklist products：`8`
  - p2 monitor products：`6`
  - deployable new slots now：`0`
  - paper rows：`0`
  - trading whitelist rows：`0`
  - current effective slots：`4`
  - target effective slots：`7`
  - hard gates：`9/9`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_report_stage633_independent_risk_slot_correlation_map_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_decision_stage633_independent_risk_slot_correlation_map_v1.json`
- orders：不适用
- daily：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_product_map_stage633_independent_risk_slot_correlation_map_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_family_map_stage633_independent_risk_slot_correlation_map_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_corr_matrix_stage633_independent_risk_slot_correlation_map_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_gates_stage633_independent_risk_slot_correlation_map_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage633_independent_risk_slot_correlation_map_chart_stage633_independent_risk_slot_correlation_map_v1.png`

## 图表视觉复盘

- 左上图：大多数家族有趋势机会代理，但低相关柱几乎为空；趋势机会广泛存在不等于能增加独立风险槽。
- 右上图：绝大多数商品位于 `0.15` 观察线右侧，说明从价格相关性看，随机扩池大概率只是增加同源风险暴露。
- 严格低相关只有 `rr.DCE` 和 `PM.CZCE`：
  - `rr.DCE` 是 grains_oilseeds 同族深度，不新增独立槽；
  - `PM.CZCE` 近期成交量代理为 `0`，不适合低单笔风险扩池。
- watch 线附近的 `CJ.CZCE/lh.DCE/au.SHFE/AP.CZCE` 也不能直接晋级：
  - `au/AP` 已在 P2 forward monitor 或 source 路线中；
  - `CJ/lh` 缺少 source/TCA/outcome 和明确产品族合同，只能观察。
- 左下热力图：P1 `black_ferrous` 内部相关块仍明显，P2 软商品/贵金属也不是天然独立白名单；它们只能保留工作流，不代表新增部署槽。
- 右下图：所有 gate 为绿，但其中包含 `target_7_slots_not_met_fail_closed` 和 `deployable_new_slots_zero`，绿色代表锁定纪律，不代表晋级。

## 结论

- 本阶段结论：
  - “减少单笔风险、扩大品种池、每年抓部分趋势、避免高相关”的方向仍成立，但本地 86 产品结构审计没有找到新的可部署独立风险槽。
  - 当前不是产品漏扫问题，而是可部署的独立风险槽不足：现有仍是 `4` 槽，目标 `7` 槽，新增 deployable slot 为 `0`。
  - 继续随机扩大商品池会把大量高相关品种加入同一风险簇，不能真正降低单槽风险。
- 是否进入下一步：继续，但不做宽池收益扫描。
- 下一步：
  - 保持 `black_ferrous` 为 P1 source/TCA 工作流，但它内部是一个风险槽，不是 8 个槽。
  - 保持 `precious_metals/soft_agri` 为 P2 forward monitor，继续累计 PIT、outcome、TCA。
  - 对 `CJ.CZCE/lh.DCE` 这类 watch 线产品，只能先做 source 可执行性和产品族合同审计；未闭合前不能 paper 或白名单。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有使用策略收益排序挑产品，没有调交易规则，也没有根据历史回测结果生成交易白名单。
  - 使用的是价格覆盖、流动性、相关性和趋势机会代理，目的是筛掉伪独立风险槽。
  - 结论是严格 fail-closed：没有新增可部署槽。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但继续方向应收窄。
- 原因：
  - 本阶段证明“全库随机扩池”不是答案，避免后续大量低质量收益扫描。
  - 下一步更有价值的是补已有 P1/P2 的 source/TCA/outcome，或对 watch 线品种先做可执行源合同，而不是扩大回测搜索面。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage333 当前状态。
- 是否更新 `research/registry.md`：是，更新当前阶段摘要。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是重要突破、路线废弃、正式候选或跨线合并。
