# Stage033 Stage757 逐月启动审计

- line_id：`futures_trend_winner_trade_forensics`
- 当前模式：`day`
- 记录时间：`2026-06-09 17:15 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 多起点稳健性回测
- 是否重要突破：否
- 是否触发A/B：是，Stage757 有可能被误认为可接入正式或 C50 候选，需按 A/C 纪律记录

## 外部调研与判断

- 参考资料：
  - CME Open Interest：`https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest.html`
  - Britannica Futures Volume and Open Interest：`https://www.britannica.com/money/futures-volume-open-interest`
  - NexusFi Open Interest 确认说明：`https://nexusfi.com/showthread.php?p=591992&t=38210`
- 我的判断：公开资料支持把“价格沿方向 + OI 上升”理解为趋势确认或新资金进入，但不支持把单个 OI 条件当普世 alpha。本阶段不是优化 OI 参数，而是验证 Stage757 在不同启动月份下是否穿越路径依赖。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage759_stage757_monthly_start.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`STAGE759_MAX_WORKERS`、`stage757_base_risk_multiplier=0.40`、`stage757_restored_risk_multiplier=0.80`、`oi_price_confirm_risk_restore_multiplier=2.00`
- 修改参数：无正式配置修改；仅运行期启用 Stage757 的 OI 确认风险恢复
- 删除参数：无

## 回测/归因参数

- 数据区间：逐月启动 `2020-01` 至 `2026-04`，统一终点 `2026-04-30`
- 账户规模：`500,000`
- 成本口径：正常滑点，并对 2020-01 起点输出 2x/3x 成本压力
- 样本过滤：共 `76` 个逐月独立起点；成熟样本为 `>=252` 交易日，共 `64` 个
- 策略/归因口径：
  - B：Stage748 C50 `stage526_500k_force95_to80_r040_pc25_maxpos4_no_streak_no_recovery_stage748`，复用 Stage749 逐月结果
  - C：Stage757 `stage526_500k_force95_to80_r040_oi_confirm_r080_no_streak_no_recovery_stage757`
  - C 保持 50万、全局 `risk_multiplier=0.40`、关闭连败缩放与 recovery sleeve；命中入场前最新已完成日线的 OI 确认时恢复到等效 `0.80`
  - 因果时点：只用入场前最新已完成合约日线，不使用开仓日 OI

## 结果

- 期末权益：Stage757 2020-01 起点 `9,571,060`
- 总收益：Stage757 2020-01 起点 `1814.2120%`
- 最大回撤：Stage757 2020-01 起点 `-41.6458%`
- Sharpe：Stage757 2020-01 起点 `1.4510`
- 总滑点：Stage757 2020-01 起点 `877,910`
- 总交易次数：Stage757 2020-01 起点 `685`
- 胜率：Stage757 2020-01 起点 `52.6678%`
- 其他关键指标：
  - Stage757 全部 `76` 个启动月：正收益 `67/76=88.1579%`，中位收益 `143.9820%`，p10 `-2.6975%`，最差 `2025-09=-11.5920%`，最佳 `2020-05=2684.0870%`，中位最大回撤 `-21.9473%`，最差最大回撤 `-50.5085%`，DD30 失败 `31/76`，DD40 失败 `24/76`
  - Stage757 成熟 `>=252` 交易日：正收益 `64/64=100.0000%`，中位收益 `200.7325%`，p10 `74.2063%`，最差 `2024-04=68.2410%`，最佳 `2020-05=2684.0870%`，中位最大回撤 `-24.1021%`，最差最大回撤 `-50.5085%`，DD30 失败 `31/64`，DD40 失败 `24/64`
  - 与 Stage748 C50 对比，全部 `76` 个起点：Stage757 收益胜出 `53/76=69.7368%`，回撤胜出仅 `1/76=1.3158%`，Sharpe 胜出 `25/76`；中位收益差 `+19.6020pp`，p10 收益差 `-11.5265pp`，中位回撤差 `-2.4833pp`；DD40 失败 `24` vs Stage748 `5`
  - 与 Stage748 C50 对比，成熟 `64` 个起点：Stage757 收益胜出 `48/64=75.0000%`，回撤胜出 `1/64=1.5625%`，Sharpe 胜出 `21/64`；中位收益差 `+26.5730pp`，p10 收益差 `-12.2210pp`，中位回撤差 `-2.5653pp`
  - 2020-01 起点对比：Stage748 `5,565,350/1013.0700%/-39.7082%/Sharpe1.3285/滑点470,250/交易686/胜率52.7165%`；Stage757 `9,571,060/1814.2120%/-41.6458%/Sharpe1.4510/滑点877,910/交易685/胜率52.6678%`
  - Stage757 2x/3x 成本压力，2020-01 起点：`8,693,150/1638.6300%/-44.8728%/Sharpe1.3547`、`7,815,240/1463.0500%/-48.2707%/Sharpe1.2584`
  - 决策：`stage757_monthly_start_not_promoted`
  - hard fail：`mature252_stage757_dd40_fail_exists`
  - watch：`stage757_all_positive_rate_lt90pct`、`mature252_stage757_dd40_fail_more_than_stage748`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage759_stage757_monthly_start_report_stage759_stage757_monthly_start_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage759_stage757_monthly_start_summary_stage759_stage757_monthly_start_v1.csv`
- orders：无逐笔订单新输出
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage759_stage757_monthly_start_curves_stage759_stage757_monthly_start_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage759_stage757_monthly_start_checks_stage759_stage757_monthly_start_v1.csv`
- 其他：`candidate_summary`、`comparison_stage748`、`cost_stress`、`decision json`、权益曲线图、收益热力图、相对 Stage748 差值热力图

## 结论

- 本阶段结论：Stage757 在多数成熟启动月提高收益，但几乎系统性恶化回撤。它不是更可靠的质量过滤器，而是右尾行情放大器；在 C50 半风险关闭连败口径下也不能晋级。
- 是否进入下一步：不进入单因子交易化下一步
- 下一步：停止扫 OI 恢复倍率、OI 天数、品种、方向、年份；若继续研究 OI，只能作为多因子质量评分的一项，并必须先解决回撤保护和成本压力。

## 过拟合反思

- 运行前判断：不是单点过拟合，因为用户要求的是已固定 Stage757 的逐月启动压力测试；但若借结果再扫恢复倍率、窗口或局部年份会过拟合。
- 运行后判断：Stage757 单因子存在明显右尾耦合和路径依赖，不是可穿越周期的稳健规则。
- 原因：收益胜率高于 Stage748，但 DD40 失败从 `5` 增至 `24`，回撤胜出只有 `1/76`；这说明规则主要放大波动和右尾，而不是稳定改善机会质量。

## 继续价值反思

- 运行前判断：有价值，因为 Stage757 全周期收益提升明显，需要验证是否只吃了单一起点或单一路径。
- 运行后判断：作为接入候选没有继续价值；作为法证标签仍有有限价值。
- 原因：多起点证明收益提升不只是 2020-01 单点，但回撤恶化太普遍，无法满足正式候选的生存线要求。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：是，追加 Stage759 结论和长期记忆
