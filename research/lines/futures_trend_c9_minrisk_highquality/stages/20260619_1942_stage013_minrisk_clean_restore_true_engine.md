# Stage013 最小风险 clean 30m 恢复真实引擎

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-19 19:42 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：冻结 A vs C 真实组合引擎 + 资金曲线/回撤/broker10/分钟 atlas 视觉复盘
- 是否重要突破：否，属于失败反证版本
- 是否触发A/B：否，收益保留、回撤、broker10、Sharpe 均未达标

## 外部调研与判断

- 参考资料：
  - Market Intraday Momentum：`https://assets.super.so/e46b77e7-ee08-445e-b43f-4ffd88ae0a0e/files/ee7dac49-530b-4950-b5d0-e0b5eee08f2e.pdf`
  - Intraday Time Series Momentum: International Evidence：`https://centaur.reading.ac.uk/95566/1/Accepted-Version.pdf`
  - pysystemtrade backtesting：`https://github.com/pst-group/pysystemtrade/blob/develop/docs/backtesting.md`
  - PyTrendFollow：`https://github.com/chrism2671/PyTrendFollow`
  - backtest-kit：`https://backtest-kit.github.io/`
- 我的判断：
  - 外部资料支持“早段分钟路径有信息”，但不能推出固定分钟窗口/阈值一定可交易。
  - 风险释放必须保持事件顺序和风险账本一致，不能用未来 MFE/MAE 或最终盈亏决定是否恢复风险。
  - Stage013 的价值在于验证最朴素的普世纪律：先 1 手观察，30m clean 才恢复；如果失败，不能围绕 `1手/30m/0.5R` 救参。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage013_minrisk_clean_restore_true_engine.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `stage013_scout_volume = 1`
  - `stage013_observation_bars = 30`
  - `stage013_heat_r = 0.50`
- 修改参数：无
- 删除参数：无
- 新增回测结果：Stage013 A/C 全周期真实组合引擎结果、成本压力、事件账本、资金曲线、分钟 atlas
- 修改回测结果：无
- 删除回测结果：无

## 预声明规则

- A：当前官方 C9/15w `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`。
- C：C9/15w + `minrisk_1lot_clean30_restore`。
- flat/reverse 新信号原始手数 `>1`，且 plan-day stop/risk 与 Stage861 入场日 30 根分钟K可用时，先开 `1` 手 scout。
- plan-day risk 或 Stage861 30m 不可用时保持官方路径，不把缺字段样本降风险。
- C9 `0.5R` stop/retry 在 30m 确认前优先；若先触发，则不恢复风险。
- 前 30 根可见分钟K满足 `directional_r > 0` 且 `MAE <= 0.5R` 时，在第 30 根收盘价恢复剩余官方手数。
- 恢复层止损为 scout 原入场价，避免恢复动作增加原始风险预算。
- 不扫观察窗口、热度阈值、恢复比例、品种、方向、年份或月份。

## 结果

