# Stage079 C3部署现金多起点审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 02:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：部署层只读审计；不修改78-1、C3信号、AI池、品种池、仓位或成交路径
- 是否重要突破：否。属于 Stage055/067 现金边界的多起点复验
- 是否触发A/B：按部署层规则只做 A/C 对照。A 为 78-1，同现金对照为 `78-1 + 11.5万现金`，C 为 `C3 50万下单 + 11.5万现金`

## 外部调研与判断

- 参考资料：
  - TradingStrategy.ai 的 walk-forward analysis 说明强调，单一全周期曲线不足以证明稳健，需要多切片验证，且 walk-forward 设计本身也可能被 meta-overfit。
  - arXiv `A General Framework for Portfolio Theory. Part II: drawdown risk measures` 将 drawdown 视为独立组合风险约束，而不是只看波动率。
- 我的判断：
  - 本阶段只验证已预声明的账户层资金结构，不优化交易规则。
  - `11.5万` 外部现金来自 Stage055/067 的正常成本边界，不应根据本阶段结果继续细调为 `10.8万/12万` 之类小数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage379_c3_deployment_cash_multistart_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STRATEGY_CAPITAL=500000`
  - `EXTERNAL_CASH=115000`
  - `ACCOUNT_CAPITAL=615000`
  - `TARGET_MAX_DD_PCT=-30`
  - `RETURN_RETENTION_GATE_PCT=80`
  - `ROLLING_WINDOWS=(252, 504)`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：C3 下单资金 `500,000`，外部不下单现金 `115,000`，账户总资金 `615,000`
- 成本口径：沿用已有 C3 日度权益正常成本口径；本阶段不重新生成成交
- 样本过滤：年度冷启动、季度冷启动、252日滚动、504日滚动；低于252个交易日的窗口不计入闸门
- 策略/归因口径：
  - `78-1 50万`
  - `78-1 + 11.5万现金`
  - `C3 50万`
  - `C3 50万下单 + 11.5万现金`

## 结果

- 期末权益：`31,040,650`
- 总收益：`4947.2602%`
- 最大回撤：`-29.7007%`
- Sharpe：`1.6211`
- 总滑点：沿用 C3 正常成本口径 `1,556,750`
- 总交易次数：沿用 C3 `757`
- 胜率：沿用 C3 `45.3826%`
- 其他关键指标：
  - 相对 C3 收益保留：`81.3008%`
  - 相对同现金 78-1 最大回撤改善：`9.5826pp`
  - 相对同现金 78-1 Ulcer 改善：`25.3387%`
  - 年度冷启动：`6/6` 回撤30以内，综合闸门 `6/6`
  - 季度冷启动：`22/22` 回撤30以内，综合闸门 `19/22`
  - 252日滚动：`1282/1282` 回撤30以内，最差收益 `7.8896%`，最差收益保留 `75.6794%`
  - 504日滚动：`1030/1030` 回撤30以内，最差收益 `92.4083%`，最差收益保留 `75.6794%`
  - 审计状态：`yellow`
  - 黄灯原因：`252日滚动窗口相对同现金78-1曾落后超过5pp`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage379_c3_deployment_cash_multistart_audit_report_stage379_c3_deployment_cash_multistart_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage379_c3_deployment_cash_multistart_audit_aggregate_stage379_c3_deployment_cash_multistart_audit_v1.csv`
- orders：无，本阶段不重放成交
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage379_c3_deployment_cash_multistart_audit_window_stats_stage379_c3_deployment_cash_multistart_audit_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage379_c3_deployment_cash_multistart_audit_decision_stage379_c3_deployment_cash_multistart_audit_v1.json`

## 结论

- 本阶段结论：正常成本下，`50万C3下单 + 11.5万外部现金` 是当前最低过拟合的可执行部署边界之一。它在全样本、年度冷启动、季度冷启动和504日滚动收益上均证明比78-1平滑很多，并把最大回撤压进30%以内。
- 是否进入下一步：是，但只作为正常成本部署候选/forward audit，不替代策略 alpha，不宣称高滑点稳健。
- 下一步：若用户接受 `61.5万账户总资金 + 50万实际下单资金`，可把它作为正常成本虚拟盘/影子盘账户口径；若仍要求 2x/3x 滑点也保收益，需要继续寻找真正低相关收益源，而不是调现金小数。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：不是过拟合。
- 原因：现金数来自既有 Stage055/067，当前只按年度、季度和滚动窗口重切已有日度权益；没有新增入场、出场、品种、阈值或现金小数搜索。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但边界明确。
- 原因：它直接回应“回撤30以内、收益不显著降低、曲线更平滑”的目标；但高滑点压力已被 Stage055/067 证明不通过，因此不能作为最终全成本稳健解。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不更新 `memory.md`
