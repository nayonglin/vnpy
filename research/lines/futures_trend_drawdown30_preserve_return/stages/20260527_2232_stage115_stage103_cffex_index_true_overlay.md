# Stage115 Stage103中金所股指真实一手Overlay

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 22:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 组合层真实整数手审计；固定 Stage079 与 Stage103，寻找新的跨资产低相关风险源。
- 是否重要突破：是。`stage103_plus_cffex_index_best1_tsmom60_guard` 晋级为新的执行相对候选，但不是绝对部署版本。
- 是否触发A/B：是；已补读 `skills/version-ab-experiment/SKILL.md`。A=Stage079，C0=Stage103，C=Stage103 叠加中金所股指期货风险预算 overlay。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen, *Time Series Momentum*：时间序列动量在 equity index、currency、commodity、bond futures 上都有显著性，且 diversified TSMOM 在极端市场中表现较好。
  - Managed futures / CTA 资料：趋势跟踪的组合价值主要来自低相关、可多可空、跨资产风险源，而不是对单一历史弱窗口打补丁。
  - 中金所股指期货合约资料与保证金知识：IF/IH 合约乘数每点 `300` 元，IC/IM 每点 `200` 元；保证金按合约价格、交易单位和保证金比率计算，期货公司会在交易所基础上上浮。
- 我的判断：
  - 股指期货 TSMOM 是结构上有意义的新风险源，值得试；但 IF/IH/IC/IM 单手名义本金较大，不能按“四个指数各一手”直接叠加到 61.5 万账户。
  - 因此 v2 增加 `best1` 与 `short1` 两种资金粒度约束形态：全股指篮子每天最多持有 1 手，或只保留下跌趋势做空信号最多 1 手。这是资金预算结构，不是相邻小数救援。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage415_stage103_cffex_index_true_overlay.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `INDEX_PRODUCTS=("IF","IH","IC","IM")`
  - 股指合约乘数：IF/IH `300`，IC/IM `200`
  - 估算保证金率：统一 `15%`
  - 最小变动价位：`0.2` 点
  - 预声明动量窗口：`60/120` 日，来自 Stage381 已有金融期货净值层 scout。
  - 执行保证金闸门：沿用 Stage103 `BROKER10_MULTIPLIER=1.10`。
  - 结构形态：`index_tsmom` 四指数各最多1手；`index_tsmom_best1` 全篮子只取绝对动量最强1手；`index_tsmom_short1` 只做空信号最多1手。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 到 `2026-04-30`。
- 账户规模：Stage079/Stage103 统一 `615,000` 账户口径，仍为 `50万C3下单 + 11.5万账户现金`。
- 成本口径：保留 C3 与 xsmom 既有滑点；股指 overlay 按每次合约变动 1 tick 计滑点，并做 `1x/2x/3x/5x` 成本压力。
- 样本过滤：不改 C3、Stage079、Stage103 交易规则；不增加资金；不选择单个指数；不调品种、月份、窗口或阈值。
- 策略/归因口径：用中金所主力连续合约日线构造点时化 TSMOM；信号 `shift(1)`，当天只使用上一交易日可知状态。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| Stage079 | `31,040,650` | `4947.2602%` | `-29.7007%` | `1.3188` | `15.0874` | `100.0000` | `100.0000` | baseline |
| Stage103 | `31,730,915` | `5059.4984%` | `-28.9792%` | `1.3681` | `14.3132` | `121.2041` | `134.4513` | 原执行相对候选 |
| 四指数各1手 60日 | `32,043,955` | `5210.2366%` | `-41.5991%` | `1.2520` | `15.5937` | `84.8233` | `133.1023` | 过暴露，拒绝 |
| 四指数各1手 120日 | `33,429,535` | `5338.1358%` | `-33.5205%` | `1.3268` | `14.0297` | `122.6445` | `102.2143` | 过暴露，拒绝 |
| `best1_tsmom60` | `33,607,695` | `5364.6659%` | `-23.5184%` | `1.4810` | `12.0786` | `183.4601` | `210.3930` | 晋级执行相对候选 |
| `best1_tsmom120` | `33,724,735` | `5383.6967%` | `-27.3979%` | `1.4159` | `12.8464` | `153.2131` | `178.5492` | `start_2022` 失败，拒绝 |
| `short1_tsmom120` | `32,070,995` | `5112.5195%` | `-28.8911%` | `1.3830` | `13.6803` | `135.7940` | `123.8168` | 保证金/坏窗口失败，拒绝 |

### `best1_tsmom60` 关键指标

