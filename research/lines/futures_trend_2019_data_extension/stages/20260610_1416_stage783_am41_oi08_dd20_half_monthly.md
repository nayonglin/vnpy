# Stage783 AM41 OI0.8 账户回撤20%后所有开仓半仓

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-10 14:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：账户级风控变体、逐月启动回测、负结论
- 是否重要突破：否
- 是否触发A/B：是，账户级开仓缩放可能作为正式候选风控层，按 `skills/version-ab-experiment/SKILL.md` 记录

## 外部调研与判断

- 参考资料：
  - 公开 position sizing / drawdown control 资料支持“组合回撤扩大后降低新交易风险”作为尾部风险控制思路。
  - trend-following 资料也提示趋势策略常在回撤后出现恢复段，机械降仓可能减少亏损，也可能错过恢复收益。
- 我的判断：
  - 该规则比品种/年份补丁更有结构性，不是明显过拟合。
  - 但 `20%` 阈值仍是单点账户路径参数，必须通过逐月多起点验证，且不能只用收益换回撤。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage783_am41_oi08_dd20_half_monthly.py`
- 修改脚本：无正式配置修改；新增研究 wrapper `QmtRollPortfolioStrategyExactAmDD20Half`
- 删除脚本：无
- 新增参数：
  - `enable_portfolio_drawdown_gate=True`
  - `portfolio_drawdown_gate_start_pct=0.20`
  - `portfolio_drawdown_gate_weight_floor=0.50`
  - `portfolio_drawdown_gate_entry_contexts="*"`
- 修改参数：
  - 基于 Stage777 `AM41 + OI0.8`，当账户权益相对历史高水位回撤 `>20%` 时，所有 `entry/add/rollover_reopen` 最终开仓手数乘 `0.5`
  - OI 命中仍先把基础等效风险从 `0.40` 恢复到 `0.80`，回撤门控在最终手数层面再减半
- 删除参数：无

## 回测/归因参数

- 数据区间：逐月起点 `2018-01` 到 `2026-05`，统一终点 `2026-05-29`
- 账户规模：`500,000`
- 成本口径：原始成本，另输出 `2x/3x` 成本压力
- 样本过滤：重点看成熟样本 `trading_days >= 252`，共 `89` 个起点
- 策略/归因口径：
  - A：Stage777 基准，`AM41`，基础等效风险 `0.40`，命中 `OI上升 + 价格沿方向` 恢复到 `0.80`，关闭连败缩放和 recovery sleeve
  - C：Stage783，在 A 基础上增加账户回撤 `>20%` 后所有新开/加仓/换月重开最终手数 `0.5x`

## 结果

### 代表起点 `2018-01`

- Stage783 期末权益：`9,009,750`
- Stage783 总收益：`1,701.950%`
- Stage783 最大回撤：`-41.7773%`
- Stage783 Sharpe：`1.2826`
- Stage783 总滑点：`527,040`
- Stage783 总交易次数：`625`
- Stage783 胜率：`52.2690%`
- 对照 Stage777 `2018-01`：`18,251,265 / 3,550.253% / -49.4213% / Sharpe 1.3671 / 滑点 1,145,460 / 交易 648 / 胜率 52.3089%`

### 全部与成熟起点

| stage | bucket | n | positive | median_return | p10_return | min_return | median_dd | worst_dd | dd30_fail | dd40_fail | dd50_fail | median_sharpe | median_trades |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Stage777 | all | 101 | 96 | 170.789 | 56.234 | -7.644 | -35.355 | -50.132 | 52 | 47 | 1 | 1.334 | 242 |
| Stage777 | mature252 | 89 | 89 | 272.349 | 83.768 | 56.234 | -43.554 | -50.132 | 52 | 47 | 1 | 1.385 | 311 |
| Stage783 | all | 101 | 90 | 92.585 | 0.000 | -12.975 | -26.045 | -46.911 | 48 | 31 | 0 | 1.218 | 193 |
| Stage783 | mature252 | 89 | 84 | 122.611 | 32.322 | -12.975 | -35.413 | -46.911 | 48 | 31 | 0 | 1.293 | 280 |

### Stage783 vs Stage777

- 全部样本收益胜出：`11/101 = 10.8911%`
- 全部样本回撤胜出：`90/101 = 89.1089%`
- 全部样本收益和回撤双胜：`11/101`
- 全部样本收益中位差：`-164.403pp`
- 全部样本回撤中位差：`+6.1071pp`
- 成熟样本收益胜出：`7/89 = 7.8652%`
- 成熟样本回撤胜出：`80/89 = 89.8876%`
- 成熟样本收益和回撤双胜：`7/89`
- 成熟样本收益中位差：`-193.086pp`
- 成熟样本回撤中位差：`+7.2219pp`

### 分段结果

- `2018-2019`：收益中位 `2385.16%`，回撤中位 `-42.0070%`，DD40 失败 `24/24`
- `2020-2021`：收益中位 `305.916%`，回撤中位 `-39.3265%`，DD40 失败 `7/24`
- `2022-2023`：收益中位 `84.538%`，回撤中位 `-21.3948%`，DD40 失败 `0/24`
- `2024-2025`：收益中位 `74.683%`，回撤中位 `-14.6210%`，DD40 失败 `0/24`
- `2026`：收益中位 `-4.744%`，回撤中位 `-8.9372%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_report_stage783_am41_oi08_dd20_half_monthly_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_summary_stage783_am41_oi08_dd20_half_monthly_v1.csv`
- orders：无单独订单文件，本阶段为逐月组合绩效审计
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_curves_stage783_am41_oi08_dd20_half_monthly_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_return_heatmap_stage783_am41_oi08_dd20_half_monthly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_dd_heatmap_stage783_am41_oi08_dd20_half_monthly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_delta_vs_stage777_heatmap_stage783_am41_oi08_dd20_half_monthly_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage783_am41_oi08_dd20_half_monthly_equity_curves_selected_stage783_am41_oi08_dd20_half_monthly_v1.png`

