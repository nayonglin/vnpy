# Stage234 AI 信号质量模型离线可行性验证

- line_id：`futures_trend_signal_quality_ai`
- 当前模式：`day`
- 记录时间：2026-05-11 00:46 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：新研究线启动、离线 meta-label 可行性审计
- 是否重要突破：否，属于方向筛查；不能直接接入仓位倍率
- 是否触发A/B：否，本阶段只做离线标签与分桶审计，不改变 `78-1`

## 外部调研与判断

- 参考资料：meta-labeling、交易信号质量模型、机器学习仓位 sizing、金融时间序列样本外验证与过拟合风险控制。
- 我的判断：用户提出的“AI 猜涨跌后加注”不应做成裸预测涨跌；更稳健的形式是 `78-1` 先给开仓信号，二级模型只判断这笔信号质量。第一阶段必须先看时间样本外是否存在稳定分层信息，不能直接接入正式策略。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage234_signal_quality_ai_feasibility.py`
- 修改脚本：无正式策略脚本修改
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无
- 新增研究线：`research/lines/futures_trend_signal_quality_ai/`

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`78-1` 官方口径，初始资金 `500,000`
- 成本口径：沿用 `78-1` 官方成交与滑点产物；本阶段标签使用 FIFO 配对后的 `gross_pnl`
- 样本过滤：仅使用 `entry_candidate_snapshots` 中 `is_opened == 1` 的真实开仓样本
- 策略/归因口径：`official_stage78_1_defensive_50w_no_sizing_cap`，AI 选品开启，无 `sizing_equity_cap`
- 标签定义：FIFO round-trip 已实现 `gross_pnl > 0` 记为 `meta_success=1`

## 结果

- 期末权益：不适用，本阶段不是回测策略
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：沿用官方 `78-1` 产物，不在本阶段重复统计
- 总交易次数：官方 `78-1` 产物为 `880`；本阶段真实开仓样本 `407`
- 胜率：全样本 meta success rate `41.03%`
- 其他关键指标：
  - `train_2020_2023`：样本 `277`，闭合标签 `277`，成功率 `42.2383%`，平均已实现盈亏 `24,441`
  - `test_2024_2025`：样本 `109`，闭合标签 `109`，成功率 `42.2018%`，平均已实现盈亏 `164,725`
  - `test_2026`：样本 `21`，闭合标签 `18`，成功率 `19.0476%`，平均已实现盈亏 `-10,071`
  - `AI rank` 分桶无稳定单调性：训练期 `ai_1_3` 优于 `ai_gt_8`，但 `2024-2025` 反而 `ai_gt_8` 成功率最高，`2026` 样本太小且极端化
  - `RSI` 分桶有结构差异但存在 regime 切换，不能直接用作固定加注规则

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_report_stage234_signal_quality_ai_feasibility_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_window_summary_stage234_signal_quality_ai_feasibility_v1.csv`
- samples：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_samples_stage234_signal_quality_ai_feasibility_v1.csv`
- bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_bucket_summary_stage234_signal_quality_ai_feasibility_v1.csv`
- window_bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_window_bucket_summary_stage234_signal_quality_ai_feasibility_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage234_signal_quality_ai_feasibility_manifest_stage234_signal_quality_ai_feasibility_v1.json`

## 结论

- 本阶段结论：信号质量问题值得继续研究，但首轮静态分桶不足以证明可以加注。
- 是否进入下一步：是，但只能进入 `Stage235 walk-forward baseline`，不能直接接入 `risk_multiplier`。
- 下一步：用严格时间滚动训练/验证做一个极简、可解释的二级评分基线；只验证高分桶是否在样本外稳定优于低分桶，并加入最小样本数约束。

## 过拟合反思

- 运行前判断：有较高过拟合风险。
- 运行后判断：仍有较高过拟合风险，且首轮结果已经显示简单分桶不稳定。
- 原因：开仓样本只有 `407`，`2026` 独立样本只有 `21`；平均盈亏受少数大趋势单强烈影响，静态特征如 `AI rank`、`RSI` 易随市场阶段反转。

## 继续价值反思

- 运行前判断：有价值，但必须先离线反证。
- 运行后判断：仍有继续价值，但价值在“证明是否存在稳定信号质量分层”，不是马上提高收益。
- 原因：`78-1` 的趋势系统本来就是低胜率、高赔率结构；如果二级模型只能提升胜率但错过大趋势，会伤害复利。下一步必须同时看成功率、平均盈亏、尾部大赢家保留率。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage234 已完成和 Stage235 下一步。
- 是否更新 `research/registry.md`：是，将最新阶段从启动改为首轮离线审计完成。
- 是否追加根目录 `memory.md/back_log.md`：是，作为新研究线启动和重要方法边界记录。
