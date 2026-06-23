# Stage252 价量共振只读预检

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-22 15:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读 preflight；复核价量共振是否值得进入 true engine
- 是否重要突破：否，预检阻断
- 是否触发A/B：否；没有形成可接入正式版本的候选

## 外部调研与判断

- 参考资料：
  - Alpha Architect, Avoiding the Big Drawdown with Trend-Following Investment Strategies: https://alphaarchitect.com/avoiding-the-big-drawdown-with-trend-following-investment-strategies/
  - GitHub, `amstrdm/mlm-trend-following`: https://github.com/amstrdm/mlm-trend-following
  - SSRN, trade sizing and drawdown/tail risk: https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3231836_code1554519.pdf?abstractid=2063848&mirid=1
  - DIVA thesis, CTA position sizing: https://www.diva-portal.org/smash/get/diva2%3A730028/fulltext01.pdf
  - GitHub, `pst-group/pysystemtrade` backtesting docs: https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md
  - Man Group, Is this time different for trend following drawdowns: https://www.man.com/insights/is-this-time-different
  - Newfound Research, Protect & Participate: https://blog.thinknewfound.com/2018/03/protect-participate-managing-drawdowns-with-trend-following/
- 我的判断：趋势跟随回撤本质上来自右尾收益的等待成本和恢复期噪声，不能用事后漂亮的权益曲线切片去补丁。价量共振是合理的一阶直觉，但必须同时满足低坏账、保右尾、保早期跑道和跨年份/交易所/方向稳定；否则继续往上叠桶就是过拟合。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage252_price_volume_consensus_preflight.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `PRICE_Q_COL=quality_quintile_aligned_bar_return_1m`
  - `VOLUME_Q_COL=quality_quintile_volume_zscore_60m`
  - `price_volume_both_high_q4q5`：价格顺势分位 `Q4/Q5` 且量能分位 `Q4/Q5`
  - `price_volume_both_low_q1q2`：价格顺势分位 `Q1/Q2` 且量能分位 `Q1/Q2`
  - promotion gate：样本数 `>=30`、坏账率相对 rest 降低 `>=5pp`、右尾捕获 `>=50%`、bottom-loss 捕获 `<=25%`、early right-tail 捕获 `>=50%`、无 PnL 正负混杂、split pass share `>=60%`、技术隔离通过
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：官方 C9/15w 基准沿用 Stage251，`2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：官方基准成本口径，不新增成本压力回测
- 样本过滤：Stage249 的 `219` 个 timestamp-ready replay order；不按品种、年份、交易所、方向做救参
- 策略/归因口径：
  - 只读合并 Stage249 frontier rows 与 Stage251 官方 A 臂曲线
  - 冻结假设：入场前价格顺势和量能惊奇同时较高，才可能是高质量信号
  - 不创建策略规则、不运行 true engine、不触发 A/B、不改变 official config、不连接 CTP/SimNow、不调用 order API

## 结果

- 官方期末权益：`39,176,437.60`
- 官方总收益：`26017.6251%`
- 官方最大回撤：`-45.0827%`
- 官方 Sharpe：`1.6331`
- 官方总滑点：`2,730,130`
- 官方总交易次数：`787`
- 官方胜率：`53.2560%`
- timestamp-ready 订单数：`219`
- both-high 订单数：`41`，覆盖 `15` 个品种、`6` 个年份
- both-high PnL：`9,609,247.20`，PnL 占比 `29.6667%`
- both-high 单笔 PnL 最小/最大：`-387,500` / `2,669,280`
- both-high 正/负订单：`17` / `24`，存在 PnL 正负混杂
- both-high risk_bad_rate：`0.121951`
- rest risk_bad_rate：`0.202247`
- 相对 rest 坏账率降低：`0.080296`
- both-high right-tail 捕获：`6/18 = 33.3333%`
- both-high bottom-loss 捕获：`2/18 = 11.1111%`
- both-high early right-tail 捕获：`2/9 = 22.2222%`
- split stability：`2/10 = 20.0000%`
- promotion gate：`4/8`，通过样本量、坏账率降低、bottom-loss 低捕获、技术隔离；失败右尾捕获、早期右尾捕获、PnL 正负混杂、split 稳定性
- 决策：`stage252_price_volume_consensus_tail_conflict_no_true_engine_no_rule`

## 视觉分析

- official path consensus chart：both-high 点分布在官方权益台阶和回撤段两侧，不是只集中在坏账区；视觉上不能作为稳定降险入口。
- consensus contribution chart：both-high 与 volume-high-only 的累计贡献主要在 `2025` 后半段快速拉升，早期贡献并不稳定；mixed_or_middle 也贡献了大量 PnL，说明价量共振不是右尾的唯一承载体。
- group rate chart：both-high 坏账率低于 rest，bottom-loss 捕获也低，但 right-tail rate 只有 `0.1463`，总右尾捕获只有 `33.33%`，不满足“最小风险搏最大收益”的保右尾目标。
- split stability heatmap：`2023` both-high 单笔 PnL 相对 rest 差 `-727k`，DCE 差 `-252k`，short 差 `-120k`；只有 `2025` 与 long 方向明显通过，跨周期和跨场所不够稳。
- promotion gate chart：技术隔离和样本数通过，但真正决定能否进入 true engine 的尾部保留、早期跑道和 split 稳定性均失败。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_report_stage252_price_volume_consensus_preflight_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_summary_stage252_price_volume_consensus_preflight_v1.csv`
- rows：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_consensus_rows_stage252_price_volume_consensus_preflight_v1.csv`
- group summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_group_summary_stage252_price_volume_consensus_preflight_v1.csv`
- split stability：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_split_stability_stage252_price_volume_consensus_preflight_v1.csv`
- promotion gate：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage252_price_volume_consensus_preflight/qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_promotion_gate_stage252_price_volume_consensus_preflight_v1.csv`
- visuals：
  - `qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_official_path_consensus_chart_stage252_price_volume_consensus_preflight_v1.png`
  - `qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_consensus_contribution_chart_stage252_price_volume_consensus_preflight_v1.png`
  - `qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_group_rate_chart_stage252_price_volume_consensus_preflight_v1.png`
  - `qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_split_stability_heatmap_stage252_price_volume_consensus_preflight_v1.png`
  - `qmt_roll_stage252_c9_minrisk_price_volume_consensus_preflight_promotion_gate_chart_stage252_price_volume_consensus_preflight_v1.png`

