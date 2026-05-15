# Stage008/Stage278 退出几何深挖

- line_id：`futures_trend_profit_lock_exit`
- 当前模式：`day`
- 记录时间：`2026-05-15 11:43 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：回应 Stage277 口径过浅的成交腿级深挖；拆分盈利锁、`prev2day_stop`、ATR/Chandelier 替换式退出。
- 是否重要突破：否，但修正 Stage277 的解释边界。
- 是否触发A/B：是，但仅为 A/C 候选前置诊断；本阶段不运行完整组合回测。

## 外部调研与判断

- 参考资料：
  - TradingView 支持文档：Chandelier Exit 是基于局部极值与 ATR 的波动率退出。
  - MarketVolume：Chandelier Exit 由 Charles Le Beau 提出，并被 Alexander Elder 推广为基于 ATR 的 trailing stop。
  - GitHub/公开代码：可找到通用 Chandelier/ATR trailing stop 实现，但没有发现可直接照搬到本仓库 Stage78-1 组合层的 vn.py 实现。
- 我的判断：
  - Stage277 的“叠加式保护层”过窄；真正应该查的是退出主导关系，以及 ATR 是作为“替换”而不是“叠加”时是否有增量。
  - 本阶段仍不调小数参数，只用 `ATR(22) * 2/3/4` 做敏感性地图，不从其中挑最优替换正式版。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage278_exit_geometry_deep_dive.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `replace_profit_lock_chandelier22_3_after5_extend60`
  - `replace_profit_lock_yoyo22_3_after5_extend60`
  - `replace_prev2day_lock_chandelier22_2/3/4_after5_extend60`
  - `replace_prev2day_lock_chandelier22_3_after10_extend60`
  - `replace_prev2day_lock_yoyo22_3_after5_extend60`
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage78-1 正式成交腿文件 `qmt_roll_official_stage78_1_trades_2020_2026_04.csv`。
- 账户规模：不适用。本阶段不是完整组合回测。
- 成本口径：沿用既有成交腿价格；替换式模拟只比较同一交易腿的退出价格差异。
- 样本过滤：可加载日线数据的 `444` 个成交腿。
- 策略/归因口径：
  - `add_overlay`：只允许 ATR 层早于真实离场，不允许延后。
  - `replace_profit_lock`：只在疑似固定盈利锁主导的 `base_stop` 且锁盈已激活交易腿上，用 ATR 替换固定锁盈，最多延后 `60` 天。
  - `replace_prev2day_and_profit_lock`：诊断性更大改动，在 `prev2day_stop/base_stop` 且锁盈已激活交易腿上，用 ATR 替换整套短跟踪退出，最多延后 `60` 天。

## 结果

- 期末权益：不适用，未运行完整组合回测。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 退出主导关系：
  - 成交腿：`444`
  - 实际离场时锁盈已激活：`209`
  - `base_stop` 且锁盈已激活：`18`
  - `prev2day_stop/base_stop` 且锁盈已激活：`180`
  - 原始退出原因：`long_prev2day_stop=274`，`short_prev2day_stop=55`，`long_base_stop=29`，`short_base_stop=26`，`rollover_close=37`
- 关键候选：
  - `replace_profit_lock_chandelier22_3_after5_extend60`
    - eligible_legs：`11`
    - changed_exit_legs：`9`
    - weighted_delta_sum：`16.0607`
    - positive_legs：`1`
    - negative_legs：`8`
    - year_win_count：`1`
    - top10_positive_share：`1.0`
    - 判定：只替换固定锁盈样本太少，正贡献只有 1 笔，不晋级。
  - `replace_prev2day_lock_chandelier22_3_after5_extend60`
    - eligible_legs：`84`
    - changed_exit_legs：`64`
    - weighted_delta_sum：`210.9603`
    - positive_legs：`23`
    - negative_legs：`41`
    - year_win_count：`4`
    - min_year_delta_sum：`-45.0560`
    - top10_positive_share：`0.9421`
    - 判定：有真实线索，但贡献集中且年份不够，不进入完整引擎。
  - `replace_prev2day_lock_yoyo22_3_after5_extend60`
    - weighted_delta_sum：`614.7731`
    - year_win_count：`5`
    - min_year_delta_sum：`-107.1226`
    - top10_positive_share：`0.9389`
    - 判定：收益线索更强，但集中度和弱年份风险更高，只能记录为结构线索。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_report_stage278_exit_geometry_deep_dive_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_summary_stage278_exit_geometry_deep_dive_v1.csv`
- dominance：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_dominance_stage278_exit_geometry_deep_dive_v1.csv`
- detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_detail_stage278_exit_geometry_deep_dive_v1.csv`
- by_year：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_by_year_stage278_exit_geometry_deep_dive_v1.csv`
- by_reason：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_by_reason_stage278_exit_geometry_deep_dive_v1.csv`
- by_product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_by_product_stage278_exit_geometry_deep_dive_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage278_exit_geometry_deep_dive_decision_stage278_exit_geometry_deep_dive_v1.json`

## 结论

- 本阶段结论：
  - 用户质疑成立：Stage277 结论过窄，不能代表“ATR退出没价值”。
  - 只替换固定盈利锁本身，没有足够稳健证据：样本太少且正贡献高度集中。
  - 真正有价值的线索是 `prev2day_stop + 盈利锁` 组合可能过早截断部分大趋势；ATR/YoYo 替换能在成交腿级模拟里释放收益，但收益严重集中，暂不能改正式版。
- 是否进入下一步：谨慎进入“结构验证设计”，但不直接写正式策略参数。
- 下一步：
  - 如果继续，应该新增一个独立实验版本：只在 `锁盈已激活 + 趋势强度仍强` 时放宽 `prev2day_stop`，而不是全量替换。
  - 先做完整组合引擎小窗口 A/C 反证，再决定是否跑多周期。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：当前不能 promotion，直接采用会过拟合。
- 原因：成交腿级替换式模拟允许延后 `60` 天，忽略资金占用、再入场冲突、换月和组合相关性；收益 top10 占比超过 `93%`，说明大部分好处来自少数历史路径。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但方向要重构。
- 原因：现在问题已从“盈利锁档位是否要改”转成“`prev2day_stop` 在已锁盈趋势里是否太短”。这是更本质的退出结构问题，值得小心做独立 A/C，但不能通过微调 ATR 倍数推进。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage008 结论。
- 是否更新 `research/registry.md`：是，更新最新阶段和下一步。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是完整回测，也不是正式候选合入。
