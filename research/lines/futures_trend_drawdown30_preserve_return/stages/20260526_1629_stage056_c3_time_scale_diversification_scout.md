# Stage056 C3时间尺度分散侦察反证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-26 16:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：同源趋势周期分散路线侦察与反证
- 是否重要突破：否，是路线反证/废弃记录
- 是否触发A/B：是。该思路可能与 C3 组合形成候选，因此已按 A/B 隔离方式新增独立 Stage356 脚本和输出。

## 外部调研与判断

- 参考资料：
  - AKShare/GitHub 期货数据文档显示国内期货仓单、库存、会员持仓、基差等接口存在，后续供需数据补齐有现实数据来源。
  - CTA/商品趋势研究普遍认为多周期、多策略、多市场分散可能降低路径回撤，但前提是新增周期或收益源本身具备有效收益，不是单纯稀释。
- 我的判断：
  - 固定快/慢周期可以作为低过拟合侦察，因为 `3/6/12/24`、`5/10/20/40`、`10/20/40/80` 是结构化整数倍，不是围绕弱窗口扫小数。
  - 但如果快/慢周期自身收益质量太弱，即使日收益相关性中等偏低，也只能用稀释降低回撤，无法满足“回撤30以内且收益不显著降低”的目标。
  - 本阶段结果支持停止同源 MA 周期方向，把精力转回供需数据 2020-2022 点时化补齐或真正独立收益源。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage356_c3_time_scale_diversification_scout.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 趋势周期组：`3/6/12/24`、`5/10/20/40`、`10/20/40/80`
  - 多窗口：`start_2020/start_2021/start_2022/start_2023/start_2024/start_2025/ytd_2026/phase_2024_2025`
  - 净值组合：`70/30`、`80/20`、`60/20/20`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：主窗口 `2020-01-01` 至当前回测终点；另含 2021/2022/2023/2024/2025/2026 起点和 2024-2025 独立启动窗口。
- 账户规模：C3 单腿 `500,000`。
- 成本口径：沿用 C3/Stage78-1 当前成本口径。
- 样本过滤：不改 AI 池、品种池、C3 供需强逆风过滤、风险簇压力降暴露。
- 策略/归因口径：只改 MA 趋势周期；净值组合只用于判断相关性和路径互补，不直接视为可交易版本。

## 结果

- C3基准周期 `5/10/20/40`：
  - 期末权益：`30,925,650`
  - 总收益：`6085.1300%`
  - 最大回撤：`-31.0767%`
  - Sharpe：`1.3663`
  - 总滑点：`1,556,750`
  - 总交易次数：`757`
  - 胜率：`45.3826%`
- 快周期 `3/6/12/24`：
  - 总收益：`105.8480%`
  - 最大回撤：`-55.9149%`
  - Sharpe：`0.2562`
  - 总交易次数：`1238`
  - 胜率：`42.6045%`
- 慢周期 `10/20/40/80`：
  - 总收益：`73.9060%`
  - 最大回撤：`-63.1489%`
  - Sharpe：`0.2747`
  - 总交易次数：`456`
  - 胜率：`46.2882%`
- 全样本日收益相关性：
  - base-fast：`0.3690`
  - base-slow：`0.3970`
  - fast-slow：`0.3528`
- 最佳全样本组合：
  - `80% base + 20% slow`
  - 总收益：`4889.0285%`
  - 收益保留：`80.3439%`
  - 最大回撤：`-29.8115%`
  - Sharpe：`1.6281`
  - 仅全样本通过，多窗口仅 `3/8` 通过，最差窗口最大回撤 `-35.3671%`。
- 最佳多窗口组合：
  - `80% base + 20% fast`
  - 多窗口通过 `5/8`
  - 最低收益保留 `79.2122%`
  - 最差窗口最大回撤 `-31.1032%`
  - 全样本总收益 `4895.4169%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_report_stage356_c3_time_scale_diversification_scout_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_summary_stage356_c3_time_scale_diversification_scout_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_curves_stage356_c3_time_scale_diversification_scout_v1.csv`
- correlation：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_correlation_stage356_c3_time_scale_diversification_scout_v1.csv`
- blend：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_blend_stage356_c3_time_scale_diversification_scout_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage356_c3_time_scale_diversification_scout_decision_stage356_c3_time_scale_diversification_scout_v1.json`

## 结论

- 本阶段结论：`fail_multiperiod_time_scale_source_not_promoted`。固定快/慢周期不能成为 C3 的稳健低回撤保收益来源。
- 是否进入下一步：该路线不进入下一步。
- 下一步：
  - 不继续扫 `4/8/16/32`、`6/12/24/48` 等相邻 MA 周期。
  - 不围绕 `80/20` 或 `70/30` 做权重小数救援。
  - 优先做供需数据 `2020-2022` 点时化补齐，固定 Stage017/018 的公式与 `-0.35` 强逆风阈值，验证 2021 剩余回撤是否能被非价格供需因子解释或降低。

## 过拟合反思

- 运行前判断：不是过拟合。周期组是预先固定的整数倍结构，不根据 2021 或 2026 弱窗口调小数。
- 运行后判断：本阶段不是过拟合，是负结果反证；若继续围绕相邻周期或权重边界微调，就会变成过拟合。
- 原因：快/慢周期自身收益质量很弱，全样本回撤改善主要来自稀释，不能穿越多起点窗口。

## 继续价值反思

- 运行前判断：有价值。多周期 CTA 分散有理论依据，且可用固定周期低自由度验证。
- 运行后判断：该具体时间尺度路线继续价值低；总研究线仍有价值。
- 原因：相关性虽然不高，但新增周期收益源质量不足。更有价值的方向是补齐 2020-2022 供需数据、或寻找真正独立且可承载的收益源。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage056 反证和停止同源周期小数救援。
- 是否更新 `research/registry.md`：是，当前线最新阶段改为 Stage056。
- 是否追加根目录 `memory.md/back_log.md`：是，属于路线废弃记录。
