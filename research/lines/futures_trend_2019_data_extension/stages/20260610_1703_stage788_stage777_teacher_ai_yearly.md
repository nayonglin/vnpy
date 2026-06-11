# Stage788 Stage777-family 新老师 PIT AI 年度首筛

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-10 17:03 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：新 AI 老师源重建 + 严格 PIT 月度选品 + 年度 A/B 首筛
- 是否重要突破：否，但属于重要边界结论：解决“旧老师早期讲课太少”的覆盖问题，同时反证直接替换正式 AI。
- 是否触发A/B：是。新 AI 选品未来可能替换正式 AI，已按 A/B 纪律预声明老师、学生和年度首筛。

## 外部调研与判断

- 参考资料：
  - scikit-learn `TimeSeriesSplit` 官方文档：`https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`
  - vn.py `ArrayManager` GitHub 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
- 我的判断：
  - 时间序列机器学习必须用 walk-forward / point-in-time 口径，训练行必须只使用当时已完成标签，不能把未来月度池倒灌回历史。
  - `ArrayManager` 满窗口后才稳定计算指标，AM41 可作为“老师早期能产生样本”的结构修复，但仍不是正式参数。
  - 老师源必须关闭旧 AI，否则新 AI 只会学习旧 AI 放行后的偏见。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage788_stage777_teacher_ai_yearly.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `STAGE788_MAX_WORKERS`，默认 `4`
  - 老师 A：`am41_no_oi`
  - 老师 B：`am41_oi08`
  - 共同：`research_exact_array_manager_size=41`、`enable_ai_product_pool_filter=False`、`streak_risk_multipliers=1,1,1,1`、关闭 `enable_recovery_sleeve`
- 修改参数：
  - 老师 A 使用 Stage748 50万、基础等效风险 `0.40`、无 OI 放大
  - 老师 B 使用 Stage757 50万、基础等效风险 `0.40`，命中可交易 OI 同向确认恢复到 `0.80`
  - 学生目标策略分别打开/关闭由各自老师生成的 PIT AI eligibility
- 删除参数：无

## 回测/归因参数

- 数据区间：
  - 老师源：`2015-01-01` 到 `2026-05-29`，preload `2014-01-01`
  - 年度 A/B：`2018-01` 到 `2026-01` 共 `9` 个年度起点，统一终点 `2026-05-29`
- 账户规模：50万研究口径
- 成本口径：正常成本，同时输出 cost stress 文件
- 样本过滤：
  - 两个老师均成功产生 `102` 个 scored eval month：`2017-12-29` 到 `2026-05-29`
  - 训练样本中位数：`456` 行、`24` 个训练月份
- 策略/归因口径：
  - 老师只负责生成月度标签和 AI 池，不开旧 AI
  - 学生同口径比较 `AI-on - AI-off`
  - AI 模型形态沿用当前方法：月度横截面品种适配度、未来 `60` 交易日标签、top8 + `fu.SHFE` 卫星

## 结果

### 老师源覆盖

- `am41_no_oi` 老师：
  - position rows：`903,365`
  - candidate snapshots：`1,024`
  - 期末权益：`3,375,875`
  - 总收益：`575.1750%`
  - 最大回撤：`-42.3873%`
  - Sharpe：`0.6743`
  - 总滑点：`518,300`
  - 总交易次数：`1,078`
  - 胜率：`41.1009%`
- `am41_oi08` 老师：
  - position rows：`903,365`
  - candidate snapshots：`1,026`
  - 期末权益：`7,274,125`
  - 总收益：`1354.8250%`
  - 最大回撤：`-54.6106%`
  - Sharpe：`0.7380`
  - 总滑点：`1,342,870`
  - 总交易次数：`1,081`
  - 胜率：`42.0475%`

### 年度 A/B 聚合

| 老师 | 样本 | 起点数 | AI收益胜出 | AI回撤胜出 | AI双胜 | 收益差中位 | 回撤差中位 | Sharpe差中位 | 交易数差中位 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `am41_no_oi` | all | 9 | 5 | 9 | 5 | `+7.545pp` | `+8.2248pp` | `+0.1568` | `-237` |
| `am41_no_oi` | mature252 | 8 | 4 | 8 | 4 | `-10.158pp` | `+10.5592pp` | `-0.0715` | `-282` |
| `am41_oi08` | all | 9 | 6 | 9 | 6 | `+24.643pp` | `+10.2009pp` | `+0.5416` | `-233` |
| `am41_oi08` | mature252 | 8 | 5 | 8 | 5 | `+36.3795pp` | `+11.5709pp` | `+0.5419` | `-275.5` |

