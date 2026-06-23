# Stage057 reentry gap TqBacktest refill

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 05:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据工程回填审计；不是 true engine，不是交易规则，不改正式配置。
- 是否重要突破：是数据资产突破，不是策略突破。Stage056 剩余 no-ready 缺口已全部通过 tick fallback 重建为 ready。
- 是否触发A/B：否；`candidate_like=false`，不需要读取 `skills/version-ab-experiment/SKILL.md`。

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html
  - TqSdk `TqApi.get_kline_serial` / `get_tick_serial` 文档：https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html
  - TqSdk backtest 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html
  - vn.py `BarGenerator` tick-to-minute 逻辑：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
- 我的判断：仓库历史 Stage856 已证明 `DataDownloader` 受账号历史下载权限阻断，但 Stage859 已验证 `TqBacktest + get_kline_serial(60)` 可以补分钟缺口。本阶段进一步确认：对剩余 reentry exact bar，分钟线仍是零 range/零 volume；但 `TqBacktest + get_tick_serial` 可以重建重入当分钟真实 high/low/volume。这是数据基础修复，不是 alpha。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage057_reentry_gap_tqsdk_backtest_refill.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `STAGE057_MAX_EVENTS=0`：默认处理 Stage056 manifest 全量未修复事件。
  - `STAGE057_MAX_SECONDS_PER_EVENT=90`
  - `STAGE057_TICK_WINDOW_MINUTES=3`
  - `STAGE057_MINUTE_DATA_LENGTH=1000`
  - `STAGE057_TICK_DATA_LENGTH=12000`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：Stage056 剩余 `19` 个 no-ready reentry 事件，覆盖 `2018-2025`。
- 账户规模：`150,000`
- 成本口径：沿用 Stage054/055/056 官方 C9/15w 曲线，不新增交易、不重算滑点。
- 样本过滤：只处理 Stage056 `download_manifest` 中未修复的 `19` 个事件。
- 策略/归因口径：
  - 先用 `TqBacktest + get_kline_serial(60)` 抽 full-session minute。
  - 若 minute exact bar 仍非 OHLCV-ready，则用 `TqBacktest + get_tick_serial` 抽重入时点前后 tick。
  - 用目标分钟内 tick 的 `last_price` 重建 open/high/low/close，用累计 `volume` 差分估计 minute volume。
  - ready 标准仍为 `bar_range>0` 且 `volume_delta>0`。

## 结果

- 官方 A：
  - 期末权益：`39,176,437.60`
  - 总收益：`26017.6251%`
  - 最大回撤：`-45.0827%`
  - Sharpe：`1.6339`
  - 总滑点：`2,730,130`
  - 总交易次数：`787`
  - 胜率：`53.2560%`
  - broker10 峰值：`111.7365%`
- Stage057 回填：
  - TqSdk 凭证状态：本机 vn.py `datafeed.name=tqsdk`，username/password 均存在；阶段记录只保留长度和存在性，不记录明文。
  - 处理事件：`19`
  - minute exact ready：`19/19`
  - minute OHLCV ready：`0/19`
  - tick target rows：每事件 `58-120` 行。
  - tick rebuilt ready：`19/19`
  - final ready：`19/19`
  - final ready reentry PnL：`+975,455.00`
  - still unresolved：`0`
  - still unresolved PnL：`0.00`
