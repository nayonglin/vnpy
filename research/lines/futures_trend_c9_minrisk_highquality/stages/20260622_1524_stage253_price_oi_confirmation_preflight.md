# Stage253 价量与 OI 确认只读预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 preflight；复核价格顺势是否需要 OI 扩张确认
- 是否重要突破：否，原假设阻断并暴露反直觉观察
- 是否触发A/B：否；没有形成可接入正式版本的候选

## 外部调研与判断

- 参考资料：
  - NBER/Hong & Yogo, What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices: https://www.nber.org/papers/w16712
  - CME Group, Understanding Open Interest: https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest
  - GitHub, `chrism2671/PyTrendFollow`: https://github.com/chrism2671/PyTrendFollow
  - GitHub, `pst-group/pysystemtrade`: https://github.com/pst-group/pysystemtrade
  - Investopedia, Intro to Open Interest in the Futures Market: https://www.investopedia.com/trading/intro-to-open-interest-in-futures-market/
- 我的判断：OI 有外生参与度含义，但单独不能区分新增多头、新增空头、平仓或换手。更普世的起点不是扫 OI 阈值，而是先用符号矩阵审计“价格顺势 + OI 扩张”是否真能表示新风险承接。本阶段结果否定这个直觉；同时发现“价格顺势 + OI 收缩”承载大量右尾，但这只能进入下一步反例审计，不能直接交易化。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage253_price_oi_confirmation_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LOOKBACK_CLOSED_BARS=61`
  - `direction_aligned_price_log_return_60m = direction_sign * log(close_end / close_start)`
  - `oi_delta_pct_60m = (oi_end - oi_start) / abs(oi_start)`
  - 四象限：`aligned_price_oi_expand`、`aligned_price_oi_contract`、`against_price_oi_expand`、`against_price_oi_contract`，另设 `flat_or_missing`
  - promotion gate：source ready `>=95%`、样本数 `>=30`、坏账率相对 rest 降低 `>=5pp`、右尾捕获 `>=50%`、bottom-loss 捕获 `<=25%`、early right-tail 捕获 `>=50%`、无 PnL 正负混杂、split pass share `>=60%`、技术隔离通过
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- 样本过滤：Stage249 的 `219` 个 timestamp-ready replay order；Stage239/180 的 cutoff-filtered predecision source 全部点时过滤
- 策略/归因口径：
  - 冻结原假设：高质量信号应表现为入场前 60 根 closed 1m bar 的价格顺着信号方向，同时 OI 扩张
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- timestamp-ready 订单数：`219`
- source ready：`219/219 = 100.0000%`
- aligned price + OI expansion 订单数：`48`
- aligned price + OI expansion PnL：`-1,971,606.40`
- aligned price + OI expansion 单笔 PnL 最小/最大：`-1,440,000` / `709,230`
- aligned price + OI expansion risk_bad_rate：`0.145833`
- rest risk_bad_rate：`0.198830`
- 相对 rest 坏账率降低：`0.052997`
- aligned price + OI expansion right-tail 捕获：`1/18 = 5.5556%`
- aligned price + OI expansion bottom-loss 捕获：`3/18 = 16.6667%`
- aligned price + OI expansion early right-tail 捕获：`0/9 = 0.0000%`
- split stability：`1/11 = 9.0909%`
- promotion gate：`5/9`，通过 source ready、样本量、坏账率降低、bottom-loss 捕获、技术隔离；失败右尾捕获、早期右尾捕获、PnL 正负混杂、split 稳定性
- 反直觉观察：`aligned_price_oi_contract` PnL `23,972,483.70`，right-tail 捕获 `10/18 = 55.5556%`，early right-tail 捕获 `6/9 = 66.6667%`，但 bottom-loss 捕获 `6/18 = 33.3333%` 且仍有 PnL 正负混杂
- 决策：`stage253_price_oi_confirmation_tail_conflict_no_true_engine_no_rule`

## 视觉分析

- official path OI confirmation chart：aligned-expand 点散布在权益台阶上，但不是右尾集中区；后半段仍有大量非 expand 状态承载收益。
- contribution chart：绿色 aligned-expand 累计曲线最终为负，蓝色 aligned-contract 才是主要 PnL 和右尾承载。这直接反证“顺势必须有 OI 扩张才高质量”的直觉。
- group rate chart：aligned-expand 坏账率略低，但 right-tail rate 只有 `0.0208`；aligned-contract right-tail rate 达 `0.1351`，但 bottom-loss 和混合 PnL 仍不可忽视。
- split heatmap：aligned-expand 只有 `2022` 通过；`2023`、`2024`、CZCE、DCE、short 等切片的 PnL 或右尾保留明显反向。
- source quality chart：数据源不是问题，`219/219` price/OI 都 ready；失败来自状态机制本身，而不是覆盖不足。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_report_stage253_price_oi_confirmation_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_summary_stage253_price_oi_confirmation_preflight_v1.csv`
- rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_oi_confirmation_rows_stage253_price_oi_confirmation_preflight_v1.csv`
- group summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_group_summary_stage253_price_oi_confirmation_preflight_v1.csv`
- split stability：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_split_stability_stage253_price_oi_confirmation_preflight_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage253_price_oi_confirmation_preflight/qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_promotion_gate_stage253_price_oi_confirmation_preflight_v1.csv`
- visuals：
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_official_path_oi_confirmation_chart_stage253_price_oi_confirmation_preflight_v1.png`
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_oi_confirmation_contribution_chart_stage253_price_oi_confirmation_preflight_v1.png`
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_group_rate_chart_stage253_price_oi_confirmation_preflight_v1.png`
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_split_stability_heatmap_stage253_price_oi_confirmation_preflight_v1.png`
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_promotion_gate_chart_stage253_price_oi_confirmation_preflight_v1.png`
  - `qmt_roll_stage253_c9_minrisk_price_oi_confirmation_preflight_source_quality_chart_stage253_price_oi_confirmation_preflight_v1.png`

## 结论

- 本阶段结论：`aligned_price_oi_expand` 原假设被否定。它略降坏账，但几乎不保右尾，且累计 PnL 为负。
- 是否进入下一步：原假设不进入 true engine、不进入正式候选、不触发 A/B；但 `aligned_price_oi_contract` 作为反直觉观察值得做 Stage254 反例与稳定性审计。
- 下一步：Stage254 只审计 `aligned_price_oi_contract` 是否跨年份/交易所/方向稳定，并画反例；不得直接把 OI 收缩写成交易规则，也不得扫 OI 百分比阈值、lookback、年份、交易所、方向或产品补丁。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：本次没有新增过拟合；直接追 `aligned_contract` 会有过拟合风险，必须先做独立反例审计。
- 原因：本阶段只用符号矩阵，不扫阈值；但 `aligned_contract` 是在结果中暴露出的反直觉状态，虽然属于预声明四象限之一，也不能跳过稳定性和反例层。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：OI 扩张确认路线无继续价值；OI 收缩/挤压状态仍有继续审计价值。
- 原因：source ready 已满，说明不是覆盖问题；真正有信息的是价格顺势时 OI 收缩可能代表平仓挤压或流动性释放，但该机制同样可能是末端追价和拥挤解除。必须先证明它不是 2025 或少数品种驱动。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage253 预检阻断与 Stage254 方向。
- 是否更新 `research/registry.md`：否，本线不新增/合并/废弃研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要合入。
