# Stage398 Stage397 0.01 版本改用 MA20 初始止损手数计算并关闭二日止损

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-07 10:34 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：结构性消融 / 有价值候选线索，不是正式晋级
- 是否重要突破：否；这是 Stage397 失败分支上的显著修复线索，但两个变量同时改变，不能直接推广
- 是否触发A/B：已按 A/B 纪律读取 `skills/version-ab-experiment/SKILL.md`；暂不进入正式 A/B，先做拆变量归因

## 外部调研与判断

- 参考资料：在线检索了 `trend following position sizing initial stop moving average 20 day`、`GitHub trend following moving average stop position sizing initial stop`、`turtle trading position sizing stop distance risk per trade trend following`。
- 我的判断：趋势跟踪里用止损距离做 fixed-fractional 手数计算是通用原则；把初始止损从最近几日极值换成 MA20 是低自由度、可解释的结构改法。它比继续扫 `0.0075/0.0125` 更不容易沦为小数过拟合。但 MA20 窗口本身仍有参数自由度，本阶段只能固定 `20` 做一次验证，不能继续扫 `10/15/30/40`。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day.py`
- 修改脚本：无正式策略脚本修改；仅在 Stage685 运行期 monkeypatch 初始止损函数和空头 case 函数
- 删除脚本：无
- 新增参数：
  - `MA_STOP_WINDOW=20`
  - `TARGET_TRADE_RISK_RATIO=0.01`
  - `TARGET_VARIANT=stage372_500k_trade_risk001_no_ai_plus25_jd_v_short_cases123_no_loss_streak_ma20stop_no_prev2day_maxpos25`
- 修改参数：
  - 手数计算的初始止损距离：优先用 MA20，做多要求 `MA20 < close`，做空要求 `MA20 > close`；不满足时回落到原始 `_entry_stop_price`
  - `enable_prev2day_stop=False`
  - `enable_profit_lock_trend_relaxed_prev2day_stop=False`
  - `streak_risk_multipliers=1.0,1.0,1.0,1.0`
- 删除参数：无；只是关闭前述二日止损相关退出开关

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：原始滑点成本，并追加 `2x/3x` 成本压力
- 样本过滤：plus25 含 `ni.SHFE/ag.SHFE/sc.INE/p.DCE/jd.DCE/v.DCE`，关闭 AI product pool filter，允许 `short_case1a/short_case2/short_case3`
- 策略/归因口径：基于 Stage397 `risk_ratio_*=0.01 + no-loss-streak + maxpos25`，只改 MA20 初始止损手数计算并关闭二日止损

## 结果

- 期末权益：`773,225`
- 总收益：`54.6450%`
- 最大回撤：`-23.1270%`
- Sharpe：`0.4977`
- 总滑点：`84,170`
- 总交易次数：`1,579`
- 胜率：`52.2083%`
- 资金占用：broker10 峰值 `55.4431%`，p95 `34.2729%`，`>90%/>100%` 天数 `0/0`
- 成本压力：2x 成本 `689,055/37.8110%/-25.9753%/Sharpe0.3794`；3x 成本 `604,885/20.9770%/-29.0249%/Sharpe0.2588`
- 年度：
  - 2020：`+170,290`，`+34.0580%`，最大回撤 `-17.4021%`
  - 2021：`-365`，`-0.0545%`，最大回撤 `-21.8518%`
  - 2022：`+8,230`，`+1.2285%`，最大回撤 `-18.7212%`
  - 2023：`-1,885`，`-0.2780%`，最大回撤 `-14.0373%`
  - 2024：`+42,685`，`+6.3118%`，最大回撤 `-6.1633%`
  - 2025：`+103,865`，`+14.4467%`，最大回撤 `-11.3888%`
  - 2026截至4月：`-49,595`，`-6.0274%`，最大回撤 `-9.3194%`
- 候选状态：`opened=726`，`sizing_zero_volume=387`，`supply_demand_headwind_blocked=164`
- 手数约束：打开候选中 `risk` 约束 `720` 个，`margin` 约束 `2` 个，`single_trade_cap` 约束 `3` 个
- 初始止损距离诊断：entry risk 记录 `791` 条，中位 stop distance `139.5`，中位 risk_per_contract `1,403.75`，中位 actual risk amount `3,499`，中位 selected_volume `2`

## 对照

- 相对 Stage397 `0.01 + 原初始止损 + prev2day`：
  - 期末权益 `613,860 -> 773,225`，增加 `159,365`
  - 总收益 `22.7720% -> 54.6450%`，增加 `31.873pp`
  - 最大回撤 `-40.1898% -> -23.1270%`，改善 `17.0628pp`
  - Sharpe `0.2692 -> 0.4977`
  - 滑点 `104,850 -> 84,170`，减少 `20,680`
  - 交易 `1,767 -> 1,579`，减少 `188`
  - 2x/3x 成本 DD 从 `-48.5104%/-58.0307%` 改善到 `-25.9753%/-29.0249%`
- 相对 Stage396 `0.005 + 原初始止损 + prev2day`：
  - 期末权益少 `78,340`
  - 总收益少 `15.668pp`
  - 最大回撤差 `-1.4324pp`
  - Sharpe 少 `0.0964`
  - 滑点少 `14,170`，交易少 `108`
- 相对 Stage393 C2：
  - 期末权益少 `755,480`
  - 总收益少 `151.096pp`
  - 最大回撤改善 `19.7442pp`
  - Sharpe 少 `0.2160`
  - 滑点少 `189,610`，交易少 `433`

## 品种归因

- 本版本净贡献较好：`au +132,020`、`fg +129,760`、`sp +50,680`、`sh +45,420`、`fu +44,050`、`v +37,315`、`lc +36,670`、`ru +19,700`、`hc +17,010`
- 主要拖累：`sm -45,840`、`p -41,020`、`jd -38,370`、`cf -36,650`、`ag -32,475`、`rb -28,270`、`si -15,725`
- 相对 Stage397 改善最大：`au +173,440`、`ma +70,060`、`v +55,675`、`sp +43,520`、`ru +39,200`、`fu +37,770`、`hc +37,100`
- 相对 Stage397 恶化最大：`ap -93,280`、`oi -82,370`、`lh -80,560`、`p -28,800`、`jd -25,540`、`rb -25,380`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day_report_stage685_stage397_ma20_initial_stop_no_prev2day_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day_summary_stage685_stage397_ma20_initial_stop_no_prev2day_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day_cost_stress_stage685_stage397_ma20_initial_stop_no_prev2day_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day_curves_stage685_stage397_ma20_initial_stop_no_prev2day_v1.csv`
- daily/annual/monthly：`annual` 与 `monthly` CSV 已输出
- positions/orders quality：`positions`、`entry_candidates`、`entry_risk`、`risk_breakdown`、`stop_distance` 已输出
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage685_stage397_ma20_initial_stop_no_prev2day_chart_stage685_stage397_ma20_initial_stop_no_prev2day_v1.png`

## 结论

- 本阶段结论：MA20 初始止损手数计算 + 关闭 prev2day，能把 Stage397 的失败路径明显修复，尤其回撤和成本压力改善很大；但它不是“更多机会”版本，交易次数从 `1,767` 降到 `1,579`，本质是更换了风险距离和退出结构后过滤/缩小了劣质敞口。
- 是否进入下一步：进入拆变量归因，不进入正式版，不进入完整 A/B。
- 下一步：
  - A：只改 MA20 初始止损手数计算，保留 prev2day 止损。
  - B：只关闭 prev2day 止损，保留原最近几日初始止损手数计算。
  - C：若 A 是主要贡献，再固定 MA20 不扫窗口，做冷启动/弱窗口/成本压力/品种贡献复验；若 B 是主要贡献，则复盘 prev2day 退出是否过早砍掉右尾，而不是继续调二日/三日。

## 过拟合反思

- 运行前判断：有过拟合风险，但低于继续扫风险小数；原因是用户指定的是通用风险距离改法，且 MA20 是固定低自由度结构。
- 运行后判断：暂不能判定为过拟合，但也不能直接晋级；原因是结果改善覆盖收益、回撤、成本压力和胜率，但两个变量同时改变，无法知道主贡献来自 MA20 sizing 还是关闭 prev2day。
- 原因：如果现在直接推广，就会把“初始止损距离”和“动态退出规则”混在一起记功，属于归因不清；正确做法是拆开后再看路径是否稳定。

## 继续价值反思

- 运行前判断：有价值；它是在 Stage397 失败后从手数计算原理入手，而不是继续小数调参。
- 运行后判断：有继续价值，但只限拆变量和稳健性复验。
- 原因：它把 `0.01` 分支从 `deployable_pass=0` 修到 `deployable_pass=1`，但收益仍低于 Stage396 和 Stage393 C2，年度 2021/2023/2026 仍弱，不能作为正式替换。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage398 摘要。
- 是否更新 `research/registry.md`：否，本线未新增或迁移。
- 是否追加根目录 `memory.md/back_log.md`：是，作为 Stage397 后的重要结构线索追加摘要。
