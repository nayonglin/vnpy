# Stage157 当前重建版 C9 stop/retry 归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-07-01 00:36 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：延续 Stage156 三臂基准，对当前重建版 `Stage847/C9` 相对 `Stage819/C4` 的 `0.5R stop/retry once` 边际做只读事件归因。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮按用户此前“不要搜索”的约束不做外网/GitHub搜索；只使用本仓 Stage156、Stage847、Stage830、Stage901 现有回测引擎。
- 我的判断：本阶段不是写新规则，而是解释 Stage156 里 C9 为什么收益/Sharpe 强、但回撤不稳定。只有先看清 C9 边际来自事件当天还是后续路径，后续优化才不会落回 R 倍数、重试次数、品种/年份黑名单扫描。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution.py`
- 修改脚本：
  - 同一新脚本内修正事件日期归一化：保留本地事件墙钟日期，只移除时区；避免夜盘事件转 UTC 后错配 daily delta。
- 删除脚本：无
- 新增参数：无策略参数；新增只读归因输出。
- 修改参数：无策略参数修改。
- 删除参数：无。

## 运行中发现的归因脚本问题

- 初版把事件 `datetime` 统一转 UTC 再去时区，导致部分夜盘/带时区事件日期错配 daily delta，产品聚合中出现 `NaN`。
- 修复后使用本地墙钟日期：`tz_localize(None).normalize()`。
- 修复后 stop/retry event day 从 `121` 天变为 `169` 天，说明初版归因确实漏匹配了事件日。
- 判断：这是 Stage157 归因脚本 bug，不是策略逻辑 bug，也不影响 Stage156 三臂回测指标。

## 回测/归因口径

- 统一资金：`150,000`
- 统一 AI 池：当前 Stage182 combined eligibility 文件
- 起点：`2018-01` 到 `2026-01`，每年 1 个独立冷启动起点
- 终点：`2026-06-30`
- 对比：
  - C4：Stage819 + C2 entry-day 1R stop + broker10 cap
  - C9：C4 + entry-day `0.5R` stop/retry once
- 输出：
  - C4/C9 起点对比
  - C9 stop/retry 事件明细
  - C9-C4 daily delta
  - 按 `final_state`、产品、方向聚合的事件日 proxy
- 注意：事件日 `net_pnl_delta` 是只读 proxy，不是逐笔因果；C9 会改变后续持仓、权益分母、sizing 和复利路径。
- 不连接 CTP，不读取账户，不调用订单 API。

## 结果

### 起点对比

- C9 收益胜 C4：`8/9`
- C9 回撤胜 C4：`4/9`
- C9 Sharpe 胜 C4：`8/9`
- C9 stop/retry 事件数：`171`
- C9 stop/retry 事件日：`169`
- C9 相对 C4 的年度起点收益差合计 proxy：`5939.4801pp`
- C9-C4 event day `net_pnl_delta` 合计 proxy：`-189,534.4`
- C9-C4 non-event day `net_pnl_delta` 合计 proxy：`+9,098,754.6`

解释：C9 的优势不是“stop/retry 事件当天直接赚钱”。事件当天整体略亏，真正的大部分收益差来自事件之后的路径改变、仓位保留/重开、权益分母和后续 sizing/复利参与。

### Stop/Retry 状态聚合

| final_state | 事件数 | volume | reentered | retry_failed | event day net pnl delta proxy | event day median delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `flat_no_reentry` | `77` | `2710` | `0` | `0` | `-109,882.6` | `675.0` |
| `open_after_reentry` | `58` | `2982` | `58` | `0` | `+61,025.0` | `-1,395.0` |
| `flat_retry_failed` | `36` | `1169` | `36` | `36` | `-141,271.8` | `-435.0` |

解释：
- `flat_no_reentry` 是最常见状态，事件日合计略负，但中位为正；说明它不是单纯坏规则，也不能直接废掉。
- `open_after_reentry` 是 C9 的核心右尾机制之一，事件日合计为正，但中位为负；它的价值更可能来自少数后续大路径，而不是稳定当天收益。
- `flat_retry_failed` 事件日合计为负，是明显需要继续追的左尾标签；但历史 Stage050 已反证二次重试，不能直接扫重试次数救它。

### 产品/方向线索

- `lh.DCE long open_after_reentry`：`15` 次，是最多的 reentry 状态；事件日 proxy 合计 `-46,210`，但这只是当天 proxy，仍需看后续路径。
- `FG.CZCE short open_after_reentry`：`8` 次，事件日 proxy `+433,370`，是较强正贡献线索。
- `SH.CZCE long flat_no_reentry`：`8` 次，事件日 proxy `-549,380.1`，是明显风险标签。
- `fu.SHFE long flat_retry_failed`：`5` 次，事件日 proxy `-114,300`，属于 retry_failed 左尾标签。
- `OI.CZCE long flat_retry_failed`：`4` 次，事件日 proxy `+121,180`，说明同为 retry_failed，也不能机械归为坏事件。

解释：产品/方向聚合只能作为风险定位，不足以生成黑名单。相同状态在不同产品上表现差异很大，真正可推广的下一步应追“事件发生时的账户/持仓压力状态”和“后续路径”，不是产品过滤。

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_summary_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_comparison_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- daily_delta：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_daily_delta_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- stop_retry_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_stop_retry_events_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- state_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_state_summary_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- product_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_product_summary_stage157_current_rebuild_c9_stop_retry_attribution_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_decision_stage157_current_rebuild_c9_stop_retry_attribution_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage157_current_rebuild_c9_stop_retry_attribution_report_stage157_current_rebuild_c9_stop_retry_attribution_v1.md`

## 结论

- C9 的 `0.5R stop/retry once` 仍然有价值：收益和 Sharpe 对 C4 的年度起点胜率均为 `8/9`。
- C9 的价值不是事件当天稳定赚钱，而是改变后续路径；这与 Stage156 的“收益增强但非低风险替代”一致。
- 当前最该追的是：
  1. `flat_retry_failed` 和 `SH long flat_no_reentry` 这类左尾标签发生时的账户/持仓压力状态；
  2. `open_after_reentry` 后续右尾路径来自哪些环境，而不是当天收益；
  3. C9 相对 C4 的 DD 扩大窗口，是否由权益分母压缩、broker10 热度、同产品方向压力簇共同造成。
- 不应直接做：
  - 二次重试；
  - 禁止某个产品/方向；
  - 按 `final_state` 机械阻断；
  - 调 `0.5R` 小数或重试次数。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只解释固定 C9/C4 差异，不改策略参数、不按结果选择年份、品种或方向。产品/方向结果只作为风险定位标签，不生成交易规则。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：归因显示 C9 优势主要来自后续路径而非事件当天，所以下一步应该转向账户/持仓层风险状态和事件后路径拆解；继续扫 C9 参数价值低。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等 C9/C4 回撤差压力窗口和账户状态归因补完后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是只读归因，不是正式候选变更或重要突破。
