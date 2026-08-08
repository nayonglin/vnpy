# Stage208 C9/15万 2R 大赢家前后5交易日 15分钟K线图谱设计

- line_id：`futures_trend_stage819_intraday_rules`
- 记录时间：`2026-08-08 17:39 CST`
- 当前模式：`day / research / readonly visualization design`
- 阶段性质：实现前冻结设计；不是策略实验，不修改正式配置，不运行新回测
- 正式版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 用户确认：采用方案A，全部聚合收益 `>=2R` 的交易；按聚合收益率从高到低排序；K线粒度为 `15分钟`
- 是否重要突破：否
- 是否触发A/B：否；本阶段只做历史交易视觉法证

## 外部调研与判断

- 参考 `mplfinance` 官方仓库的多日分钟图说明：多日分钟K可以压缩没有数据的非交易区间；大量分钟蜡烛需要控制粒度，避免图形不可读。
  - `https://github.com/matplotlib/mplfinance`
  - `https://github.com/matplotlib/mplfinance/wiki/Plotting-Too-Much-Data`
- 本仓当前 `.py311` 没有安装 `mplfinance`，但已有 `pandas + matplotlib`，且 Stage825/861 已有自绘分钟K图实现。
- 判断：不新增依赖，复用本仓 Matplotlib 画法；把1分钟数据按交易日内真实时间顺序聚合为15分钟OHLC，压缩休市空白，保留交易日分隔线。

## 目标

对标准正式 C9/15万 `2020-01` 冷启动基准中的全部 `>=2R` 聚合开仓事件，绘制开仓交易日前5个交易日、开仓日、后5个交易日，共11个交易日的连续15分钟K线图，用于只读观察大赢家开仓前后的跨日价格结构。

## 数据身份与冻结样本

### 正式交易账本

- 输入：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage006_current_quality_feature_binder/rebuilt_c9_stage006_current_quality_feature_binder_closed_lots_stage006_current_quality_feature_binder_v1.csv`
- 只保留 `requested_start_month == "2020-01"`。
- 按 `open_trade_id` 聚合同一次开仓对应的分批平仓 lot。
- 聚合字段：
  - `realized_pnl = sum(realized_pnl)`
  - `risk_amount = sum(risk_amount)`
  - `aggregate_r = realized_pnl / risk_amount`
  - `exit_date = max(exit_date)`
- 固定样本门：`aggregate_r >= 2.0`。
- 当前预检：`309` 个聚合开仓事件中 `71` 个满足门槛。
- 排序：`aggregate_r` 降序；并列时依次按 `realized_pnl` 降序、`entry_date` 升序、`open_trade_id` 升序。
- 禁止按品种、年份、方向、图形好坏或事后主观判断删除样本。

### 分钟数据

- 主输入：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv`。
- 数据字段：`vt_symbol/bar_datetime/open/high/low/close/volume/open_oi/close_oi/minute_source`。
- 当前主输入范围：`2018-01-15 09:00 -> 2026-04-24 14:58`，`1,291,049` 行、`502` 个合约。
- 只读取71个目标事件需要的合约和窗口，不把完整分钟文件复制进新输出。
- 预检已知：71笔中有1笔开仓日晚于主分钟源截止日，即 `BACKTESTING.626 / jm2609.DCE / 2026-06-03 / aggregate_r=4.6667`。该笔不得删除；若没有合法本地分钟源，生成明确的缺失占位图并写入覆盖清单。

## 交易日和夜盘语义

- 用标准正式 `2020-01` 曲线中的交易日期作为有序交易日历。
- `20:00` 及以后开始的夜盘分钟归入下一个可用交易日；`00:00-02:59` 与当日日盘归入该自然日对应交易日。
- 每笔图固定取入场交易日在交易日历中的前5、当日、后5，共11个交易日；样本位于边界时允许不足11日，但必须在 manifest 记录实际天数。
- 图中按真实分钟时间先后排序，但压缩周末、节假日和盘中休市空白；每个交易日边界画垂直分隔线并标注交易日期。

