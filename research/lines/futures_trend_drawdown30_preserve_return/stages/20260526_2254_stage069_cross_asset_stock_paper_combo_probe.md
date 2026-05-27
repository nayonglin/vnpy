# Stage069 跨资产股票paper组合探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 22:54 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：跨资产低相关承载净值层探针；出现研究候选，需要 OOS 与真实资本约束复核
- 是否重要突破：是，首次在不明显牺牲收益的前提下，把 C3 组合全样本回撤压进 `30%`，且优于同权重现金稀释
- 是否触发A/B：是。股票 paper 曲线若作为组合承载，有可能影响正式资金配置，只能按 A/B/C 隔离验证，不得直接改 78-1 或 C3 正式路径。

## 外部调研与判断

- 参考资料：
  - AQR《A Century of Evidence on Trend-Following Investing》与 Moskowitz/Ooi/Pedersen《Time Series Momentum》均支持跨市场、跨资产分散是趋势类策略路径平滑的重要来源。
  - AQR managed futures 资料同样强调多资产类别与低相关承载，但也明确分散不能消除亏损风险。
- 我的判断：
  - 当前期货内部供需、风险簇、季节性、xsmom、期限结构等多条路线已被反证；继续在 C3 内部调小数参数过拟合风险高。
  - 用已有股票震荡 paper 曲线做 5% 小比例组合，结构上属于“独立承载 + 低相关平滑”，不是针对 2021 或 2026 单一弱窗口的补丁。
  - 但股票腿仍是 paper 监控线，不能直接视为可实盘候选；必须先通过 OOS、真实账户资金、交易成本、容量与执行约束。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage369_cross_asset_stock_paper_combo_probe.py`
- 修改脚本：
  - 同上，修正组合标签浮点取整问题，补充负收益窗口判定逻辑，并加入正式78-1参照与 HTML 曲线页。
- 删除脚本：无
- 新增参数：
  - `COMBO_WEIGHTS=(0.95, 0.90, 0.85, 0.80, 0.70)`，表示 C3 权重。
  - 股票 paper 权重为 `5%/10%/15%/20%/30%`。
  - 同权重现金稀释对照：`C3权重 + 现金权重`。
  - 硬闸门：最大回撤 `>= -30%`，相对 C3 收益保留 `>=80%`，必须优于同权重现金稀释，所有起始窗口和弱窗口通过。
- 修改参数：无。未修改 C3、78-1、股票 paper 信号或交易规则。
- 删除参数：无

## 回测/归因参数

- 数据区间：公共区间 `2020-01-02` 至 `2026-04-27`。
- 账户规模：净值层按 `500,000` 初始资金归一化；本阶段不是实盘资金拆分。
- 成本口径：
  - C3 成本沿用 Stage336 已有日曲线。
  - 股票 paper 成本沿用 `stock_range_reversion_liquid_q3_paper_ledger_v1_daily_ledger.csv` 中的 paper 日收益。
  - 本阶段没有新增滑点压力，后续必须补。
- A/B/C：
  - O：正式78-1参照。
  - A：`A_c3_100`，当前最强 C3 研究基准。
  - B：`B_stock_paper_100`，股票震荡 paper 独立腿。
  - C：`C_c3_95_stock_05` 等 C3 + 股票 paper 组合。
  - 现金对照：`cash_control_c3_95_cash_05` 等。

## 结果

### 全样本核心结果

| 版本 | 总收益 | 最大回撤 | 相对C3收益保留 | Sharpe | Ulcer | 最长水下天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 正式78-1 | `4961.9770%` | `-40.1659%` | `84.9892%` | `1.1559` | `20.7931` | `403` |
| C3 | `5838.3600%` | `-31.0767%` | `100.0000%` | `1.3044` | `16.2075` | `369` |
| 股票paper独立腿 | `81.9040%` | `-15.1555%` | `1.4029%` | `0.5614` | `6.0209` | `426` |
| `95%C3+5%股票paper` | `5078.5193%` | `-29.5080%` | `86.9854%` | `1.3138` | `15.3641` | `369` |
| `95%C3+5%现金` | `4908.2096%` | `-29.7155%` | `84.0683%` | `1.3044` | `15.4329` | `369` |

### 多窗口核心结果

- `95%C3+5%股票paper` 全样本通过：总收益 `5078.5193%`，最大回撤 `-29.5080%`，收益保留 `86.9854%`。
- `start_2021`：总收益 `4021.5797%`，最大回撤 `-29.5080%`，收益保留 `87.2580%`。
- `start_2022`：总收益 `1476.9573%`，最大回撤 `-28.9798%`，收益保留 `89.6497%`。
- `start_2023`：总收益 `671.6598%`，最大回撤 `-18.4121%`，收益保留 `91.6947%`。
- `start_2024`：总收益 `275.6225%`，最大回撤 `-18.4121%`，收益保留 `94.1054%`。
- `ytd_2026`：总收益 `5.8339%`，最大回撤 `-10.7021%`，收益保留 `101.3247%`。
- `2021 C3峰谷窗口`：收益 `-22.6321%`，最大回撤 `-29.5080%`，相对 C3 路径亏损改善。

### 年度参照

- `95%C3+5%股票paper` 年度最大回撤均未低于 `-30%`：
  - 2020：`25.6440%/-27.0279%`
  - 2021：`161.3628%/-29.5080%`
  - 2022：`104.3591%/-28.9798%`
  - 2023：`105.4349%/-15.6085%`
  - 2024：`43.8066%/-18.4121%`
  - 2025：`146.8017%/-16.3463%`
  - 2026：`5.8339%/-10.7021%`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_summary_stage369_cross_asset_stock_paper_combo_probe_v1.csv`
