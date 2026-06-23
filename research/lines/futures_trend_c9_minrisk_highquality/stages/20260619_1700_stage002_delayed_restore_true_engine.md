# Stage002 延迟恢复风险真实引擎反证

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：day
- 记录时间：2026-06-19 17:00 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：当前官方正式 C9/15w 的冻结 A vs C 真实组合引擎；分钟级入场日恢复风险验证
- 是否重要突破：否。属于重要反证版本，但不是可接正式候选。
- 是否触发A/B：是，A vs C。C 是执行层候选，可能影响正式版风险释放方式，因此按 `skills/version-ab-experiment/SKILL.md` 记录。

## 外部调研与判断

- 参考资料：
  - `pysystemtrade` / Rob Carver 系统化期货框架：https://github.com/pst-group/pysystemtrade
  - Robert Carver systematic trading 起点页：https://qoppac.blogspot.com/p/systematic-trading-start-here.html
  - Concretum trend-following position sizing / pyramiding 文章：https://concretumgroup.com/position-sizing-in-trend-following-comparing-volatility-targeting-volatility-parity-and-pyramiding/
  - SSRN `A Guide to Trend Following Strategies`：https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID4438260_code412374.pdf?abstractid=4438260&mirid=1
- 我的判断：
  - 外部资料支持系统化风险预算、仓位释放纪律、趋势确认后再承担更多风险、多起点/多市场验证。
  - 外部资料不支持复制具体分钟参数，也不支持在看到失败后继续扫 `50%/0.5R/0.25R/1R`。
  - 本阶段只采用第一性原则：先小仓、方向证明后恢复原风险、失败快速承认；规则若不能穿过真实资金路径，应直接反证，不救参。

## 本次变更

- 新增脚本：
  - `research/lines/futures_trend_c9_minrisk_highquality/tools/stage002_delayed_restore_true_engine.py`
- 修改脚本：
  - 同脚本内修复一次实现缺陷：原 pending restore 以信号日做 key，真实开仓成交在下一交易日，导致 `restore_event_count=0`；修正为同合约/方向匹配最近 7 个自然日内的前序 pending，分钟 K 仍按实际成交日推进。
- 删除脚本：无
- 新增参数：
  - `enable_stage002_delayed_restore=True`
  - `stage002_initial_fraction=0.50`
  - `stage002_progress_r=0.50`
  - 整数手规则：原始手数 `>=2` 时 `floor(50%)` 作为 scout，剩余手数 deferred；`1` 手无法拆分，保持原版。
  - 恢复层止损：原始入场价。
  - `rollover_reopen` 不拆分，避免换月时凭空降风险。
- 修改参数：无正式参数修改；不改 C9 `0.5R` stop/retry，不改品种池、AI池、资金口径、执行链路。
- 删除参数：无

## 回测/验证参数

- A：当前官方正式 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- C：`C_stage002_delayed_restore_50pct_after_05r`
- 区间：`2018-01-01 -> 2026-06-15`
- 账户：`150,000`
- 数据：日线组合回测 + 入场日分钟 K
- 成本：主口径 `1x`，并输出候选 `2x/3x` 成本压力
- 输出：A/C 全路径资金曲线、回撤曲线、broker10 曲线、分钟 K atlas、事件表、决策 JSON
- 不连接 CTP，不读取真实账户，不调用订单 API。

## 结果

| 指标 | A 官方 C9/15w | C Stage002 |
| --- | ---: | ---: |
| 期末权益 | `39,176,437.60` | `26,004,739.10` |
| 总收益 | `26017.6251%` | `17236.4927%` |
| 收益保留 | - | `66.2493%` |
| 最大回撤 | `-45.0827%` | `-40.7691%` |
| 回撤改善 | - | `+4.3135pp` |
| Sharpe | `1.6331` | `1.5669` |
| 总滑点 | `2,730,130` | `1,598,210` |
| 总交易次数 | `787` | `1,033` |
| 胜率 | `53.2560%` | `51.1033%` |
| broker10 峰值 | `111.7365%` | `116.8005%` |
| days_over_100pct | `5` | `9` |

