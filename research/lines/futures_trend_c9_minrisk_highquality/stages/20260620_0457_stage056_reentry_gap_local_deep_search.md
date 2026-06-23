# Stage056 reentry gap local deep search

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 04:57 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读数据工程审计；不是 true engine，不是交易规则，不改正式配置。
- 是否重要突破：否；本地深搜基本反证“已有文件可补齐剩余缺口”。
- 是否触发A/B：否；`candidate_like=false`，不需要读取 `skills/version-ab-experiment/SKILL.md`。

## 外部调研与判断

- 参考资料：
  - TqSdk `DataDownloader` 文档：https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.tools.download.html
  - TqSdk 介绍：https://doc.shinnytech.com/tqsdk/latest/intro.html
  - vn.py `BarGenerator` tick-to-minute 逻辑：https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py
  - vn.py issue #2883：https://github.com/vnpy/vnpy/issues/2883
- 我的判断：TqSdk 官方文档确认历史数据可按 `dur_sec=60` 下载 1 分钟 K、`dur_sec=0` 下载 tick；vn.py 当前 BarGenerator 明确维护 close、volume、open_interest，历史 issue 也说明零 close/volume/OI 可能是生成问题。本阶段应该优先做剩余重入缺口的数据覆盖审计和下载清单，不能把本地文件是否 ready 当作交易信号。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage056_reentry_gap_local_deep_search.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 扫描目录：`examples/portfolio_backtesting/downloaded_futures/**/*.csv`
  - 样本：Stage055 剩余 no-ready reentry events。
  - ready 标准：exact reentry bar 存在，且 `high-low>0`、`volume>0`。
  - download manifest：每个未修复事件给出 `dur_sec=60` 主下载和 `dur_sec=0` fallback tick 下载建议。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage055 剩余 `20` 个 C9 reentry no-ready 事件，覆盖 `2018-2025`。
- 账户规模：`150,000`
- 成本口径：沿用 Stage054/055 官方 C9/15w 曲线，不新增交易、不重算滑点。
- 样本过滤：只读扫描 Stage055 best-source 仍 `ohlcv_ready=0` 的事件。
- 策略/归因口径：按合约代码在本地所有 downloaded_futures CSV 中深搜，区分 `no_candidate_file`、`not_minute_no_bar_datetime`、`no_exact_bar`、`exact_zero_range_or_volume`、`exact_ohlcv_ready`。

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
- 本地深搜：
  - 输入缺口事件：`20`
  - 相关本地 CSV 扫描文件：`73`
  - 扫描记录：`77`
  - 新增本地 OHLCV-ready：`1`
  - 新增 ready reentry PnL：`-5,760.00`
  - 仍未修复：`19`
  - 仍未修复 reentry PnL：`+975,455.00`
  - 仍未修复正收益：`+1,012,790.00`
  - 仍未修复亏损绝对值：`37,335.00`
  - 最大未修复右尾：`FG601.CZCE`，`2025-11-05 09:07:00`，reentry PnL `+950,000.00`
- 源质量：
  - `tqsdk_stage461_completed_preclose_full_dates_probe` 仅修复 `lh2109.DCE` 1 笔，PnL `-5,760.00`。
  - `tqsdk_stage859_stage856_remaining_gap_backfill` 对 `19` 个事件有文件、`18` 个 exact bar，但 OHLCV-ready 为 `0`，主要是 exact zero range / zero volume。
  - Tushare `2015-2019` 文件是日线，不含 `bar_datetime`，不能用于重入分钟 OHLCV。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_report_stage056_reentry_gap_local_deep_search_v1.md`
- decision：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_decision_stage056_reentry_gap_local_deep_search_v1.json`
- source scan：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_source_scan_stage056_reentry_gap_local_deep_search_v1.csv`
- event best：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_event_best_stage056_reentry_gap_local_deep_search_v1.csv`
- source summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_source_summary_stage056_reentry_gap_local_deep_search_v1.csv`
- download manifest：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_download_manifest_stage056_reentry_gap_local_deep_search_v1.csv`
- contribution curve：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_gap_contribution_curve_stage056_reentry_gap_local_deep_search_v1.csv`
- path chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_gap_path_chart_stage056_reentry_gap_local_deep_search_v1.png`
- source chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_source_gap_chart_stage056_reentry_gap_local_deep_search_v1.png`
- event chart：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage056_reentry_gap_local_deep_search/qmt_roll_stage056_c9_minrisk_reentry_gap_local_deep_search_event_gap_chart_stage056_reentry_gap_local_deep_search_v1.png`

## 视觉分析

- path chart：绿色“本地新增修复”几乎贴近 0 且为负，红色“仍未修复”到 `2025` 因 `FG601.CZCE` 一笔跃升到约 `+97.5万`。说明剩余缺口主要是右尾数据缺口，不能把 missing/ready 状态当坏信号。
- event chart：唯一绿色本地修复是 `lh2109.DCE` 小亏损；红色未修复事件里 `FG601.CZCE +950,000` 远大于其他事件，属于必须优先补的右尾样本。
- source chart：Stage859/856 能对上大量 exact bar，但几乎都是零 range / 零 volume；Stage461 只补到 1 个真实 OHLCV。已有本地 CSV 不能解决剩余重入质量规则的数据基础。

## 结论

- 本阶段结论：`stage056_local_deep_search_no_additional_robust_trade_rule`。
- 是否进入下一步：进入数据下载/回填准备，不进入 true engine 或 A/B。
- 下一步：
  - 按 `download_manifest` 优先补 `FG601.CZCE 2025-11-05 09:07`，其次补 `jm2101/MA909/MA005` 等正贡献缺口，再补 2018/2019 全部零量 exact bar。
  - 下载优先 `dur_sec=60` full-session minute；如果仍 zero range/volume，则退到 `dur_sec=0` tick 并用 BarGenerator 语义重建分钟 OHLCV。
  - 覆盖补齐前，不允许把 OHLCV-ready、source、zero volume、local missing、event-year 或单合约缺口写成规则。

## 过拟合反思

- 运行前判断：过拟合风险低。只做全仓库本地源覆盖扫描和下载清单，不新增阈值、规则或样本切片。
- 运行后判断：不过拟合，但必须警惕把 coverage 当 alpha。新增 ready 只有 1 笔且为亏损，未 ready 反而净右尾。
- 原因：本阶段证明的是数据完整性，不证明任何交易质量；视觉图显示缺口状态与收益方向相反，交易化会变成数据缺失偏差。

## 继续价值反思

- 运行前判断：有价值。Stage055 发现 Stage491/459/462 可以修复一部分 exact OHLCV，本阶段检验本地是否还有未纳入的可用源。
- 运行后判断：仍有价值，但继续方向更窄：必须按 manifest 下载/重建真实 OHLCV，而不是继续在已有 CSV 中找规则。
- 原因：本地深搜只修复 `1/20`，剩余 `19` 个仍有 `+975,455` reentry PnL，尤其 `FG601.CZCE` 单笔 `+950,000`。不补这些样本，任何重入当刻 OHLCV 规则都可能系统性误杀右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage056 摘要与下一步边界。
- 是否更新 `research/registry.md`：否；不是正式候选、路线合并或全局重要突破。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段仍是本线数据工程审计。
