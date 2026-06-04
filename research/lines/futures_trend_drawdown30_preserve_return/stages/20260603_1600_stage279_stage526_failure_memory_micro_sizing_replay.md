# Stage279 Stage526失败记忆轻量加仓真实引擎重放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 16:00 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/B paper 探针；真实引擎重放；默认关闭的新 sizing 规则。
- 是否重要突破：否。收益提高但路径风险劣化，不晋级。
- 是否触发A/B：是。该规则若有效可能接入 Stage526/第78体系，因此已按 `skills/version-ab-experiment/SKILL.md` 预声明 A/C、闸门和停止条件。

## 外部调研与判断

- 参考资料：
  - Clare et al. trend following / stop-loss caveat：`https://link.springer.com/article/10.1057/jam.2013.11`
  - pysystemtrade position sizing architecture：`https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization`
  - Concretum trend-following position sizing comparison：`https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/`
  - Davidsson position sizing / trend following risk management：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2248261`
- 我的判断：
  - 趋势策略里用状态调整仓位是合理方向，但“连续失败后加一点风险”本质上接近轻量逆向加仓/赌趋势终会出现，必须非常克制。
  - Stage262 显示同品种同方向连续失败后胜率和中位收益更好，所以值得做一次冻结真实引擎 replay。
  - 如果本次失败后继续扫 `>=1/>=2/>=3`、`1.05/1.10/1.20`、品种名单或弱窗口，就会变成过拟合。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay.py`
- 修改策略脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - 新增默认关闭参数：
    - `enable_failure_memory_micro_sizing=False`
    - `failure_memory_micro_sizing_lookback_days=252`
    - `failure_memory_micro_sizing_min_consecutive_failures=2`
    - `failure_memory_micro_sizing_multiplier=1.10`
    - `failure_memory_micro_sizing_entry_contexts="flat_entry"`
  - 新增候选快照字段，记录是否触发、连续失败次数、上次失败日期、基础/生效风险倍率。
  - 仅在开启该参数时记录并使用同品种同方向历史 outcome；默认关闭时不应影响基准。
- 删除脚本：无。
- 新增交易参数：如上，仅作为 default-off paper 探针。
- 修改参数：无既有 Stage526 默认参数被主动修改。
- 删除参数：无。

## 预声明 A/C

- A：`stage526_control`，即 Stage526 `r080_pc25_maxpos4` 控制组，不启用失败记忆。
- C：`stage526_failure_memory_micro_sizing`，即 A + 同品种同方向连续失败 `>=2` 后，仅 `flat_entry` 的风险乘数 `*1.10`。
- 固定 lookback：`252` 日。
- 固定 entry context：`flat_entry`。
- 不做阈值扫描、倍率扫描、产品名单筛选、弱窗口补丁。
- 硬闸门：
  - 总收益不劣化。
  - 最大回撤不劣化。
  - Ulcer 不劣化。
  - Sharpe 不劣化。
  - broker10 最大保证金/权益不劣化。
  - 2x/3x 成本最大回撤不劣化。
  - 63/126 日持有体验左尾不劣化。
  - 触发样本存在。

## 回测参数

- 引擎：Stage517/Stage526 同源真实组合引擎，下一真实窗口/真实价格链路沿用当前工作区实现。
- 数据区间：`2020-01-01` 至 `2026-04-30`。
- 初始资金：`615,000` 账户口径。
- 成本口径：正常成本主审计，同时重构 `2x/3x` 成本压力。
- 组合结构：Stage526 control + frozen xsmom carry 组合口径。
- 账户风险基准：`risk_multiplier=0.80`、单产品 cap25、最大活跃产品 4、broker10 exact margin。

## 结果

- 决策：`failure_memory_micro_sizing_no_promotion`
- 闸门：`3/10` 通过。
- 触发样本：候选实际开仓触发 `45` 次。

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 3x成本DD | 63日p05 | 126日p05 | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A Stage526 control | `24,599,320` | `3899.8894%` | `-36.2670%` | `14.4436` | `1.6575` | `99.7299%` | `-42.0555%` | `-18.2169%` | `-10.9700%` | `1,394,500` | `905` | `53.5581%` |
| C failure-memory micro | `25,908,640` | `4112.7870%` | `-37.2060%` | `14.6377` | `1.6616` | `99.8350%` | `-43.0981%` | `-19.1283%` | `-11.7349%` | `1,471,380` | `905` | `53.4082%` |

## 闸门明细

- 通过：
  - 总收益不劣化：`4112.7870% > 3899.8894%`
  - Sharpe 不劣化：`1.6616 > 1.6575`
  - 触发样本存在：`45`
