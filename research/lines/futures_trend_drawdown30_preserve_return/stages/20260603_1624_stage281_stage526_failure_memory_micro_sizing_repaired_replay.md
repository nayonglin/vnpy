# Stage281 Stage526失败记忆微仓位修复后真实引擎复验

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-03 16:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 真实引擎复验；修复 Stage580 控制组漂移后替代 Stage279 污染版结论。
- 是否重要突破：否。结论是明确不晋级，但它关掉了“失败后轻量加仓”这一条候选路线。
- 是否触发A/B：是，按 `skills/version-ab-experiment/SKILL.md` 执行。该版本改变风险 sizing，理论上可能进入正式候选。

## 外部调研与判断

- 趋势跟踪资料普遍把 position sizing 视为组合风险治理核心，但也提示亏损后加风险或过度止损可能伤害趋势右尾与路径稳健。
- 本地判断：Stage262 显示同品种连续失败后 segment 质量改善，这个经验有诊断价值；但它若进入交易，只能是一次预声明、低幅度 sizing 探针，不能做交易 gate、品种名单或阈值救援。

参考：

- Clare et al. trend following / stop-loss caveat: https://link.springer.com/article/10.1057/jam.2013.11
- pysystemtrade position sizing architecture: https://deepwiki.com/robcarver17/pysystemtrade/3.2-position-sizing-and-optimization
- Concretum position sizing: https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
- Davidsson position sizing / trend following risk management: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2248261

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay.py`
- 复用脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage577_stage526_failure_memory_micro_sizing_replay.py`
- 修改正式策略参数：无。Stage279 已新增默认关闭参数，本阶段只复跑。
- 新增参数：无新增交易参数。
- 修改参数：无。
- 删除参数：无。
- A：`stage526_control`
- C：`stage526_control + 同品种同方向连续失败>=2 后 flat_entry 风险乘数 * 1.10`
- 固定规则：`lookback_days=252`，`min_consecutive_failures=2`，`multiplier=1.10`，`entry_contexts=flat_entry`，不扫阈值、不扫倍率、不设产品名单。

## 回测参数

- 账户规模：C3 下单资金 `500,000`，组合账户口径沿用 Stage526/Stage580。
- 时间范围：`2020-01-02` 到 `2026-06-02`。
- 成本口径：`1x/2x/3x`。
- 控制组：Stage580 修复后恢复旧权威 Stage526，控制组必须等于 `23,369,505/3699.9195%/-36.2670%`。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | broker10峰值 | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A Stage526 | `23,369,505` | `3699.9195%` | `-36.2670%` | `14.4691` | `1.6385` | `99.7299%` | `1,342,190` | `905` | `53.6330%` |
| C failure-memory micro sizing | `24,833,205` | `3937.9195%` | `-37.2060%` | `14.6619` | `1.6455` | `99.8350%` | `1,426,140` | `905` | `53.4831%` |

成本压力：

| 版本 | 1x DD | 2x DD | 3x DD |
| --- | ---: | ---: | ---: |
| A Stage526 | `-36.2670%` | `-39.0565%` | `-42.0555%` |
| C failure-memory micro sizing | `-37.2060%` | `-40.0453%` | `-43.0981%` |

任意启动持有体验：

| 版本 | 63日p05 | 63日p10 | 63日亏损率 | 126日p05 | 126日p10 | 126日亏损率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A Stage526 | `-18.2169%` | `-9.5763%` | `23.2131%` | `-10.9700%` | `-4.1865%` | `13.6558%` |
| C failure-memory micro sizing | `-19.1283%` | `-9.6983%` | `23.6896%` | `-11.7349%` | `-3.4893%` | `12.9445%` |

晋级闸门：

- 通过 `3/10`：总收益、Sharpe、触发样本数。
- 失败 `7/10`：最大回撤、Ulcer、broker10峰值、2x成本DD、3x成本DD、63日左尾、126日左尾。
- 触发 opened events：`46` 次。

## 归因复盘

- C 相对 A 期末多 `1,463,700`，但收益增量主要来自后段右尾，而不是坏窗口修复。
- 年度增量：
  - 2020：`+26,575`
  - 2021：`+179,755`
  - 2022：`-35,940`
  - 2023：`+315,250`
  - 2024：`+351,025`
  - 2025：`+743,700`
  - 2026：`-156,990`
- 最大回撤窗口完全相同：`2022-03-09 -> 2022-12-07`。
  - A：`-36.2670%`
  - C：`-37.2060%`
- C 在最大回撤窗口内仍触发 `4` 次加风险：`lh2209.DCE`、`fu2209.SHFE`、`fu2301.SHFE`、`jm2301.DCE`。其中 `fu2301.SHFE` 触发 `base_multiplier=1.0 -> effective=1.10`。
- 触发集中度：`MA.CZCE long` `9` 次，`SM.CZCE long` `5` 次，`cu.SHFE long` `4` 次，说明触发不是均匀分布的通用机制。

## 图表视觉复盘

- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_chart_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.png`
- 左上权益曲线：C 红线在 2024 后明显高于 A 蓝线，说明规则有材料性收益增量，不是纯噪声。
- 右上水下图：C 和 A 水下路径高度重合，但 C 在 2022 最大水下段更深；这直接违背当前目标的“真实可成交且 DD40 内保收益”优先级。
- 左下成本压力图：2x 成本下 C 已经到 `-40.0453%`，刚好打穿 DD40；3x 为 `-43.0981%`，比 A 更差。
- 右下触发图：触发集中在少数产品长方向，尤其 `MA/SM/cu`，不能解释为稳定的全市场失败记忆机制。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay.py`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_decision_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_report_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_chart_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.png`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_summary_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_cost_stress_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage581_stage526_failure_memory_micro_sizing_repaired_replay_rolling_holding_stage581_stage526_failure_memory_micro_sizing_repaired_replay_v1.csv`

## 结论

- 决策：`failure_memory_micro_sizing_no_promotion`
- Stage262 的失败记忆经验是诊断事实，但不能晋级为交易 gate 或轻量加仓。
- Stage279 污染版结论已被本阶段替代；最终引用应使用 Stage581 数字。
- 后续禁止继续救 `>=2/252d/1.10`、倍率小数、触发产品名单或坏窗口特判。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合，但后续若继续改阈值、倍率或产品名单救失败结果，就会进入过拟合。
- 原因：本阶段是单次预声明复验，控制组先由 Stage580 修复为旧权威，C 没有使用未来赢家或弱窗口补丁。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：该子路线继续主动优化价值低；总目标仍有价值。
- 原因：C 的收益右尾变厚，但风险路径和成本压力更差，不满足当前目标；继续调小数只会把诊断事实过拟合成交易规则。

## TODO

- 停止 failure-memory micro-sizing 交易化。
- 回到三条主线：真实执行 TCA/滑点压降、point-in-time 外生/舆情 selector 样本累计、低保证金低相关独立收益源。
