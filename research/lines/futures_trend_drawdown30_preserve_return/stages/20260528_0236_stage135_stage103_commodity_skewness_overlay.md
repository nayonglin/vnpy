# Stage135 Stage103商品期货偏度异象overlay审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 02:36 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：外部先验驱动的低自由度结构验证；不改 Stage079/C3，不改 Stage103，不增加资金。
- 是否重要突破：否；但属于有价值的强 paper 线索。它显示低偏度商品期货 overlay 有收益和体验改善能力，但未通过“任何时候启动”的硬约束。
- 是否触发A/B：是。A=`Stage079`；C0=`Stage103 broker10_guard`；C1=`low_skew252_monthly_best1`；C2=`low_skew252_monthly_top3`。

## 外部调研与判断

- 参考资料：
  - Fernandez-Perez / Frijns / Fuertes / Miffre 的商品期货偏度研究：商品期货中做多低偏度、做空高偏度可形成横截面收益。
  - EDHEC 相关摘要显示，系统性买低偏度商品、卖高偏度商品的收益不能完全由 backwardation/contango 解释。
  - 后续 expected skewness 研究也支持商品期货预期偏度与未来收益负相关。
- 我的判断：
  - 这是不同于 Stage103 xsmom 的风险源，值得一次固定审计。
  - 为避免过拟合，本阶段只用文献口径的 `252` 交易日偏度、shift 一日、约月频再平衡；不按本地坏窗口调日期、品种或阈值。
  - `best1` 是最小可执行承载，`top3` 是文献型横截面组合承载；这不是相邻小数扫描。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage435_stage103_commodity_skewness_overlay.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `SKEW_LOOKBACK_DAYS=252`
  - `REBALANCE_EVERY=20`
  - `low_skew252_monthly_best1`：偏度最低1个品种做多、偏度最高1个品种做空，每品种1手。
  - `low_skew252_monthly_top3`：偏度最低3个品种做多、偏度最高3个品种做空，每品种1手。
  - 沿用 `BROKER10_MULTIPLIER=1.10` 组合保证金闸门。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：当前权威 `2020-01-02` 起至 2026 数据末端。
