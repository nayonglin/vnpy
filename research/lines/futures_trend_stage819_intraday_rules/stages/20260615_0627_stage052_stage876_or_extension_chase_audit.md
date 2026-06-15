# Stage052 Stage876 OR Extension 追价审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 06:27 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读代理审计 + K线视觉复核；不改官方正式版、不改官方候选配置、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否；这是一个 OR/追价分支的反证。
- 是否触发A/B：否；未形成可接入正式候选或 A/B 的稳定新版本。

## 外部调研与判断

- 参考资料：
  - Turtle 规则支持固定突破、止损和 whipsaw 后重新入场，但不支持按个别亏损交易反推过滤：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Opening Range Breakout 是常见日内规则形状，早盘区间可以作为自然价格尺度，但参数容易被过拟合；本阶段只用固定 `OR15` 与 `1x OR width`。
  - Backtrader stop/trailing stop 示例提醒，真实规则必须落到逐根 bar 可执行语义，而不是事后 skip-trade 标签：https://www.backtrader.com/docu/order-creation-execution/trail/stoptrail/
  - vn.py CTA engine 参考说明实盘接入前必须明确 runtime 事件和订单语义：https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/engine.py
- 我的判断：
  - “入场价已经在信号方向超过开盘区间边界”可能描述追价风险，但它必须同时满足低右尾误伤和跨年份稳定，才值得写真实引擎。
  - 这次只允许一次固定尺度只读审计，不扫 OR 分钟数、OR width 倍数、品种、方向或年份。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage876_stage861_or_extension_chase_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE = "Stage876"`
  - `MODEL_TAG = "stage876_stage861_or_extension_chase_audit_v1"`
  - 固定开盘区间 `OPENING_RANGE_BARS = 15`
  - 固定自然尺度 `1x OR width`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage861 全量分钟K覆盖与 Stage819 候选 closed lots。
- 账户规模：未新增；沿用 Stage861/Stage825 候选逐笔口径。
- 成本口径：只读 skip-trade 代理，读取既有 realized PnL；不重算资金联动、滑点节省或释放保证金后的后续交易。
- 样本过滤：
  - Stage861 entry lots `341` 笔。
  - 每笔计算信号方向下，`entry_price` 相对 `OR15` 信号侧边界的标准化扩展：
    - long：`(entry_price - OR_high) / OR_width`
    - short：`(OR_low - entry_price) / OR_width`
  - 分桶：
    - `inside_or_or_opposite`：`or_extension <= 0`
    - `edge_to_1or`：`0 < or_extension <= 1`
    - `extended_gt_1or`：`or_extension > 1`
    - `missing_or`
- 策略/归因口径：
  - `P1_block_edge_to_1or`：跳过 `0 < or_extension <= 1`。
  - `P2_block_extended_gt_1or`：跳过 `or_extension > 1`。
  - `P3_block_all_beyond_edge`：跳过 `or_extension > 0`。
  - 以上都是只读代理，不是 live engine。

## 结果

- 期末权益：未新增；本阶段不是组合回测。
- 总收益：未新增；本阶段不是组合回测。
- 最大回撤：未新增；本阶段不是组合回测。
- Sharpe：未新增；本阶段不是组合回测。
- 总滑点：未新增；本阶段不是组合回测。
- 总交易次数：未新增；本阶段不是组合回测。
- 胜率：未新增；本阶段不是组合回测。
- 其他关键指标：
  - Stage861 entry lots：`341`，base realized PnL `+28,171,880`。
  - `inside_or_or_opposite`：`260` 笔，PnL `+30,565,390`，胜率 `51.5385%`，big winner `28`。
  - `edge_to_1or`：`37` 笔，PnL `-1,472,105`，胜率 `29.7297%`，big winner `2`。
  - `extended_gt_1or`：`43` 笔，PnL `-1,271,055`，胜率 `25.5814%`，big winner `1`。
  - `P1_block_edge_to_1or`：affected `37`，gross proxy delta `+1,472,105`，winner_cut `-1,497,505`，loser_saved `+2,969,610`，big_winner_cut `-1,187,500`。
  - `P2_block_extended_gt_1or`：affected `43`，gross proxy delta `+1,271,055`，winner_cut `-3,881,260`，loser_saved `+5,152,315`，big_winner_cut `-351,200`。
  - `P3_block_all_beyond_edge`：affected `80`，gross proxy delta `+2,743,160`，winner_cut `-5,378,765`，loser_saved `+8,121,925`，big_winner_cut `-1,538,700`。
  - `P3` 年度：正 delta `6` 年、负 delta `3` 年；其中 `2022` `+2,238,640`、`2023` `+1,302,600`，但 `2021` `-934,640`、`2020` `-352,520`、`2026` `-165,310`。

## 视觉复核

- summary chart 显示 `edge_to_1or` 和 `extended_gt_1or` 两个 beyond-edge 桶本身为负，但 `inside_or_or_opposite` 才是收益主体。
- atlas page001 显示该标签确实能抓到若干追价后全天逆行的左尾，如 `fu2205.SHFE`、`jm2301.DCE`、`SH409.CZCE`。
- atlas page003 显示关键反证：`OI201.CZCE`、`sp2205.SHFE`、`au2412.SHFE` 都是 beyond-edge，但后续仍能延展为赢家。
- atlas page004 显示 `inside_or_or_opposite` 的大赢家也不是单纯早盘强突破，它们往往需要早盘后继续发展；这说明 OR extension 更像复盘标签，而不是稳定入场过滤器。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_report_stage876_stage861_or_extension_chase_audit_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_features_stage876_stage861_or_extension_chase_audit_v1.csv`
- bucket_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_bucket_summary_stage876_stage861_or_extension_chase_audit_v1.csv`
- proxy_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_proxy_summary_stage876_stage861_or_extension_chase_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_yearly_stage876_stage861_or_extension_chase_audit_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_summary_chart_stage876_stage861_or_extension_chase_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_manifest_stage876_stage861_or_extension_chase_audit_v1.csv`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_page001_stage876_stage861_or_extension_chase_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_page002_stage876_stage861_or_extension_chase_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_page003_stage876_stage861_or_extension_chase_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_page004_stage876_stage861_or_extension_chase_audit_v1.png`
- atlas：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_atlas_page005_stage876_stage861_or_extension_chase_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage876_stage861_or_extension_chase_audit_decision_stage876_stage861_or_extension_chase_audit_v1.json`

