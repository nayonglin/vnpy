# Stage035 Stage859 TqBacktest补齐Stage856剩余分钟K缺口

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 02:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据补齐与替代源侦察，不是策略回测
- 是否重要突破：否，属于本研究线数据通路突破，但不是策略收益突破或正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - TqSdk `TqBacktest + get_kline_serial(..., duration_seconds=60)` 历史回放路径。
  - AKShare `futures_zh_minute_sina(symbol, period='1')` 新浪期货分钟线接口。
  - 本仓库既有 Stage445/446/448/456 记录：`DataDownloader` 历史下载权限被阻断，但 `TqBacktest` 历史回放路径曾可取得分钟K。
- 我的判断：
  - Stage856 的失败不是“历史分钟K不可得”，而是 `DataDownloader` 专业版下载权限阻断。
  - AKShare/Sina 能返回部分老合约分钟线，但实测多为合约后段约 `1023` 根，对 Stage856 早期入场日缺口覆盖为 `0`，不能作为主补数源。
  - `TqBacktest + get_kline_serial(60)` 是当前账户下最可行的补数路径；本阶段已用它完整覆盖 Stage856 剩余 exact contract/date 缺口。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE859_MAX_BATCHES`：默认 `25`，本次最终用 `0` 表示全量 batches。
  - `STAGE859_ENABLE_TQSDK_BACKTEST`：默认 `1`。
  - `STAGE859_MAX_SECONDS_PER_BATCH`：默认 `75`。
  - `STAGE859_AKSHARE_MAX_SYMBOLS`：默认 `8`。
  - `STAGE859_MINUTE_BAR_MIN_COUNT`：默认 `10`，低于该值不视为分钟覆盖。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage856 剩余 exact contract/date 缺口。
- 账户规模：不适用，本阶段不跑组合回测。
- 成本口径：不适用，本阶段只补分钟K证据。
- 样本过滤：
  - 输入请求：Stage856 remaining gap requests `97` 个。
  - 输入 batch：按 `(vt_symbol, required_date)` 去重后 `91` 个。
  - 覆盖判定：目标日期分钟K根数 `>=10`。
- 策略/归因口径：
  - 本地非日线 cache 扫描。
  - AKShare/Sina 小样本覆盖探测。
  - TqSdk `TqBacktest + get_kline_serial(60)` 全量补抽。

## 结果

- 期末权益：不适用，本阶段不是回测。
- 总收益：不适用，本阶段不是回测。
- 最大回撤：不适用，本阶段不是回测。
- Sharpe：不适用，本阶段不是回测。
- 总滑点：不适用，本阶段不是回测。
- 总交易次数：不适用，本阶段不是回测。
- 胜率：不适用，本阶段不是回测。
- 其他关键指标：
  - Stage856 剩余请求：`97`。
  - Stage856 剩余 batches：`91`。
  - TqBacktest 抽取：`91/91` 成功，失败 `0`。
  - Stage859 覆盖请求：`97/97`。
  - Stage859 覆盖 entry-day 请求：`90/90`。
  - Stage859 覆盖 pressure key date 请求：`7/7`。
  - 覆盖 priority abs PnL：`6,434,115`。
  - 覆盖 big-winner requests：`6`。
  - 新增分钟K：`31,118` 根。
  - 覆盖 unique symbols：`65`。
  - 目标日期最少分钟K根数：`225`。
  - 本地非日线 cache 新增覆盖：`0`。
  - AKShare/Sina 探测可覆盖目标日期：`0`。
  - 决策：`stage859_tqsdk_backtest_gap_backfill_full_success_no_rule`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_report_stage859_stage856_tqsdk_backtest_gap_backfill_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_summary_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_batch_plan_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_source_readiness_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_local_cache_scan_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_akshare_probe_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_tqsdk_extract_status_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_minute_bars_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_request_coverage_after_stage859_stage859_stage856_tqsdk_backtest_gap_backfill_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage859_stage856_tqsdk_backtest_gap_backfill_decision_stage859_stage856_tqsdk_backtest_gap_backfill_v1.json`
  - raw cache：`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage859_stage856_remaining_gap_backfill/`

## 结论

- 本阶段结论：
  - Stage034 的“补数阻断”已被数据通路层解除：Stage856 剩余 `97/97` 请求均已由 TqBacktest 补到分钟K。
  - 这仍不是交易规则证据；必须先做 Stage860，把 Stage859 raw 统一导入，重算 Stage825 entry-day 覆盖、Stage849 pressure key date 覆盖，并重画全量/新增图谱。
  - AKShare/Sina 对本次关键缺口不适合作为主补数源；RQData 当前未见凭证，暂不进入主路径。
- 是否进入下一步：是。
- 下一步：
  - Stage860：导入 Stage859 raw minute bars，重算覆盖偏差。预期应从 Stage855 的 `251/341` 提升到 `341/341`，Stage849 pressure key dates 从 `12/19` 提升到 `19/19`，但必须用脚本验证，不能只凭 Stage859 请求覆盖推断。
  - Stage861：基于完整分钟K重画 entry-day 全量图谱和 pressure path 图谱，再决定是否恢复规则假设研究。
  - 在 Stage860/861 前仍不写新日内交易规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只解决 exact contract/date 数据缺口，不按收益结果选择规则、不调参数、不做交易策略优化。补数会减少选择偏差，而不是制造过拟合。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是，且价值显著提高。
- 原因：Stage859 把 Stage034 的核心阻断从“缺分钟K导致无法全周期判断”推进到“已有完整 raw，待导入重算和视觉复盘”。继续做 Stage860/861 有直接价值；此时仍不应跳过数据验证直接写规则。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线数据通路进展，不是策略突破或正式候选。
