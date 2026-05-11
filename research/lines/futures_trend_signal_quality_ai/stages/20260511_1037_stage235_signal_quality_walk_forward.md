# Stage235 Walk-forward 信号质量基线验证

- line_id：`futures_trend_signal_quality_ai`
- 当前模式：`day`
- 记录时间：2026-05-11 10:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：离线 walk-forward 二级评分验证
- 是否重要突破：否，结论为反证
- 是否触发A/B：否，本阶段不改 `78-1`，不接入仓位倍率

## 外部调研与判断

- 参考资料：meta-labeling 信号过滤、二级模型按主信号正确概率做 sizing、walk-forward 时间序列验证、金融机器学习过拟合控制。
- 我的判断：meta-labeling 的正确用法是只判断主信号质量，而不是裸预测涨跌；但是否能用于加注，必须由 OOS 高分桶稳定性决定。若高分桶在样本外不能稳定优于低分桶，就不能进入策略层。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage235_signal_quality_walk_forward.py`
- 修改脚本：无正式策略脚本修改
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`78-1` 官方口径，初始资金 `500,000`
- 成本口径：沿用 Stage234 FIFO round-trip `gross_pnl`
- 样本过滤：仅使用 Stage234 的真实开仓样本
- 策略/归因口径：`official_stage78_1_defensive_50w_no_sizing_cap`
- 训练/测试：只用历史训练窗口生成特征桶质量分，再对下一年 OOS 样本打分
- 特征：`direction_key`、`signal`、`ai_rank_bucket`、`rsi_bucket`、`portfolio_dd_bucket`、`corr_bucket`

## 结果

- 期末权益：不适用，本阶段不是回测策略
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：沿用官方 `78-1` 产物，不在本阶段重复统计
- 总交易次数：官方 `78-1` 产物为 `880`；本阶段 OOS scored samples 为 `184`
- 胜率：OOS 各年整体成功率分别为 `40.7407%`、`43.6364%`、`40.7407%`、`19.0476%`
- 其他关键指标：
  - `2023`：高分桶成功率 `33.3333%`，低分桶 `50.0000%`；高分桶平均盈亏 `89,056`，低分桶 `117,151`
  - `2024`：高分桶成功率 `47.3684%`，低分桶 `33.3333%`；高分桶平均盈亏 `176,552`，低分桶 `-37,578`
  - `2025`：高分桶成功率 `27.7778%`，低分桶 `44.4444%`；高分桶平均盈亏 `-26,371`，低分桶 `226,883`
  - `2026`：高分桶成功率 `14.2857%`，低分桶 `28.5714%`；高分桶平均盈亏 `214,960`，低分桶 `-36,068`
  - 只有 `2024` 高分桶同时优于低分桶，`2023/2025/2026` 均未通过稳定性要求

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_report_stage235_signal_quality_walk_forward_v1.md`
- scored_samples：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_scored_samples_stage235_signal_quality_walk_forward_v1.csv`
- window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_window_summary_stage235_signal_quality_walk_forward_v1.csv`
- score_bucket_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_score_bucket_summary_stage235_signal_quality_walk_forward_v1.csv`
- feature_quality_table：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_feature_quality_table_stage235_signal_quality_walk_forward_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage235_signal_quality_walk_forward_manifest_stage235_signal_quality_walk_forward_v1.json`

## 结论

- 本阶段结论：当前简单二级信号质量模型被反证，不能用于 `78-1` 加注或减仓。
- 是否进入下一步：否，按预设停止条件暂停本线。
- 下一步：不继续微调特征桶、不训练复杂模型；若未来有更长样本或独立行情状态标签，再重新开阶段评估。

## 过拟合反思

- 运行前判断：有高过拟合风险。
- 运行后判断：是，若继续调特征或阈值会明显过拟合。
- 原因：OOS 高分桶优势只出现在 `2024`，在 `2023/2025/2026` 失效；趋势策略收益来自少数大单，简单质量评分容易学到历史阶段噪声。

## 继续价值反思

- 运行前判断：有条件继续，前提是 OOS 高分桶稳定。
- 运行后判断：当前无继续价值。
- 原因：它不能稳定识别“好信号”，继续做复杂模型只会提高拟合能力而非穿越周期能力。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage235 反证并暂停。
- 是否更新 `research/registry.md`：是，将下一步改为暂停，等待更长样本或新证据。
- 是否追加根目录 `memory.md/back_log.md`：是，记录该方向的负结论，避免后续重复过拟合。
