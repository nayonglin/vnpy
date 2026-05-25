# Stage016 国内会员持仓净变化开仓质量探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-25 18:53 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：外生开仓质量因子只读分桶验证
- 是否重要突破：否
- 是否触发A/B：否，本阶段没有形成可接入正式版本的候选

## 外部调研与判断

- 参考资料：
  - AKShare 期货数据文档和 `get_rank_sum_daily` 接口。
  - 国内期货会员持仓排名因子常见做法：前5/10/20会员净持仓、净持仓变化、净持仓占比、与趋势方向一致性。
  - Stage014 CFTC COT 反证结论：外盘持仓只能作为温度计，不宜直接映射中国商品开仓。
- 我的判断：
  - 用户截图里关于 CFTC/COT 的判断方向基本正确：外盘持仓数据不能直接当中国期货市场持仓真相。
  - 更贴近本策略的是国内交易所会员持仓、仓单/库存和基差；但这些数据仍必须先做点时化分桶验证，不能直接变成开仓信号。
  - 会员净多变化是有经济含义的低自由度特征，但如果样本外排序不成立，继续微调权重、窗口或阈值会快速走向过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage315_member_rank_quality_probe.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `FETCH_START_DAY=20230101`
  - `FETCH_END_DAY=20260417`
  - `ROLLING_DAYS=120`
  - `MIN_ROLLING_DAYS=40`
  - `MAX_SIGNAL_AGE_DAYS=7`
  - `member_rank_directional_component = 0.25 * 净持仓水平分量 + 0.75 * 净多变化分量`
  - `suggested_volume_multiplier = clip(1 + 0.12 * quality, 0.88, 1.12)`
  - `veto_flag = quality <= -0.80`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2023-01-01 到 2026-04-17
- 账户规模：不适用，本阶段不运行策略收益回测
- 成本口径：不适用，本阶段只做开仓候选分桶
- 样本过滤：
  - 只使用 Stage78-1 开仓候选样本。
  - 国内会员排名按交易日20:00后可见处理，只允许影响下一交易日及之后候选。
  - 首轮只覆盖 SHFE/CZCE 已能稳定取到 `get_rank_sum_daily` 的品种。
- 策略/归因口径：
  - 不修改第78-1交易逻辑。
  - 不按收益调参，不扫 TopN，不扫阈值。
  - 沿用 Stage013 外生信号评估器，以 valid/test 分桶判断是否有开仓质量排序能力。

## 结果

- 期末权益：不适用，本阶段没有策略收益回测
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 判定：`fail_quality_score_not_monotonic_on_oos_forward_r`
  - 特征行数：`11,753`
  - 外生信号行数：`23,506`
  - 候选样本数：`953`
  - 实际开仓候选数：`315`
  - 候选命中外生信号数：`460`
  - 实际开仓命中外生信号数：`119`
  - 候选命中率：`48.2686%`
  - 实际开仓命中率：`37.7778%`

### 分桶结果

valid 分桶：

- 低分：样本数 `51`，平均20日R `-0.4214`，平均20日不利波动R `4.4133`
- 中分：样本数 `50`，平均20日R `-2.3302`，平均20日不利波动R `5.3312`
- 高分：样本数 `51`，平均20日R `0.4833`，平均20日不利波动R `2.9508`

test 分桶：

- 低分：样本数 `103`，平均20日R `2.4665`，平均20日不利波动R `3.6658`
- 中分：样本数 `102`，平均20日R `3.0380`，平均20日不利波动R `7.9087`
- 高分：样本数 `103`，平均20日R `0.6688`，平均20日不利波动R `3.5537`

真实开仓样本的补充检查：

- valid 高分真实开仓平均20日R `1.0683`，好于低分 `-0.5582`。
- test 高分真实开仓平均20日R `-0.8166`，低于低分 `0.4309`。
- test 中分真实开仓平均20日R `13.1053`，但主要受少数异常样本影响，不构成稳定排序。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_report_stage315_member_rank_quality_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_summary_stage315_member_rank_quality_probe_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_bucket_summary_stage315_member_rank_quality_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_joined_candidates_stage315_member_rank_quality_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_features_stage315_member_rank_quality_probe_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage315_member_rank_quality_probe_external_signals_stage315_member_rank_quality_probe_v1.csv`

## 结论

- 本阶段结论：国内会员净多变化有经济含义，也有一定覆盖率，但不能稳定区分第78-1的好开仓和差开仓。
- 是否进入下一步：不进入 A/C 回测，不接入第78-1，不作为加仓或开仓倍率因子。
- 下一步：
  - 不继续调会员净多变化的权重、窗口、阈值或 TopN。
  - 转向更贴近供需的仓单/库存与基差因子，仍然采用固定低自由度公式和只读分桶。
  - 会员持仓可以作为日后组合解释变量保留，但暂不作为执行因子。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：仍不是过拟合，但继续沿当前公式调参会变成过拟合。
- 原因：
  - 本阶段预先固定公式，没有用结果反推参数。
  - valid 好看、test 失败，说明信号不稳定；如果继续为了让 test 好看而改权重或阈值，就是在拟合噪声。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：这条具体因子不值得继续调参，但外生数据方向仍有价值。
- 原因：
  - 本阶段反证了“会员净多变化直接提升开仓质量”的朴素想法，减少了后续误接入风险。
  - 数据层已经建立缓存，后续国内仓单/库存、基差因子可以复用同一套 Stage013 评估框架。
  - 第78-1回撤目标仍未完成，继续寻找更本质的开仓质量过滤是必要的。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`，不追加 `memory.md`
