# Stage077 Stage900 C9 深度逐笔可信度审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 20:46 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读法证审计；不重跑策略优化、不改 C9 规则、不连接 CTP、不调用下单。
- 是否重要突破：否。属于高收益可信度审计和旧口径纠偏。
- 是否触发A/B：否。没有新策略版本或接入正式版动作。

## 外部调研与判断

- 参考资料：
  - Freqtrade lookahead-analysis：`https://www.freqtrade.io/en/stable/lookahead-analysis/`
  - StoneX Backtesting glossary：`https://www.stonex.com/en/business/financial-glossary/backtesting/`
  - QuantStart continuous futures contracts：`https://www.quantstart.com/articles/Continuous-Futures-Contracts-for-Backtesting-Purposes/`
- 我的判断：
  - 外部资料确认，收益异常高时优先排查三类问题：信号是否使用成交后信息、连续合约/数据源是否有回填偏差、成交价假设是否过于乐观。
  - C9 当前本地输出未发现“信号日晚于成交日”或“日内事件触发条件失败”这类硬未来函数证据。
  - 但 C9 仍不是逐 tick/盘口级撮合：日内 stop/retry 使用 Stage861 采样分钟K，高比例 `open=high=low=close` 退化，按阈值价成交有成交精度风险。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/audit_qmt_roll_stage900_c9_deep_trade_forensics.py`
- 修改脚本：
  - 同上。修正空 CSV 容错、Stage898 `status=pass` 解释、日/夜盘代理窗口映射、事件触发条件与阈值成交价分离。
- 删除脚本：无。
- 新增参数：无策略参数；新增审计指标 `open_proxy_window_missing_count`、`event_trigger_condition_failed_count`、`event_threshold_not_observed_inside_bar_count`。
- 修改参数：无策略参数。
- 删除参数：无。

## 回测/归因参数

- 数据区间：读取当前 Stage863 C9 输出，曲线范围 `2018-01-02 -> 2026-05-29`，`2037` 个交易日。
- 账户规模：`300,000`。
- 成本口径：沿用 Stage863 当前输出，总滑点 `3,646,200`。
- 样本过滤：不筛年份、品种、方向；读取 C9 全部交易和 closed lots。
- 策略/归因口径：
  - 原始开仓信号匹配：用 `entry_risk` 与 `trades` 匹配，检查 `signal_date <= fill_date`。
  - 开仓代理价格：区分 `signal_date 21:00-21:05` 夜盘窗口与 `fill_date 09:00-09:05` 日盘窗口。
  - C9 日内事件：检查 first stop、reentry、retry failed、继承 C2 stop 的事件时间、分钟K存在性、方向性触发条件。
  - 收益合理性：按 closed lot 做 PnL 集中度、年度、品种方向和 exit reason 归因。

## 结果

- 期末权益：`51,297,786.20`
- 总收益：`16,999.2621%`
- 最大回撤：`-41.6664%`
- Sharpe：`1.6404`
- 总滑点：`3,646,200`
- 总交易次数：`790`
- 胜率：`53.5299%`（非零日胜率）
- 其他关键指标：
  - Stage898 当前本地 P0 完整性检查：`5` 项，失败 `0`。
  - 原始开仓匹配：`333` 行；`signal_after_fill_bug_count=0`；`entry_match_missing_count=3`。
  - 非 fallback 开仓代理：可复核窗口 `205` 行，窗口外价格 `0`；缺少可复核分钟窗口 `16`。
  - fallback 原始开仓：`109` 笔；关联 closed lot PnL `6,595,980.60`。
  - 日内事件检查：`217` 行；分钟K缺失 `0`；方向性触发失败 `0`。
  - 日内成交精度风险：`threshold_not_observed_inside_bar=176`，`degenerate_minute_bar=213`，median overshoot `3.68`，max overshoot `192.5`。
  - 收益集中度：top 10 winners PnL `41,243,960`，占净 PnL `75.4692%`；big winners `26` 笔，PnL `36,210,740`，占净 PnL `66.2593%`。
  - 毛利润 `91,067,270`，毛亏损 `-36,417,193.8`，gross profit factor `2.5007`。
  - 年度 PnL：`2025 +17,128,660`、`2023 +14,867,475`、`2021 +13,550,583`、`2024 +7,522,620`、`2026 -2,051,669.4`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_report_stage900_c9_deep_trade_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_summary_stage900_c9_deep_trade_forensics_v1.csv`
- findings：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_findings_stage900_c9_deep_trade_forensics_v1.csv`
- per_lot_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_per_lot_audit_stage900_c9_deep_trade_forensics_v1.csv`
- entry_execution_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_entry_execution_audit_stage900_c9_deep_trade_forensics_v1.csv`
- event_price_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage900_c9_deep_trade_forensics_event_price_audit_stage900_c9_deep_trade_forensics_v1.csv`
- orders/daily/quality：本阶段不产生订单级新回测输出；只读 Stage863 既有交易、曲线和质量审计表。

## 结论

- 本阶段结论：
  - C9 收益高，但当前 Stage900 没发现硬未来函数或明显汇总 bug：信号没有晚于成交日，日内事件触发条件全部成立，交易数与 summary 一致。
  - C9 的高收益更像趋势右尾复利和 30 万整数手进攻性放大：top 10 winners 贡献净 PnL 的 `75.47%`，不是稳定小胜率套利。
  - 当前不能把 C9 称为“逐笔盘口级完全无偏差”：`109` 笔 fallback open、`16` 笔非 fallback 代理窗口缺复核、`176/217` 个日内阈值价没有被采样 OHLC 直接包含，说明成交价精度和数据粒度仍需复核。
  - Stage073 的旧“8 笔 entry-day 缺口”不再适用于当前本地 Stage898 输出；当前 Stage898 P0 fail 为 `0`。旧记录保留历史含义，但后续应以 Stage900 当前审计为准。
- 是否进入下一步：可以继续，但不应继续调参。
- 下一步：
  - 优先把 top PnL / top overshoot / fallback open 的样本做 tick 或交易所原始分钟源交叉核对。
  - 若无法获得更细数据，C9 只能作为研究参考或高风险候选，不应以“数据无任何偏差”口径晋级正式版本。

## 过拟合反思

- 运行前判断：否。只读审计已有 C9 输出，不改规则、不筛样本、不新增参数。
- 运行后判断：否。没有基于审计结果新增交易规则或优化参数。
- 原因：本阶段只验证时间顺序、代理窗口、事件触发和 PnL 集中度，目标是降低误判风险，不是提高收益。

## 继续价值反思

- 运行前判断：有价值。C9 收益异常高，必须解释是否来自 bug、未来函数或成交假设。
- 运行后判断：有价值，但方向应转为数据复核，不应继续做 C9 小参数救参。
- 原因：硬未来函数证据未出现；剩余风险集中在 fallback/采样分钟K/阈值成交价，这些只能靠更细数据或同源数据复核解决。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage077 最新状态并纠偏旧缺口结论。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是可信度审计，不是正式候选或重要合入。
