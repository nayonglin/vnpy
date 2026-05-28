# Stage108 Stage079 xsmom多空腿不对称审计

- 时间：2026-05-27 20:40 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 阶段性质：结构拆解；固定 Stage103 `0.5/10%/63日/broker10_guard`，只拆 xsmom 卫星多头腿与空头腿。
- 是否重要突破版本：否。发现 `short_only` 是 Stage079 口径下的合格次级候选，但它被 Stage103 多空双边支配；`long_only` 直接打穿30回撤和滚动闸门。
- 是否触发 A/B/C：是。A=`Stage079`；C0=`Stage103 xsmom多空双边`；C1=`xsmom只保留多头腿`；C2=`xsmom只保留空头腿`。
- 本次脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage408_stage079_xsmom_leg_asymmetry_audit.py`
- 输出报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage408_stage079_xsmom_leg_asymmetry_audit_report_stage408_stage079_xsmom_leg_asymmetry_audit_v1.md`
- 输出图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage408_stage079_xsmom_leg_asymmetry_audit_chart_stage408_stage079_xsmom_leg_asymmetry_audit_v1.png`

## 开始前反思

- 是否在过拟合：否。Stage108 没有调阈值、窗口、品种、月份或资金数额，只按动量 crash 文献中“短腿反弹风险”和多空腿风险来源的结构问题做拆解。
- 是否仍有价值继续做：是。Stage103 已是最强执行相对候选，但仍未达成全部理想3/6个月目标；拆腿能判断剩余风险主要来自多头腿还是空头腿，避免后续误救。

## 外部调研和判断

- 调研来源：
  - Daniel 与 Moskowitz 的 Momentum Crashes 研究指出，动量策略在特定状态下会发生崩盘，且左尾风险与赢家/输家腿的反转有关。
  - NBER `Momentum Trading, Return Chasing, and Predictable Crashes` 讨论了动量拥挤和可预测崩盘风险。
  - GitHub 上 `pysystemtrade`、`PyTrendFollow` 等系统化期货框架强调多市场趋势、风险预算和稳健组合构建，而不是事后窗口补丁。
- 调研判断：拆多空腿是合理的结构审计，不是曲线拟合；但如果某一腿失败，不能继续用日期、单品种或相邻参数补救。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage408_stage079_xsmom_leg_asymmetry_audit.py`
- 新增参数：
  - `xsmom_vt10_q_momq_long_only_round_half_broker10_guard`：固定 Stage103 规则，只保留 xsmom 多头腿。
  - `xsmom_vt10_q_momq_short_only_round_half_broker10_guard`：固定 Stage103 规则，只保留 xsmom 空头腿。
- 修改参数：无。未修改 `scale>=0.5`、`target_vol=10%`、`63日`、`1.10` 保证金闸门。
- 删除参数：无正式策略默认修改；仅在审计候选中删除一侧 xsmom 腿。

## 回测结果

Stage079：期末权益 `31,040,650`，总收益 `4947.2602%`，最大回撤 `-29.7007%`，Sharpe `1.3188`，Ulcer `15.0874`，总滑点 `1,556,750`，总交易次数 `757`，胜率 `45.3826%`。

Stage103 `broker10_guard`：期末权益 `31,730,915`，总收益 `5059.4984%`，最大回撤 `-28.9792%`，Sharpe `1.3681`，Ulcer `14.3132`，3个月分 `121.2041`，6个月分 `134.4513`，总滑点 `1,569,265`，总交易次数约 `1217`。

`long_only`：期末权益 `31,284,665`，总收益 `5005.6366%`，最大回撤 `-30.2223%`，Sharpe `1.3322`，Ulcer `14.9166`，3个月分 `105.3457`，6个月分 `114.2634`。失败项：全周期最大回撤深于30，252/504日滚动破30率 `0.0981/0.2511`，年度/季度回撤30内通过率仅 `80.00%/77.27%`，`start_2022` 回撤 `-31.1678%`。决策：淘汰。

`short_only`：期末权益 `31,256,900`，总收益 `5001.1220%`，最大回撤 `-28.7881%`，Sharpe `1.3555`，Ulcer `14.4485`，3个月分 `114.6444`，6个月分 `119.8979`，用户目标8项改善 `6/8` 与 `6/8`，多起点冷启动全部过30，成本压力不差于 Stage079。

`short_only` 的弱点：相对 Stage103，它总收益低 `58.3764pp`，Sharpe 低，Ulcer 高，3个月/6个月体验分低，且 `2x/3x` 成本压力不如 Stage103；因此 `stage103_relative_promotion_pass=0`。

卫星腿归因：

- Stage103 多空双边：卫星PnL `690,265`，滑点 `12,515`，换手 `460` 手，最大卫星保证金 `161,674`。
- `long_only`：卫星PnL `359,015`，滑点 `5,605`，换手 `236` 手，最大卫星保证金 `140,822`，但路径左尾明显更差。
- `short_only`：卫星PnL `331,250`，滑点 `6,910`，换手 `224` 手，最大卫星保证金 `84,510`，路径比 long_only 稳，但总收益和体验不如多空双边。

## 结论

- 决策：`no_new_primary_promotion`。Stage103 仍是当前最强主候选。
- `short_only` 可以标记为 Stage079 的次级合格备选：它通过 Stage079 硬闸门和3/6个月提升闸门，且最大卫星保证金显著低于 Stage103。
- 但我不建议把 `short_only` 升为主版本，因为它被 Stage103 支配：收益、Sharpe、Ulcer、短持有综合分均更弱。
- 最重要的新知识：xsmom 多头腿单独承载会放大 `start_2022/weak_2021` 风险，不能作为简化方向；Stage103 的多空双边并不是多余复杂度，而是在收益与路径稳定之间形成了更好的结构平衡。

## 后续规划和 TODO

1. 不继续拆腿比例、小数权重或“多头减半/空头加倍”等连续比例扫描。
2. `short_only` 只保留为低保证金、低复杂度备选知识，不替代 Stage103。
3. 继续主线时优先做 Stage103 工程化复跑、paper/影子盘与真实券商保证金接入；若继续寻找理想3/6个月目标，必须换真正不同的风险暴露，不再围绕 xsmom 腿比例救援。

## 结束后反思

- 是否在过拟合：不是。失败后没有继续补比例、日期、品种或阈值。
- 是否还有价值继续做：拆腿子路线继续价值低；总目标仍有价值，但 Stage103 已经接近当前可执行边界，继续优化必须引入更不同的外生/跨资产状态暴露。
