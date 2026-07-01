# Stage016 Account Pressure Attribution

- 记录时间：`2026-07-01 14:08 CST`
- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- model_tag：`stage016_account_pressure_attribution_v1`
- 阶段性质：只读账户压力归因；不改策略、不连接 CTP、不调用下单 API。
- 是否重要突破版本：`否`
- 决策：`stage016_pressure_attribution_no_engine_yet`

## 本次目标

Stage015 已反证 3/5/10 日确认后加仓和 `jd.DCE` 直接入共享 AI 池。本阶段转向账户层压力治理，只读回答：

1. `broker10` 高热是否是 Stage013 剩余负窗口的可交易前置信号。
2. 最差窗口是在起点就高压，还是起点后逐步形成压力。
3. 是否存在比高 `broker10` 更前置、但不会明显误伤右尾的账户状态标签。

## 外部调研判断

- CME 风控教育强调 margin 是 broker/账户层风险约束，但不等价于交易信号；这支持本阶段把 `broker10` 当风险标签审计，而不是直接把高保证金改成平仓规则。
- CTA/趋势跟随资料更支持 volatility targeting、仓位规模、组合层风险预算与分散化管理；不支持按单一年份、品种、方向或临界热度补丁化。
- GitHub 上 PyTrendFollow/MLM 类趋势跟随项目的共识也是先做组合级波动/仓位规模，再看具体市场信号；这与当前 C9 多品种真实引擎的“右尾不能被一刀切砍掉”一致。

参考：

- https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
- https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
- https://github.com/chrism2671/PyTrendFollow

## 历史反证约束

- 旧 C9 线 Stage865 已反证账户 heat sizing brake：投影 broker10 高热能碰到部分风险单，但太钝，砍掉赢家和大赢家更多，不能进真实引擎。
- 旧 C9 线 Stage887 已反证 sleeve pressure gate：前置 heat/pressure gate 最宽阻断 `79` 次，skip proxy `-114,051.15`，winner cut `-170,746.95` 大于 loser saved `56,695.80`。
- 因此 Stage016 不重复做 `broker80/90` 强制缩手、强制减仓或高压退出。

## 数据和输出

- 输入：Stage013 curves、fixed horizon windows、worst windows；Stage015 closed lots。
- 本阶段输出目录：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage016_account_pressure_attribution/`
- 主要输出：
  - `rebuilt_c9_stage016_account_pressure_attribution_fixed_window_start_state_summary_stage016_account_pressure_attribution_v1.csv`
  - `rebuilt_c9_stage016_account_pressure_attribution_daily_forward_pressure_summary_stage016_account_pressure_attribution_v1.csv`
  - `rebuilt_c9_stage016_account_pressure_attribution_worst_window_pressure_path_detail_stage016_account_pressure_attribution_v1.csv`
  - `rebuilt_c9_stage016_account_pressure_attribution_worst_window_pressure_path_summary_stage016_account_pressure_attribution_v1.csv`
  - `rebuilt_c9_stage016_account_pressure_attribution_entry_pressure_summary_stage016_account_pressure_attribution_v1.csv`
  - `rebuilt_c9_stage016_account_pressure_attribution_chart_stage016_account_pressure_attribution_v1.png`
  - `rebuilt_c9_stage016_account_pressure_attribution_report_stage016_account_pressure_attribution_v1.md`

## 核心结果

`broker10>=80%` 不是好前置信号：

- 样本数 `24` 天。
- 后续 `252` 交易日负收益率 `0%`，最差收益 `12.6402%`，中位收益 `674.1184%`。
- 后续 `366` 交易日负收益率 `0%`，最差收益 `10.6799%`，中位收益 `593.223%`。

最差窗口不是起点就高热：

- Top100 最差窗口起点中位 broker10 仅 `28.6952%`。
- 起点中位 drawdown 仅 `-1.1315%`。
- 起点中位活跃品种 `3` 个。
- 开始后前 `63` 个交易日，broker10 中位最大值升到 `49.8426%`，中位最深回撤到 `-27.2178%`，中位最大活跃品种升到 `4` 个。
- 前 `126` 个交易日，broker10 中位最大值 `53.6015%`，最深回撤中位 `-31.3804%`。

更像前置风险标签的是高位拥挤暴露，但不能交易化：

- 固定窗口起点 `active_products_4` 的 `366` 日负收益率 `27.7207%`，显著高于 `active_products_1` 的 `8.0635%`。
- 每日状态 `active4_near_peak` 后续 `252` 交易日负收益率 `22.0588%`，最差 `-36.0767%`，但中位收益仍有 `101.8748%`，均值 `196.7189%`。
- 这说明它是真风险标签，但也是右尾来源，不能直接禁开/减仓。

Stage013 pilot condition 更像恢复期保护：

- `stage013_pilot_condition` 后续 `366` 交易日负收益率 `0%`，最差 `3.8485%`，中位 `79.7772%`。
- 这说明深回撤低活跃时降低新开仓是合理保护，但它不是剩余左尾的起点；剩余左尾起于权益高位后的拥挤回撤。

逐笔 entry 压力桶：

- `2022-2023` 中，`active3plus_dd_le10pct` 只有 `4` 笔，PnL `-301,510`，样本太少，不能直接写规则。
- `active3plus_any_dd_corr_ge0.6` 在焦点段 `10` 笔，PnL `3,774,010`，说明同向相关高不等于一定危险，仍会包含右尾。

## 回测字段

- 本阶段是否为正式回测候选：`否`
- 期末权益：`N/A`
- 总收益：`N/A`
- 最大回撤：`N/A`
- Sharpe：`N/A`
- 总滑点：`N/A`
- 总交易次数：`N/A`
- 胜率：`N/A`

## 结论

Stage016 不晋级真实引擎候选。

原因是：高 `broker10` 是后验压力/右尾伴生标签，不是可直接砍仓信号；高位 4 品种拥挤暴露更前置，但会同时覆盖大量右尾。账户压力方向仍有价值，但不能再走 `broker80/90` 强制减仓、active4 禁开、同向相关一刀切这几条路径。

## 后续规划

1. 不写 `broker80/90` forced deleverage / forced shrink engine。
2. 不写 `active4_near_peak` 禁开或缩手规则。
3. 下一步更适合引入低自由度外生 regime/volatility 信号，先做只读证据，判断能否在“高位拥挤暴露”里区分右尾和假突破。
4. `jd.DCE` 若继续，只能做非挤占小预算真实引擎验证，不替换核心 AI topN。

## 反思

- 开始前过拟合反思：否。本阶段从 Stage015 反证后转账户压力，只验证预声明的压力形状。
- 开始前继续价值反思：是。剩余左尾明显涉及持仓路径和账户状态，值得检查 broker10 是否前置。
- 结束后过拟合反思：否。结果主动保留反证，没有把 `broker10>=80` 或 `active4_near_peak` 写成规则。
- 结束后继续价值反思：是，但要换信息源。单靠内部账户压力字段无法低误伤地区分右尾和左尾，下一步应找外生 regime/volatility 或非交易层生存线。