### 关键年度细节

- `am41_no_oi`：
  - `2018-01`：AI-on `89.681%/-25.7968%`，AI-off `359.123%/-44.6912%`，少 `269.442pp` 收益但回撤改善 `18.8944pp`
  - `2019-01`：AI-on `92.039%/-25.5372%`，AI-off `444.064%/-42.1194%`，少 `352.025pp` 收益但回撤改善 `16.5822pp`
  - 成熟样本收益差中位为负，说明它更像强过滤/降波动，不是收益增强 AI。
- `am41_oi08`：
  - `2018-01`：AI-on `97.411%/-49.1885%`，AI-off `711.085%/-56.6345%`
  - `2019-01`：AI-on `73.312%/-50.5249%`，AI-off `848.035%/-56.9794%`
  - `2021-01` 后多个起点 AI-on 同时提高收益和回撤，但早期 AI-on 仍出现 DD50 失败。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_report_stage788_stage777_teacher_ai_yearly_v1.md`
- source_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_source_summary_stage788_stage777_teacher_ai_yearly_v1.csv`
- ai_training_audit：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_ai_training_audit_stage788_stage777_teacher_ai_yearly_v1.csv`
- selected_products：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_selected_products_stage788_stage777_teacher_ai_yearly_v1.csv`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_summary_stage788_stage777_teacher_ai_yearly_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_cost_stress_stage788_stage777_teacher_ai_yearly_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_curves_stage788_stage777_teacher_ai_yearly_v1.csv`
- comparison_detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_comparison_detail_stage788_stage777_teacher_ai_yearly_v1.csv`
- comparison_aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_comparison_aggregate_stage788_stage777_teacher_ai_yearly_v1.csv`
- comparison_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_comparison_chart_stage788_stage777_teacher_ai_yearly_v1.png`
- equity_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_equity_selected_stage788_stage777_teacher_ai_yearly_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage788_stage777_teacher_ai_yearly_decision_stage788_stage777_teacher_ai_yearly_v1.json`

## 结论

- 本阶段结论：
  - “旧老师早期讲课太少”的问题已解决：两个新老师都能从 `2017-12` 到 `2026-05` 连续 scored。
  - 新 AI 明确有过滤效果：两个老师下 AI-on 都把年度起点回撤改善为 `9/9`，交易数中位减少约 `230~280` 笔。
  - 但它还不能替换正式 AI：
    - `am41_no_oi` 老师成熟样本收益差中位为 `-10.158pp`，更像防守过滤器，不是收益增强器。
    - `am41_oi08` 老师成熟样本收益差中位为正，但 AI-on 仍有 DD50 失败，说明把 OI 版本当老师会继承高回撤属性。
- 是否进入下一步：
  - 不进入正式替换。
  - 不直接扩大到正式版逐月推广。
- 下一步：
  - 如果继续，应只做“AI 拦截样本归因”：看 AI 砍掉的交易是否集中在低质量品种/方向/case/OI 状态。
  - 若要做可接正式的候选，优先从 `am41_no_oi` 老师研究“防守型 AI pool”，而不是把 `am41_oi08` 直接接正式。
  - 暂停围绕 topN、OI 倍率、AM 根数、训练窗或 future horizon 的扫参。

## 过拟合反思

- 运行前判断：中等风险。
- 运行后判断：仍为中等风险，不可推广。
- 原因：
  - AM41 和 OI 都来自前序研究，不是完全外生新信息。
  - 本轮用预声明两个老师、固定模型形态/top8/fu卫星、先年度起点首筛来压低过拟合。
  - 结果显示收益与回撤目标冲突，没有资格继续用小参数救。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有诊断价值，但作为交易版本继续价值有限。
- 原因：
  - 覆盖性问题被解决，说明重建老师源是正确方向。
  - 但年度 A/B 已说明当前新 AI 更偏防守过滤，不是稳定收益增强器。
  - 后续价值在解释“AI 拦掉了什么”，而不是直接替换正式 AI。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 和 `memory.md`。