- C 开仓拆分次数：`314`
- C 恢复事件：`166`
- C 恢复后同日回到原入场价止损：`73`
- C9 stop/retry 事件：A `125`；C `126`
- 3x 成本压力下 C：
  - 期末权益 `22,808,319.10`
  - 总收益 `15105.5461%`
  - 最大回撤 `-49.6197%`
  - Sharpe `1.4023`
  - broker10 峰值 `144.0787%`
  - days_over_100pct `24`

## 视觉分析

- 资金曲线图显示 C 长期低于 A，尤其 2023 年以后右尾斜率明显不足；这不是单一窗口或单一品种事故，而是降低初始风险后未充分恢复右尾复利。
- 回撤图显示 C 的最低回撤从 A 的 `-45.08%` 改到 `-40.77%`，但改善幅度只有 `4.31pp`，没有达到“明显降低最大回撤”的目标。
- broker10 图显示 C 虽然很多阶段比 A 低，但恢复层在大手数年份制造了更高尖峰，峰值从 `111.74%` 升到 `116.80%`，3x 成本下更升到 `144.08%`。
- 分钟 K atlas 显示，多数恢复是在开盘或盘中早段确认 `+0.5R`，随后同日回落到原入场价止损；恢复层增加了交易次数和保证金峰值，却没有保住足够右尾收益。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_report_stage002_delayed_restore_true_engine_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_decision_stage002_delayed_restore_true_engine_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_summary_stage002_delayed_restore_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_comparison_stage002_delayed_restore_true_engine_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_curve_stage002_delayed_restore_true_engine_v1.csv`
- restore events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_restore_events_stage002_delayed_restore_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage002_delayed_restore_true_engine/qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_path_chart_stage002_delayed_restore_true_engine_v1.png`
- minute atlas：
  - `qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_atlas_page001_stage002_delayed_restore_true_engine_v1.png`
  - `qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_atlas_page002_stage002_delayed_restore_true_engine_v1.png`
  - `qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_atlas_page003_stage002_delayed_restore_true_engine_v1.png`
  - `qmt_roll_stage002_c9_minrisk_delayed_restore_true_engine_atlas_page004_stage002_delayed_restore_true_engine_v1.png`

## 结论

- 决策：`stage002_failed_return_retention_stop_shape_no_param_rescue`
- 该形状不进入多起点扩展验证，不接正式候选，不做 A/B 晋级。
- 原因：
  - 收益保留只有 `66.2493%`，低于 `80%` 硬门槛。
  - 回撤只改善 `4.3135pp`，不足以抵消收益损失。
  - broker10 峰值和 days_over_100pct 均恶化。
  - 成本压力下 C 的回撤和 broker10 尾部进一步恶化。
- 不允许的后续：
  - 不扫 `initial_fraction=0.33/0.67/0.75`
  - 不扫 `progress_r=0.25/0.75/1.0`
  - 不按 `2022/2024/2025`、品种、方向、交易所、月份补丁化

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否，但仅限于“本次冻结验证”。
- 原因：
  - 本次规则来自 Stage001 预声明，没有看结果后调比例或 R 倍数。
  - 修复 pending key 是成交日工程 bug，不是策略参数修补。
  - 若现在为了救收益保留去改 `50%` 或 `0.5R`，就会变成过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：这个具体形状没有继续价值；整条研究线仍有价值。
- 原因：
  - C9/15w 的 DD40/DD50 和 broker10 尾部问题仍存在。
  - Stage002 说明“机械半仓等 +0.5R 恢复”过度砍右尾，同时恢复层会制造保证金尖峰。
  - 下一步应换一个更普世的执行原则，而不是救参数：优先研究“只在原 C9 已经因风险/保证金受限时做风险释放顺序调整”，或账户层持仓风险净额治理；核心仍然是分钟级实际可见信息和全路径资金曲线。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：否；并行新线仍由合入者统一更新 registry。
- 追加根目录 `back_log.md`：是；本次属于 A vs C 回测，按 A/B 技能要求记录。