- 关键样本：
  - `FG601.CZCE 2025-11-05 09:07`：tick rebuilt `open=1110/high=1111/low=1109/close=1109`，`tick_count=120`，`volume_delta=15531`，reentry PnL `+950,000`。
  - `jm2101.DCE 2020-11-26 13:37`：tick rebuilt range `1.5`、volume_delta `477`，reentry PnL `+27,300`。
  - `MA909.CZCE 2019-07-10 22:20`：tick rebuilt range `8`、volume_delta `17,795`，reentry PnL `+17,160`。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_report_stage057_reentry_gap_tqsdk_backtest_refill_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_decision_stage057_reentry_gap_tqsdk_backtest_refill_v1.json`
- event status：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_event_status_stage057_reentry_gap_tqsdk_backtest_refill_v1.csv`
- minute bars：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_minute_bars_stage057_reentry_gap_tqsdk_backtest_refill_v1.csv`
- tick rebuilt bars：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_tick_rebuilt_bars_stage057_reentry_gap_tqsdk_backtest_refill_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_refill_contribution_curve_stage057_reentry_gap_tqsdk_backtest_refill_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_refill_path_chart_stage057_reentry_gap_tqsdk_backtest_refill_v1.png`
- event chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_event_refill_chart_stage057_reentry_gap_tqsdk_backtest_refill_v1.png`
- status chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/qmt_roll_stage057_c9_minrisk_reentry_gap_tqsdk_backtest_refill_status_chart_stage057_reentry_gap_tqsdk_backtest_refill_v1.png`
- raw minute dir：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/raw_minute/`
- raw tick dir：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage057_reentry_gap_tqsdk_backtest_refill/raw_tick/`

## 视觉分析

- path chart：Stage056 的红色 unresolved 贡献在本阶段归零，全部转为蓝色 tick-ready refill PnL；蓝线最终为 `+975,455`，主要跃升来自 `2025` 的 `FG601`。这说明数据覆盖问题被修复，但也说明此前 unresolved 承载的是右尾，不可当坏信号。
- event chart：所有事件均为 tick-ready，但 reentry PnL 正负混杂，且 `FG601 +950,000` 单笔右尾显著高于其他事件。不能把 tick-ready、minute-not-ready 或重建状态当交易条件。
- status chart：最终状态只有 `tick_rebuilt_ready` 一类，说明本阶段解决了覆盖，但还没有形成区分好坏的结构。

## 结论

- 本阶段结论：`stage057_tqsdk_backtest_refill_data_audit_no_trade_rule`。
- 是否进入下一步：进入全量整合审计，不进入 true engine 或 A/B。
- 下一步：
  - 将 Stage055 已 ready 的 `34` 笔、Stage056 本地新增 ready 的 `1` 笔、Stage057 tick rebuilt 的 `19` 笔合并成 `54/54` reentry OHLCV ready 统一表。
  - 重新生成全量 reentry OHLCV scatter、年度/产品热图、资金贡献曲线和 atlas。
  - 只有在统一表上预声明、跨年跨品种、且不砍 `FG601/lh2301/sp2205` 这类右尾时，才允许考虑下一步只读交叉；仍不得直接写交易规则。

## 过拟合反思

- 运行前判断：过拟合风险低。本阶段只按 Stage056 manifest 全量补数据，不按盈亏挑样本，不新增交易阈值。
- 运行后判断：不过拟合，但有数据窥视风险。因为 tick-ready 覆盖了全部事件，状态本身没有区分力；如果后续围绕某几笔 PnL 设 range/volume 阈值，就会立刻进入过拟合。
- 原因：本阶段目标是把缺失 OHLCV 修成可审计数据，不是从结果反推规则；视觉图也显示右尾集中，必须保护而不是筛掉。

## 继续价值反思

- 运行前判断：有价值。Stage056 证明本地已有 CSV 无法补齐，必须尝试 tick fallback。
- 运行后判断：很有价值。`19/19` 缺口被 tick 重建补齐，stop/retry 当刻 OHLCV 分支的数据阻塞解除。
- 原因：此前 Stage031/032 的核心阻塞是重入当根 range/volume 全退化；现在可以构建 `54/54` 全量真实 OHLCV ready 表，下一步终于能做完整而非半覆盖的只读交叉。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage057 摘要与下一步边界。
- 是否更新 `research/registry.md`：否；不是正式候选、路线合并或全局重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否；虽是数据资产突破，但尚未形成策略候选或正式合入摘要。
