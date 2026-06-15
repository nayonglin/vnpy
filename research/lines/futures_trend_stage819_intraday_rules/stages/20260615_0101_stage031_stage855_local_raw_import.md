# Stage031 Stage855 本地raw分钟K导入与覆盖重算

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 01:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据补齐；只导入本地 raw 中已存在的 exact contract/date 分钟K，不下载数据、不改策略、不接引擎、不连接 CTP、不调用下单
- 是否重要突破：否。属于证据覆盖改善，不是策略 alpha 突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 `DataDownloader` 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - TqSdk 官方 `get_kline_serial` 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.api.TqApi.get_kline_serial`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - vn.py TQSDK 数据服务 GitHub：`https://github.com/vnpy/vnpy_tqsdk`
- 我的判断：
  - 本轮只复用本地 raw，暂不下载；这是比直接下载更稳妥的第一步。
  - `DataDownloader` 仍是后续补剩余 exact contract/date 的合适路径。
  - `get_kline_serial` 不适合作为全周期缺口补数主路径。
  - 数据覆盖改善不能被解释为品种、年份或方向过滤证据；它只说明后续视觉法证可以更完整。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage855_stage854_local_raw_import.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `BAR_COLUMNS = ["vt_symbol", "tq_symbol", "bar_datetime", "bar_id", "open", "high", "low", "close", "volume", "open_oi", "close_oi"]`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage853/854 的 `126` 个 exact contract/date gap requests
- 账户规模：不适用，本阶段不跑策略回测
- 成本口径：不适用，本阶段不跑交易
- 样本过滤：
  - 输入为 Stage854 `local_import_manifest` 中的本地 raw 可恢复请求
  - 只抽取 raw CSV 中 `bar_datetime` 自然日期等于 `required_date` 的分钟K
  - 不使用同产品其他合约替代 exact 合约
- 策略/归因口径：
  - 生成本线专用 patch source：`stage855_patch_minute_bars`
  - 用 Stage853 gap detail + patch source 重算 request 覆盖
  - 用 Stage825 intraday features 重算全周期 closed lots 入场日覆盖
  - 用 Stage849 minute features 重算压力段 key date 覆盖

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - Stage853 gap requests：`126`
  - Stage855 patch 覆盖 requests：`29`
  - patch symbols：`18`
  - patch required dates：`26`
  - patch minute bars：`7,236`
  - patch 覆盖缺口绝对 PnL：`9,378,200`
  - patch 覆盖 big-winner requests：`2`
  - 仍需下载 requests：`97`
  - 仍需下载缺口绝对 PnL：`6,434,115`
  - 仍需下载 big-winner requests：`6`
  - Stage825 closed lots：`341`
  - Stage825 原入场日覆盖：`227/341 = 66.5689%`
  - Stage825 patch 后入场日覆盖：`251/341 = 73.6070%`
  - Stage825 覆盖增量：`24` 笔 closed lots
  - Stage849 压力 key dates：`19`
  - Stage849 原覆盖：`7/19 = 36.8421%`
  - Stage849 patch 后覆盖：`12/19 = 63.1579%`
  - Stage849 覆盖增量：`5` 个 key dates
  - 仍需下载批次：`84`
  - 年度覆盖变化：
    - 2018：`0/25`，仍全缺
    - 2019：`0/45`，仍全缺
    - 2020：`63/74 -> 66/74`
    - 2021：`55/61 -> 58/61`
    - 2022：`34/45 -> 40/45`
    - 2023：`25/28 -> 26/28`
    - 2024：`23/26 -> 26/26`
    - 2025：`22/25 -> 23/25`
    - 2026：`5/12 -> 12/12`
  - Stage849 新增覆盖 key dates：
    - `fu_long_20220325_0401`：`fu2205.SHFE 2022-03-25`
    - `fu_long_20220418_0419`：`fu2209.SHFE 2022-04-18/2022-04-19`
    - `fu_long_20220506_0509`：`fu2209.SHFE 2022-05-06/2022-05-09`
  - Stage849 仍缺 key dates：
    - `fg_short_20220524_0602`：`FG209.CZCE 2022-05-24/2022-05-27/2022-06-02`
    - `fu_long_20220325_0401`：`fu2205.SHFE 2022-03-30/2022-04-01`
    - `fu_long_20220527_0531`：`fu2209.SHFE 2022-05-27/2022-05-31`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_report_stage855_stage854_local_raw_import_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_summary_stage855_stage854_local_raw_import_v1.csv`
- patch_minute_bars：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_patch_minute_bars_stage855_stage854_local_raw_import_v1.csv`
- patch_date_summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_patch_date_summary_stage855_stage854_local_raw_import_v1.csv`
- request_coverage_after_patch：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_request_coverage_after_patch_stage855_stage854_local_raw_import_v1.csv`
- stage825_coverage_after_patch：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_stage825_coverage_after_patch_stage855_stage854_local_raw_import_v1.csv`
- stage825_year_coverage_after_patch：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_stage825_year_coverage_after_patch_stage855_stage854_local_raw_import_v1.csv`
- stage849_pressure_coverage_after_patch：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_stage849_pressure_coverage_after_patch_stage855_stage854_local_raw_import_v1.csv`
- remaining_download_manifest：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_remaining_download_manifest_stage855_stage854_local_raw_import_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage855_stage854_local_raw_import_decision_stage855_stage854_local_raw_import_v1.json`

## 结论

- 本阶段结论：`stage855_local_raw_patch_imported_coverage_improved_no_rule`
- 是否进入下一步：是，但仍只进入数据补齐，不进入策略规则。
- 下一步：
  - 按 Stage855 `remaining_download_manifest` 下载剩余 `97` 个 exact contract/date 缺口。
  - 下载后把 Stage855 patch source 和下载 source 一起作为额外分钟源，重跑 Stage825/849 覆盖和 K线 atlas。
  - 在 `FG209`、`fu2205`、`fu2209` 关键压力段补齐前，不写新的入场/出场规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只导入已存在的 exact 合约分钟K，没有根据收益结果筛选规则、阈值、品种、年份或方向；覆盖率提升只是证据更完整，不是策略有效性证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段显著提高了 Stage825 和 Stage849 的分钟K覆盖，尤其把 2022 多个 `fu` 压力段从缺证据推进到部分可视化；但 2018/2019 仍全缺，`FG209` 和部分 `fu` 压力段仍缺，必须继续补数后再做视觉法证。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与 Stage031 后续规划。
- 是否更新 `research/registry.md`：否，非正式候选、非路线废弃、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是策略突破。
