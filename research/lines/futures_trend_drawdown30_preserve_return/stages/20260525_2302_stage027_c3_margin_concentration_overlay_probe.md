# Stage027 C3保证金/持仓拥挤状态识别

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-25 23:02 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：在 C3 上做账户状态归因与日级覆盖层边界探针
- 是否重要突破：否，但形成重要反证
- 是否触发A/B：是；这是 C3 + 账户层状态覆盖的 A/C 探针

## 外部调研与判断

- 参考资料：
  - Kim/Tse/Wald, Time series momentum and volatility scaling：趋势/期货动量表现很大程度受波动率缩放和风险预算影响，而不是只靠信号本身。https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379
  - Portfolio rebalancing based on time series momentum and downside risk：趋势动量可以结合 downside risk / CVaR 作为仓位控制，但必须点时化并避免事后窗口调参。https://academic.oup.com/imaman/article/34/2/355/6427746
  - Diversifying Trends：趋势组合的风险不只是普通相关性，也应关注趋势同向暴露和 drawdown risk。https://www.sciencedirect.com/science/article/abs/pii/S245230622100109X
- 我的判断：
  - 降回撤的低过拟合方向应优先检查波动、保证金、持仓广度和相关暴露，而不是继续改供需阈值或单品种黑名单。
  - 本阶段先用上一交易日可知的保证金/持仓广度做日级边界探针；即便跑出好结果，也必须后续落到真实引擎。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage327_c3_margin_concentration_overlay_probe.py`
- 修改脚本：
  - 无
- 删除脚本：
  - 无
- 新增参数：
  - `C_margin_soft_60_80_floor085`：上一交易日保证金/权益 60%-80% 线性降到 0.85
  - `C_margin_soft_70_90_floor080`：上一交易日保证金/权益 70%-90% 线性降到 0.80
  - `C_margin_review80_floor075`：上一交易日保证金/权益 >=80% 时降到 0.75
  - `C_active_products_6_8_floor085`：上一交易日持仓品种 6-8 个线性降到 0.85
  - `C_margin80_active7_floor080`：保证金/权益 >=80% 且持仓品种 >=7 时降到 0.80
- 修改参数：
  - 无
- 删除参数：
  - 无

## 回测/归因参数

- 数据区间：`2020-01-02` 到 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：沿用 C3 真实回测口径，总滑点 `1,556,750`，手续费为 0
- 样本过滤：固定 C3，不改 AI 池、品种池、入场 alpha 和供需强逆风过滤
- 策略/归因口径：
  - A：`C3_supply_headwind`
  - C：`C3_supply_headwind + 上一交易日保证金/持仓广度日级风险覆盖层`
  - 本阶段覆盖层是日收益级边界探针，不是可直接实盘的真实引擎版本

## 结果

- C3 原始结果：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.3663`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- 覆盖层全样本结果：

| 版本 | 总收益 | 收益保留 | 最大回撤 | Sharpe | 降暴露天数 | 是否通过 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A_c3_no_overlay | 6092.8091% | 100.0000% | -31.0767% | 1.6173 | 0 | 否 |
| C_active_products_6_8_floor085 | 6084.4870% | 99.8634% | -30.6795% | 1.6177 | 9 | 否 |
| C_margin_review80_floor075 | 5908.2149% | 96.9703% | -30.9059% | 1.6243 | 20 | 否 |
| C_margin_soft_70_90_floor080 | 5941.4323% | 97.5155% | -30.9694% | 1.6173 | 37 | 否 |
| C_margin_soft_60_80_floor085 | 5939.2163% | 97.4791% | -31.6517% | 1.6105 | 79 | 否 |
| C_margin80_active7_floor080 | 6092.8091% | 100.0000% | -31.0767% | 1.6173 | 0 | 否 |

- 其他关键指标：
  - C3 最大保证金/权益：`103.7672%`
  - P95 保证金/权益：`60.2739%`
  - 60%观察线天数：`79`
  - 80%复核线天数：`20`
  - 100%拒绝线天数：`2`
  - 最大回撤窗口：`2021-05-12` 到 `2021-07-02`
  - 最大回撤谷底保证金/权益：`23.7855%`
  - 最大回撤谷底持仓品种：`1`
  - 最大回撤谷底持仓合约：`1`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_report_stage327_c3_margin_concentration_overlay_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_summary_stage327_c3_margin_concentration_overlay_probe_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_daily_state_stage327_c3_margin_concentration_overlay_probe_v1.csv`
- overlay_paths：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_overlay_paths_stage327_c3_margin_concentration_overlay_probe_v1.csv`
- bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_bucket_attribution_stage327_c3_margin_concentration_overlay_probe_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage327_c3_margin_concentration_overlay_probe_decision_stage327_c3_margin_concentration_overlay_probe_v1.json`

## 结论

- 本阶段结论：
  - 预声明的保证金/持仓广度覆盖层没有在全样本同时满足 `最大回撤30以内 + C3收益保留80%`。
  - 最接近的是 `C_active_products_6_8_floor085`：收益保留 `99.8634%`，最大回撤 `-30.6795%`，仍未过线。
  - 更关键的是，C3 最大回撤谷底并非高保证金或多品种拥挤状态，而是低保证金、单品种路径亏损；因此“保证金拥挤闸门”不是解决剩余 `-31.08%` 回撤的本质钥匙。
- 是否进入下一步：不沿着保证金/持仓广度小数阈值继续。
- 下一步：
  - 转向 C3 单品种/单合约路径风险的状态识别，例如趋势成熟度、跳空/反转波动状态、开平仓后 MAE 分布，或者寻找真正能覆盖单品种路径亏损的独立收益源。
  - 若继续账户层，只能做“波动状态/趋势反转状态”这类一阶风险，不再调保证金阈值。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段不是过拟合；继续调保证金/持仓品种阈值会过拟合。
- 原因：
  - 本阶段只使用上一交易日可知的账户状态，阈值来自既有SOP粗线或整数持仓广度。
  - 结果显示最大回撤不发生在高保证金/多品种拥挤状态，继续把 60/80 改成 63/77 是对历史路径的拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：研究线仍有价值，但本具体分支继续价值低。
- 原因：
  - C3 距离30%目标只差约 1.08 个百分点，检查账户状态是必要反证。
  - 反证后可排除一条看似合理但非本质的路径，后续应转向单品种路径风险或更独立收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage027 反证。
- 是否更新 `research/registry.md`：是，最新阶段从 Stage026 更新为 Stage027。
- 是否追加根目录 `memory.md/back_log.md`：是，本阶段改变后续研究方向，需追加摘要。
