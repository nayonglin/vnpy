# Stage400 - 正式版 Stage372 打开做空 case1a/2/3 影子分支

- 记录时间：2026-06-07 13:48 CST
- line_id：`futures_trend_drawdown30_preserve_return`
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage687_official_stage372_short_cases123.py`
- 输出前缀：`qmt_roll_stage687_official_stage372_short_cases123_*_stage687_official_stage372_short_cases123_v1`
- 是否重要突破版本：否
- 决策：`official_stage372_short_cases123_rejected_keep_official_short_case1a`

## 本次目的

用户要求在当前正式版本上再起一条新分支，把做空的几个 case 都打开，回测看看。本阶段以当前正式实盘默认 `official_live_stage372_20w_recovery_sleeve` 为 A，新增 C 分支只修改 fresh short entry 白名单：从仅允许 `short_case1a` 改为允许 `short_case1a/short_case2/short_case3`。

运行前反思：不是典型过拟合，因为这是一个低自由度、结构性问题：空头入口是否过窄。继续价值为“有”，因为它能直接回答正式版是否应该扩大空头入口。但如果失败后继续扫 `case2 only/case3 only/年份/品种/月度`，就会转为明显过拟合。

## 外部调研与判断

外部资料显示，趋势跟踪和 managed futures 的通用框架确实支持跨市场、可多可空暴露；AQR `Trends Everywhere` 强调在更多市场和 long-short 因子上检验趋势，`A Century of Evidence on Trend-Following Investing` 也描述趋势跟随按过去收益决定多空方向。因此，“做空不是原则上不该做”。

我的判断：这些资料支持的是“多空趋势暴露的方向”，不支持把仓库内部所有 short case 不经账户路径验证直接放入正式版。正式版的关键约束是 20万资金、最大并发4、恢复仓 sleeve、强制减仓、成本压力和右尾复利路径；所以必须用 A/C 账户级回测决策。

## 改动内容

新增参数：

- `ALLOWED_SHORT_SIGNALS={short_case1a,short_case2,short_case3}`
- `TARGET_VARIANT=stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_short_cases123`
- Stage687 输出 `summary/cost_stress/comparison/annual/monthly/daily/positions/product/trade_usage/forced_events/forced_summary/report/decision/chart`

修改参数：

- 仅在 Stage687 运行期 monkeypatch `_can_open_short_signal()`：`signal == "short_case1a"` 改为 `signal in {short_case1a,short_case2,short_case3}`

删除参数：

- 无。

未改内容：

- 不修改 `qmt_roll_official_live_config.py`
- 不修改正式实盘默认 `OFFICIAL_LIVE_VERSION`
- 不改 AI 选品池、20万资金、force95->80、recovery sleeve、product cap25、`max_concurrent_positions=4`
- 不连接 CTP，不调用下单 API

## 回测结果

A 当前正式版 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`：

- 期末权益：`8,728,285`
- 总收益：`4264.1425%`
- CAGR：`81.6752%`
- 最大回撤：`-38.6713%`
- Sharpe：`1.6279`
- 总滑点：`506,220`
- 总交易次数：`633`
- 胜率：`52.2586%`
- broker10 峰值：`79.6015%`
- broker10 p95：`55.0005%`
- 强制减仓：`6` 次，合计 `299` 手，最大观察比例 `119.7845%`
- 2x/3x 成本最大回撤：`-40.6555%/-42.7649%`

C 新分支 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_short_cases123`：

- 期末权益：`1,652,090`
- 总收益：`726.0450%`
- CAGR：`39.6348%`
- 最大回撤：`-35.6432%`
- Sharpe：`1.1027`
- 总滑点：`184,880`
- 总交易次数：`805`
- 胜率：`51.0791%`
- broker10 峰值：`68.9566%`
- broker10 p95：`48.9393%`
- 强制减仓：`16` 次，合计 `343` 手，最大观察比例 `142.2293%`
- 2x/3x 成本最大回撤：`-38.4146%/-41.7797%`
- 相对正式版收益保留：`17.0268%`

对比：

- 期末权益差：`-7,076,195`
- 总收益差：`-3538.0975pp`
- 最大回撤改善：`+3.0282pp`
- Sharpe 差：`-0.5251`
- 交易次数差：`+172`
- 胜率差：`-1.1795pp`
- broker10 峰值改善：`-10.6449pp`
- 强制减仓次数增加：`+10`
- 强制减仓手数增加：`+44`

## 分年结果

正式版年度 PnL：

- 2020：`+144,230`
- 2021：`+717,550`
- 2022：`+171,455`
- 2023：`+1,205,895`
- 2024：`+961,295`
- 2025：`+4,558,225`
- 2026截至4月：`+883,065`

新分支年度 PnL：

- 2020：`+75,900`
- 2021：`+11,270`
- 2022：`+94,145`
- 2023：`+124,535`
- 2024：`+311,955`
- 2025：`+958,685`
- 2026截至4月：`-144,005`

## 归因判断

新增分支确实增加交易次数，`633 -> 805`，所以不是“没打开机会”。问题是新增 short_case2/3 改变了账户路径和风险槽分配：正常回撤略浅、资金占用略低，但核心右尾复利被大幅削弱。正式版主要盈利品种如 `jm +3,149,700`、`oi +1,398,720`、`lc +562,760`、`au +545,060`、`ru +432,250` 在新分支中显著收缩或转负；新分支还把强制减仓从 `6` 次推高到 `16` 次，最大强制前比例升到 `142.2293%`。

这说明 short_case2/3 不是简单“多出来的免费 alpha”，而是在当前 20万、maxpos4、恢复仓和强制减仓体系下，提前消耗了风险槽、改变了复利路径，并压制原正式版最重要的右尾持仓。

## 过拟合反思

运行后判断：本次单点结构检验不是过拟合，但结果反而提示“继续救这个方向”很容易过拟合。因为它只带来约 `3.03pp` 的最大回撤改善，却牺牲 `3538.10pp` 总收益和 `0.5251` Sharpe，还让 2026 变成负收益。若继续通过 `case2 only/case3 only/品种/年份/月度` 找补，基本是在事后挑历史路径。

## 继续价值反思

直接把 short_case2/3 合入正式版：无继续价值。

机制归因：有价值，但只应做只读归因，例如拆出 short_case2/3 是如何挤掉 `jm/OI/lc/au/ru` 的右尾、哪些入场触发了更早强制减仓、是否存在账户级风险槽冲突。不要把它推进成正式 A/B。

## 后续 TODO

- 不推广 Stage400，不修改正式版，正式版继续只允许 fresh short `short_case1a`。
- 若用户要求继续，只做只读归因：short_case2/3 与旧右尾品种的持仓冲突、强制减仓触发链、年度窗口损失来源。
- 不扫 `case2 only/case3 only`、月份、品种、年份过滤或小数风险参数。