## 结论

- 本阶段结论：`stage876_or_extension_chase_proxy_not_promoted_no_engine`。
- 是否进入下一步：否，不接 OR extension 真实引擎。
- 下一步：
  - 停止 OR 分钟数、OR width 倍数、追价阈值、品种、方向、年份扫描。
  - 若继续本线，应回到更本质的账户/持仓层生存问题；否则暂停等待新的低自由度外生特征。

## 过拟合反思

- 运行前判断：否。本阶段只使用固定 `OR15` 与 `1x OR width` 的自然尺度，不扫描参数。
- 运行后判断：当前审计本身不是过拟合，但继续救这个分支会过拟合。
- 原因：
  - 表面正 delta 来自 beyond-edge 桶整体亏损，但真实可用性被赢家削减、big winner 削减和年份不稳削弱。
  - 若继续改成 `0.5x/1.5x/2x OR`、改 OR 分钟数、按 2022/2023 或燃油/黑色品种调参，本质就是追着压力年份救参。

## 继续价值反思

- 运行前判断：有有限价值。它检验一个不同于已反证 OR15 过滤的追价假设，且用固定自然尺度。
- 运行后判断：该具体分支没有继续价值。
- 原因：
  - `P3_block_all_beyond_edge` 虽有 `+2,743,160` skip proxy，但要砍 `-5,378,765` 赢家和 `-1,538,700` big winner。
  - 2021 年该规则会产生 `-934,640` 负 delta，说明它不是能穿越周期的稳定规则。
  - 视觉上 beyond-edge 同时包含左尾和右尾，不能作为错误充分条件。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage052 反证和停止 OR extension 分支。
- 是否更新 `research/registry.md`：否，本线状态未发生路线级变化。
- 是否追加根目录 `memory.md/back_log.md`：否，不是重要突破、路线废弃、正式候选、跨线合并或记录体系迁移。
