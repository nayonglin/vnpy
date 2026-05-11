# Stage236 Path-aware 信号质量验证

- line_id：`futures_trend_signal_quality_ai`
- 当前模式：`day`
- 记录时间：2026-05-11 10:59 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：路径标签 + purged walk-forward 反证
- 是否重要突破：否，但属于更强负结论
- 是否触发A/B：否，本阶段不改 `78-1`，不接入仓位倍率

## 外部调研与判断

- 参考资料：triple-barrier、meta-labeling、purging/embargo、金融时间序列交叉验证与过拟合控制。
- 我的判断：上一轮 Stage235 的确可能“方法太粗”，因此本阶段改为更接近问题本质的方法。若在更合理的路径标签和 purged walk-forward 下仍然不能稳定分层，则应把问题更多归因于“当前可见特征不足”，而不是“验证方法太弱”。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage236_signal_quality_path_aware.py`
- 修改脚本：无正式策略脚本修改
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：`78-1` 官方口径，初始资金 `500,000`
- 成本口径：沿用 Stage234 的真实开仓样本和 FIFO 已实现收益
- 路径数据：`qmt_roll_official_stage78_1_position_changes_2020_2026_04.csv`
- 路径标签：
  - `quality_label = (mfe_20d_r >= 2.0) and (mae_10d_r >= -1.0)`
  - `eventual_big_winner_label = risk_reward_proxy >= 2.0`
  - `eventual_failure_label = risk_reward_proxy <= -1.0`
- 验证：purged expanding walk-forward，训练集对测试起点做 `20` 天 embargo，并剔除与测试起点标签区间重叠的样本
- 特征：`direction_key`、`signal`、`pairwise_rank_bucket`、`ai_rank_bucket`、`rsi_bucket`、`portfolio_dd_bucket`、`corr_bucket`、`active_positions_bucket`、`breakout_bucket`、`risk_mode_bucket`

## 结果

- 期末权益：不适用，本阶段不是回测策略
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：沿用官方 `78-1` 产物，不在本阶段重复统计
- 总交易次数：官方 `78-1` 产物为 `880`；本阶段样本 `407`
- 胜率：路径高质量标签占比 `38.82%`；最终大赢家占比 `11.79%`；最终失败占比 `24.08%`
- 其他关键指标：
  - `2022`：高分桶质量率 `40.0000%`，低分桶 `55.0000%`；高分桶大赢家率 `10.0000%`，低分桶 `20.0000%`
  - `2023`：高分桶质量率 `16.6667%`，低分桶 `55.5556%`；高分桶大赢家率 `0.0000%`，低分桶 `16.6667%`
  - `2024`：高分桶质量率 `42.1053%`，低分桶 `55.5556%`；高分桶大赢家率 `5.2632%`，低分桶 `22.2222%`
  - `2025`：高分桶质量率 `33.3333%`，低分桶 `61.1111%`；高分桶大赢家率 `11.1111%`，低分桶 `33.3333%`
  - `2026`：高分桶质量率 `28.5714%`，低分桶 `28.5714%`；高分桶大赢家率 `0.0000%`，低分桶 `0.0000%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_report_stage236_signal_quality_path_aware_v1.md`
- samples_enriched：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_samples_enriched_stage236_signal_quality_path_aware_v1.csv`
- window_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_window_summary_stage236_signal_quality_path_aware_v1.csv`
- bucket_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_bucket_summary_stage236_signal_quality_path_aware_v1.csv`
- feature_quality_table：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_feature_quality_table_stage236_signal_quality_path_aware_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage236_signal_quality_path_aware_manifest_stage236_signal_quality_path_aware_v1.json`

## 结论

- 本阶段结论：即便把方法升级为“路径标签 + purged walk-forward”，高分桶仍未稳定优于低分桶，当前信号质量加注方向不成立。
- 是否进入下一步：否，暂停本线的结论被强化。
- 下一步：不再继续优化二级信号质量加注；如未来重开，应基于新的外生特征源或更长样本，而不是继续调现有静态特征。

## 过拟合反思

- 运行前判断：有较高过拟合风险，但可通过更合理标签和 purging 明显降低。
- 运行后判断：是，继续在现有特征上做更复杂模型大概率只是增强拟合，不会增强稳健性。
- 原因：在更强验证框架下，高分桶依然长期弱于低分桶，说明不是简单由粗糙评分器导致。

## 继续价值反思

- 运行前判断：有价值，因为能回答“是不是方法不对”。
- 运行后判断：当前方向已无继续价值。
- 原因：这次反证已经比 Stage235 更接近问题本质；继续调参只会重复劳动。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage236 强反证。
- 是否更新 `research/registry.md`：是，维持暂停/降级并注明“路径标签后仍失败”。
- 是否追加根目录 `memory.md/back_log.md`：是，记录“方法升级后仍不成立”的负结论。
