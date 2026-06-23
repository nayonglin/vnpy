# Stage019 no-follow 30m 固定 80% 轻削风险真实引擎

- 记录时间：`2026-06-19 20:52 CST`
- 当前模式：`day`
- line_id：`futures_trend_c9_minrisk_highquality`
- 当前官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once` / `Stage847-C9-15w`
- 阶段性质：冻结 A vs C 真实组合引擎；不改正式配置、不连接 CTP、不调用订单 API。
- 是否重要突破：否。它是关键反证，正式排除 no-follow 轻削比例路线。
- 是否触发 A/B：是。已读取 `skills/version-ab-experiment/SKILL.md`，因为该真实引擎若通过，可能进入下一验证阶段。

## 外部调研与判断

- 调研来源：
  - https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
  - https://github.com/chrism2671/PyTrendFollow
  - https://alphaarchitect.com/conditional-volatility-targeting/
  - https://www.cfm.com/wp-content/uploads/2022/12/188-2018-Making-fat-right-tails-fatter-with-trend-following-most-of-the-time.pdf
- 判断：趋势跟随 CTA 的 position sizing 研究支持在 alpha 不变时测试风险暴露管理，但趋势策略的核心收益来自正偏右尾，任何 drawdown reducer 都必须证明没有切断复利台阶。Stage019 因此只做 Stage018 代理的单次真引擎验真，不允许继续扫比例或窗口。

## 候选假设

- A：当前官方 C9/15w 全路径。
- C：官方 C9 正常开仓，保留原 C2 intraday stop、broker10 cap、`0.5R` stop/retry-once；若入场后前 `30` 根 entry-day 分钟 K 收盘相对入场方向的 directional R `<=0`，则把 active volume 降到 `floor(80%)`，最低保留 `1` 手。
- 缺 entry-day 分钟K、风险距离无效、原仓位只有 `1` 手或 C9 stop/retry 已先触发时，保持官方路径。

## 预声明通过标准

- 收益保留 `>=80%`。
- 最大回撤改善，且进入晋级路径前优先要求 `>=5pp` 实质改善。
- broker10 峰值和 `days_over_100pct` 不得恶化。
- Sharpe 不显著恶化，阈值 `>= -0.10`。
- 2x/3x 成本压力不得暴露隐藏失败。
- 资金曲线和分钟 atlas 必须支持指标叙事。

## 版本变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage019_no_follow_light_shave_true_engine.py`
- 新增输出目录：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/`
- 新增参数：
  - `enable_stage019_no_follow_reduce=True`
  - `stage019_reduce_fraction=0.80`
  - `stage019_window_minutes=30`
- 修改参数：无正式参数修改。
- 删除参数：无。
- 验证：`.py311/bin/python -m py_compile research/lines/futures_trend_c9_minrisk_highquality/tools/stage019_no_follow_light_shave_true_engine.py` 通过。
- 订单/CTP：`order_api_called=false`，`ctp_connected=false`。

## 新增回测结果

| arm | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 | over100天数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A official C9/15w | `39,176,437.60` | `26017.6251%` | `-45.0827%` | `1.6331` | `2,730,130` | `787` | `53.2560%` | `111.7365%` | `5` |
| C Stage019 | `30,914,376.90` | `20509.5846%` | `-47.2451%` | `1.5351` | `2,415,600` | `822` | `52.6549%` | `120.9328%` | `12` |

- 收益保留：`78.8296%`，未达到 `80%`。
- 期末权益差：`-8,262,060.70`。
- 回撤改善：`-2.1625pp`，即最大回撤反而恶化。
- Sharpe 差：`-0.0980`，勉强未触发显著恶化阈值，但没有实际晋级意义。
- 触发轻削事件：`36` 次。
- reduce volume：`970` 手。

## 成本压力

| cost multiplier | 期末权益 | 总收益 | 最大回撤 | Sharpe | broker10峰值 | over100天数 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `1x` | `30,914,376.90` | `20509.5846%` | `-47.2451%` | `1.5351` | `120.9328%` | `12` |
| `2x` | `28,498,776.90` | `18899.1846%` | `-51.2871%` | `1.4443` | `133.5561%` | `19` |
| `3x` | `26,083,176.90` | `17288.7846%` | `-56.7251%` | `1.3544` | `156.8134%` | `27` |

## 视觉分析

- 资金曲线显示 C 从 `2021` 后长期低于 A，说明即使只轻削 `20%`，也会切断部分右尾复利底座。
- `2022-03-09 -> 2022-06-29` 同一峰谷窗口，A 从 `9,506,360` 回落到 `5,220,640`，C 从 `7,226,440` 回落到 `3,812,300`；C 不只是少赚，回撤百分比也更深。
- broker10 曲线显示 C 的尖峰更高，`days_over_100pct` 从 `5` 增到 `12`，主要是权益分母被削弱后保证金压力更重。
- atlas page001 中 `AP210/AP501/SH405/SH607` 的 30m no-follow 后仍存在后续反转或趋势延续，`SH405` 这类 false positive 继续证明 no-follow 不是错误充分条件。
- atlas page002 中 `au2412/lh2409/SM109/lh2309` 进一步显示 no-follow 后存在慢启动右尾；轻削不是免费降风险。
- atlas page003 中 `fu2209/MA305/si2310/SM505` 显示触发事件既有真风险，也有后续恢复机会。简单 30m 标签无法区分。

## 决策

- 决策：`stage019_failed_return_retention_no_param_rescue`
- 晋级：不晋级，不进入 half-year/monthly 多起点验证，不接正式配置，不做 A/B promotion。
- 删除结果：删除“Stage018 no-follow 80% 代理线索可能通过真引擎成为候选”的假设。
- 新增结果：真实引擎证明 Stage018 代理高估了轻削价值；整数手、stop/retry、复利路径和保证金分母效应会把代理优势反转。

## 反思

- 运行前是否过拟合：有限风险但可接受。把 Stage008 的 `50%` 改成 `80%` 如果重复做就是参数救援；本次只因 Stage018 预先固定 `80%` 且要求一次真引擎验真才执行。
- 运行后是否过拟合：本次没有新增过拟合，但如果继续改 `80%`、`30m`、按年份/品种/方向筛 no-follow，就是过拟合。
- 是否还有价值继续做：no-follow 风险比例路线没有继续价值。整条“最小风险高质量信号”目标仍有价值，但下一步必须换第一性原则，不再从 no-follow 降仓比例救参。

## 后续规划和 TODO

- 停止 `no_follow_30m_reduce_to_half` 和 `no_follow_30m_reduce_to_80` 这一族，不扫 `70/75/85/90`，不扫 `15/30/60m`。
- 不再把 Stage018 daily proxy 当候选依据；代理只能用于归因。
- 下一阶段若继续，应转向不改变官方单笔路径的外部风险源或账户层机制，例如资金分层、出金锁盈、独立 sleeve 或真正外生的可交易状态，不再用入场后 30m 单标签做仓位削减。

## 输出文件

- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_decision_stage019_no_follow_light_shave_true_engine_v1.json`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_summary_stage019_no_follow_light_shave_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_comparison_stage019_no_follow_light_shave_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_path_chart_stage019_no_follow_light_shave_true_engine_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage019_no_follow_light_shave_true_engine/qmt_roll_stage019_c9_minrisk_no_follow_light_shave_true_engine_atlas_page001_stage019_no_follow_light_shave_true_engine_v1.png`
