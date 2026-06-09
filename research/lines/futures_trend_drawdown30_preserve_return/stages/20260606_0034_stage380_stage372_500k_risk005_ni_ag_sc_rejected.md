# Stage380 Stage372 50万 risk0.05 同时加 ni/ag/sc A/C 多周期审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-06 00:34 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：产品池 add-three A/C 审计，研究隔离，不改正式实盘配置
- 是否重要突破：否
- 是否触发A/B：是，产品池变更可能影响后续候选，按 A/C 执行

## 外部调研与判断

- 参考资料：
  - INE 原油期货标准合约：`https://www.ine.cn/products/futures/energyandchemical/sc_f/standard_sc_f/202312/t20231205_802540.html`
  - INE 英文原油期货合约页：`https://tsite.shfe.com.cn/eng/market/futures/energy/sc/contract/`
  - Trend-following trading strategies in commodity futures: A re-examination：`https://www.sciencedirect.com/science/article/pii/S037842660900199X`
- 我的判断：
  - `sc.INE` 是上海国际能源交易中心原油期货，交易代码 `SC`，交易单位 `1000桶/手`，足以作为能源风险源研究对象。
  - 趋势跟随的第一性原理支持跨品种、跨风险源分散，能源品种理论上可以补金属/农化/黑色的风险来源。
  - 但本次是在 `ni+ag` 已经跑出正线索之后继续手工追加 `sc`，存在明显选择后验证风险；必须用 `ni+ag` 本身作为强对照，而不是只看是否打赢 baseline。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab.py`
  - 修改内容：把 Stage667 主体泛化为可参数化 A/C runner，便于 Stage668 复用；不改正式实盘脚本。
- 删除脚本：无
- 新增参数：
  - `CAPITAL=500000.0`
  - `RISK_MULTIPLIER=0.05`
  - `EXTRA_PRODUCTS=("ni.SHFE", "ag.SHFE", "sc.INE")`
  - `PLUS_COMBO_STRATEGY=stage668_stage372_500k_risk005_plus_ni_ag_sc_entry_filter`
- 修改参数：
  - B 将 `account_capital/c3_capital` 改为 `500000`，`capital.risk_multiplier` 改为 `0.05`，产品池保持当前 Stage372 官方 19 品种。
  - C 在 B 基础上把产品宇宙从 `19` 个固定扩为 `22` 个，并在每个 AI eligibility `eval_date` 追加 `ni.SHFE`、`ag.SHFE`、`sc.INE`；不重训、不重排、不改变原品种分数顺序。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 历史全周期与多起点：`2020-01-01` 至 `2026-04-30`
  - 最新 AI 池 YTD：`2026-01-01` 至 `2026-06-05`
- 账户规模：`500,000`
- 成本口径：原回测滑点，另输出 `1x/2x/3x` 成本压力
- 样本过滤：沿用 Stage372 官方产品池和 AI eligibility；C 仅固定追加 `ni.SHFE`、`ag.SHFE`、`sc.INE`
- 策略/归因口径：
  - B：`stage372_500k_risk005_no_ni_ag_sc`
  - C：`stage372_500k_risk005_plus_ni_ag_sc`

## 结果

### B：不加 ni/ag/sc

- 期末权益：`930,295`
- 总收益：`86.0590%`
- 最大回撤：`-19.7233%`
- Sharpe：`0.8696`
- 总滑点：`30,630`
- 总交易次数：`307`
- 胜率：`48.0122%`
- broker10 保证金峰值：`53.5010%`
- 2x/3x 成本最大回撤：`-21.1782% / -22.8701%`

### C：同时固定加入 ni/ag/sc

- 期末权益：`1,090,155`
- 总收益：`118.0310%`
- 最大回撤：`-18.5669%`
- Sharpe：`0.8761`
- 总滑点：`35,600`
- 总交易次数：`321`
- 胜率：`49.5902%`
- broker10 保证金峰值：`51.7692%`
- 2x/3x 成本最大回撤：`-19.1319% / -19.7080%`

### C 相对 B

- 全周期收益：`+31.9720pp`
- 全周期最大回撤：改善 `+1.1563pp`
- Sharpe：`+0.0065`
- 总交易：`+14`
- 总滑点：`+4,970`
- broker10 峰值：下降 `-1.7317pp`
- 2x 成本回撤：改善 `+2.0463pp`
- `ni/ag/sc` 自身合计净 PnL：`+117,775`
  - `ag` 净 PnL `+105,495`，滑点 `1,020`，活跃 `68` 天
  - `ni` 净 PnL `+75,480`，滑点 `1,040`，活跃 `102` 天
  - `sc` 净 PnL `-63,200`，滑点 `2,800`，活跃 `41` 天

### 与 Stage379 ni/ag 对照

- Stage379 `ni+ag` C：`1,167,925/133.5850%/-17.6657%/Sharpe0.9751`
- Stage380 `ni+ag+sc` C：`1,090,155/118.0310%/-18.5669%/Sharpe0.8761`
- 加入 `sc` 后相对 `ni+ag`：
  - 期末权益少 `77,770`
  - 总收益少 `15.5540pp`
  - 最大回撤劣化 `0.9013pp`
  - Sharpe 少 `0.0990`
  - 总滑点多 `930`
  - 总交易多 `8`
  - broker10 峰值升高 `0.9669pp`
- 判断：`sc` 是拖累项，不应进入当前 `ni+ag` 观察组合。

### 多周期重点

- `since_2021`：B `61.3400%/-19.6936%/Sharpe0.8360`，C `109.4310%/-18.4563%/Sharpe0.9287`，收益 `+48.0910pp`
- `since_2022`：B `31.1100%/-13.5351%/Sharpe0.6228`，C `58.6980%/-14.9981%/Sharpe0.7306`，收益 `+27.5880pp`，但回撤劣化 `1.4630pp`
- `since_2023`：B `54.2550%/-14.6518%/Sharpe1.0590`，C `135.3710%/-17.5609%/Sharpe1.2995`，收益 `+81.1160pp`，但回撤劣化 `2.9091pp`
- `since_2024`：B `38.8020%/-11.5302%/Sharpe1.2230`，C `126.7560%/-18.5647%/Sharpe1.5031`，收益 `+87.9540pp`，但回撤劣化 `7.0344pp`
- `since_2025`：B `38.0020%/-4.7964%/Sharpe1.8892`，C `68.0540%/-11.9552%/Sharpe1.7222`，收益 `+30.0520pp`，但回撤劣化 `7.1588pp` 且 Sharpe 下降
- `ytd_2026_latest_ai`：B `-0.4130%/-1.4001%/Sharpe-0.2951`，C `-0.5300%/-1.4017%/Sharpe-0.3503`，收益 `-0.1170pp`，保证金峰值从 `2.7247%` 升至 `6.4049%`

### 滚动窗口

- B 63/126/252日 p05：`-7.6182% / -8.9641% / -13.8217%`
- C 63/126/252日 p05：`-8.7114% / -11.5266% / -12.8368%`
- 判断：C 只改善 252日左尾，63/126日短中周期左尾变差。

### 资金占用

- B 全周期 active days `591`，active rate `38.58%`，平均占用 `2.94%`，active 平均占用 `7.63%`，p95 `24.33%`，峰值 `53.50%`，`>30%` 天数 `18`，`>50%` 天数 `5`
- C 全周期 active days `662`，active rate `43.21%`，平均占用 `4.26%`，active 平均占用 `9.85%`，p95 `25.75%`，峰值 `51.77%`，`>30%` 天数 `30`，`>50%` 天数 `2`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_report_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_summary_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_comparison_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_cost_stress_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_rolling_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- daily/curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_curves_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_extra_activity_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- quality/checks：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_checks_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_chart_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage668_stage372_500k_risk005_ni_ag_sc_ab_decision_stage668_stage372_500k_risk005_ni_ag_sc_ab_v1.json`

