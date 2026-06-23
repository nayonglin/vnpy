# Stage128 Stage901 C9 分钟K注入修复与 Stage936/937 重算

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-23 13:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前实盘 live shadow/backtest 接线 bug 修复，以及 Stage936/937 修正版重算
- 是否重要突破：是，属于实盘 shadow/backtest 口径修复；不改变策略参数，但修正了 C9 分钟级 stop/retry 在 Stage901 包装入口没有历史分钟K的问题。
- 是否触发A/B：否。本阶段不引入新策略、不替换实盘版本、不调整参数。

## 外部调研与判断

- 新增外部调研：无。本阶段是本地代码审计和复现实验。
- 参考背景：Stage847/863/896/897/928 既有研究入口均会在运行前把 Stage861 全量分钟K加载到 `s827._GLOBAL_MINUTE_BY_SYMBOL`；Stage901 live wrapper 漏了这一步。
- 我的判断：用户质疑“一个事件都没有”是正确的。C9 历史版本本来有 stop/retry 事件；Stage937 初版显示 `intraday_only=0` 是 Stage901 包装入口没有注入分钟K导致的假阴性，不是市场真的没有触发。

## Bug 归因

- 现象：Stage937 初版显示 `intraday_only` 事件数 `0`，但 Stage863 历史 C9 stop_retry_events 在 `2020+` 有大量事件。
- 复现：对 Stage901 `_run_live_c9()` 跑 `2020-01-01 -> 2021-01-01`，hook 被调用 `62` 次，`enable_stage847_half_r_stop_retry=True`，持仓 state/layers 均存在，但 `minute_empty=62`，所以每次直接返回 `None`。
- 具体原因：Stage901 `_run_live_c9()` 复用 `s847._run_profile()`，但没有像 Stage847/896/928 主入口那样先设置 `s847.s827._GLOBAL_MINUTE_BY_SYMBOL`。
- 影响范围：
  - 影响 Stage901 包装入口下的历史 shadow/backtest 路径，以及依赖 `_run_live_c9()` 的 Stage936/937 统计。
  - 不等同于实盘 Stage904 盘中守护失效；Stage904 运行时读取实时 tick/分钟状态和 broker 持仓，不依赖 Stage901 的历史全量分钟K全局变量。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage937_c9_live_15w_stop_execution_stress.py`
- 新增逻辑：
  - Stage901 增加 `_load_stage861_full_minute_bars()` 和 `_ensure_c9_minute_bars()`。
  - 使用 Stage861 full minute bars 文件：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv`
  - 加载后写入 `s847.s827._GLOBAL_MINUTE_BY_SYMBOL`，并在 `_run_live_c9()` 结束后恢复原全局变量。
  - 增加内存 cache，避免 Stage936/937 多起点重跑时重复读 290MB 分钟K文件。
  - Stage901 report/decision 增加 `minute_audit`。
  - Stage937 dashboard 去掉旧硬编码文案 `intraday_only 本次事件数为 0`。
- 删除逻辑：无
- 策略参数改动：无

## 修复验证

- 修复前小窗口：`2020-01-01 -> 2021-01-01`
  - hook calls：`62`
  - enabled true calls：`62`
  - minute_empty：`62`
  - stop_retry_events：`0`
- 修复后同窗口：
  - intraday_events：`30`
  - c2_events：`3`
  - stop_retry_events：`27`
  - 已重新出现 `rb2005.SHFE` 2020-01-09 long 0.5R stop/retry 事件，`first_stop_time=2020-01-09T09:01:00`
- minute audit：
  - requested_symbol_count：`782`
  - loaded_symbol_count：`220`
  - source_exists：`true`
  - 说明：`missing_symbol_count` 是全 metadata 合约全集与 Stage861 已覆盖分钟K合约集的差，不等于当前开仓样本缺分钟K。

## Stage936 修正版结果

- 当前实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 起点：从 `2020-01-01` 起，每年 `1月1日` 和 `7月1日`
- 数据终点：`2026-06-15`
- 账户规模：`150,000`
- AI 池：Stage182 月更 AI 池
- 样本：半年 `12` 个，一年 `11` 个
- 半年：
  - 最低收益 `-6.8463%`
  - 中位收益 `18.7133%`
  - 最高收益 `149.1644%`
  - 正收益 `11/12`
  - 最差起点 `2022-01`
  - 最差 horizon 内最大回撤 `-27.3710%`
- 一年：
  - 最低收益 `16.6550%`
  - 中位收益 `46.6351%`
  - 最高收益 `641.3979%`
  - 正收益 `11/11`
  - 最差起点 `2023-07`
  - 最差 horizon 内最大回撤 `-36.9546%`
- 对旧 Stage126 的修正：
  - 旧半年 `-26.42% / 13.58% / 157.86%` 作废
  - 旧一年 `-32.18% / 35.99% / 428.51%` 作废

## Stage937 修正版结果

