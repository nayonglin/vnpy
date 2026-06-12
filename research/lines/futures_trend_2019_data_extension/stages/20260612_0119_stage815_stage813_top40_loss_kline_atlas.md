# Stage815 Stage813亏损比例Top40 K线图谱

- line_id：`futures_trend_2019_data_extension`
- 当前模式：day
- 记录时间：2026-06-12 01:19 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：全周期回测 + 只读法证画图
- 是否重要突破：否
- 是否触发A/B：否。本阶段只复跑 Stage813 单臂，不比较新策略

## 外部调研与判断

- 参考资料：快速查看 `mplfinance`/Matplotlib 金融图实现资料，确认不需要引入新依赖；本仓已有 Stage797/798/780 自绘 K 线 atlas 更贴近当前合约日线、OI 和成交标记格式。
- 我的判断：本阶段适合做左尾结构观察，不适合直接生成新交易规则。画图不过拟合；看完图后若按这 40 笔倒推过滤阈值，会变成高过拟合风险。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage815_stage813_top40_loss_kline_atlas.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TOP_N=40`
  - `PRE_BARS=50`
  - `POST_BARS=50`
  - `PER_PAGE=4`
  - 画图数据 fallback：Tq 日线 -> 分钟聚合日线 -> Tushare 2015-2019 早期日线
- 修改参数：无策略参数修改；Stage813 官方候选 overrides 原样使用
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01 -> 2026-05-29`
- 账户规模：`500,000`
- 成本口径：沿用 Stage813/Stage804 年度回测口径
- 样本过滤：按 closed lots 中 `theory_return_pct < 0` 的亏损笔，按 `theory_loss_pct=-directional(entry->exit return pct)` 从大到小取前 `40`
- 策略/归因口径：`official_candidate_stage813_50w_am41_oi08_old_ai_long_tighter_stop_rsi95_v1`，即 Stage804 多头更紧初始止损 + RSI95 半平锁盈 + Stage777 AM41/OI0.8/旧AI/maxpos4/关闭连败缩放和 recovery sleeve

## 结果

- 期末权益：`26,293,495`
- 总收益：`5158.699%`
- 最大回撤：`-46.5025%`
- Sharpe：`1.3618`
- 总滑点：`2,029,740`
- 总交易次数：`673`
- 胜率：`53.3847%`
- 其他关键指标：
  - closed lots：`346`
  - 亏损 lots：`176`
  - Top40 最差理论亏损比例：`6.3561%`
  - Top40 第40名理论亏损比例：`2.2777%`
  - Top40 实际 PnL 合计：`-15,102,795`
  - Top40 中 OI 放大命中：`20/40`
  - Top40 中多头：`33/40`，空头：`7/40`
  - Top40 年份集中：`2022` 有 `12` 笔，`2020` 有 `8` 笔，`2021` 有 `6` 笔
  - Top40 退出集中：`long_prev2day_stop=22`、`long_base_stop=11`、`short_prev2day_stop=5`、`short_base_stop=2`
  - Top40 品种数量靠前：`fu.SHFE=7`、`jm.DCE=6`、`AP.CZCE=5`、`ru.SHFE=4`、`MA.CZCE=4`
  - 画图缺失 K 线：`0`；其中分钟聚合日线 `6` 笔，Tushare 早期日线 `5` 笔

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_report_stage815_stage813_top40_loss_kline_atlas_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_summary_stage815_stage813_top40_loss_kline_atlas_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_curve_stage815_stage813_top40_loss_kline_atlas_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_decision_stage815_stage813_top40_loss_kline_atlas_v1.json`
- closed_lots：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_closed_lots_stage815_stage813_top40_loss_kline_atlas_v1.csv`
- top40：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_top40_losses_stage815_stage813_top40_loss_kline_atlas_v1.csv`
- chart：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page01_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page02_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page03_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page04_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page05_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page06_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page07_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page08_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page09_stage815_stage813_top40_loss_kline_atlas_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage815_stage813_top40_loss_kline_atlas_page10_stage815_stage813_top40_loss_kline_atlas_v1.png`

## 结论

- 本阶段结论：Stage813 全周期复跑指标与登记时 2018 起点一致；Top40 亏损图已补齐，无缺失 K 线。左尾观察上，亏损笔明显偏多头、2022 和 OI 放大，但这只能作为复盘线索，不是可直接交易化的过滤规则。
- 是否进入下一步：可以进入人工看图和只读特征归因；不能直接进入规则修改。
- 下一步：如果肉眼看到共性，先把特征定义成不看未来的预声明规则，再跑年度/逐月启动验证；不要直接扫阈值。

## 过拟合反思

- 运行前判断：低。只读复盘和图形生成，不改策略参数。
- 运行后判断：画图本身仍低；但后续解释风险高。
- 原因：Top40 是亏损样本的条件集合，天然会放大坏形态的视觉印象，不能把它当作全样本规律。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值在于识别左尾结构和提出可验证假设。
- 原因：Top40 已暴露 OI 放大、2022、长多头腿和 `prev2day/base_stop` 的集中度；这些可用于下一步只读统计或预声明 A/B，但不能直接改正式候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage815 当前状态
- 是否更新 `research/registry.md`：否，本阶段不改变研究线总方向
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`
