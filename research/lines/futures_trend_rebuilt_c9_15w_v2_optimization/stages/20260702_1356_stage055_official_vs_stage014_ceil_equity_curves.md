# Stage055 正式版 vs Stage014 ceil integer 资金曲线单独对比

- 记录时间：2026-07-02 13:56 CST
- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- model_tag：`stage055_official_vs_stage014_ceil_equity_curves_v1`
- 是否重要突破版本：否，本阶段只绘制 Stage053 已汇总曲线，不新增策略规则。
- 新增参数：无交易参数；新增对比集合 `Official C9/15w Stage847` vs `Stage014 guarded ceil integer`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。
- 回测/绘图口径：逐半年起点，终点统一 `2026-06-30`，绝对资金曲线初始资金 `150,000`。

## 外部调研判断

- 本阶段不新增策略假设，不重新调研外部 alpha；沿用 Stage053 的判断：趋势跟踪评估应看多起点路径、右尾保留、回撤和弱窗口，而不是只看单一起点终点收益。
- 本阶段只读取既有曲线产物并单独绘图，不迁移回测框架。

## 过拟合与继续价值反思

- 开始是否过拟合：否。只是把已冻结的正式版和 Stage014 ceil 曲线单独画出来，不新增阈值、日期、品种、方向或参数。
- 结束是否过拟合：否。图表只用于观察路径差异，不据此调参。
- 开始是否值得继续：有。Stage014 ceil 是质量加风险链里整数手可实现性较强的 proxy，需要单独看它相比正式版的路径和弱窗口。
- 结束是否值得继续：有。Stage014 ceil 在 `16/17` 个起点终点权益高于正式版，且最差回撤好于正式版；但 `2026-01` 短窗口输给正式版，且 ceil 存在系统性超配小手数问题，不能直接上线。

## 结果

| 指标 | 结果 |
| --- | ---: |
| 起点数 | `17` |
| Stage014 ceil 终点权益胜正式版 | `16/17` |
| Stage014 ceil 最小收益 | `0.0677%` |
| 正式版最小收益 | `1.9011%` |
| Stage014 ceil 中位收益 | `312.0621%` |
| 正式版中位收益 | `203.6425%` |
| Stage014 ceil 最差最大回撤 | `-39.4718%` |
| 正式版最差最大回撤 | `-56.2069%` |
| 最低终点权益比例 Stage014 ceil/正式版 | `0.9820` |
| 中位终点权益比例 Stage014 ceil/正式版 | `1.2490` |
| 最高终点权益比例 Stage014 ceil/正式版 | `1.3571` |

## 观察

- Stage014 ceil 在大部分中早期和中期起点红线明显高于正式版，尤其 `2021-07`、`2022-07` 等窗口优势较大。
- `2026-01` 是唯一终点权益输正式版的起点：Stage014 ceil 期末权益 `150,101.6`，正式版 `152,851.6`，比例 `0.9820`。
- Stage014 ceil 的中位收益和最差最大回撤均优于正式版，但它是整数手 proxy，不是真实引擎；ceil 会系统性把部分小手数向上取整，可能高估可执行风险承载。
- 本阶段不能改变 Stage014 的原结论：`stage014_integer_rounding_not_enough`，它有价值但不能直接晋级。

## 输出

- all_halfyear_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage055_official_vs_stage014_ceil_equity_curves/rebuilt_c9_v2_stage055_official_vs_stage014_ceil_absolute_equity_curves.png`
- focus_chart: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage055_official_vs_stage014_ceil_equity_curves/rebuilt_c9_v2_stage055_official_vs_stage014_ceil_focus_equity_curves.png`
- per_start_compare: `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage055_official_vs_stage014_ceil_equity_curves/rebuilt_c9_v2_stage055_official_vs_stage014_ceil_per_start_equity_compare.csv`
