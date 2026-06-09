# Stage377 Stage372 50万 risk0.05 加/不加 ni 多周期审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-05 23:29 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：资金/风险倍率/扩池 A/C 审计
- 是否重要突破：否，属于明确反证
- 是否触发A/B：是，B=50万/risk0.05不加ni，C=50万/risk0.05固定加ni

## 外部调研与判断

- 参考资料：
  - TradeAlgo futures risk management/position sizing：https://www.tradealgo.com/trading-guides/futures/futures-risk-management
  - SSRN `Trend Following, Risk Parity and Momentum in Commodity Futures`：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126813
  - GitHub `mlm-trend-following`：https://github.com/amstrdm/mlm-trend-following
  - GitHub `PyTrendFollow`：https://github.com/chrism2671/PyTrendFollow
- 我的判断：外部资料和开源实现仍支持“资金规模、波动、风险倍率、组合风险预算”这类结构性仓位治理；没有证据支持把 `ni.SHFE` 作为手工固定扩池项能提高商品趋势组合稳健性。因此本阶段只做隔离反证，不修改正式实盘配置。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage665_stage372_500k_risk005_ni_ab.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `CAPITAL=500000.0`
  - `RISK_MULTIPLIER=0.05`
  - `NI_PRODUCT=ni.SHFE`
  - `PLUS_NI_STRATEGY=stage665_stage372_500k_risk005_plus_ni_entry_filter`
- 修改参数：
  - `account_capital/c3_capital` 从当前正式 20万口径改为本实验 50万。
  - `capital.risk_multiplier` 从当前正式 `0.80` 改为 `0.05`。
  - C 臂产品宇宙从正式 `19` 个固定扩为 `20` 个，新增 `ni.SHFE`，并在每个 AI eligibility `eval_date` 固定追加 `ni.SHFE`。
- 删除参数：无
- 正式配置：未修改 `qmt_roll_official_live_config.py`；未连接 CTP；未调用下单。

## 回测/归因参数

- 数据区间：历史窗口到 `2026-04-30`；最新 AI 池 YTD 到 `2026-06-05`。
- 账户规模：`500,000`
- 成本口径：正常成本、2x成本、3x成本压力。
- 样本过滤：沿用当前 Stage372 官方产品池、Stage182 最新 AI 池；C 臂只固定追加 `ni.SHFE`，不重训、不重排。
- 策略/归因口径：
  - B：`stage372_500k_risk005_no_ni`
  - C：`stage372_500k_risk005_plus_ni`

## 结果

### B：50万/risk0.05/不加ni

- 期末权益：`930,295`
- 总收益：`86.0590%`
- 最大回撤：`-19.7233%`
- Sharpe：`0.8696`
- 总滑点：`30,630`
- 总交易次数：`307`
- 胜率：`48.0122%`
- broker10 峰值保证金/权益：`53.5010%`
- 超100%保证金天数：`0`
- 强制减仓：`0` 次 / `0` 手
- 2x成本：`899,665 / 79.9330% / -21.1782% / Sharpe 0.8150`
- 3x成本：`869,035 / 73.8070% / -22.8701% / Sharpe 0.7600`

### C：50万/risk0.05/固定加ni

- 期末权益：`742,720`
- 总收益：`48.5440%`
- 最大回撤：`-19.0516%`
- Sharpe：`0.6046`
- 总滑点：`24,990`
- 总交易次数：`283`
- 胜率：`48.0190%`
- broker10 峰值保证金/权益：`49.6617%`
- 超100%保证金天数：`0`
- 强制减仓：`0` 次 / `0` 手
- 2x成本：`717,730 / 43.5460% / -19.6744% / Sharpe 0.5510`
- 3x成本：`692,740 / 38.5480% / -20.9520% / Sharpe 0.4969`

### C 相对 B

- 全周期收益少：`-37.5150pp`
- 最大回撤改善：`+0.6717pp`
- Sharpe 下降：`-0.2650`
- 交易少：`-24`
- 滑点少：`-5,640`
- 2x成本回撤改善：`+1.5038pp`
- `ni` 自身全周期净 PnL：`-12,270`
- `ni` 自身滑点：`740`
- `ni` 持仓活跃日：`77`
- `ni` 活跃范围：`2020-07-07` 至 `2026-01-29`

