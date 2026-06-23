# Stage035 entry_session_microstructure_forensics

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 00:24 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前官方 C9/15w 入场日 session 微观结构只读法证；不新增交易规则、不改正式配置、不连接 CTP、不调用订单 API
- 是否重要突破：否
- 是否触发A/B：否，`candidate_ready=0`，本阶段没有可接入正式版的候选规则

## 外部调研与判断

- 参考资料：
  - [Intraday Seasonality in Efficiency, Liquidity, Volatility and Volume](https://www.econ.kobe-u.ac.jp/wp/wp-content/uploads/2023/06/1722.pdf)：日内效率、流动性、波动和成交量存在 session/时段季节性，商品市场文献也观察到成交量 U 型等现象。
  - [Revisiting the U-shaped Patterns in Volatility and Price Impacts](https://digitalcommons.chapman.edu/business_articles/176/)：交易活动在 trade-time 口径下仍呈 U 型，但 calendar-time 波动/冲击估计可能受聚合偏差影响。
  - [Forecasting Intraday Volatility: Evidence from China Gold Futures Market](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4359812)：中国期货夜盘/日盘分段对已实现波动预测有信息含量，夜盘信息不能简单忽略。
  - [Can night trading reduce price volatility? Evidence from China's corn and corn starch futures markets](https://ideas.repec.org/a/wly/jfutmk/v44y2024i4p585-604.html)：中国期货夜盘制度改变了日间波动和隔夜风险结构。
- 我的判断：
  - 日内开盘/收盘/夜盘微观结构是普世到足以做审计的方向，但绝不是天然可交易规则。
  - 本仓库官方 trades 的开仓时间全部是 `00:00:00` 日线占位，不是精确成交分钟；因此本阶段只能审计 Stage861 entry-day session exposure，不能宣称“入场分钟时段规则”已经可交易。
  - 若要把时段用于执行，需要真实分钟成交/执行引擎或独立的入场前外生信息源；否则容易把产品交易时长、年份右尾和最终 PnL 混成伪规律。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage035_entry_session_microstructure_forensics.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `FIRST_N_BARS=30`：只用于复用首 30 根分钟路径观察，不作为交易阈值
  - `ATLAS_WINDOW_BARS=180`
  - 固定 session 模板：`day_session_only`、`day_plus_night_2300`、`day_plus_night_2330`、`day_plus_night_2400`、`midnight_cross_entry_day`、`late_partial_entry_day`、`missing_stage861_session`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-02` 至 `2026-06-15`，沿用 Stage010 官方 C9/15w replay 输出
- 账户规模：`150,000`
- 成本口径：沿用官方 Stage010，`cost_multiplier=1.0`
- 样本过滤：官方 closed lots `399` 笔；Stage861 entry-day session covered `398` 笔，仍保持 `OI609.CZCE 2026-06-02` hard missing
- 策略/归因口径：
  - A：当前官方正式版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 本阶段只把每笔 closed lot 绑定到 Stage861 entry-day 首根/末根分钟、session 模板、first clock bucket、首 30 根分钟路径，不改变 A 的交易路径

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：closed-lot 胜率 `36.0902%`
- 其他关键指标：
  - official closed lots：`399`
  - Stage861 session covered：`398/399 = 99.7494%`
  - open trade exact minute ready：`0`
  - open trade daily placeholder：`399`
  - `day_plus_night_2300`：`231` 笔、`23` 产品、`9` 年、净 PnL `35,132,282.70`、正收益年份 `8`、负收益年份 `1`、负收益绝对覆盖 `53.9521%`
  - `day_session_only`：`100` 笔、`19` 产品、`9` 年、净 PnL `3,396,135.50`、正收益年份 `5`、负收益年份 `4`、负收益绝对覆盖 `37.0947%`
  - `midnight_cross_entry_day`：`23` 笔、`4` 产品、`8` 年、净 PnL `2,842,551.50`，但 top3 产品绝对贡献占 `99.9844%`
  - `day_plus_night_2330`：`30` 笔、`9` 产品、`2` 年、净 PnL `92.90`，几乎无解释力
  - first clock `09:00` 桶覆盖 `368` 笔，净 PnL `38,575,141.10`，但负收益绝对覆盖 `91.3859%`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_report_stage035_entry_session_microstructure_forensics_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_summary_stage035_entry_session_microstructure_forensics_v1.csv`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_decision_stage035_entry_session_microstructure_forensics_v1.json`
- features：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_features_stage035_entry_session_microstructure_forensics_v1.csv`
- session stats：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_session_template_stats_stage035_entry_session_microstructure_forensics_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_contribution_curve_stage035_entry_session_microstructure_forensics_v1.csv`
- 资金/回撤/session 贡献图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_session_path_chart_stage035_entry_session_microstructure_forensics_v1.png`
- 年度热图：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_session_year_heatmap_stage035_entry_session_microstructure_forensics_v1.png`
- clock distribution：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_clock_distribution_stage035_entry_session_microstructure_forensics_v1.png`
- scatter：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_session_first30_scatter_stage035_entry_session_microstructure_forensics_v1.png`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage035_entry_session_microstructure_forensics/qmt_roll_stage035_c9_minrisk_entry_session_microstructure_forensics_atlas_page001_stage035_entry_session_microstructure_forensics_v1.png` 至 page005

## 视觉结论

- session path chart 显示官方权益大台阶主要由 `day_plus_night_2300` 贡献，但该桶也承担最大负收益覆盖，不能削掉或单独保留。
- session-year heatmap 显示 `day_plus_night_2300` 在 `2021-2025` 贡献右尾，但 `2026` 暂负；`day_session_only` 在 `2022/2023/2024/2026` 为负、`2025` 又大正，完全不单调。
- clock distribution 显示 first bar around `09:00` 几乎覆盖全部样本和大部分正负收益，这是回测/分钟源结构，不是一个可交易 edge。
- scatter 显示首 30 分钟 directional R 与最终 PnL 有趋势右尾关系，但负向和中性区域混杂，且 Stage034 已禁止围绕 30m 路径扫规则。
- atlas 显示同一 session 模板内既有 `OI309/jm2509` 这类大右尾，也有 `ru2605/ru2409/SH607/lc2401` 等失败路径；风险和右尾共存，不支持时段过滤。

## 结论

- 本阶段结论：`stage035_session_microstructure_readonly_no_trade_rule`
- 是否进入下一步：本分支不进入 true engine，不触发 A/B，不接正式版。
- 下一步：
  - 停止 session template / first clock bucket 直接交易化；不扫 `09:00/夜盘/日盘/23:00/23:30/24:00` 等时段桶。
  - 若继续分钟执行方向，必须先解决真实成交分钟不可用的问题，或构建真实分钟级执行回放，而不是用日线占位时间反推规则。
  - 若不做数据工程，下一步转向真正入场前可见、覆盖完整、非最终盈亏标签的外生风险源，或只做 forward watch。

## 过拟合反思

- 运行前判断：否，但高风险。日内 session 微观结构有跨市场依据，值得审计；风险在于把交易时长/品种/年份右尾误当成普世规则。
- 运行后判断：若交易化就是过拟合；只读审计本身不是。
- 原因：
  - `open_trade_exact_minute_ready_lots=0`，说明不能做精确开仓时段规则。
  - 主要桶不是单调风险桶，`day_plus_night_2300` 同时覆盖大部分右尾和大部分负收益。
  - 小桶如 `midnight_cross_entry_day/day_plus_night_2400` 有明显产品集中，不能穿越周期。

## 继续价值反思

- 运行前判断：有价值。它能确认是否存在普世的开盘/夜盘风险源，也能约束后续不要滥用 session 标签。
- 运行后判断：本分支作为规则研究继续价值低；作为证据边界和数据工程约束有价值。
- 原因：
  - 它证明当前官方回测输出没有真实开仓分钟，后续分钟进出场研究必须补执行层数据或只用 entry-day 路径。
  - 它把 session/first-clock 标签降级为风险解释和 forward-watch，避免后续时段补丁化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage035 摘要和约束。
- 是否更新 `research/registry.md`：否；不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是本线内部只读审计，不是重要合入摘要。
