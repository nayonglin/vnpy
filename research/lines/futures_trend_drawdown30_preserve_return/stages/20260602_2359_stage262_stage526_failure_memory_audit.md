# Stage262 Stage526 失败记忆审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-02 23:59 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：策略本体只读归因；检验“同一品种连续失败后，下一次信号是否更容易成功”。
- 是否重要突破：否；但用户提出的失败记忆直觉得到部分数据支持，不能简单否定。
- 是否触发A/B：否。没有形成可接入正式版本的新策略候选。

## 外部调研与判断

- 参考资料：
  - 趋势跟随与 ATR/动态止损研究：动态止损、time stop、ATR stop 对趋势系统有机制价值，但容易切掉右尾趋势，交易成本会决定成败。
  - Rob Carver / 系统化趋势实践：趋势系统更依赖分散、波动归一和长期右尾；过早从亏损样本学习，容易把噪音变成规则。
  - 趋势/EMA 模型文献：趋势策略的有效性来自收益自相关与趋势持续性，过度响应短期失败会增加 whipsaw 风险。
- 我的判断：失败记忆值得审计，因为它不是小数参数，而是一个可解释的市场状态假设：同品种多次被震荡打脸后，后续可能更容易走出趋势。但它必须先作为只读诊断验证，不能直接变成开仓门禁或加仓规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage562_stage526_failure_memory_audit.py`
- 修改脚本：无既有策略脚本修改。
- 删除脚本：无。
- 新增输出：
  - enriched segments CSV。
  - bucket summary CSV。
  - rule probe CSV。
  - product failure memory CSV。
  - decision JSON。
  - report。
  - chart。
- 新增参数/闸门：
  - `MIN_SEGMENTS_FOR_PROMOTION=20`
  - `MIN_WIN_RATE_IMPROVEMENT_PP=10.0`
  - `MIN_ESTIMATED_DELTA=100000.0`
  - `MAX_POSITIVE_PNL_AT_RISK_PCT=15.0`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage526 固定持仓段账本。
- 账户规模：Stage526 `r080_pc25_maxpos4` 参考。
- 成本口径：使用 Stage526 已落盘持仓段 `net_pnl`，包含该阶段滑点口径；不重跑成本。
- 样本过滤：读取 `qmt_roll_stage537_stage526_segment_lifecycle_audit_segments_...csv` 的 `338` 个持仓段。
- 策略/归因口径：按 `product_vt_symbol` 时间顺序计算 prior segment、prior loss、consecutive loss、recent3/recent5 loss、days since prior segment；所有规则探针都是近似账本探针，不等价真实引擎。

## 结果

- 决策：`failure_memory_positive_diagnostic_not_trade_gate`
- Stage526 参考：
  - 版本：`r080_pc25_maxpos4`
  - 期末权益：`23,369,505`
  - 总收益：`3699.9195%`
  - 相对 Stage079 收益保留：`74.7872%`
  - 最大回撤：`-36.2670%`
  - Sharpe：`1.6385`
  - Ulcer：`14.4691`
  - broker10 最大保证金/权益：`99.7299%`
  - 总滑点：`1,342,190`
  - 总交易次数：`905`
  - 非零日胜率：`53.6330%`
- 持仓段总体：
  - segment count：`338`
  - 段净损益合计：`22,108,320`
  - 全体段胜率：`45.2663%`
  - 全体段中位净损益：`-2,600`
- 连续亏损分桶：
  - `0` 次连续亏损后入场：`166` 段，净损益 `-1,728,475`，胜率 `38.5542%`，中位 `-7,180`，坏窗口净损益 `-668,040`。
  - `1` 次连续亏损后入场：`94` 段，净损益 `6,462,330`，胜率 `48.9362%`。
  - `2` 次连续亏损后入场：`46` 段，净损益 `14,055,205`，胜率 `50.0000%`。
  - `3+` 次连续亏损后入场：`32` 段，净损益 `3,319,260`，胜率 `62.5000%`，中位 `8,665`。
  - 连续亏损 `>=2` 后入场：`78` 段，净损益 `17,374,465`，胜率 `55.1282%`，相对全体胜率改善 `9.8619pp`，中位 `7,430`，坏窗口净损益 `650,820`。
- 规则探针：
  - 最好探针 `only_after_consecutive_loss_ge1`：触发 `172` 段，选择段净损益 `23,836,795`，估算相对 Stage526 增量 `1,728,475`，选择段胜率 `51.7442%`。
  - 但该探针会放弃 `10,318,410` 的正收益段，positive pnl at risk `24.7838%`，超过预设 `15%` 上限。
  - `only_after_consecutive_loss_ge2` 虽质量更高，但只保留 `17,374,465` 净损益，估算相对 Stage526 少 `4,733,855`，且会放弃 `22,146,200` 正收益段。
- Spearman 诊断：
  - `consecutive_loss_count -> net_pnl`：`0.1968`
  - `recent3_loss_count -> net_pnl`：`0.1176`
  - `recent5_loss_count -> net_pnl`：`0.1068`
  - `prior_loss_count -> net_pnl`：`-0.0192`
- 产品分布：
  - 连续亏损 `>=2` 后表现最强：`jm.DCE +7,583,550`、`ru.SHFE +2,378,400`、`FG.CZCE +1,705,620`、`AP.CZCE +1,407,020`、`OI.CZCE +1,036,630`。
  - 主要失败产品：`MA.CZCE -607,380`、`SH.CZCE -456,300`、`SA.CZCE -54,840`。

## 回测指标

- 期末权益：不适用，本阶段不重跑策略；Stage526 参考为 `23,369,505`。
- 总收益：不适用，本阶段不重跑策略；Stage526 参考为 `3699.9195%`。
- 最大回撤：不适用，本阶段不重跑策略；Stage526 参考为 `-36.2670%`。
- Sharpe：不适用，本阶段不重跑策略；Stage526 参考为 `1.6385`。
- 总滑点：不适用，本阶段不重跑策略；Stage526 参考为 `1,342,190`。
- 总交易次数：不适用，本阶段不重跑策略；Stage526 参考为 `905`。
- 胜率：不适用，本阶段不重跑策略；持仓段胜率为 `45.2663%`。
- 其他关键指标：连续亏损 `>=2` 后入场段净损益 `17,374,465`、胜率 `55.1282%`、Spearman `0.1968`。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_chart_stage562_stage526_failure_memory_audit_v1.png`
- 左上图清楚显示 `0` 次连续亏损后入场整体为负，而 `1/2/3+` 分桶均为正，其中 `2` 次连续亏损后入场贡献最大。这说明用户的失败记忆直觉不是空想。
- 右上图显示近3段亏损数越高，胜率和中位净损益越好；`3` 个近端亏损桶的胜率明显高于全体段胜率。
- 左下图显示直接做规则门禁很危险：`only_after_consecutive_loss_ge1` 近似正增量，但其它更严格的“只做失败后”规则会快速丢失右尾收益；反向阻断失败后信号更是明显伤害收益。
- 右下图显示连续亏损 `>=2` 后的收益集中在 `jm/ru/FG/AP/OI`，而 `MA/SH/SA` 仍失败，说明失败记忆不能脱离品种状态单独作为硬规则。

