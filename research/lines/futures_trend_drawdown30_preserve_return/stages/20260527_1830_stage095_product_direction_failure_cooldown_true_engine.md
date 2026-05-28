# Stage095 同品种同方向失败冷却真实引擎验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 18:30 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage094 固定后续候选的真实引擎 A/C 验证；不扫次数、不扫冷却天数。
- 是否重要突破：否。重要反证：失败记忆冷却会错过后续趋势段，不能晋级。
- 是否触发A/B：是。A 为 Stage079，C 为 `同品种+同方向` 252日内 `3次连续已执行亏损` 后 flat entry 冷却 `90日`。

## 外部调研与判断

- 参考资料：
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Kim, Tse, Wald, *Time series momentum and volatility scaling*：https://www.sciencedirect.com/science/article/pii/S1386418116301379
  - 本轮网络/GitHub 检索关键词：`trend following whipsaw filter failed breakout frequency cooldown strategy research`、`trend following repeated whipsaws regime filter false breakout frequency research`、`GitHub trend following whipsaw filter failed breakout cooldown Python`。
- 我的判断：
  - 趋势跟随的核心收益来自少数大趋势，反复 whipsaw 既可能代表震荡，也可能是大趋势展开前的试探。
  - Stage094 已显示连续失败后胜率略升但均值下降，因此本轮只能验证“冷却是否减少坏持有体验”，不能做“失败后加仓”。
  - 真实引擎结果显示冷却挡掉了若干大趋势入场，收益和回撤都劣化，说明该经验线索不能作为 Stage079 优化规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage395_stage079_product_direction_failure_cooldown.py`
- 修改脚本：`examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
- 删除脚本：无。
- 新增参数：
  - `enable_product_direction_failure_cooldown = False`，默认关闭。
  - `product_direction_failure_cooldown_lookback_days = 252`
  - `product_direction_failure_cooldown_min_consecutive_failures = 3`
  - `product_direction_failure_cooldown_days = 90`
  - `product_direction_failure_cooldown_entry_contexts = "flat_entry"`
- 修改参数：无正式默认参数修改；新增钩子默认关闭，不影响 Stage079 基准。
- 删除参数：无。
- 实现修正：冷却历史日期统一为无时区归一化交易日，避免 vn.py bar datetime 与 pandas Timestamp 时区比较异常。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-30`。
- 账户规模：Stage079 账户口径 `61.5万`，即 `50万C3下单 + 11.5万外部现金`。
- 成本口径：正常成本 `1x`，并额外做 `2x/3x/5x` 滑点压力。
- 样本过滤：无品种黑名单、无年份排除、无相邻参数扫描。
- 策略/归因口径：只使用入场日前已经完成并已知盈亏的同品种同方向交易结果；仅对 `flat_entry` 新开仓候选触发冷却。

## 结果

- 基准 Stage079：
  - 期末权益 `31,040,650`
  - 总收益 `4947.2602%`
  - 最大回撤 `-29.7007%`
  - Sharpe `1.3188`
  - Ulcer `15.0874`
  - 总滑点 `1,556,750`
  - 总交易次数 `757`
  - 胜率 `45.3826%`
- 候选 `pd_fail3_252d_cool90_true_engine`：
  - 期末权益 `10,460,100`
  - 总收益 `1600.8293%`
  - 最大回撤 `-35.1486%`
  - Sharpe `1.0586`
  - Ulcer `17.3844`
  - 总滑点 `600,740`
  - 总交易次数 `702`
  - 胜率 `44.0341%`
- 3个月任意启动体验：
  - Stage079：5%分位收益 `-11.4702%`，中位收益 `13.5434%`，正收益率 `73.4804%`，年化低于5%概率 `29.4012%`，最差窗口回撤 `-29.1988%`，破30率 `0%`，Ulcer P95 `17.7786`。
  - 候选：5%分位收益 `-14.7295%`，中位收益 `8.3544%`，正收益率 `67.8973%`，年化低于5%概率 `35.4795%`，最差窗口回撤 `-31.2328%`，破30率 `1.9811%`，Ulcer P95 `15.0366`。
- 6个月任意启动体验：
  - Stage079：5%分位收益 `-2.0393%`，中位收益 `33.9947%`，正收益率 `93.4772%`，年化低于5%概率 `9.0099%`，最差窗口回撤 `-29.7007%`，破30率 `0%`，Ulcer P95 `19.9011`。
  - 候选：5%分位收益 `-14.8550%`，中位收益 `18.0594%`，正收益率 `80.6664%`，年化低于5%概率 `22.0554%`，最差窗口回撤 `-32.3975%`，破30率 `6.2881%`，Ulcer P95 `17.5403`。
- 成本压力：
  - 候选 `1x/2x/3x/5x` 最大回撤为 `-35.1486%/-35.4261%/-38.6415%/-39.2964%`。
  - Stage079 `1x/2x/3x/5x` 最大回撤为 `-29.7007%/-35.7770%/-33.0393%/-41.1430%`。
  - 候选在 `1x` 和 `3x` 明显差于 Stage079 压力口径。
- 冷却触发：正常成本下阻断 `27` 次，涉及 `8` 个品种，首次 `2020-07-09`，末次 `2026-04-30`，最大连续失败数 `4`。
- 晋级闸门：`no_promotion`。失败项包括总收益、最大回撤、回撤30以内、Sharpe、Ulcer、252/504日滚动破30、年度/季度冷启动破30、成本压力不劣化。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_report_stage395_stage079_product_direction_failure_cooldown_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_summary_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_horizon_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- score：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_score_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- promotion：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_promotion_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- cost stress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_cost_stress_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- cooldown triggers：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_cooldown_triggers_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_daily_stage395_stage079_product_direction_failure_cooldown_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_decision_stage395_stage079_product_direction_failure_cooldown_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage395_stage079_product_direction_failure_cooldown_equity_drawdown_stage395_stage079_product_direction_failure_cooldown_v1.png`

## 结论

- 本阶段结论：同品种同方向连续失败记忆特征不能作为 Stage079 的优化规则。它在只读层面能解释局部胜率，但真实引擎冷却会显著降低大趋势捕获，导致收益、回撤、Sharpe、Ulcer 和任意启动持有体验整体劣化。
- 是否进入下一步：本路线不继续。
- 下一步：停止围绕失败次数、冷却天数、品种或信号形态做救援；若继续短持有体验优化，应回到真实低相关收益源、成本更低承载，或不来自坏窗口归因的外生状态变量。

## 过拟合反思

- 运行前判断：不是过拟合。规则来自 Stage094 之前定义的固定假设，且只测 `3次/252日/90日/flat_entry` 一组。
- 运行后判断：当前验证没有过拟合，但如果继续调 `2/3/4次`、`30/60/120日` 或按品种挑选，会明显过拟合。
- 原因：真实引擎已经在固定规则下失败，继续救小数只是在历史坏窗口上拟合噪声。

## 继续价值反思

- 运行前判断：有价值。该想法直接对应用户提出的信号出现次数/失败记忆，并且可能影响3个月和6个月体验。
- 运行后判断：该子路线继续价值低；总目标仍有价值。
- 原因：候选触发 27 次但方向错误，既没有保住全周期硬指标，也没有改善3个月/6个月目标；经验上它更像“胜率提高但右尾被砍掉”的典型趋势策略陷阱。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage095 边界。
- 是否更新 `research/registry.md`：否，未形成正式候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；`memory.md` 暂不更新。
