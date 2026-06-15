# Stage032 Stage856 Stage855后剩余分钟K缺口下载尝试

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 01:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据下载与覆盖审计
- 是否重要突破：否
- 是否触发A/B：否；本阶段不改策略、不接引擎、不连接 CTP、不调用下单

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 官方文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - TqSdk `get_kline_serial` 官方文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.api.TqApi.get_kline_serial`
  - vn.py TQSDK 网关 GitHub：`https://github.com/vnpy/vnpy_tqsdk`
- 我的判断：
  - `DataDownloader` 是本阶段补 exact contract/date 历史分钟K CSV 的正确接口；`dur_sec=60` 与本线分钟K需求一致。
  - `get_kline_serial` 更适合实时/近端序列对象，不适合作为全周期历史缺口补数主路径。
  - 本次失败来自账号历史数据下载权限，不是策略逻辑、TQ 符号映射或脚本流程失效；因此不能据此写规则或否定分钟级研究本身。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage856_stage855_remaining_gap_download.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MAX_BATCHES`
  - `BATCH_OFFSET`
  - `PER_BATCH_TIMEOUT_SECONDS`
  - `SLEEP_SECONDS`
  - `FORCE_REFRESH`
  - `RAW_ROOT`
  - `BAR_COLUMNS`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据输入：
  - Stage855 request coverage：`qmt_roll_stage855_stage854_local_raw_import_request_coverage_after_patch_stage855_stage854_local_raw_import_v1.csv`
  - Stage855 remaining download manifest：`qmt_roll_stage855_stage854_local_raw_import_remaining_download_manifest_stage855_stage854_local_raw_import_v1.csv`
  - Stage825 intraday features
  - Stage849 pressure minute features
- 下载路径：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage856_remaining_gap_backfill/`
- 下载方式：TqSdk `DataDownloader`，`dur_sec=60`
- 本阶段只下载/覆盖审计，不跑交易引擎，不生成新规则。

## 结果

- 决策：`stage856_remaining_gap_download_attempt_no_rule`
- selected_batches：`84`
- selected_missing_dates：`91`
- downloaded_or_cached_batches：`0`
- failed_batches：`84`
- timeout_batches：`0`
- empty_batches：`0`
- permission_blocked_batches：`84`
- downloaded_minute_bars：`0`
- covered_dates_in_selected_batches：`0`
- stage853_gap_requests：`126`
- stage856_newly_covered_requests：`0`
- covered_requests_after_stage856：`29`
- remaining_gap_requests_after_stage856：`97`
- priority_abs_pnl_newly_covered_by_stage856：`0`
- priority_abs_pnl_remaining_after_stage856：`6,434,115`
- big_winner_requests_newly_covered_by_stage856：`0`
- big_winner_requests_remaining_after_stage856：`6`
- Stage825 closed lots：`341`
- Stage825 original covered lots：`227`
- Stage825 after Stage856 covered lots：`251`
- Stage825 after Stage856 coverage：`73.6070%`
- Stage849 key dates：`19`
- Stage849 original covered dates：`7`
- Stage849 after Stage856 covered dates：`12`
- Stage849 after Stage856 coverage：`63.1579%`
- status_counts：`{"failed": 84}`

## 失败原因

- `84/84` 个下载批次的失败信息一致：当前 TqSdk 账号不支持下载历史数据功能，需要购买/开通后才能使用。
- 排名前几的仍缺批次：
  - `rb2210.SHFE 2022-07-07`
  - `FG601.CZCE 2025-11-05`
  - `fu2205.SHFE 2022-03-30/2022-04-01`
  - `AP210.CZCE 2022-04-06`
  - `lc2401.GFEX 2023-11-07`
  - `fu2209.SHFE 2022-05-27/2022-05-31`
  - `FG209.CZCE 2022-05-24/2022-05-27/2022-06-02`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_report_stage856_stage855_remaining_gap_download_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_summary_stage856_stage855_remaining_gap_download_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_decision_stage856_stage855_remaining_gap_download_v1.json`
- download_status：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_download_status_stage856_stage855_remaining_gap_download_v1.csv`
- downloaded_minute_bars：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_downloaded_minute_bars_stage856_stage855_remaining_gap_download_v1.csv`
- request_coverage_after_download：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_request_coverage_after_download_stage856_stage855_remaining_gap_download_v1.csv`
- stage825_year_coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_stage825_year_coverage_after_download_stage856_stage855_remaining_gap_download_v1.csv`
- stage849_pressure_coverage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_stage849_pressure_coverage_after_download_stage856_stage855_remaining_gap_download_v1.csv`
- remaining_gap_requests：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage856_stage855_remaining_gap_download_remaining_gap_requests_stage856_stage855_remaining_gap_download_v1.csv`

## 结论

- 本阶段结论：Stage856 没有新增任何分钟K覆盖；Stage855 后的覆盖状态保持不变。
- 是否允许新规则：否。
- 是否允许新引擎：否。
- 原因：剩余缺口中包含 `6` 个 big-winner requests 和 `6,434,115` 绝对 PnL 影响，且压力关键日期仍缺 `7/19`。在 exact contract/date 视觉证据不完整时继续写入场/出场规则，会把分钟级研究变成片段化拟合。
- 下一步：
  - 若开通 TqSdk 历史下载权限，直接重跑 Stage856 或按 `BATCH_OFFSET/MAX_BATCHES` 分批跑。
  - 若不能开通权限，转向替代数据源或继续扫描本机已有 raw/source；优先补 `FG209/fu2205/fu2209/rb2210/FG601/AP210/lc2401`。
  - 补数完成前，只允许做覆盖审计、数据源路由、图谱重绘准备，不写新的交易规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做数据权限和覆盖审计，没有根据结果修改规则、阈值、品种或方向。真正的过拟合风险在于忽略数据缺口，直接用已覆盖的 `251/341` 笔和局部压力图谱设计新规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：仍有价值，但路径收窄。
- 原因：Stage856 把阻塞从“脚本是否能下载”明确收敛为“账号历史下载权限不足”。继续价值不在重复跑同一权限失败，而在开通权限、找替代分钟源，或对已覆盖样本做明确标注的局部只读复盘；全周期规则验证必须等关键缺口恢复。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否；本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是数据权限边界，不是策略突破或正式候选变更。
