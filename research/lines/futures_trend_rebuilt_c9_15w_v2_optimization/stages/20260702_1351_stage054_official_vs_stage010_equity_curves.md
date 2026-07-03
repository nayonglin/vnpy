# Stage054 正式版 vs Stage010 资金曲线单独对比

- 记录时间：2026-07-02 13:51 CST
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- model_tag：`stage054_official_vs_stage010_equity_curves_v1`
- 是否重要突破版本：否，本阶段只绘制 Stage053 已汇总曲线，不新增策略规则。
- 新增参数：无交易参数；新增对比集合 `Official C9/15w Stage847` vs `Stage010 quality +25% proxy`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。
- 回测/绘图口径：逐半年起点，终点统一 `2026-06-30`，绝对资金曲线初始资金 `150,000`。

## 外部调研判断

- 本阶段不新增策略假设，不重新调研外部 alpha；沿用 Stage053 的判断：趋势跟踪评估应看多起点路径和右尾保留，不只看单一起点终点收益。
- 本阶段只读取既有曲线产物并单独绘图，不迁移回测框架。

## 过拟合与继续价值反思

- 开始是否过拟合：否。只是把已冻结的正式版和 Stage010 曲线单独画出来，不新增阈值、日期、品种、方向或参数。
- 结束是否过拟合：否。图表只用于观察路径差异，不据此调参。
- 开始是否值得继续：有。Stage010 是当前质量加风险链里最直观胜正式版的 proxy，需要单独看路径是不是只是终点抬高。
- 结束是否值得继续：有。Stage010 在多数路径中红线持续高于正式版，但它仍是 closed-lot proxy，不是真实引擎。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 起点数 | `17` |
| Stage010 终点权益胜正式版 | `17/17` |
| Stage010 最小收益 | `3.3513%` |
| 正式版最小收益 | `1.9011%` |
| Stage010 中位收益 | `286.7196%` |
| 正式版中位收益 | `203.6425%` |
| Stage010 最差最大回撤 | `-41.2213%` |
| 正式版最差最大回撤 | `-56.2069%` |
| 最低终点权益比例 Stage010/正式版 | `1.0142` |
| 中位终点权益比例 Stage010/正式版 | `1.2247` |

## 观察

- Stage010 在 `17/17` 个逐半年起点的终点权益都高于正式版。
- 大部分中早期起点红线不仅终点更高，中间路径也长期高于正式版；这说明不是单一最后几笔交易抬高。
- `2025-07` 和 `2026-01` 的优势很薄，分别约 `1.0695x` 和 `1.0142x`，不能把它理解成稳定解决晚近冷启动问题。
- Stage010 仍是 `AI rank 1-8 + selected_volume>1 +25%` 的 closed-lot proxy；后续必须做真实引擎化和失败窗口归因，不能直接上线。

## 输出

- all_halfyear_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage054_official_vs_stage010_equity_curves/rebuilt_c9_v2_stage054_official_vs_stage010_absolute_equity_curves.png`
- focus_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage054_official_vs_stage010_equity_curves/rebuilt_c9_v2_stage054_official_vs_stage010_focus_equity_curves.png`
- per_start_compare: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage054_official_vs_stage010_equity_curves/rebuilt_c9_v2_stage054_official_vs_stage010_per_start_equity_compare.csv`
