# Stage149 Stage128 旧记录口径一致性审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 20:08 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：旧正式记录口径复跑与重建一致性审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：快速复核了 vn.py 回测应用文档与 vn.py GitHub，结论仍是用本仓 Stage901 live wrapper 复跑最稳，因为 C9/15w 的 AI 池、分钟K注入、broker10 cap 和 0.5R stop/retry 都是本仓封装路径，不能用裸 vn.py 示例脚本替代。
- 我的判断：这次不是优化 alpha，也不是调参；核心是把 `memory.md/back_log.md/LINE.md` 中能查到的旧正式口径记录转成可复验对照，判断当前功能性重建是否等于旧产物状态。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage940_c9_live_15w_full_201801_20260615_reference_compare.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；Stage939 新增只读冻结池文件，把 `2026-05-29` 最新 eval_date membership 替换为旧记录 `SA/si/FG/MA/OI/jm/AP/rb/fu`
- 修改参数：无正式参数修改
- 删除参数：无

## 回测/归因参数

- Stage939 数据区间：Stage936 旧口径，`2020-01-01` 起每年 `1月1日/7月1日`，数据终点 `2026-06-15`，只统计完整半年/一年 horizon
- Stage940 数据区间：旧全周期 A 臂口径 `2018-01-01 -> 2026-06-15`
- 账户规模：`150000`
- 成本口径：现有组合引擎与 Stage650 `_metrics` 口径
- 样本过滤：Stage939 排除 `2026-01` 未满半年起点；Stage940 不做滚动过滤
- 策略/归因口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，复用 Stage901 `_run_live_c9()`；不连接 CTP，不读取账户，不调用订单 API

## 结果

- Stage939 旧最新池 membership replay 没有恢复 Stage128 记录：
  - 半年：当前重建/Stage939 均为最低 `-29.5400%`、中位 `17.5883%`、最高 `159.9707%`、正收益 `10/12`
  - Stage128 旧记录为半年最低 `-6.8463%`、中位 `18.7133%`、最高 `149.1644%`、正收益 `11/12`
  - 一年：当前重建/Stage939 均为最低 `-15.2867%`、中位 `45.7572%`、最高 `460.4040%`、正收益 `8/11`
  - Stage128 旧记录为一年最低 `16.6550%`、中位 `46.6351%`、最高 `641.3979%`、正收益 `11/11`
- Stage940 全周期旧基准也不一致：
  - 当前重建复跑：期末权益 `12,952,634.10`，总收益 `8535.0894%`，最大回撤 `-56.2069%`，Sharpe `1.3559`，总滑点 `1,508,530`，总交易次数 `805`，胜率 `52.7709%`，broker10 峰值 `91.4950%`
  - 旧 `back_log.md` A 臂记录：期末权益 `39,176,437.60`，总收益 `26017.6251%`，最大回撤 `-45.0827%`，Sharpe `1.6331`，总滑点 `2,730,130`，总交易次数 `787`，胜率 `53.2560%`，broker10 峰值 `111.7365%`
- 其他关键指标：Stage939 和当前 Stage936 完全一致，说明单独替换最新 `2026-05-29` 池 membership 没有改变这些 horizon 统计；不一致不应归因成单点 `SM/rb` 替换。

## 输出文件

- Stage939 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare_report_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare_v1.md`
- Stage939 comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare_comparison_stage939_c9_live_15w_stage128_recorded_pool_horizon_compare_v1.csv`
- Stage940 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage940_c9_live_15w_full_201801_20260615_reference_compare_report_stage940_c9_live_15w_full_201801_20260615_reference_compare_v1.md`
- Stage940 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage940_c9_live_15w_full_201801_20260615_reference_compare_summary_stage940_c9_live_15w_full_201801_20260615_reference_compare_v1.csv`
- Stage940 comparison：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage940_c9_live_15w_full_201801_20260615_reference_compare_comparison_stage940_c9_live_15w_full_201801_20260615_reference_compare_v1.csv`

## 结论

- 本阶段结论：当前功能性重建不能 1:1 复现旧 Stage128/旧全周期 A 臂记录；只冻结旧记录中明确写到的最新 AI 池 membership 也不能解释差异。
- 是否进入下一步：是，但下一步应该是追原始产物和 hash，不是调参。
- 下一步：优先找当时原始 Stage182 eligibility 全文件、Stage861 full minute bars、Stage149/501 相关派生产物、旧 Stage936/Stage847 输出备份；如果找不到，只能把当前重建结果作为当前实盘风险口径，把旧记录作为历史参考而非可执行基准。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本次固定旧口径和旧记录 membership，只做一致性审计；没有根据结果新增策略规则、筛选窗口、筛选品种或扫参数。但如果后续为了逼近旧记录反向搜索 AI 池组合或改 Stage847 参数，就是过拟合。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：已经证明“不一致”不是单点最新池 membership 能解释，继续追原始产物有价值；继续调策略无价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，本次审计直接影响当前 live 风险口径解释
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，本次不是正式候选突破，也不是路线废弃；若后续找到原始产物或确认永久无法恢复，再追加总账