## 结论

- 本阶段结论：价量共振是有解释价值的弱线索，但不能进入 true engine。它能降低坏账率和 bottom-loss 捕获，却漏掉太多右尾和早期跑道右尾，并且在年份、交易所、方向切片上不稳。
- 是否进入下一步：Stage252 价量共振交易化路线不进入下一步，不进入正式候选，不触发 A/B。
- 下一步：不要继续加价格/量能小格、阈值、年份、交易所、方向或产品补丁；若继续当前大目标，应转向真正外生且入场前可见的信息源，或研究不改变正式持仓路径的部署层资金治理。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：本次没有新增过拟合；继续救参会过拟合。
- 原因：本阶段只组合 Stage239 已冻结的两个 watch-only 直觉，且只设一个低自由度 `Q4/Q5 price + Q4/Q5 volume` 共振假设，没有扫阈值、年份、交易所、方向、产品或事件豁免。失败来自右尾保留与 split 稳定性不足，不是参数没调好。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：价量共振小格路线无继续交易化价值；降低回撤的大目标仍有价值。
- 原因：Stage251 已否定账户 DD 主动降仓，Stage252 检查了最自然的两项入场前弱信号组合，结果仍无法保右尾。继续叠加更多分钟特征会越来越像历史拟合；真正值得继续的是寻找信息层级更高、因果上更接近风险来源的数据，而不是在同一套分钟派生指标里做组合爆炸。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage252 预检阻断摘要。
- 是否更新 `research/registry.md`：否，本线不新增/合并/废弃研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是日常路线预检阻断，不是正式候选、重要合入或跨线事件。
