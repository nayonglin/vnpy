# Stage056 Stage880 C9 时段边界只读审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 07:09 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因与分钟K视觉审计；不改策略、不接真实引擎、不连接 CTP、不调用下单。
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - `https://github.com/vnpy/vnpy`
  - `https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf`
  - `https://www.cmegroup.com/education/courses/introduction-to-futures/open-interest.html`
- 我的判断：
  - Stage879 已反证 early OI 退出，继续扫 OR/R/OI 小阈值会过拟合。
  - 交易时段边界属于交易制度外生结构，不是从单个品种、年份或亏损样本反推的小补丁；值得一次只读审计。
  - 但时段边界只能作为实时已知语义标签，不能直接写成“禁止夜盘重试/禁止跨时段重试”，必须先证明不砍右尾。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage880_stage863_session_boundary_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - 固定时段标签：`pre_day_night=00:00-02:45`、`day_session=09:00-15:15`、`post_day_night=21:00-23:59`。
  - 固定代理：`P1_same_session_only_retry`，即 C9 首次 `0.5R` 止损后，只允许在同一连续时段内重回原入场价重试。
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage863/C9 全周期 `2018-01-01` 至 `2026-05-29`。
- 账户规模：Stage819 候选 `30w` 口径。
- 成本口径：读取 Stage863 C9 已生成成交与 closed lots，不新增成交成本假设。
- 样本过滤：
  - 仅取 `profile == stage847_stage819_c4_05r_stop_retry_once` 的 C9 stop/retry events。
  - C9 stop/retry events `121` 个，全部匹配 C9 closed lots。
  - 分钟K读取 Stage861 full minute bars。
- 策略/归因口径：
  - 不重跑组合引擎，不生成新权益曲线。
  - 按 `first_stop_time`、`reentry_time`、`retry_failed_time` 的实际分钟时间做时段归类。
  - 对跨时段重试只做代理：若不允许跨时段重试，则保留首次止损，不承接 reentry leg。

## 结果

- 期末权益：不适用，本阶段不是组合回测；参考 C9 为 `50,637,144.6`。
- 总收益：不适用；参考 C9 为 `16,779.0482%`。
- 最大回撤：不适用；参考 C9 为 `-42.6313%`。
- Sharpe：不适用；参考 C9 为 `1.6312`。
- 总滑点：不适用；参考 C9 为 `3,607,030`。
- 总交易次数：不适用；参考 C9 为 `786`。
- 胜率：不适用；参考 C9 为 `53.5299%`。
- 其他关键指标：
  - C9 stop/retry events：`121`
  - `flat_no_reentry`：`70` 个，matched PnL `-7,254,608.7`
  - `flat_retry_failed`：`25` 个，matched PnL `-2,822,189.6`
  - `open_after_reentry`：`26` 个，matched PnL `+4,305,799.7`
  - 跨时段重试：`9` 个，全部为 `day_session -> post_day_night`
  - 跨时段重试原始 matched PnL：`+1,138,795.0`
  - `day_session -> post_day_night -> none` 的 `open_after_reentry`：`6` 个，matched PnL `+1,399,275.0`
  - `day_session -> post_day_night -> post_day_night` 的 `flat_retry_failed`：`3` 个，matched PnL `-260,480.0`
  - `P1_same_session_only_retry` affected events：`9/121 = 7.4380%`
  - `P1_same_session_only_retry` gross proxy delta：`-1,533,365.0`
  - `P1_same_session_only_retry` winner_cut：`-1,816,900.0`
  - `P1_same_session_only_retry` loser_saved：`+283,535.0`
  - `P1_same_session_only_retry` big_winner_cut：`0.0`
  - 年度 proxy delta：正 `3` 年、负 `3` 年；最差 `2022 = -1,812,720.0`，最好 `2023 = +128,265.0`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_report_stage880_stage863_session_boundary_audit_v1.md`
- features：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_features_stage880_stage863_session_boundary_audit_v1.csv`
- session_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_session_summary_stage880_stage863_session_boundary_audit_v1.csv`
- proxy_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_proxy_summary_stage880_stage863_session_boundary_audit_v1.csv`
- yearly：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_yearly_stage880_stage863_session_boundary_audit_v1.csv`
- summary_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_summary_chart_stage880_stage863_session_boundary_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_atlas_manifest_stage880_stage863_session_boundary_audit_v1.csv`
- atlas：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_atlas_page001_stage880_stage863_session_boundary_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_atlas_page002_stage880_stage863_session_boundary_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_atlas_page003_stage880_stage863_session_boundary_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_atlas_page004_stage880_stage863_session_boundary_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage880_stage863_session_boundary_audit_decision_stage880_stage863_session_boundary_audit_v1.json`

## 结论

- 本阶段结论：`stage880_session_boundary_same_session_retry_not_promoted_no_engine`
- 是否进入下一步：不进入真实引擎，不接 A/B，不做成本压力或滚动起点。
- 下一步：
  - 时段边界保留为复盘标签。
  - 停止“禁止夜盘重试”“禁止跨时段重试”“开盘/收盘分钟小窗口”这类直接规则。
  - 若继续，只能围绕账户/持仓层生存问题，或寻找能保护 `day -> post_night` 恢复右尾的新低自由度外生信息源。

## 过拟合反思

- 运行前判断：不是过拟合。
- 运行后判断：本阶段本身不是过拟合，但若继续把 `day/post_night` 拆成更多分钟、品种、年份或方向规则，会过拟合。
- 原因：
  - 本阶段只用交易制度时段边界和一个固定代理，没有扫描阈值。
  - 结果显示跨时段重试样本少，且净贡献为正；如果为了救 3 个 retry_failed 而禁止所有夜盘重试，就是典型右尾误伤。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：时段边界路线本身继续价值低；整条研究线继续价值只剩账户/持仓生存或新外生信息源。
- 原因：
  - Stage880 证明跨时段重试不是 C9 的主要错误来源，反而包含恢复右尾。
  - 继续做夜盘/日盘细分大概率只是在已知失败簇上救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage056 与限制。
- 是否更新 `research/registry.md`：否，本阶段不是重要突破或正式候选。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是本线内反证。
