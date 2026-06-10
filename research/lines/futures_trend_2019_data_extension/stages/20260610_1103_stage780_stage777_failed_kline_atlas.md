# Stage780 Stage777 2022 失败交易 K 线图谱

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：`2026-06-10 11:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因绘图；不改策略、不重跑回测、不连接 CTP、不下单
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - CME Group / Britannica / Investopedia 对 OI 的常见解释：OI 上升可辅助确认市场参与度和趋势参与，但不是独立的低风险 alpha。
  - Man Group / Alpha Architect 关于趋势跟踪 whipsaw 和 drawdown 的讨论：趋势系统在反复震荡和政策/宏观冲击期容易出现连续亏损簇。
- 我的判断：
  - 本阶段不基于坏交易调参数，只把 Stage779 已识别的 2022 失败 lot 画出来，辅助肉眼复盘趋势失效和 OI 放大在 K 线结构上的表现。
  - OI 命中后的失败图谱只说明该单因子在 2022 失效窗口会放大错误仓位，不能据此直接推出某个局部 K 线过滤条件。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage780_stage777_failed_kline_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `PRE_BARS=50`
  - `POST_BARS=50`
  - `PER_PAGE=4`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage779 聚焦窗口 `2022-03-09 -> 2022-06-29` 的失败 lot，图中向前/向后各扩展 50 根日线。
- 账户规模：不适用，本阶段不回测。
- 成本口径：沿用 Stage779 已有闭合 lot 的 realized PnL 和 R 倍数，不重新计算成本。
- 样本过滤：
  - 来源：`qmt_roll_stage779_stage777_2022_loss_streak_review_worst_sequence_stage779_stage777_2022_loss_streak_review_v1.csv`
  - 仅保留 `realized_pnl < 0` 的失败交易。
- 策略/归因口径：
  - 版本：Stage777 `oi_restore_am40` / `2021-09` 代表起点。
  - 按 Stage779 的 `seq` 出场序列排序。
  - 图形沿用此前 K 线 atlas 格式：蓝线/蓝三角为入场，紫线/紫三角为出场，红色阴影为持仓亏损段，下方为成交量柱和 OI 线。

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：`14` 笔失败 lot
- 胜率：`0%`，本阶段只筛失败交易
- 其他关键指标：
  - 失败 lot 合计 realized PnL：`-326,330`
  - 其中 OI 命中放大：`9` 笔
  - 缺 K 线数据：`0` 笔
  - 图页数：`4`

## 输出文件

- report：不单独生成 markdown report，本 stage 文件即记录
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_summary_stage780_stage777_failed_kline_atlas_v1.csv`
- manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_manifest_stage780_stage777_failed_kline_atlas_v1.csv`
- charts：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_page01_stage780_stage777_failed_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_page02_stage780_stage777_failed_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_page03_stage780_stage777_failed_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage780_stage777_failed_kline_atlas_page04_stage780_stage777_failed_kline_atlas_v1.png`
- orders：不适用
- daily：不适用
- quality：完成图片非空校验，4 张图尺寸均为 `3230x2635`，像素标准差非零；人工抽查 page01/page04 正常。

## 结论

- 本阶段结论：Stage777 代表起点 2022 失败交易 K 线图谱已生成；失败并非单一 K 线形态，而是多品种在同一趋势失效窗口出现的连续小亏/中亏，其中 OI 命中放大覆盖 9/14 笔。
- 是否进入下一步：可以进入下一步，但方向应是只读提取候选特征，不应直接扫参。
- 下一步：
  - 对这 14 张图和历史大赢家图做结构对照，重点看入场前 10/20 日的路径顺畅度、ATR 压缩/扩张、OI 是否拥挤、同向相关持仓是否拥挤。
  - 若要做规则，先预声明少数跨周期特征，再在全起点/逐年验证，不能只为 2022 失败样本定制过滤。

## 过拟合反思

- 运行前判断：低过拟合风险。
- 运行后判断：低过拟合风险。
- 原因：本阶段只绘制已发生失败交易，不修改规则、不筛选盈利窗口、不根据图形调参数。但如果下一步直接针对这 14 笔设计过滤条件，会迅速转为过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但只限于归因和候选特征发现。
- 原因：图片能帮助识别失败窗口的默会结构，例如突破后不延续、OI/成交量拥挤、均线附近反复、长趋势末端追入等；但最终必须用全周期统计验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage780 当前状态。
- 是否更新 `research/registry.md`：否，本阶段不是路线状态变化。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是详细复盘图谱，不是重要突破或正式候选。
