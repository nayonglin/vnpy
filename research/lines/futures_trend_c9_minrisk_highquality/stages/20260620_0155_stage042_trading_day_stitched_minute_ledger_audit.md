# Stage042 Trading-Day Stitched Minute Ledger Audit

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 01:55 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读账本审计 / session convention 统一 / 不生成交易规则
- 是否重要突破：否，属于必要数据工程闸门，不是收益突破
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - 郑商所夜盘 FAQ：`https://www.czce.com.cn/cn/ypzt/cjwtjd/webinfo/2014/11/1415698818009586.htm`
  - 大连商品交易所交易时间：`https://www.dce.com.cn/dalianshangpin/ywfw/ywzy/jyywzy/ywlcyzl26/8588664/index.html`
  - vn.py `BarGenerator` 源码：`https://github.com/vnpy/vnpy/blob/master/vnpy/trader/utility.py`
  - Backtrader order execution 文档：`https://www.backtrader.com/docu/order/`
  - NautilusTrader backtesting 文档：`https://nautilustrader.io/docs/latest/concepts/backtesting/`
- 我的判断：
  - 国内期货夜盘交易日口径的本质是“前一工作日晚间夜盘 + 当天日盘”组成同一交易日；因此 `candidate_date 21:00` 与 `official_open_date 09:00` 不能简单按自然日割裂。
  - 成熟回测框架都强调订单执行时间、bar 时间戳和 fill model 必须先统一。Stage041 已证明价格锚点能解释，但事件扫描时间轴没有统一；所以 Stage042 只应做账本审计，不能写分钟进出场规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage042_trading_day_stitched_minute_ledger_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增审计字段 `stage042_session_convention_status`、`stage042_raw_event_before_official_open`、`stage042_raw_to_official_open_minutes`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用官方 C9/15w Stage041 输入，`2018-01-02` 至 `2026-06-04` 左右的官方曲线与 Stage861 分钟源
- 账户规模：`150000`
- 成本口径：沿用官方曲线，`total_slippage=2,730,130`
- 样本过滤：Stage041 `timestamp_ready=1` 的 initial orders，共 `219` 笔；其中 raw Stage861 replay ready `204` 笔
- 策略/归因口径：
  - 官方正式版：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
  - 仅构建 trading-day stitched minute ledger，把 raw timestamp、official open anchor、official intraday event 与 Stage861 bar 顺序放到同一 session 口径。
  - 不生成候选策略、不改变 entry/exit、不改变资金路径。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - timestamp-ready orders：`219`
  - raw Stage861 replay ready：`204`
  - raw timestamp 在 official date 内：`64`
  - raw timestamp 在 candidate date 夜盘但不在 official date 内：`140`
  - Stage861 缺 raw timestamp：`15`
  - session convention consistent：`152`
  - raw replay 在 official open 前触发任意事件：`44`
  - raw replay 在 official open 前触发且造成 mismatch：`18`
  - official diagnostics 在 official open 前触发：`0`
  - raw replay after official open mismatch：`8`
  - raw 到 official open 中位间隔：`720` 分钟
  - stitched session 中位 bar 数：`465`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_report_stage042_trading_day_stitched_minute_ledger_audit_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_summary_stage042_trading_day_stitched_minute_ledger_audit_v1.csv`
- orders：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_session_order_ledger_stage042_trading_day_stitched_minute_ledger_audit_v1.csv`
- daily：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_session_path_chart_stage042_trading_day_stitched_minute_ledger_audit_v1.png`
- quality：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_event_diagnostic_stage042_trading_day_stitched_minute_ledger_audit_v1.csv`
- stitched bar ledger：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_stitched_bar_ledger_stage042_trading_day_stitched_minute_ledger_audit_v1.csv`
- atlas：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage042_trading_day_stitched_minute_ledger_audit/qmt_roll_stage042_c9_minrisk_trading_day_stitched_minute_ledger_audit_atlas_manifest_stage042_trading_day_stitched_minute_ledger_audit_v1.csv`

## 结论

- 本阶段结论：
  - Stage042 已把 `candidate_date 21:00` 夜盘、`official_open_date 09:00` 日盘、Stage861 `bar_datetime` 与 official intraday diagnostics 放到同一 trading-day stitched ledger。
  - Stage041 raw stitched replay 的 `26` 个 mismatch 中，`18` 个是 raw replay 扫描了 official open 前的夜盘 bar 后先触发事件；官方 diagnostics 本身没有 official open 前事件。这证明当前差异主要是 session convention，而不是新的信号质量差异。
  - same-exit raw stitched 曲线与官方曲线重合，仍只说明成交价锚点一致，不证明 raw timestamp 可以直接作为分钟规则起点。
- 是否进入下一步：进入账本语义修复下一步，但不进入候选策略、不触发 A/B。
- 下一步：
  - 在 Stage042 ledger 基础上修 replay semantics：明确 official intraday diagnostics 是否从 official open anchor 开始扫描，夜盘 raw timestamp 只作为成交价来源还是也应作为可交易事件时间。
  - replay 与官方事件口径未通过前，继续暂停新增分钟开仓、恢复、降仓或退出规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有选择收益窗口、品种、方向或参数，也没有用最终盈亏筛样本。
  - 只把交易所夜盘交易日常识、Stage861 分钟时间戳和官方事件诊断统一成可审计账本，属于防止伪精度的基础设施。

## 继续价值反思

- 运行前判断：有。
- 运行后判断：有。
- 原因：
  - 现在能清楚解释 raw timestamp replay 的主要不一致来源：`18` 个 pre-official night mismatch。
  - 这能避免后续把夜盘扫描口径差异误当成可交易信号，降低后续研究过拟合风险。
  - 下一步仍有价值，但必须继续限定在 replay semantics 修复，不应急着写规则。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage042 结论与下一步。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是线内账本闸门，不是重要合入摘要。