- 多起点：`start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/phase_2024_2025/weak_2021_full/ytd_2026`。
- 账户规模：`615,000` 账户口径；Stage079 为 `50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本，并复验 `1x/2x/3x/5x` 滑点压力。
- 样本过滤：无日期、月份、品种补丁；偏度全量基于交易日前已知日收益。
- 策略/归因口径：Stage103 固定路径上叠加商品偏度横截面 overlay。

## 结果

### 全周期核心结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 3个月分 | 6个月分 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 100.0000 | 100.0000 |
| Stage103 broker10_guard | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 121.2041 | 134.4513 |
| low_skew252_best1 | 32,017,870 | 5106.1577% | -27.4339% | 1.3984 | 13.7806 | 144.2581 | 146.9918 |
| low_skew252_top3 | 32,143,540 | 5126.5919% | -27.8044% | 1.3773 | 14.1392 | 123.9362 | 137.7984 |

### 交易与胜率

| 版本 | 总滑点 | 总交易次数 | 日胜率 | 非零日胜率 |
|---|---:|---:|---:|---:|
| Stage079 | 1,556,750 | 757 | 36.2924% | 48.3478% |
| Stage103 broker10_guard | 1,569,265 | 1,217 | 43.0809% | 50.3432% |
| low_skew252_best1 | 1,575,495 | 1,417 | 50.1958% | 51.4037% |
| low_skew252_top3 | 1,583,775 | 1,695 | 49.5431% | 50.8372% |

### 短持有体验

- `low_skew252_best1`：
  - 3个月：p05收益 `-10.5394%`，中位收益 `13.3479%`，正收益率 `75.0563%`，低增长率 `27.8253%`，最差期内回撤 `-25.2820%`，破20回撤率 `11.8865%`，Ulcer P95 `15.5764`，P95最长水下 `87.0` 天。
  - 6个月：p05收益 `-0.8702%`，中位收益 `34.1040%`，正收益率 `94.4627%`，低增长率 `8.4937%`，最差期内回撤 `-27.4339%`，破20回撤率 `32.9423%`，Ulcer P95 `17.1953`，P95最长水下 `162.5` 天。
- `low_skew252_top3`：
  - 3个月：p05收益 `-10.7177%`，中位收益 `13.4787%`，正收益率 `75.1013%`，低增长率 `27.6002%`，最差期内回撤 `-27.8044%`，破20回撤率 `16.9293%`，Ulcer P95 `16.3760`。
  - 6个月：p05收益 `-0.8484%`，中位收益 `33.8976%`，正收益率 `94.4158%`，低增长率 `8.3998%`，最差期内回撤 `-27.8044%`，破20回撤率 `35.7109%`，Ulcer P95 `18.3968`。

### 失败点

- `low_skew252_best1` 全周期硬指标和成本压力都优于 Stage079/Stage103，但 `ytd_2026` 冷启动最大回撤为 `-42.6937%`，因此 `fresh_start_dd30_pass=0`，不能正式晋级。
- `low_skew252_top3` 全周期收益更高，但 `start_2022` 冷启动最大回撤为 `-39.7633%`，且多个 1.10x 保证金窗口相对 Stage103 变差。
- 任意启动相对 Stage103：
  - best1 的 90/180/252/504日收益胜率仅 `47.9514%/39.8874%/37.6396%/36.1372%`，收益胜率不足；但风险体验更稳，504日最大回撤/Ulcer 不劣化率均为 `100%`。
  - top3 的 90/180/252/504日收益胜率为 `56.1459%/55.8423%/59.2035%/51.6879%`，收益胜率好，但风险不劣化率不足且冷启动失败。
- 最大贡献日剔除：
  - best1 剔除相对 Stage103 最大5个正贡献日后仍略高 `+0.5602pp`，剔除10个后转负。
  - top3 剔除最大10个正贡献日后仍高 `+16.3602pp`，剔除20个后转负。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_report_stage435_stage103_commodity_skewness_overlay_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_chart_stage435_stage103_commodity_skewness_overlay_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_summary_stage435_stage103_commodity_skewness_overlay_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_daily_stage435_stage103_commodity_skewness_overlay_v1.csv`
- overlay：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_overlay_daily_stage435_stage103_commodity_skewness_overlay_v1.csv`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_features_stage435_stage103_commodity_skewness_overlay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage435_stage103_commodity_skewness_overlay_decision_stage435_stage103_commodity_skewness_overlay_v1.json`

## 结论

- 本阶段结论：`no_new_promotion`。偏度 overlay 有真实研究价值，但不能进入当前 Stage079 硬目标主版本。
- 是否进入下一步：
  - 正式主线：不进入，当前主执行相对候选仍是 Stage103。
  - paper 观察：`low_skew252_best1` 值得作为强 paper 线索保留，因为它全周期、成本压力、3/6个月分都优于 Stage103，且贡献日不算极端集中；但必须标红 `ytd_2026` 冷启动破30风险。
- 下一步：
  1. 不继续扫 `63/126/504` 偏度窗口、`best1/top2/top3`、偏度阈值、日期或品种补丁。
  2. 若未来真实券商保证金和2026之后 OOS 能覆盖该弱点，可重新只读复核。
  3. 当前目标继续时，仍应优先 Stage103 工程化复跑或寻找更轻保证金、样本更充分的新风险源。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合；如果继续救 2026 窗口，就会转向过拟合。
- 原因：本阶段规则来自外部文献先验，只测试两个离散承载；失败点出现后没有按 `2026` 日期、品种或阈值补丁救结果。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该子路线不适合继续主动优化，但值得 paper 观察；总目标仍有价值。
- 原因：偏度 overlay 的收益源比前几条 xsmom 质量过滤更独立，best1 指标强于 Stage103；但当前目标强调“任何时候启动”，而它在 `ytd_2026` 冷启动打穿30，不能回避。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage135 约束和阶段文件。
- 是否更新 `research/registry.md`：否，未形成新的正式主候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 简要摘要；不更新 `memory.md`。