## 结论

- 脚本硬闸门结论：`plus_ni_ag_sc_watch_not_auto_promote`
- 人工研究结论：`sc_addition_rejected_keep_ni_ag_watch`
- 是否进入下一步：`sc.INE` 不进入当前观察组合；保留 Stage379 `ni+ag` 作为更优观察口径。
- 原因：
  - `ni+ag+sc` 虽然打赢低风险 baseline，但相对刚形成的 `ni+ag` 组合明显变差。
  - `sc` 自身全周期净 PnL 为 `-63,200`，且滑点 `2,800`，不是低成本分散源。
  - 加 `sc` 以后全周期收益、最大回撤、Sharpe、滑点、交易数、保证金峰值均弱于 `ni+ag`。
  - 近期 `2026` 年度拆解更弱，C 年度为 `-18.0800%`，不能作为实盘扩池依据。
- 下一步：
  - 不改当前官方实盘版本 `official_live_stage372_20w_recovery_sleeve`。
  - 不围绕 `sc` 入池月份、方向、权重、过滤年份继续救援。
  - 如继续扩池，应回到通用 selector、风险槽、低风险 satellite 或外生状态验证，而不是手工逐个追加。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：过拟合风险仍高，且 `sc` 本次不值得继续。
- 原因：
  - `sc` 是在 `ni+ag` 跑出强结果后继续手工追加，属于选择后扩展。
  - 虽然没有调小数阈值，也跑了全周期、多起点、成本压力和滚动窗口，但 `sc` 自身贡献为负，且削弱 `ni+ag` 的综合结果。
  - 继续围绕 `sc` 筛月份、方向或权重，会明显变成历史拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：`sc` 这条手工追加路线没有继续价值；扩池总方向仍有价值。
- 原因：
  - 这次反证提供了边界：能源风险源“理论上可分散”，但当前策略和当前数据下 `sc` 不是有效低风险补充。
  - Stage379 的 `ni+ag` 仍是更干净的观察组合；下一步应验证通用机制，而不是对 `sc` 做补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage380 反证结论。
- 是否更新 `research/registry.md`：否，正式实盘状态不变。
- 是否追加根目录 `memory.md/back_log.md`：是，`back_log.md` 记录回测，`memory.md` 记录 `sc` 不进入当前观察组合。
