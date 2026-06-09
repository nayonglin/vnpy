# Stage381 Stage372 50万 risk0.05 同时加 ni/ag/p A/C 多周期审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-06-06 01:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：产品池 add-three A/C 审计，研究隔离，不改正式实盘配置
- 是否重要突破：否
- 是否触发A/B：是，产品池变更可能影响后续候选，按 A/C 执行

## 外部调研与判断

- 参考资料：
  - 大连商品交易所棕榈油期货合约说明，交易代码 `P`、交易单位 `10吨/手`：`https://www.bocifco.com/newsinfo.aspx?cid=4&id=42068`
  - 信易科技大商所棕榈油业务规则解读，交易单位 `10吨/手`：`https://www.shinnytech.com/articles/business-rules/products/dce.p`
  - 东方财富棕榈油合约资料，交易代码 `P`、交易单位 `10吨/手`：`https://futures.eastmoney.com/qihuo/p.html`
- 我的判断：
  - `p.DCE` 是标准、活跃的油脂农产品期货，理论上可作为农产品/油脂风险源补充。
  - 但本次是在 Stage379 `ni+ag` 已经形成观察组合后继续手工追加单品种，存在选择后验证风险。
  - 因此不能只看是否打赢 baseline，必须强制对比 Stage379 的 `ni+ag` 组合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage667_stage372_500k_risk005_ni_ag_ab.py`
  - 修改内容：把 Stage667 通用 runner 里残留的 `ni/ag` 文案泛化为 `EXTRA_PRODUCTS` 组合文案；不改正式实盘脚本。
- 删除脚本：无
- 新增参数：
  - `CAPITAL=500000.0`
  - `RISK_MULTIPLIER=0.05`
  - `EXTRA_PRODUCTS=("ni.SHFE", "ag.SHFE", "p.DCE")`
  - `PLUS_COMBO_STRATEGY=stage669_stage372_500k_risk005_plus_ni_ag_p_entry_filter`
- 修改参数：
  - B 将 `account_capital/c3_capital` 改为 `500000`，`capital.risk_multiplier` 改为 `0.05`，产品池保持当前 Stage372 官方 19 品种。
  - C 在 B 基础上把产品宇宙从 `19` 个固定扩为 `22` 个，并在每个 AI eligibility `eval_date` 追加 `ni.SHFE`、`ag.SHFE`、`p.DCE`；不重训、不重排、不改变原品种分数顺序。
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 历史全周期与多起点：`2020-01-01` 至 `2026-04-30`
  - 最新 AI 池 YTD：`2026-01-01` 至 `2026-06-05`
- 账户规模：`500,000`
- 成本口径：原回测滑点，另输出 `1x/2x/3x` 成本压力
- 样本过滤：沿用 Stage372 官方产品池和 AI eligibility；C 仅固定追加 `ni.SHFE`、`ag.SHFE`、`p.DCE`
- 策略/归因口径：
  - B：`stage372_500k_risk005_no_ni_ag_p`
  - C：`stage372_500k_risk005_plus_ni_ag_p`

## 结果

### B：不加 ni/ag/p

- 期末权益：`930,295`
- 总收益：`86.0590%`
- 最大回撤：`-19.7233%`
- Sharpe：`0.8696`
- 总滑点：`30,630`
- 总交易次数：`307`
- 胜率：`48.0122%`
- broker10 保证金峰值：`53.5010%`
- 2x/3x 成本最大回撤：`-21.1782% / -22.8701%`

### C：同时固定加入 ni/ag/p

- 期末权益：`1,046,730`
- 总收益：`109.3460%`
- 最大回撤：`-17.8253%`
- Sharpe：`0.9049`
- 总滑点：`30,590`
- 总交易次数：`319`
- 胜率：`50.7483%`
- broker10 保证金峰值：`56.9404%`
- 2x/3x 成本最大回撤：`-18.3764% / -18.9379%`

### C 相对 B

- 全周期收益：`+23.2870pp`
- 全周期最大回撤：改善 `+1.8980pp`
- Sharpe：`+0.0353`
- 总交易：`+12`
- 总滑点：`-40`
- broker10 峰值：升高 `+3.4394pp`
- 2x 成本回撤：改善 `+2.8018pp`
- `ni/ag/p` 自身合计净 PnL：`+98,640`
  - `ag` 净 PnL `+38,670`，滑点 `690`，活跃 `68` 天
  - `ni` 净 PnL `+81,190`，滑点 `820`，活跃 `97` 天
  - `p` 净 PnL `-21,220`，滑点 `1,100`，活跃 `55` 天

### 与 Stage379 ni/ag 对照

- Stage379 `ni+ag` C：`1,167,925/133.5850%/-17.6657%/Sharpe0.9751`
- Stage381 `ni+ag+p` C：`1,046,730/109.3460%/-17.8253%/Sharpe0.9049`
- 加入 `p` 后相对 `ni+ag`：
  - 期末权益少 `121,195`
  - 总收益少 `24.2390pp`
  - 最大回撤劣化 `0.1596pp`
  - Sharpe 少 `0.0702`
  - broker10 峰值升高 `6.1380pp`
- 判断：`p` 是拖累项，不应进入当前 `ni+ag` 观察组合。

### 多周期重点

- `since_2021`：B `61.3400%/-19.6936%/Sharpe0.8360`，C `88.2210%/-17.8392%/Sharpe0.9191`，收益 `+26.8810pp`
- `since_2022`：B `31.1100%/-13.5351%/Sharpe0.6228`，C `46.8380%/-15.2904%/Sharpe0.7152`，收益 `+15.7280pp`，但回撤劣化 `1.7553pp`
- `since_2023`：B `54.2550%/-14.6518%/Sharpe1.0590`，C `74.1000%/-11.8555%/Sharpe1.0642`，收益 `+19.8450pp`
- `since_2024`：B `38.8020%/-11.5302%/Sharpe1.2230`，C `71.1890%/-12.5520%/Sharpe1.2794`，收益 `+32.3870pp`，但回撤劣化 `1.0218pp`
- `since_2025`：B `38.0020%/-4.7964%/Sharpe1.8892`，C `19.0480%/-9.7022%/Sharpe0.9723`，收益 `-18.9540pp`，回撤劣化 `4.9057pp`
- `ytd_2026_latest_ai`：B `-0.4130%/-1.4001%/Sharpe-0.2951`，C `-0.5300%/-1.4017%/Sharpe-0.3503`，收益 `-0.1170pp`，保证金峰值从 `2.7247%` 升至 `6.4049%`

### 滚动窗口

- B 63/126/252日 p05：`-7.6182% / -8.9641% / -13.8217%`
- C 63/126/252日 p05：`-8.4748% / -10.7858% / -11.6698%`
- 判断：C 只改善 252日左尾，63/126日短中周期左尾变差。

### 资金占用

口径：全周期 `2020-01-02` 至 `2026-04-30`，使用 `broker10_margin_to_rebased_equity_pct`。

| 版本 | active days | active rate | 平均占用 | 持仓日平均占用 | p95 | 峰值 | >30%天数 | >50%天数 | >90%天数 | >100%天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | `591` | `38.58%` | `2.94%` | `7.63%` | `24.33%` | `53.50%` | `18` | `5` | `0` | `0` |
| Stage379 `ni+ag` | `677` | `44.19%` | `4.00%` | `9.06%` | `25.78%` | `50.80%` | `26` | `1` | `0` | `0` |
| Stage381 `ni+ag+p` | `660` | `43.08%` | `3.72%` | `8.63%` | `24.88%` | `56.94%` | `15` | `4` | `0` | `0` |

判断：`ni+ag+p` 的常态占用低于 `ni+ag`，但峰值从 `50.80%` 升至 `56.94%`，且收益和 Sharpe 明显弱于 `ni+ag`；资金占用形状不足以抵消收益质量下降。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_report_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_summary_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_comparison_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_cost_stress_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_rolling_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.csv`
- activity：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_extra_activity_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_chart_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage669_stage372_500k_risk005_ni_ag_p_ab_decision_stage669_stage372_500k_risk005_ni_ag_p_ab_v1.json`

## 结论

- 脚本硬闸门结论：`plus_ni_ag_p_watch_not_auto_promote`
- 人工研究结论：`p_addition_rejected_keep_ni_ag_watch`
- 是否进入下一步：`p.DCE` 不进入当前观察组合；保留 Stage379 `ni+ag` 作为更优观察口径。
- 原因：
  - `ni+ag+p` 虽然打赢低风险 baseline，但相对刚形成的 `ni+ag` 组合明显变差。
  - `p` 自身全周期净 PnL 为 `-21,220`，且滑点 `1,100`。
  - 加 `p` 以后全周期收益、最大回撤、Sharpe、保证金峰值均弱于 `ni+ag`。
  - `since_2025` 和最新 AI 池 YTD 明显弱于 baseline，近期路径不合格。
- 下一步：
  - 不改当前官方实盘版本 `official_live_stage372_20w_recovery_sleeve`。
  - 不围绕 `p` 入池月份、方向、权重、过滤年份继续救援。
  - 如继续扩池，应回到通用 selector、风险槽、低风险 satellite 或外生状态验证，而不是手工逐个追加。

## 过拟合反思

- 运行前判断：有过拟合风险。
- 运行后判断：过拟合风险仍高，且 `p` 本次不值得继续。
- 原因：
  - `p` 是在 `ni+ag` 跑出强结果后继续手工追加，属于选择后扩展。
  - 虽然没有调小数阈值，也跑了全周期、多起点、成本压力和滚动窗口，但 `p` 自身贡献为负，且削弱 `ni+ag` 的综合结果。
  - 继续围绕 `p` 筛月份、方向或权重，会明显变成历史拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：`p` 这条手工追加路线没有继续价值；扩池总方向仍有价值。
- 原因：
  - 这次反证提供了边界：油脂农产品“理论上可分散”，但当前策略和当前数据下 `p` 不是有效低风险补充。
  - Stage379 的 `ni+ag` 仍是更干净的观察组合；下一步应验证通用机制，而不是对 `p` 做补丁。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage381 反证结论。
- 是否更新 `research/registry.md`：否，正式实盘状态不变。
- 是否追加根目录 `memory.md/back_log.md`：是，`back_log.md` 记录回测，`memory.md` 记录 `p` 不进入当前观察组合。