- A 期末权益：`39,176,437.60`
- C 期末权益：`6,170,215.30`
- A 总收益：`26017.6251%`
- C 总收益：`4013.4769%`
- 收益保留：`15.4260%`
- A 最大回撤：`-45.0827%`
- C 最大回撤：`-55.4688%`
- 回撤改善：`-10.3862pp`
- A Sharpe：`1.6331`
- C Sharpe：`1.1071`
- A broker10 峰值：`111.7365%`
- C broker10 峰值：`165.0527%`
- A `days_over_100pct`：`5`
- C `days_over_100pct`：`15`
- A 总滑点：`2,730,130`
- C 总滑点：`534,810`
- A 总交易次数：`787`
- C 总交易次数：`864`
- A 胜率：`53.2560%`
- C 胜率：`48.8073%`
- Stage013 quality check events：`170`
- clean restore events：`97`
- restore stop events：`56`
- restore volume：`6,881`
- open adjustments：`172`
- 3x 成本 C 期末权益：`5,100,595.30`
- 3x 成本 C 最大回撤：`-66.4075%`
- 3x 成本 C broker10 峰值：`222.7812%`
- 决策：`stage013_failed_return_retention_no_param_rescue`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_report_stage013_minrisk_clean_restore_true_engine_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_summary_stage013_minrisk_clean_restore_true_engine_v1.csv`
- comparison：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_comparison_stage013_minrisk_clean_restore_true_engine_v1.csv`
- curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_curve_stage013_minrisk_clean_restore_true_engine_v1.csv`
- cost stress：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_cost_stress_stage013_minrisk_clean_restore_true_engine_v1.csv`
- quality events：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_quality_restore_events_stage013_minrisk_clean_restore_true_engine_v1.csv`
- event summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_event_summary_stage013_minrisk_clean_restore_true_engine_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_path_chart_stage013_minrisk_clean_restore_true_engine_v1.png`
- minute atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage013_minrisk_clean_restore_true_engine/qmt_roll_stage013_c9_minrisk_clean_restore_true_engine_atlas_page001_stage013_minrisk_clean_restore_true_engine_v1.png` 至 `page005`

## 视觉分析

- path chart 显示 C 从 `2021` 后长期系统性低于 A，不是单一窗口失败；C 的权益底座过低，导致后续即使有盈利也无法追上正式版复利。
- drawdown 子图显示 C 在 `2022-06/2022-07` 达到 `-55.47%`，明显比 A 的 `-45.08%` 更深；这不是降低回撤，而是削弱收益底座后放大路径波动。
- broker10 子图显示 C 峰值 `165.05%`，恶化主要来自权益分母被打低，而不是单纯保证金名义暴露增加；说明“降初始手数”并不自动改善账户压力。
- atlas page001 显示 `rb2605/FG601/MA409` 等 clean 样本 30m 后恢复了 `499/421` 手级别的大额 deferred volume，随后回到入场价止损；clean 不是稳定恢复充分条件。
- atlas page004 显示 `SA605/SM505/SH605` 等 no-restore 样本 30m 不 clean 后仍可能走出后续趋势；no-clean 不是坏信号充分条件。
- 视觉结论：`1` 手默认观察同时漏掉右尾复利，又在 clean 后恢复大量手数制造回踩噪声；这是结构失败，不是阈值问题。

## 结论

- 本阶段结论：`stage013_failed_return_retention_no_param_rescue`
- 是否进入下一步：进入，但必须换第一性原则，不能救 Stage013 形状
- 明确禁止：
  - 不扫 `1/2/3` 手 scout。
  - 不扫 `15/30/60` 分钟观察窗口。
  - 不扫 `0.25R/0.5R/1R` heat 或 stop。
  - 不按品种、方向、年份、月份选择性恢复。
  - 不把 clean/no-follow 标签直接做开满、半仓、删除或硬退出。
- 下一步：
  - 停止“全体默认最小风险，然后靠 30m 恢复”的主形状。
  - 下一阶段应先做只读失败归因：对比 Stage013 最大右尾损失来自哪些官方赢家被 1 手观察压缩、哪些 clean restore 当日止损消耗最多、这些样本在入场前/入场当刻是否有不依赖未来的共同结构。
  - 如果找不到入场前/入场当刻可见结构，信号质量方向应暂时降级，转向不改变单笔路径的账户层外部资金分层/出金锁盈/独立 sleeve，而不是继续改开仓手数。

## 过拟合反思

- 运行前判断：否。Stage013 是单一冻结规则，不按品种、年份、方向、月份分支，也没有窗口/比例/R 倍数扫描。
- 运行后判断：否。失败结果不是过拟合导致，而是结构本身不成立；但如果现在围绕 `1手/30m/0.5R` 改参救结果，就会变成过拟合。
- 原因：规则普世但错误，真实资金路径已经反证。

## 继续价值反思

- 运行前判断：有。Stage011/012 已经把 30m 质量标签和 plan-day risk 账本修清，必须用真实组合引擎验证。
- 运行后判断：本形状没有继续价值。收益保留仅 `15.4260%`，回撤、Sharpe、broker10 全部恶化；不能接正式、不能 A/B、不能救参。
- 对研究线整体判断：仍有价值，但必须换原则；继续研究应聚焦“不要破坏 C9 右尾复利底座”的入场前结构或账户层外部风险承载。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage013 反证和下一步边界。
- 是否更新 `research/registry.md`：否，本阶段未形成正式候选、跨线合并或路线废弃。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线内部失败反证，不是正式候选或重要合入。