### 多周期核心对比

| 窗口 | B收益/回撤 | C收益/回撤 | C-B收益 |
| --- | ---: | ---: | ---: |
| full_2020_20260430 | `86.0590% / -19.7233%` | `48.5440% / -19.0516%` | `-37.5150pp` |
| since_2021 | `61.3400% / -19.6936%` | `61.9820% / -19.1430%` | `+0.6420pp` |
| since_2022 | `31.1100% / -13.5351%` | `5.9700% / -14.7407%` | `-25.1400pp` |
| since_2023 | `54.2550% / -14.6518%` | `41.4110% / -14.7686%` | `-12.8440pp` |
| since_2024 | `38.8020% / -11.5302%` | `-1.2300% / -12.8157%` | `-40.0320pp` |
| since_2025 | `38.0020% / -4.7964%` | `10.4180% / -10.7741%` | `-27.5840pp` |
| phase_2020_2021 | `49.6060% / -16.5226%` | `47.5400% / -16.3753%` | `-2.0660pp` |
| phase_2022_2023 | `0.3310% / -13.3279%` | `9.8140% / -14.7407%` | `+9.4830pp` |
| phase_2024_2025 | `38.9290% / -11.5302%` | `1.1620% / -11.6683%` | `-37.7670pp` |
| ytd_2026_latest_ai | `-0.4130% / -1.4001%` | `-0.5300% / -1.4017%` | `-0.1170pp` |

### 滚动窗口

- B：63/126/252日 p05 收益分别为 `-7.6182% / -8.9641% / -13.8217%`
- C：63/126/252日 p05 收益分别为 `-7.4099% / -8.8884% / -12.9965%`
- 判断：C 的短持有左尾略有改善，但不足以抵消全周期收益和 Sharpe 的明显损失。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_report_stage665_stage372_500k_risk005_ni_ab_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_summary_stage665_stage372_500k_risk005_ni_ab_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_comparison_stage665_stage372_500k_risk005_ni_ab_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_cost_stress_stage665_stage372_500k_risk005_ni_ab_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_rolling_stage665_stage372_500k_risk005_ni_ab_v1.csv`
- daily/curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_curves_stage665_stage372_500k_risk005_ni_ab_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_chart_stage665_stage372_500k_risk005_ni_ab_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage665_stage372_500k_risk005_ni_ab_decision_stage665_stage372_500k_risk005_ni_ab_v1.json`

## 结论

- 本阶段结论：`plus_ni_rejected`。50万/risk0.05 不加 `ni` 是一个低回撤、低保证金占用、但收益显著低于当前正式 20万 Stage372 的防守口径；固定加 `ni` 在这个口径下仍不值得接入。
- 是否进入下一步：固定加 `ni` 不进入下一步。50万/risk0.05 可作为“极防守资金口径”经验保留，但不是当前正式替换候选。
- 下一步：如果继续 50万方向，应比较更通用的风险倍率前沿或组合层资金分层，而不是继续围绕 `ni` 做入池月份、方向、权重过滤。

## 过拟合反思

- 运行前判断：50万/risk0.05 是结构性 sizing 测试，过拟合风险较低；但 `ni` 是在 2022 趋势品种复盘后点名加入，有选择后验证风险。
- 运行后判断：固定加 `ni` 若继续救会进入过拟合。
- 原因：C 只在少数窗口略胜，且全周期收益少 `37.5150pp`、Sharpe 少 `0.2650`；继续调 `ni` 入池日期、方向、权重就是对历史路径补丁。

## 继续价值反思

- 运行前判断：有价值。它回答“提高资金规模且降低风险倍率后，ni 是否仍破坏组合”的结构性问题。
- 运行后判断：固定加 `ni` 没有继续价值；50万低风险倍率本身还有作为防守资金口径的参考价值。
- 原因：不加 `ni` 的 50万/risk0.05 全周期 DD 只有 `-19.7233%`、2x成本 DD `-21.1782%`，说明风险降低有效；但收益只有 `86.0590%`，偏防守，不适合替代当前收益优先正式版。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage377 反证。
- 是否更新 `research/registry.md`：否，正式状态不变。
- 是否追加根目录 `memory.md/back_log.md`：是，追加重要回测摘要与长期约束。
