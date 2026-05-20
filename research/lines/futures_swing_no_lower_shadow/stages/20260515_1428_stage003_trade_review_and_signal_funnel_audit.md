# Stage003 交易复盘页与信号漏斗校验

- line_id：`futures_swing_no_lower_shadow`
- 当前模式：day
- 记录时间：2026-05-15 14:28 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：交易明细复盘与候选数量复核
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段是本地回测复盘产物检查，没有新增外部调研。
- 我的判断：
  - 用户质疑交易次数过少是合理的，必须先排除候选生成漏算，再继续讨论策略优劣。
  - 复核后看，少交易主要来自严格 `open == low` 且 `close > open` 连续两日这个定义本身，不是交易明细输出缺失。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_no_lower_shadow_swing_trade_review.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `LOOKBACK_BARS = 20`
  - `LOOKAHEAD_BARS = 20`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：继承 Stage001，2020-01-01 到 2026-04-30。
- 账户规模：500,000。
- 成本口径：继承 Stage001。
- 样本过滤：
  - HTML 复盘覆盖 Stage001 的 86 笔实际开仓回合。
  - 信号漏斗按 eligible 57 个品种、主力合约映射、回测同款合约 tick 重新扫描。
- 策略/归因口径：
  - 单根信号：按入场合约 tick 取整后 `open == low` 且 `close > open`。
  - 连续信号：前两根交易日均满足单根信号，第 3 个交易日作为潜在入场日。

## 结果

- 期末权益：`463,825`（Stage001 原始回测）
- 总收益：`-7.2350%`（Stage001 原始回测）
- 最大回撤：`-13.5818%`（Stage001 原始回测）
- Sharpe：`-0.4146`（Stage001 原始回测）
- 总滑点：`21,130`（Stage001 原始回测）
- 总交易次数：`207`（Stage001 原始回测）
- 胜率：`23.2558%`（Stage001 原始回测）
- 其他关键指标：
  - eligible 品种数：`57`
  - 可观察品种日：`75,751`
  - 单根严格无下影线上涨：`2,711`，占 `3.5788%`
  - 连续两根候选（持仓过滤前）：`119`
  - 信号两日到入场日同合约：`113`
  - Stage001 实际候选文件：`112`
  - 实际开仓：`86`
  - 跳过：`26`，其中 `risk_budget_below_one_contract` 17、`rollover_between_signal_and_entry` 6、`entry_open_not_above_stop` 3

## 输出文件

- trade_review_html：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_trade_review.html`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_candidates.csv`
- trades：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_trades.csv`
- roundtrips：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_roundtrips.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_no_lower_shadow_swing_v1_daily.csv`

## 结论

- 本阶段结论：
  - 交易次数少基本可信，核心原因是严格形态稀疏：75,751 个品种日里只有 119 组连续两日信号。
  - Stage001 候选 112 与漏斗复核的 113 个同合约连续候选基本闭合，差异来自回测运行中的持仓状态/候选生成时点过滤。
  - HTML 复盘页已可逐笔查看信号日、开盘入场、首日减半、初始/移动止损和实际平仓点。
- 是否进入下一步：可以，但先让用户看复盘细节确认信号链路。
- 下一步：
  - 用户确认交易链路无误后，再做 Stage002 提到的首日执行反事实。
  - 若用户在 HTML 中发现某些合约或日期不符合预期，先修数据/信号口径，不急着优化策略。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：
  - 本阶段只生成复盘页和信号漏斗核对，没有调整策略参数。
  - 复核交易少的原因是为了防止错误结论，不是为了筛选样本。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 如果交易数是代码漏算，前面归因都不可靠；现在漏斗基本闭合，Stage002 的失败归因才有讨论基础。
  - 但这也说明该形态在严格定义下天然样本少，后续任何分桶都要非常克制，不能把小样本当大样本训练。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage003 漏斗校验结论。
- 是否更新 `research/registry.md`：是，更新最新阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是复盘和审计，不是正式候选或路线废弃。
