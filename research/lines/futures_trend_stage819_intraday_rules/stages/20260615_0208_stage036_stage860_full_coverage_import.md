# Stage036 Stage860 Stage859 raw导入与完整覆盖重算

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 02:08 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：数据导入与覆盖重算，不是策略回测
- 是否重要突破：否，属于本研究线数据覆盖恢复，不是策略收益突破或正式候选
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Stage859 已验证 TqSdk `TqBacktest + get_kline_serial(60)` 可补齐 `DataDownloader` 权限阻断下的剩余分钟K缺口。
  - Stage855 已验证本地 raw patch 可作为研究线专用 patch source。
- 我的判断：
  - Stage859 的 raw 成功必须进入覆盖体系重算后才算证据可用；不能只凭“raw 文件存在”宣称全周期视觉样本恢复。
  - Stage860 的任务是把 Stage855 本地 raw 与 Stage859 TqBacktest raw 合并为 patch source，重新证明 Stage825/849 覆盖状态。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage860_stage859_full_coverage_import.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage825 全周期 closed lots、Stage849 pressure key dates、Stage853 全部 gap requests。
- 账户规模：不适用，本阶段不是回测。
- 成本口径：不适用，本阶段只重算分钟K覆盖。
- 样本过滤：不新增交易样本；只合并 Stage855 与 Stage859 的 exact contract/date minute patch。
- 策略/归因口径：
  - Stage853 gap requests：`126`。
  - Stage855 patch covered requests：`29`。
  - Stage859 patch covered requests：`97`。
  - Stage825 closed lots：`341`。
  - Stage849 pressure key dates：`19`。

## 结果

- 期末权益：不适用，本阶段不是回测。
- 总收益：不适用，本阶段不是回测。
- 最大回撤：不适用，本阶段不是回测。
- Sharpe：不适用，本阶段不是回测。
- 总滑点：不适用，本阶段不是回测。
- 总交易次数：不适用，本阶段不是回测。
- 胜率：不适用，本阶段不是回测。
- 其他关键指标：
  - Stage853 gap requests：`126`。
  - Stage855 覆盖：`29`。
  - Stage859 覆盖：`97`。
  - Stage860 后剩余缺口：`0`。
  - combined patch minute bars：`38,354`。
  - combined patch symbols：`80`。
  - Stage825 entry-day 覆盖从原始 `227/341 = 66.5689%` 提升到 `341/341 = 100%`。
  - 2018 年从 `0/25` 提升到 `25/25`。
  - 2019 年从 `0/45` 提升到 `45/45`。
  - Stage849 pressure key dates 覆盖从原始 `7/19 = 36.8421%` 提升到 `19/19 = 100%`。
  - 决策：`stage860_full_minute_coverage_restored_no_rule`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_report_stage860_stage859_full_coverage_import_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_summary_stage860_stage859_full_coverage_import_v1.csv`
- orders：不适用。
- daily：不适用。
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_combined_patch_minute_bars_stage860_stage859_full_coverage_import_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_request_coverage_after_stage860_stage860_stage859_full_coverage_import_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_stage825_coverage_after_stage860_stage860_stage859_full_coverage_import_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_stage825_year_coverage_after_stage860_stage860_stage859_full_coverage_import_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_stage849_pressure_coverage_after_stage860_stage860_stage859_full_coverage_import_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage860_stage859_full_coverage_import_decision_stage860_stage859_full_coverage_import_v1.json`

## 结论

- 本阶段结论：
  - Stage819 候选分钟级研究线的 entry-day 与 pressure key date 分钟K覆盖已从证据层恢复完整。
  - Stage034 的覆盖偏差阻断已解除，但 Stage860 只证明数据覆盖，不证明任何日内入场/出场规则有效。
  - Stage849 pressure 表中的部分 OHLC 派生字段仍是旧口径空值；这不是覆盖失败，而是因为 Stage860 不重新计算图谱特征。下一步必须用 combined patch minute bars 重算视觉特征。
- 是否进入下一步：是。
- 下一步：
  - Stage861：基于 `combined_patch_minute_bars` 重画全量 `341` 笔 entry-day 图谱和 `19` 个 pressure key dates 图谱，并输出分桶特征。
  - Stage862：在完整视觉证据上重新审计低自由度规则假设；仍禁止直接扫 R 倍数、窗口、品种/方向阈值。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只重算覆盖完整性，不使用收益结果调参，也不生成交易规则；完整覆盖会降低此前 covered subset 选择偏差。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：数据覆盖已经恢复到全周期，可以重新做逐笔 K 线视觉复盘；但此时继续价值在 Stage861 视觉证据，不在直接写策略引擎。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否，本阶段不是正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是本线数据覆盖恢复，不是策略突破或正式候选。