- 失败：
  - 最大回撤：`-37.2060%` 劣于 `-36.2670%`
  - Ulcer：`14.6377` 劣于 `14.4436`
  - broker10 最大保证金/权益：`99.8350%` 劣于 `99.7299%`
  - 2x 成本最大回撤：`-40.0453%` 劣于 `-39.0565%`
  - 3x 成本最大回撤：`-43.0981%` 劣于 `-42.0555%`
  - 63日 p05：`-19.1283%` 劣于 `-18.2169%`
  - 126日 p05：`-11.7349%` 劣于 `-10.9700%`

## 触发分布

- 主要触发产品/方向：
  - `MA.CZCE long`：`9`
  - `SM.CZCE long`：`5`
  - `cu.SHFE long`：`4`
  - `AP.CZCE long`、`SA.CZCE long`、`fu.SHFE long`、`jm.DCE long`、`lh.DCE long`、`rb.SHFE long`、`ru.SHFE long`：各 `3`
- 解释：
  - 失败记忆的确在部分产品上抓到后续趋势收益。
  - 但它把账户在原本已脆弱的时段进一步加杠杆，导致水下曲线和高成本压力变差。

## 控制组漂移说明

- 本阶段发现当前工作区重跑的 A 控制组与旧 Stage526 权威输出在总收益/滑点上不完全一致：
  - 旧 Stage526 权威文件：期末权益 `23,369,505`、总收益 `3699.9195%`、最大回撤 `-36.2670%`、总滑点 `1,342,190`、交易 `905`。
  - Stage577 当前工作区 A：期末权益 `24,599,320`、总收益 `3899.8894%`、最大回撤 `-36.2670%`、总滑点 `1,394,500`、交易 `905`。
  - 日度对比显示两者 `1532` 行完全对齐，累计 net PnL 差 `+1,229,815`，累计滑点差 `+52,310`；最大差异日包括 `2025-07-28`、`2023-08-01`、`2025-07-21`。
- 处理原则：
  - 本阶段晋级判断只按同跑 A/C 判断，所以 C 相对 A 的路径劣化结论有效。
  - 旧 Stage526 权威口径不被本阶段替换。
  - 后续如要引用 Stage526 绝对收益，必须先做单独的控制组漂移审计，确认当前工作区差异来源。

## 图表视觉复盘

- 左上权益图：C 红线长期高于 A 蓝线，说明轻量加仓确实增加收益。
- 右上水下图：C 在 2022 和后续局部深水段更差，最大回撤更深。
- 左下成本压力图：C 在 `1x/2x/3x` 三档都比 A 更差，3x 已到 `-43.0981%`，明显越过 DD40 约束。
- 右下触发分布图：触发集中在 `MA/SM/cu` 等少数产品，不是广泛稳定的组合风险改善。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_summary_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_gates_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_rolling_holding_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- window：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_window_metrics_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- micro events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_micro_sizing_events_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- product summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_product_trigger_summary_stage577_stage526_failure_memory_micro_sizing_replay_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_decision_stage577_stage526_failure_memory_micro_sizing_replay_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_report_stage577_stage526_failure_memory_micro_sizing_replay_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay_chart_stage577_stage526_failure_memory_micro_sizing_replay_v1.png`

## 结论

- 不晋级 failure-memory micro-sizing。
- Stage262 的“连续失败后趋势质量改善”只能保留为诊断事实，不能升级为交易门禁，也不能升级为轻量加仓规则。
- 原因不是它没有收益，而是它用更差的持有体验和更差的高成本边界换收益；这和当前总目标“真实可成交、DD40以内、保留大部分收益”冲突。
- 本子路线停止，不再救阈值、倍率、产品名单或弱窗口。

## 后续规划和 TODO

- 立即 TODO：
  - 单独做 `Stage526 control drift audit`，查清当前工作区 A 与旧 Stage526 权威输出的收益/滑点差异来源。
- 主线 TODO：
  - 继续补 Stage277 的 P0 真实执行 TCA 证据。
  - 继续累计 Stage276/274 的 point-in-time 外生 selector forward 样本。
  - 若继续选品路线，必须按 Stage261 固定协议做 IC/bucket/paper sleeve，不再做 hindsight 产品筛选。

## 过拟合反思

- 运行前判断：否。规则在运行前固定，只有一个 A/C，未扫阈值、倍率、品种名单或弱窗口。
- 运行后判断：否。本阶段主动拒绝了收益更高版本，没有事后救参。
- 风险边界：如果继续调整 `>=2`、`252d`、`1.10` 或触发产品，就是过拟合，应停止。

## 继续价值反思

- 运行前判断：有价值。Stage262 的 segment 证据足够支持一次真实引擎 replay。
- 运行后判断：本子方向继续价值低，应停止。
- 总目标继续价值：仍然有。更值得推进的是真实执行偏差、外生 point-in-time 选品和低相关低保证金独立收益源，而不是失败后加风险。
