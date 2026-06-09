# Stage411 Stage407 0手补最小参与仓反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 12:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：连败风控结构归因 / 0手补仓机制 A/C 反证
- 是否重要突破：否，关键负结果
- 是否触发A/B：是，风险 sizing 机制可能影响正式版；按 A/C 隔离评估

## 外部调研与判断

- 参考资料：
  - Man Group：Trend following market mix，趋势跟踪收益依赖跨市场右尾捕捉，市场组合变化会改变右尾效率。
  - AQR：Trend Following / Understanding Managed Futures，趋势跟踪风控应偏向通用风险预算和多市场分散，不应围绕单个历史窗口补丁化。
  - 公开 fixed-fractional / ATR sizing 资料：期货手数一般按账户风险预算除以止损距离计算，但整数合约会产生“理论风险预算小于一手”的离散问题。
- 我的判断：Stage409/410 说明抬高所有三连败风险会伤害全周期；因此本阶段只针对用户真正指出的问题，验证“风险预算算出 0 手但保证金允许”时补最小参与仓，避免放大已有非零仓位。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage698_stage407_zero_volume_min_one.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MIN_ONE_BROKER_MARGIN_MULTIPLIER=1.65`
  - `MIN_ONE_MAX_SINGLE_CONTRACT_BROKER_MARGIN_TO_EQUITY=0.20`
- 修改参数：无，保留 `streak_risk_multipliers=1.0,1.0,1.0,0.1`
- 删除参数：无
- 补仓硬条件：`entry_context=flat_entry`、`selected_volume=0`、`sizing_method=risk_budget`、`contracts_by_risk=0`、`contracts_by_margin>=1`、`contracts_by_single_trade_cap>=1`、风险簇允许、`risk_multiplier<=0.1`、单手 broker 保证金估算不超过权益 `20%`。

## 回测/归因参数

- 数据区间：沿用 Stage407 口径，`2020-01-01` 至仓库当前期货数据末端。
- 账户规模：`200,000`
- 成本口径：正常滑点成本，并输出 2x/3x 成本压力。
- 样本过滤：不重新训练、不改正式 AI 训练过程；Stage407 口径为原正式 AI 池 + `jd.DCE` 参与 AI 重排 `top9`，`maxpos5`。
- 策略/归因口径：
  - A：当前正式 Stage372/20w `maxpos4`，原连败倍率 `1,1,1,0.1`。
  - D：A 仅加 0手补最小参与仓规则。
  - B：Stage407 基线，原正式 AI 池 + `jd.DCE` 参与 AI 重排 top9，`maxpos5`，原连败倍率。
  - C：B 仅加 0手补最小参与仓规则。

## 结果

- A 正式版原版：期末权益 `8,728,285`，总收益 `4264.1425%`，最大回撤 `-38.6713%`，Sharpe `1.6279`，总滑点 `506,220`，总交易次数 `633`，胜率 `52.2586%`，broker10 峰值 `79.6015%`，强制减仓 `6` 次 `299` 手，`deployable_pass=1`。
- D 正式版 0手补1手：期末权益 `6,901,460`，总收益 `3350.7300%`，最大回撤 `-37.9921%`，Sharpe `1.5142`，总滑点 `424,890`，总交易次数 `666`，胜率 `52.1589%`，broker10 峰值 `80.6265%`，强制减仓 `8` 次 `368` 手，`deployable_pass=1`。
- B Stage407 原版：期末权益 `3,284,935`，总收益 `1542.4675%`，最大回撤 `-33.2821%`，Sharpe `1.3858`，总滑点 `298,030`，总交易次数 `688`，胜率 `51.7181%`，broker10 峰值 `82.6211%`，强制减仓 `14` 次 `361` 手，`deployable_pass=1`。
- C Stage407 0手补1手：期末权益 `2,643,000`，总收益 `1221.5000%`，最大回撤 `-34.1149%`，Sharpe `1.2766`，总滑点 `254,030`，总交易次数 `717`，胜率 `51.7749%`，broker10 峰值 `73.5834%`，强制减仓 `12` 次 `248` 手，`deployable_pass=1`。
- C 相对 B：交易 `+29`，但期末权益 `-641,935`，收益 `-320.9675pp`，最大回撤 `-0.8328pp`，Sharpe `-0.1092`。
- D 相对 A：交易 `+33`，但期末权益 `-1,826,825`，收益 `-913.4125pp`，Sharpe `-0.1136`，强制减仓次数 `+2`、手数 `+69`。
- 红框窗口 `2025-04-16` 至 `2025-07-25`：A 增长 `+5,605,230`，D 增长 `+4,435,560`，B 增长 `+90,830`，C 只有 `+65,650`，C 相对 B 还少 `25,180`。
- 0手补仓命中情况：正式 D 全周期 inferred 补仓 `24` 个，其中 `23` 个发生在三连败后；Stage407 C 全周期 inferred 补仓 `25` 个，其中 `24` 个发生在三连败后。但红框窗口 inferred 补仓为 `0`，说明红框问题不是“0手开不出来”，而是已经开了但仓位偏小且右尾品种被挤出。
- Stage407 红框已开仓中位 `selected_volume` 从 B 的 `17` 降到 C 的 `13.5`，窗口 selected volume sum 从 `295` 降到 `238`，因为补仓改变早期路径后权益底座反而更低。
- 品种归因：C 相对 B 改善很小，`lc +30,200`、`sa +26,520`、`sp +14,920`；恶化集中在 `jm -182,970`、`oi -178,520`、`rb -79,910`、`ap -63,130`、`ru -50,350`、`au -46,920`、`lh -40,960`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_report_stage698_stage407_zero_volume_min_one_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_summary_stage698_stage407_zero_volume_min_one_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_daily_stage698_stage407_zero_volume_min_one_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_positions_stage698_stage407_zero_volume_min_one_v1.csv`
- entry_risk_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_entry_risk_summary_stage698_stage407_zero_volume_min_one_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_equity_only_stage698_stage407_zero_volume_min_one_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage698_stage407_zero_volume_min_one_decision_stage698_stage407_zero_volume_min_one_v1.json`

## 结论

- 本阶段结论：`stage407_zero_volume_min_one_not_promoted`。0手补最小参与仓确实命中了“风险预算不够一手但保证金允许”的离散问题，但补到的是全周期其他位置，不是用户图里红框缺口；红框增长缺失的主因仍是 AI 重排挤掉 `fu/jm/si/lc/fg` 右尾和已有仓位被 0.1 档压小。
- 是否进入下一步：本形态不进入下一步。
- 下一步：停止沿主账户连败风控做“补1手/抬底线/扫倍率”。如果继续解决鸡蛋方向，应回到非挤占式结构：原正式 AI 池不被鸡蛋替换，鸡蛋只做独立小 sleeve 或独立风险预算；若继续连败机制，只做只读审计，不再调小数。

## 过拟合反思

- 运行前判断：否。本阶段是结构性单点验证，只针对风险预算 0 手的离散问题，不按红框窗口、品种或年份过滤。
- 运行后判断：继续救本形态会过拟合。
- 原因：机制确实增加交易次数，但没有修复目标窗口，并对正式版和 Stage407 全周期都伤害收益；后续若加上月份、品种、信号类型过滤，就是用历史亏损位置反向打补丁。

## 继续价值反思

- 运行前判断：有价值。它是比 Stage409/410 更贴近用户问题、自由度更低的测试。
- 运行后判断：主账户连败风控修复路线继续价值很低。
- 原因：Stage409/410/411 三个结构都证明，问题不只是连败 0.1 本身，而是 AI 重排破坏原右尾后，账户路径变弱，任何简单补仓都无法把红框右尾恢复回来。

## 合入建议

- 是否更新本线 `LINE.md`：是，登记 Stage411 为负结果。
- 是否更新 `research/registry.md`：否，本次不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：是，登记长期反证与后续研究边界。