## 输出文件

- enriched segments：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_segments_enriched_stage562_stage526_failure_memory_audit_v1.csv`
- bucket summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_bucket_summary_stage562_stage526_failure_memory_audit_v1.csv`
- rule probe：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_rule_probe_stage562_stage526_failure_memory_audit_v1.csv`
- product summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_product_failure_memory_stage562_stage526_failure_memory_audit_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_decision_stage562_stage526_failure_memory_audit_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_report_stage562_stage526_failure_memory_audit_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage562_stage526_failure_memory_audit_chart_stage562_stage526_failure_memory_audit_v1.png`

## 结论

- 本阶段结论：失败记忆有正向诊断价值，但不能直接晋级成交易门禁。它更适合作为未来低自由度观察/轻量 sizing 因子的候选，而不是“只在失败后开仓”或“失败后加仓”的规则。
- 是否进入下一步：进入经验保留，不进入 A/B 或真实策略接入。
- 下一步：
  - 不做 `>=1/>=2/>=3` 小数救援。
  - 若未来继续该方向，只允许测试一个冻结的低幅度 sizing 观察因子，并必须真实引擎重放，因为跳过段会改变后续失败记忆状态。
  - 策略本体优化更优先转向成本 churn、真实执行偏差、或者 Stage526 已知 3x 成本失败路径。

## 过拟合反思

- 运行前判断：不是过拟合。本阶段只读 Stage526 固定持仓段，检验一个预先明确的失败记忆假设，不调阈值。
- 运行后判断：不是过拟合。结果有正向线索但未晋级，没有为了救结论继续改 `>=2/>=3` 或按产品名单过滤。
- 原因：这次把直觉转成数据审计，并明确标出规则探针只是近似账本，不等价真实引擎。

## 继续价值反思

- 运行前判断：有价值。该假设来自“多次失败后可能更容易走出震荡”的直觉，需要用数据反证。
- 运行后判断：该子方向有经验价值但主动继续价值中低。它可作为未来观察因子，但不是当前解决 DD40/保收益/3x成本失败的主线。
- 原因：失败记忆改善的是段质量排序，不是直接降低回撤或成本压力；真实接入还会遇到递归状态变化。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：是，作为用户失败记忆假设的阶段性结论。