## 结论

- 本阶段结论：
  - Stage783 是强防守壳：成熟 DD40 失败从 Stage777 的 `47/89` 降到 `31/89`，DD50 失败从 `1` 降到 `0`。
  - 但收益牺牲过大：成熟收益中位从 `272.349%` 降到 `122.611%`，p10 从 `83.768%` 降到 `32.322%`，成熟样本正收益从 `89/89` 降到 `84/89`。
  - 回撤改善主要靠切掉回撤后的仓位，代价是把后续恢复段和右尾行情也一起切掉；不适合接 Stage777。
- 是否进入下一步：不推广，不接正式版。
- 下一步：
  - 不扫 `15/20/25%` 或 `0.4/0.5/0.6`。
  - 如果继续账户层风险治理，应研究“坏环境识别/恢复条件/出金锁盈/外层资金分层”，而不是单一深回撤后机械半仓。

## 过拟合反思

- 运行前判断：低到中等。账户层回撤降仓有第一性原理，但 `20%` 阈值仍可能是路径参数。
- 运行后判断：本次单点验证不是过拟合；继续扫阈值会过拟合。
- 原因：
  - 多起点结果显示规则方向稳定降低回撤，但收益损失也稳定存在，不是一个阈值微调能从本质上修复的问题。

## 继续价值反思

- 运行前判断：有价值。它直接验证账户层防守能否替代连败/单因子风控。
- 运行后判断：该形态无继续价值；账户层风控目标仍有价值。
- 原因：
  - 机械半仓降低了风险暴露，但没有判断“回撤后是否已经进入恢复段”，因此削弱趋势策略最重要的右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加当前状态。
- 是否更新 `research/registry.md`：否，本次仍属于既有研究线。
- 是否追加根目录 `memory.md/back_log.md`：是，`back_log.md` 记录回测摘要；`memory.md` 记录不继续扫账户回撤半仓阈值。
