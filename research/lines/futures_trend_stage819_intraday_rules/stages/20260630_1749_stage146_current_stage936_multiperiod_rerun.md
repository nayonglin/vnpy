# Stage146 当前版本 Stage936 多周期回测复跑

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-30 17:49 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：当前 live C9/15w 固定半年、固定一年 horizon 复跑与旧基准对比
- 是否重要突破：否，但这是一次重要复核；结论是“当前版本不等于 Stage128 旧数”
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：GitHub `vnpy/vnpy` 仍定位为本地量化交易框架，包含行情、回测、网关和交易接口能力；本阶段只使用本地 backtest 脚本和 CSV 产物，不连接 CTP/SimNow，不调用订单接口。
- 我的判断：用户要看“现在版本是否和之前一样”，核心不是继续优化参数，而是用当前 live config 复跑 Stage936，并把不一致的本地证据说清楚。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无策略参数
- 删除参数：无策略参数
- 重建生成物：
  - `qmt_roll_stage861_stage860_full_visual_atlas_full_minute_bars_stage861_stage860_full_visual_atlas_v1.csv`：从本地 Stage459/498/859 raw cache 归一化重建，`1,291,049` 行、`502` 合约。
  - `qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv`：从本地 Stage448 raw cache 聚合重建，`1,453,601` 行、`228` 合约。
  - `qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv`：补最小空 seed 文件，让 Stage501 走既有 raw fallback roots 取 14:55/21:00/09:00 代理价。

## 回测/归因参数

- 数据区间：Stage936 固定最新完整数据日 `2026-06-15`
- 起点计划：从 `2020-01-01` 起，每年 `1月1日/7月1日`
- horizon：完整半年与完整一年；周年日不是交易日时取之前或当天最后交易日
- 账户规模：当前 live C9/15w，`150,000`
- 成本口径：沿用当前 Stage936/Stage901 live C9 包装，不新增成本压力
- 样本过滤：`2026-01` 未满半年，按脚本排除
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`

## 结果

- 期末权益：不适用；本阶段统计多起点 horizon 分布
- 总收益：不适用
- 最大回撤：半年 horizon 最差路径内最大回撤 `-37.5238%`；一年 horizon 最差路径内最大回撤 `-54.0397%`
- Sharpe：不适用
- 总滑点：沿脚本输出，不单独汇总
- 总交易次数：沿脚本输出，不单独汇总
- 胜率：
  - 半年完整样本 `12` 个，正收益 `10/12`
  - 一年完整样本 `11` 个，正收益 `8/11`
- 其他关键指标：
  - 半年：最低 `-29.5400%`，中位 `17.5883%`，最高 `159.9707%`；最差起点 `2022-01`，最好起点 `2021-01`
  - 一年：最低 `-15.2867%`，中位 `45.7572%`，最高 `460.4040%`；最差起点 `2022-01`，最好起点 `2021-01`
  - 订单 API：`send_order_api_called_count=0`，`cancel_order_api_called_count=0`，`ctp_connected=false`

## 与 Stage128 旧基准对比

- Stage128 旧基准：
  - 半年：最低 `-6.8463%`，中位 `18.7133%`，最高 `149.1644%`，正收益 `11/12`
  - 一年：最低 `16.6550%`，中位 `46.6351%`，最高 `641.3979%`，正收益 `11/11`
- 本次当前版本：
  - 半年：最低 `-29.5400%`，中位 `17.5883%`，最高 `159.9707%`，正收益 `10/12`
  - 一年：最低 `-15.2867%`，中位 `45.7572%`，最高 `460.4040%`，正收益 `8/11`
- 结论：不一样，不能宣称 1:1 复现 Stage128。
- 本地证据原因：
  - 当前 Stage182 最新 AI 池为 `SA.CZCE / MA.CZCE / OI.CZCE / si.GFEX / AP.CZCE / FG.CZCE / SM.CZCE / jm.DCE / fu.SHFE`，而 Stage128 旧记录写的是 `SA / si / FG / MA / OI / jm / AP / rb / fu`，当前已由 `SM` 替换旧 `rb`，这会改变当前 live 回测路径。
  - Stage449/861 是从保留 raw cache 功能性重建，不是原始 `backtest_outputs` 字节级恢复；其中 Stage149 detail 使用空 seed 让 Stage501 走 raw fallback，适合当前复跑，但不能证明与旧 detail 字节级完全一致。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_report_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.md`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_stats_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- detail：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_detail_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_curves_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.csv`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_dashboard_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage936_c9_live_15w_halfyear_start_horizon_returns_decision_stage936_c9_live_15w_halfyear_start_horizon_returns_v1.json`

## 结论

- 本阶段结论：当前版本 Stage936 多周期回测已跑通，但结果不等于 Stage128 旧基准；主要应按“当前 AI 池与当前重建输入下的新结果”理解，而不能说历史输出被 1:1 复原。
- 是否进入下一步：有条件进入下一步。
- 下一步：如果目标是“当前实盘风险预期”，用本次结果；如果目标是“Stage128 字节级复现”，必须找回当时原始 Stage149/861/182 产物或冻结当时 AI 池，不能用当前月更 AI 池替代。

## 过拟合反思

- 运行前判断：否。起点、horizon、资金口径和 live version 都由既有 Stage936 固定。
- 运行后判断：否。本阶段没有按结果改参数、挑窗口或筛品种。
- 原因：差异用于识别当前版本与旧基准不一致，不用于反向救参；继续拿本结果调 R 倍数、重试次数、品种或 AI topN 才会过拟合。

## 继续价值反思

- 运行前判断：是。用户明确要确认当前版本多周期结果是否和之前一致。
- 运行后判断：是，但下一步目标要分清。
- 原因：当前实盘心理预期需要用当前版本数；历史复现需要原始字节级产物或冻结旧 AI 池，二者不能混用。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage146 当前结果和“不等于 Stage128”的结论。
- 是否更新 `research/registry.md`：否；未改变当前 live default 或 SOP。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段不是新策略突破或正式候选变更。