- `intraday_only` 事件数：`203`
- `all_strategy_stop_close` 事件数：`400`
- `intraday_only` 半年：
  - 0 tick：最低 `-6.8463%`、中位 `18.7133%`、最高 `149.1644%`
  - 1 tick：最低 `-7.4996%`、中位 `18.1933%`、最高 `148.3977%`
  - 2 tick：最低 `-8.1529%`、中位 `17.6733%`、最高 `147.6311%`
  - 5 tick：最低 `-10.1129%`、中位 `16.1133%`、最高 `145.3311%`
- `intraday_only` 一年：
  - 0 tick：最低 `16.6550%`、中位 `46.6351%`、最高 `641.3979%`
  - 1 tick：最低 `16.4150%`、中位 `45.9717%`、最高 `638.4112%`
  - 2 tick：最低 `16.1750%`、中位 `45.3084%`、最高 `635.4245%`
  - 5 tick：最低 `15.4550%`、中位 `43.3184%`、最高 `626.4645%`
- `all_strategy_stop_close` 半年：
  - 0 tick：最低 `-6.8463%`、中位 `18.7133%`、最高 `149.1644%`
  - 1 tick：最低 `-7.7763%`、中位 `17.8933%`、最高 `147.8244%`
  - 2 tick：最低 `-8.7063%`、中位 `17.0733%`、最高 `146.4844%`
  - 5 tick：最低 `-11.4963%`、中位 `14.6133%`、最高 `142.4644%`
- `all_strategy_stop_close` 一年：
  - 0 tick：最低 `16.6550%`、中位 `46.6351%`、最高 `641.3979%`
  - 1 tick：最低 `15.6750%`、中位 `45.5217%`、最高 `635.0212%`
  - 2 tick：最低 `14.6950%`、中位 `44.4084%`、最高 `628.6445%`
  - 5 tick：最低 `11.7550%`、中位 `41.0684%`、最高 `609.5145%`
- 对旧 Stage127 的修正：
  - 旧 `intraday_only=0` 作废，修正为 `203`
  - 旧 `all_strategy_stop_close=376` 作废，修正为 `400`

## 输出文件

- Stage936 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_report_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.md`
- Stage936 stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_stats_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- Stage936 dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_dashboard_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.png`
- Stage937 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_report_stage937_c9_live_15w_stop_execution_stress_v1.md`
- Stage937 stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_stats_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- Stage937 events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_events_stage937_c9_live_15w_stop_execution_stress_v1.csv`
- Stage937 dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage937_c9_live_15w_stop_execution_stress_dashboard_stage937_c9_live_15w_stop_execution_stress_v1.png`

## 自动化影响判断

- Stage930/Stage903/Stage929 均通过 subprocess 启动子命令；下一轮会读取修复后的 Stage901 代码，不是常驻 import 旧 `_run_live_c9()`。
- 当前修复不调用 CTP、不读取账户、不调用订单 API。
- 这次修复不改变 Stage904/931 实盘盘中止损执行逻辑；它修正的是 Stage901 历史 shadow/backtest 的 C9 分钟K输入。
- 已手动刷新 Stage901 当前目标日：`--analysis-start 2026-06-16 --target-date 2026-06-22`，生成时间 `2026-06-23 13:56:37`，`minute_audit.source_exists=true`、`loaded_symbol_count=220`、订单 API `0`。刷新后 pending order 仍为 `rb2610.SHFE Short/Open 11 @ 3126`，说明修复没有让当前 rb 信号消失。

## 结论

- 本阶段结论：用户质疑成立，Stage937 初版“一个实时止损事件都没有”是 bug。修复后 `intraday_only=203`，说明 C9 分钟级止损/重进场事件确实在历史回放中存在。
- 是否进入下一步：是。下一步应把 Stage901 minute audit 作为 live shadow 必查项，并在后续报告/回测里确认 `intraday_events` 不再异常为 0。
- 下一步：如果今晚/明早自动化生成新报告，应检查 Stage901 decision 里 `minute_audit.loaded_symbol_count` 和 `intraday_events` 输出；真实 TCA 仍按 Stage120/931 final reprice 逻辑监控。

## 过拟合反思

- 运行前判断：否。问题是数据输入接线 bug，不是策略参数选择。
- 运行后判断：否。修复只恢复 C9 已冻结规则需要的分钟K输入；没有扫 R 倍数、重试次数、品种、方向或时间窗口。
- 原因：这是让回放语义与既有 Stage847/C9 设计一致，而不是用结果反推新规则。

## 继续价值反思

- 运行前判断：是。若 Stage901 live shadow 少跑 C9 分钟逻辑，会直接污染实盘报告、回测分布和执行压力评估。
- 运行后判断：是。修复后事件数、收益分布和压力结果全部改变，说明继续追查是必要的。
- 原因：当前 live 版本依赖 Stage901 作为报告/执行输入之一，shadow 口径必须和 C9 策略定义一致。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage128 修复摘要，并标注 Stage126/127 旧结果作废。
- 是否更新 `research/registry.md`：否。未改变路线状态或正式版本。
- 是否追加根目录 `memory.md/back_log.md`：否。本次是实盘 shadow/backtest 接线修复，但未切换正式版本；若后续发现真实报告信号因此变化，再写入重要合入摘要。