- window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_window_summary_stage369_cross_asset_stock_paper_combo_probe_v1.csv`
- annual_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_annual_summary_stage369_cross_asset_stock_paper_combo_probe_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_daily_stage369_cross_asset_stock_paper_combo_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_decision_stage369_cross_asset_stock_paper_combo_probe_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_report_stage369_cross_asset_stock_paper_combo_probe_v1.md`
- html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage369_cross_asset_stock_paper_combo_probe_equity_drawdown_stage369_cross_asset_stock_paper_combo_probe_v1.html`

## 结论

- 本阶段结论：`95%C3 + 5%股票paper` 是一个有效研究候选。它在公共样本内把 C3 最大回撤从 `-31.0767%` 降到 `-29.5080%`，总收益保留 `86.9854%`，并且收益和回撤都略优于 `95%C3 + 5%现金`。
- 与正式78-1相比，它在公共样本内收益略高，最大回撤从 `-40.1659%` 降到 `-29.5080%`，Ulcer 从 `20.7931` 降到 `15.3641`，路径明显更平滑。
- 是否进入下一步：是，但只能进入“真实性复核”，不能直接实盘或替代78-1。
- 下一步：
  1. 复核股票 paper 腿是否完全点时化，尤其是调仓价格、停牌、涨跌停、流动性、交易成本和撮合假设。
  2. 做真实资金拆分：`47.5万 C3 + 2.5万股票paper` 是否可交易，还是需要独立账户/融资融券/股票池容量调整。
  3. 做 OOS：从 2024/2025 之后只用之后数据滚动评估，不允许继续调权重。
  4. 做滑点/冲击成本压力，尤其股票腿的买卖约束。

## 过拟合反思

- 运行前判断：不是过拟合。原因是先验来自跨资产低相关和独立承载，不是针对某一年或某个品种的补丁。
- 运行后判断：当前结果仍不能证明实盘可用，因为股票腿是 paper；但本阶段没有调权重小数救结果，`5%` 是预声明粗档位，且必须打败同权重现金稀释。
- 风险：如果后续围绕 `4%/6%/7%` 或股票 paper 内部参数救援，就会变成过拟合。

## 继续价值反思

- 运行前判断：有价值。当前期货内部多条卫星和风控路线已反证，继续找独立收益源比继续调 C3 内部参数更合理。
- 运行后判断：有价值。`5%` 股票paper 承载不是单纯稀释，确实略优于同权重现金，并改善正式78-1/C3路径；值得进入真实性复核。
- 原因：这条路线第一次同时满足回撤、收益保留、多窗口和现金对照四个闸门，但还缺真实可执行证明。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage069 研究候选。
- 是否更新 `research/registry.md`：是，最新关键阶段改为 Stage069。
- 是否追加根目录 `memory.md/back_log.md`：是，作为当前最强净值层研究候选与下一步真实性复核方向。
