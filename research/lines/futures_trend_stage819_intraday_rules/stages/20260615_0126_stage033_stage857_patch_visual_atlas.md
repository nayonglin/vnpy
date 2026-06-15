# Stage033 Stage857 Stage855新增覆盖分钟K视觉图谱

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 01:26 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读视觉复盘与特征重算
- 是否重要突破：否
- 是否触发A/B：否；本阶段不改策略、不接引擎、不连接 CTP、不调用下单

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 官方文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.tools.download.html`
  - TqSdk `get_kline_serial` 官方文档：`https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html#tqsdk.api.TqApi.get_kline_serial`
  - vn.py TQSDK 网关 GitHub：`https://github.com/vnpy/vnpy_tqsdk`
- 我的判断：
  - Stage856 已确认历史分钟K下载受账号权限阻断，因此本阶段不重复下载。
  - Stage855 已恢复的本地 raw patch 必须转成可审计图谱，否则覆盖率改善无法服务“逐笔 + K线视觉分析”的目标。
  - 本阶段只能整理新增视觉证据，不能从 `24` 笔新增 entry-day 样本反推阈值或新规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage857_stage855_patch_visual_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `PER_ENTRY_PAGE = 6`
  - `PATCH_ENTRY_ATLAS_TEMPLATE`
  - `PATCH_PRESSURE_ATLAS_PATH`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 输入：
  - Stage855 patch minute bars
  - Stage855 request coverage after patch
  - Stage855 Stage849 pressure coverage after patch
  - Stage825 closed lots
  - Stage849 minute features
- 图谱口径：
  - entry-day lot atlas：只画 Stage855 新增覆盖的 `stage825_entry_day` lots。
  - pressure key-date atlas：只画 Stage855 新增覆盖的 Stage849 pressure key dates。
  - 分钟K来自既有 Stage825 源 + Stage855 patch 合并去重，patch 对同一 `vt_symbol/bar_datetime` 优先。
- 本阶段不接真实交易引擎，不构造 A/C 策略版本。

## 结果

- 决策：`stage857_stage855_patch_visual_atlas_no_rule`
- patch_minute_bars：`7,236`
- patch_entry_lots：`24`
- patch_entry_big_winner_lots：`2`
- patch_entry_pnl_sum：`1,440,860`
- patch_pressure_key_dates：`5`
- patch_pressure_minute_bars：`1,067`
- entry_atlas_pages：`4`
- pressure_atlas_pages：`1`
- stage856_permission_blocked_batches：`84`
- new_rule_allowed：`0`
- engine_allowed：`0`

## 新增 entry-day 数据观察

- `1R target_first` 桶：`9` 笔，PnL 合计 `3,960,340`，胜率 `66.6667%`，含 `1` 个 big winner。
- `1R stop_first` 桶：`12` 笔，PnL 合计 `-2,025,560`，胜率 `25.0000%`，但也含 `1` 个 big winner。
- `0.5R stop_first` 桶：`13` 笔，PnL 合计 `-1,485,090`，胜率 `30.7692%`，同样含 `1` 个 big winner。
- `fail_fast_30m_05r=1` 桶：`10` 笔，PnL 合计 `-1,499,470`，胜率 `20.0000%`，但仍含 `1` 个 big winner。
- 判断：新增样本继续支持“快速止损能捕捉左尾，但不能简单 no-retry/fail-fast”，因为局部 stop-first/fail-fast 桶里仍有大赢家。

## 新增压力 key-date 视觉观察

- 新增覆盖的压力 key dates 共 `5` 个：
  - `fu2205.SHFE 2022-03-25`
  - `fu2209.SHFE 2022-04-18`
  - `fu2209.SHFE 2022-04-19`
  - `fu2209.SHFE 2022-05-06`
  - `fu2209.SHFE 2022-05-09`
- `fu2209 2022-04-18`：directional close `-2.6588%`，intraday adverse `-3.6000%`，range `4.3202%`。
- `fu2209 2022-04-19`：directional close `-3.6043%`，intraday adverse `-4.3783%`，range `5.9954%`。
- `fu2209 2022-05-06`：directional close `0.4646%`，intraday adverse `-0.7898%`，range `2.3882%`。
- `fu2209 2022-05-09`：只剩 `16` 根分钟K，directional close `-0.9533%`，不能独立解释全段。
- 判断：新增 `fu` 压力图谱强化了“部分压力段是持仓后日内/隔夜连续不利路径，而非单纯入场分钟确认问题”的证据；但 `fu2205 2022-03-30/04-01`、`fu2209 2022-05-27/31`、`FG209 2022-05-24/27/06-02` 仍缺，不能宣称压力段视觉证据完整。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_report_stage857_stage855_patch_visual_atlas_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_summary_stage857_stage855_patch_visual_atlas_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_decision_stage857_stage855_patch_visual_atlas_v1.json`
- patch_entry_features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_patch_entry_lot_features_stage857_stage855_patch_visual_atlas_v1.csv`
- patch_entry_bucket_stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_patch_entry_bucket_stats_stage857_stage855_patch_visual_atlas_v1.csv`
- patch_pressure_features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_patch_pressure_features_stage857_stage855_patch_visual_atlas_v1.csv`
- entry atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_entry_atlas_manifest_stage857_stage855_patch_visual_atlas_v1.csv`
- pressure atlas manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_pressure_atlas_manifest_stage857_stage855_patch_visual_atlas_v1.csv`
- entry atlas pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_entry_atlas_page001_stage857_stage855_patch_visual_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_entry_atlas_page002_stage857_stage855_patch_visual_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_entry_atlas_page003_stage857_stage855_patch_visual_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_entry_atlas_page004_stage857_stage855_patch_visual_atlas_v1.png`
- pressure atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage857_stage855_patch_visual_atlas_pressure_key_dates_stage857_stage855_patch_visual_atlas_v1.png`

## 质量检查

- `py_compile`：通过。
- Stage857 运行完成，生成 `13` 个输出文件。
- PNG 尺寸检查：
  - entry atlas 4 页均为 `2700 x 2790`
  - pressure atlas 为 `2700 x 2400`
- 运行中只出现 TqSdk 免责声明，这是既有模块导入链副作用；Stage857 不调用下载、交易或下单 API。

## 结论

- 本阶段结论：`stage857_stage855_patch_visual_atlas_no_rule`。
- 是否允许新规则：否。
- 是否允许新引擎：否。
- 原因：新增视觉证据有用，但仍是局部补强；剩余 `97` 个 exact contract/date gap requests、`6` 个 big-winner requests 和多个压力关键日期未补齐。
- 下一步：
  - 若数据权限可解决，继续补数并重跑全量 Stage825/849 图谱。
  - 若权限暂不可解决，可以只做“已覆盖样本 vs 未覆盖样本”的偏差审计，判断当前图谱是否系统性偏向某些年份/品种/胜负类型；仍不写交易规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做已恢复分钟K的可视化和统计整理，没有修改规则、阈值、品种或方向。真正的过拟合风险是拿这 `24` 笔新增 entry-day 覆盖直接调 `R` 倍数、OR 窗口或重试次数。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但仍受数据缺口约束。
- 原因：Stage857 把 Stage855 的覆盖改善转成了可读图谱，能继续服务人工逐笔复盘；但全周期规则验证仍依赖剩余关键分钟K补齐或偏差审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否；本阶段不是正式候选、重要突破或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是视觉证据补强，不是策略突破或正式候选变更。
