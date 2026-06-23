# Stage018 质量条件 80% 轻削风险代理审计

- 记录时间：`2026-06-19 20:43 CST`
- 当前模式：`day`
- line_id：`futures_trend_c9_minrisk_highquality`
- 当前官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 阶段性质：只读 daily active-risk proxy；不是真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否。形成一个强代理线索，但候选就绪数仍为 `0`。
- 是否触发 A/B：否。Stage018 是代理审计，不是可接正式的真实版本。

## 外部调研与判断

- 调研来源：
  - https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
  - https://github.com/chrism2671/PyTrendFollow
  - https://alphaarchitect.com/conditional-volatility-targeting/
  - https://www.cfm.com/wp-content/uploads/2022/12/188-2018-Making-fat-right-tails-fatter-with-trend-following-most-of-the-time.pdf
- 判断：CTA/trend-following 资料支持在不改 alpha 的情况下研究 position sizing 和风险暴露，但也反复提示不能破坏趋势策略正偏右尾。Stage018 因此只冻结一个 `80%` 低质量风险权重，不扫 `70/75/85/90`，也不扫窗口、品种、方向和年份。

## 版本变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage018_quality_conditioned_risk_shave_proxy.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/`
- 新增参数：
  - `LOW_QUALITY_WEIGHT=0.80`
  - 固定使用 Stage861 full minute 质量标签和 Stage012 修复后的 no-follow 标签。
- 修改参数：无正式参数修改。
- 删除参数：无。
- 订单/CTP：`order_api_called=false`，`ctp_connected=false`。

## 代理口径

- A：官方 C9/15w 原路径。
- fixed80：所有 active official daily PnL 固定乘 `80%`。
- no_follow：只把 repaired `no_follow_30m` active risk share 乘 `80%`。
- entry_unaligned：只把 entry/first-minute 未对齐 active risk share 乘 `80%`。
- combined：`no_follow_30m OR entry_unaligned` 乘 `80%`。
- strict_hq：仅 `ai_rank_4_6 AND entry/first-minute aligned` 保持满权重，其余 active risk 乘 `80%`。

## 新增回测/代理结果

| variant | 期末权益 | 总收益 | 收益保留 | 最大回撤 | 回撤改善 | Sharpe | broker10峰值 | over100天数 | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A official | `39,176,437.60` | `26017.6251%` | `100.0000%` | `-45.0827%` | `0.0000pp` | `1.6339` | `111.7365%` | `5` | 基准 |
| fixed80 | `31,371,150.08` | `20814.1001%` | `80.0000%` | `-44.9055%` | `+0.1771pp` | `1.6157` | `102.9675%` | `5` | 回撤改善太小 |
| no_follow_30m_low_quality_80 | `40,100,599.84` | `26633.7332%` | `102.3680%` | `-40.5160%` | `+4.5666pp` | `1.6988` | `112.6528%` | `4` | 最强代理线索，但 broker10 略差且非真引擎 |
| entry_unaligned_low_quality_80 | `36,906,804.98` | `24504.5367%` | `94.1844%` | `-42.3656%` | `+2.7171pp` | `1.6567` | `117.3114%` | `9` | 不候选 |
| combined_low_quality_80 | `36,990,490.29` | `24560.3269%` | `94.3988%` | `-41.3782%` | `+3.7044pp` | `1.6623` | `117.5158%` | `8` | 不候选 |
| strict_hq_only_full_else80 | `32,390,544.35` | `21493.6962%` | `82.6121%` | `-44.9202%` | `+0.1625pp` | `1.6114` | `104.7649%` | `6` | 回撤改善太小 |

## 特征桶归因

- `no_follow_30m`：`191` 笔、`35` 产品、`9` 年，官方 PnL `-4,451,531.10`，正收益捕获 `12.2703%`，负收益捕获 `52.0107%`，big winner `0`。
- `entry_unaligned`：`269` 笔，官方 PnL `17,527,693.90`，big winner `9`，说明它不是低质量充分条件。
- `combined_low_quality`：`281` 笔，官方 PnL `16,765,527.50`，big winner `9`。
- `strict_hq`：`24` 笔，官方 PnL `10,677,322.50`，但覆盖太小。

## 视觉分析

- path/drawdown 图显示 `no_follow_30m_low_quality_80` 没有像 CPPI/TIPP 那样躺平，仍保留 `2021/2023/2025` 的右尾台阶，并在 `2022/2023` 回撤段明显高于官方路径。
- daily weight 图显示 no-follow 触发稀疏，平均风险权重 `0.9727`，不是全局降风险壳。
- scatter 图显示 no-follow 代理最接近目标：收益保留 `102.3680%`，最大回撤 `-40.5160%`，但 broker10 从 `111.7365%` 升到 `112.6528%`，且回撤改善未达到 `5pp`。
- atlas page001 中 `SH607/AP210/cu2307/lh2411` 等大亏样本前 30m 没有立即顺向跟随，轻削风险有直觉基础。
- atlas page002 中 `SH405/au2412` 等 no-follow false positive 后续走出大赢家，证明不能硬删，也不能继续扩大削仓。

## 决策

- 决策：`stage018_quality_conditioned_risk_shave_proxy_no_candidate`
- 候选就绪数：`0`
- 结论：Stage018 只能支持一次真引擎 falsification，即 Stage019 固定 `80%` 轻削；若真引擎失败，停止 no-follow 风险比例路线，不做 `70/75/85`、`15/60m` 或品种/方向/年份救参。

## 反思

- 运行前是否过拟合：否。特征来自前序宽口径视觉法证，比例固定为 `80%`，没有扫窗口/比例/产品/年份。
- 运行后是否过拟合：否，但如果把代理最优点继续调成别的比例或窗口，就是过拟合。
- 是否还有价值继续做：有，但仅限一次真引擎验证。代理不能作为候选证据。

## 输出文件

- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_decision_stage018_quality_conditioned_risk_shave_proxy_v1.json`
- metrics：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_metrics_stage018_quality_conditioned_risk_shave_proxy_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_path_drawdown_chart_stage018_quality_conditioned_risk_shave_proxy_v1.png`
- daily weight chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_daily_weight_share_chart_stage018_quality_conditioned_risk_shave_proxy_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage018_quality_conditioned_risk_shave_proxy/qmt_roll_stage018_c9_minrisk_quality_conditioned_risk_shave_proxy_atlas_page001_stage018_quality_conditioned_risk_shave_proxy_v1.png`