- 期末权益：`33,607,695`
- 总收益：`5364.6659%`
- 最大回撤：`-23.5184%`
- Sharpe：`1.4810`
- Ulcer：`12.0786`
- 总滑点：`1,594,705`
- 总交易次数：`1,719`
- 胜率：日胜率 `52.5457%`，非零收益日胜率 `53.8462%`
- 90日体验：收益5%分位 `-9.3869%`，正收益率 `77.4876%`，DD20 触发率 `8.5547%`，DD30 触发率 `0%`，Ulcer P95 `13.5323`
- 180日体验：收益5%分位 `+0.4703%`，正收益率 `95.2135%`，DD20 触发率 `21.8677%`，DD30 触发率 `0%`，Ulcer P95 `14.5325`
- 8项短持有目标改善：90日 `7/8`，180日 `8/8`
- 年度/季度冷启动 DD30 通过率：`100%/100%`
- rolling252/504 DD30 破线率：`0%/0%`
- 多起点：`start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026/weak_2021_full/phase_2024_2025` 全部最大回撤在 30% 内；`start_2022` 为 `866.8585%/-29.5919%`。
- 成本压力最大回撤 `1x/2x/3x/5x`：`-23.5184%/-25.9791%/-29.9034%/-39.1469%`，均不差于 Stage079 与 Stage103。
- 保证金：`1.10x` 全周期最大保证金/权益 `101.2144%`，出现 `1` 天绝对穿线；但相对 Stage103 不更差，因此只通过 execution-relative，不通过 absolute deployment。

### 贡献与集中度 sanity check

- `best1_tsmom60` 在 `start_2020` 全周期 overlay 净 PnL 为 `1,876,780`，股指滑点 `25,440`，overlay 换手 `502`，保证金闸门跳过 `6` 天，持有天数 `1,282`。
- 分品种贡献：IM `823,200`，IC `546,120`，IF `368,360`，IH `139,320`；不是单一合约支撑。
- 分年度 overlay PnL：2020 `36,180`，2021 `461,580`，2022 `220,780`，2023 `149,640`，2024 `409,640`，2025 `460,700`，2026 `138,480`；不是单一年份支撑。
- 剔除最大 `1/3/5/10/20` 个 overlay 盈利日后，总收益仍约 `5349.99%/5322.98%/5298.09%/5247.23%/5170.85%`，仍高于 Stage103 `5059.4984%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_report_stage415_stage103_cffex_index_true_overlay_v2.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_summary_stage415_stage103_cffex_index_true_overlay_v2.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_daily_stage415_stage103_cffex_index_true_overlay_v2.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_gate_stage415_stage103_cffex_index_true_overlay_v2.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_cost_stress_stage415_stage103_cffex_index_true_overlay_v2.csv`
- fresh_start：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_fresh_start_stage415_stage103_cffex_index_true_overlay_v2.csv`
- margin_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_margin_audit_stage415_stage103_cffex_index_true_overlay_v2.csv`
- overlay：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_overlay_daily_stage415_stage103_cffex_index_true_overlay_v2.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_chart_stage415_stage103_cffex_index_true_overlay_v2.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage415_stage103_cffex_index_true_overlay_decision_stage415_stage103_cffex_index_true_overlay_v2.json`

## 结论

- 本阶段结论：`stage103_plus_cffex_index_best1_tsmom60_guard` 值得晋级为新的 Stage103 后继执行相对候选。它明显优于 Stage079 与 Stage103，尤其是 90/180 日任意启动体验、最大回撤、Ulcer 和成本压力。
- 是否进入下一步：是，但只进入更严格鲁棒性/工程化复跑，不直接替代正式部署。
- 下一步：
  - 固定 `best1_tsmom60`，做 Stage116 级别鲁棒性审计：rolling 任意启动收益胜率、block bootstrap、月份重排、顶部贡献日剔除、真实券商保证金表接入。
  - 不继续扫 `best1` 的窗口、指数选择、保证金比例、动量阈值或做相邻变体。
  - 四指数各一手与 `short1` 危机对冲形状停止，不救。

## 过拟合反思

- 运行前判断：不是过拟合。研究假设来自外部 TSMOM/managed futures 文献和 Stage381 的金融期货低相关净值层线索；先测试真实一手与保证金约束。
- 运行后判断：`best1_tsmom60` 本身暂不判定为过拟合，但晋级层级必须克制。
- 原因：`best1` 是股指合约粒度过大后的资金预算结构，非小数调参；胜出跨品种、跨年度且剔除顶部贡献日仍保留。但它是在四指数各1手失败后追加的结构修正，仍需 Stage116 独立鲁棒性验证，不能直接部署。

## 继续价值反思

- 运行前判断：有价值。Stage103/现金/股票槽位已经接近瓶颈，必须找不同风险暴露来源。
- 运行后判断：有价值，且价值上升。
- 原因：股指 `best1_tsmom60` 同时改善收益、回撤、Ulcer 和 3/6 个月持有体验，是目前少数既不是现金稀释也不是坏窗口补丁的真实新增风险源。

## 合入建议

- 是否更新本线 `LINE.md`：是，作为 Stage115 后执行约束。
- 是否更新 `research/registry.md`：是，最新关键阶段应更新为 Stage115。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要突破和新执行相对候选。