## 15分钟聚合

- 在每个交易日内按实际 `bar_datetime` 的15分钟桶聚合，不能跨交易日或跨夜/日盘边界合并。
- OHLCV/OI 规则：
  - `open = first(open)`
  - `high = max(high)`
  - `low = min(low)`
  - `close = last(close)`
  - `volume = sum(volume)`
  - `open_oi = first(open_oi)`
  - `close_oi = last(close_oi)`
- 去重键为 `vt_symbol + bar_datetime`；同键保留 Stage861 已冻结记录，不做价格插值。
- 空桶不补K线，不把前值填充为虚假成交。

## 图表设计

- 每个聚合开仓事件输出一张独立 PNG。
- 主图：11交易日连续15分钟蜡烛图。
- 颜色：上涨红、下跌绿；同时用轮廓和方向文字避免仅依赖颜色判断。
- 标记：
  - 开仓交易日背景使用低透明度强调。
  - 开仓价格画水平虚线，标题显示 `long/short`、入场价、聚合R、累计盈亏、持有天数。
  - 正式日线开仓记录只有日期且部分初始开仓时间为 `00:00`；没有可信分钟时间时只标记“开仓交易日 + 开仓价格”，不伪造具体开仓分钟。
  - 若真实平仓时间落在11日窗口内且可由 trades 账本定位，则标记平仓；否则只在标题展示最终平仓日。
- 辅图：成交量柱，不增加技术指标、均线或策略解释标签。
- 文件名前缀包含四位收益排名、合约、方向、开仓日和聚合R，确保文件系统排序与收益率排序一致。
- 另生成分页 atlas，每页4笔，顺序与单图一致，便于连续浏览。

## 输出

- 实现脚本：`research/lines/futures_trend_stage819_intraday_rules/tools/stage208_c9_2r_winner_15m_atlas.py`
- 单元测试：`research/lines/futures_trend_stage819_intraday_rules/tests/test_stage208_c9_2r_winner_15m_atlas.py`
- 输出目录：`research/lines/futures_trend_stage819_intraday_rules/outputs/stage208_c9_2r_winner_15m_atlas/`
- 必需产物：
  - `winner_manifest.csv`：71笔冻结样本、收益排名、聚合R、PnL、数据覆盖和图路径
  - `coverage_summary.csv`：每笔目标11交易日的原始1分钟/聚合15分钟覆盖
  - `winner_*.png`：每笔独立图或缺失占位图
  - `atlas_page*.png`：每页4笔的分页图谱
  - `decision.json`：输入hash、样本数、覆盖率、图数、订单API计数和结论
  - `report.md`：中文结果与口径边界

## 失败关闭与验证

- 若 `2020-01` 基准聚合事件数不等于 `309`，或 `>=2R` 数量不等于 `71`，脚本直接失败，不静默改变门槛。
- 每个 manifest 行必须有且只有一个单图路径；缺数据也必须输出占位图。
- 有数据的图必须满足：OHLC非空、`high >= max(open, close)`、`low <= min(open, close)`、时间严格递增、交易日数不超过11。
- 收益排名必须单调非增；抽查排名1、末位和已知缺失样本。
- `send_order_api_called_count=0`、`cancel_order_api_called_count=0`、`ctp_connected=false`。
- 运行本阶段不修改正式配置、AI池、回测参数、CTP、邮件或launchd。

## 过拟合反思

- 运行前：否。样本门槛、样本范围、排序和图形窗口都在看图前冻结，并且71笔全部绘制。
- 风险：图谱属于事后赢家法证，不能因为某种视觉形态常见就直接写交易规则；任何候选假设必须另行预注册并包含非赢家对照和OOS验证。

## 继续价值反思

- 有。它能把正式大赢家的开仓日放回前后11个交易日的真实分钟上下文，检查趋势启动、回撤和时段结构。
- 价值边界：本阶段只提供观察证据，不证明可交易规则，不触发A/B，不改变正式版本。

