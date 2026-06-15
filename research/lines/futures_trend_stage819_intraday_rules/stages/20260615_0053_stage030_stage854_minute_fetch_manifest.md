# Stage030 Stage854 分钟K补数清单与本地raw预检

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 00:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：数据补齐预检；不下载数据、不改策略、不接引擎、不连接 CTP、不调用下单
- 是否重要突破：否。属于数据管道关键进展，不是策略 alpha 突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk 官方 `DataDownloader` 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - TqSdk 官方 `get_kline_serial` 文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.api.TqApi.get_kline_serial`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
  - vn.py TQSDK 数据服务 GitHub：`https://github.com/vnpy/vnpy_tqsdk`
- 我的判断：
  - `DataDownloader` 明确用于历史行情下载和导出 CSV，更适合 exact contract/date 分钟K补数。
  - `get_kline_serial` 更适合近端/实时序列引用，文档也强调序列随时间推进自动更新；不应作为本次全周期缺口补数主路径。
  - GitHub 上现有 TqSdk 与 vn.py TQSDK 路径可复用，但旧合约、权限、空文件必须记录为数据阻断，不能解释成策略现象。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage854_stage853_minute_fetch_manifest.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `RAW_FILE_PATTERNS = ("{symbol}_minute*.csv",)`
  - `DOWNLOAD_START_HOUR = 20`
  - `DOWNLOAD_END_HOUR = 3`
  - `MAX_BATCH_GAP_DAYS = 7`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage825/849/853 既有缺口请求，覆盖 Stage819 2018-01-01 至 2026-05-29 全周期交易缺口
- 账户规模：不适用，本阶段不跑策略回测
- 成本口径：不适用，本阶段不跑交易
- 样本过滤：
  - 输入为 Stage853 `126` 个 exact contract/date gap requests
  - 本地 raw 目录只扫描 `downloaded_futures/*/<exchange>/<symbol>_minute*.csv`
- 策略/归因口径：
  - exact 合约当天有 raw minute bars：标记为 `local_raw_import_candidate`
  - exact 合约有 raw 文件但缺当天：标记为需补 exact contract/date
  - exact 合约无 raw 文件：标记为需补 full symbol/date
  - 不允许使用同产品其他合约替代 exact 合约路径

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
  - gap symbols：`80`
  - 本地 raw 可恢复 requests：`29`
  - 本地 raw 可恢复 symbols：`18`
  - 仍需下载 requests：`97`
  - 仍需下载 symbols：`65`
  - 下载批次：`84`
  - 本地 raw 可恢复缺口绝对 PnL：`9,378,200`
  - 仍需下载缺口绝对 PnL：`6,434,115`
  - 本地 raw 可恢复 big-winner requests：`2`
  - 仍需下载 big-winner requests：`6`
  - 命中 raw 的目录数：`3`
  - 有 raw 文件但日期不对的 symbols：`14`
  - raw 命中目录：
    - `tqsdk_stage452_true_path_fallback_1455`：覆盖 required dates `14`
    - `tqsdk_stage504_next_real_open_fallback_backfill`：覆盖 required dates `13`
    - `tqsdk_stage506_next_real_forward_risk_signal_frontier`：覆盖 required dates `9`
  - 本地可恢复高影响样例：
    - `ru2501.SHFE` `2024-09-12`，`2,097,600`，raw bars `136`
    - `hc2210.SHFE` `2022-07-07`，`1,430,310`，big winner `1`，raw bars `345`
    - `fu2205.SHFE` `2022-03-25`，`790,000`，raw bars `136`
    - `ru2605.SHFE` `2026-02-13`，`532,500`，big winner `1`，raw bars `225`
    - `fu2209.SHFE` `2022-05-06`，`526,680`，raw bars `225`
  - 仍需下载高影响样例：
    - `rb2210.SHFE` `2022-07-07`，`1,174,250`，big winner `1`
    - `FG601.CZCE` `2025-11-05`，`950,000`，big winner `1`
    - `fu2205.SHFE` `2022-03-30,2022-04-01`，`945,640`
    - `AP210.CZCE` `2022-04-06`，`861,560`
    - `lc2401.GFEX` `2023-11-07`，`652,050`
    - `fu2209.SHFE` `2022-05-27,2022-05-31`，`524,280`

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_report_stage854_stage853_minute_fetch_manifest_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_summary_stage854_stage853_minute_fetch_manifest_v1.csv`
- request_preflight：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_request_preflight_stage854_stage853_minute_fetch_manifest_v1.csv`
- local_import_manifest：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_local_import_manifest_stage854_stage853_minute_fetch_manifest_v1.csv`
- download_batch_manifest：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_download_batch_manifest_stage854_stage853_minute_fetch_manifest_v1.csv`
- symbol_preflight：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_symbol_preflight_stage854_stage853_minute_fetch_manifest_v1.csv`
- raw_root_summary：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_raw_root_summary_stage854_stage853_minute_fetch_manifest_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage854_stage853_minute_fetch_manifest_decision_stage854_stage853_minute_fetch_manifest_v1.json`

## 结论

- 本阶段结论：`stage854_local_raw_partial_recovery_then_download_manifest_no_rule`
- 是否进入下一步：是，但只进入数据补齐，不进入策略规则。
- 下一步：
  - 先把 `local_import_manifest` 中的本地 raw minute bars 合并为本研究线专用分钟源。
  - 再对 `download_batch_manifest` 里仍缺的 exact contract/date 用 TqSdk `DataDownloader` 补数。
  - 补完后重跑 Stage825/849 的覆盖表和 K线 atlas；仍不直接写新规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只处理数据覆盖和下载路径，没有选择交易规则、阈值、品种、年份或方向；发现 raw 可恢复只说明数据合并管道不完整，不构成策略解释。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段把 Stage853 的 `126` 个缺口拆成 `29` 个本地可恢复和 `97` 个仍需下载，能先恢复约 `9,378,200` 绝对 PnL 影响的分钟证据，避免重复下载；但继续价值仍限于补数据和重画图谱，不能跳到规则开发。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与 Stage030 后续规划。
- 是否更新 `research/registry.md`：否，非正式候选、非路线废弃、非跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是策略突破。
