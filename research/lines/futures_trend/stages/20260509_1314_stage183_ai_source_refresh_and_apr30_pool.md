# Stage183 AI源刷新与4月30月度品种池

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-09 13:14 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：准实盘月度AI选品工程修复与留痕
- 是否重要突破：否，属于上线前数据链路补齐
- 是否触发A/B：否，未改正式Stage78策略参数，未接入正式 eligibility

## 外部调研与判断

- 参考资料：本次重点是本地数据链路审计，依据 `work-type.txt`、`research/registry.md`、Stage182/Stage183 输出报告与本地CSV最大日期判断；未新增外部策略资料。
- 我的判断：用户指出“5月9日应使用4月30数据生成5月品种池”是正确的。此前 Stage182 回落到 `2026-03-31`，原因不是月度口径错误，而是 AI 选品源归因文件仍停在 `2026-04-17`/`2026-04-21`，无法确认4月完整月末。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py`
- 修改脚本：`examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py` 增加 `--source-prefix`，允许使用独立刷新源，不覆盖正式Stage78源文件。
- 删除脚本：无
- 新增参数：
  - Stage182：`--source-prefix`
  - Stage183：`--analysis-start`、`--analysis-end`、`--source-prefix`
- 修改参数：无正式策略参数修改
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-01 至 2026-05-07
- 账户规模：沿用源归因脚本默认资金口径；本阶段不代表30万实盘资金曲线。
- 成本口径：沿用 floor35 源归因口径；总滑点 `352,640`，手续费 `0.0`
- 样本过滤：
  - Stage183 仅刷新 AI 源归因文件到 `2026-05-07`
  - Stage182 live inference 使用 `eval_date=2026-04-30`
  - 训练标签截止 `2026-01-27`，避免使用4月30之后的未来60日标签
- 策略/归因口径：`ai_top8_plus_fu_satellite_post_signal_entry_filter` 的月度 live inference；不覆盖正式Stage78 eligibility。

## 结果

- 期末权益：`2,915,585`
- 总收益：`1357.7925%`
- 最大回撤：`-36.9907%`
- Sharpe：`1.0211`
- 总滑点：`352,640`
- 总交易次数：`1168`
- 胜率：`40.9781%`
- 其他关键指标：
  - Stage183 刷新后 `position_changes_max_date=2026-05-07`
  - Stage183 刷新后 `entry_candidate_snapshots_max_date=2026-05-07`
  - Stage182 live inference `eval_date=2026-04-30`
  - Stage182 `source_max_date=2026-05-07`
  - Stage182 `train_rows=1296`
  - Stage182 `feature_count=108`
  - 5月候选池写入Top9：`SA.CZCE`、`SH.CZCE`、`FG.CZCE`、`si.GFEX`、`MA.CZCE`、`jm.DCE`、`rb.SHFE`、`AP.CZCE`、`fu.SHFE`

## 输出文件

- report：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_report_stage183_ai_product_pool_source_refresh_v1.md`
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_report_stage182_ai_product_pool_live_inference_v1.md`
- summary：
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_summary_stage183_ai_product_pool_source_refresh_v1.json`
  - `/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
- orders：无新增实盘订单；`real_order_enabled=false`
- daily：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_source_floor35_daily.csv`
- quality：通过输出 summary 的安全字段确认：
  - `overwrites_official_stage78_eligibility=false`
  - `uses_future_label_for_eval_date=false`
  - `real_order_enabled=false`

## 结论

- 本阶段结论：确认为“AI源文件未更新”导致月度 live inference 未能走到 `2026-04-30`。刷新源文件后，5月品种池已按 `2026-04-30` 口径生成。
- 是否进入下一步：是。
- 下一步：
  1. 每月第一个可用交易日后，先运行 Stage183 刷新AI源，再运行 Stage182 生成月度池。
  2. 影子盘日报只读取 Stage182 输出，不自动覆盖正式Stage78 eligibility。
  3. 若后续要把5月池接入影子盘，需要再做一次“使用新池的 forward shadow report”对账。

## 过拟合反思

- 运行前判断：否。本次不是调参找更高收益，而是修正数据新鲜度与月度推理链路。
- 运行后判断：否。输出独立前缀，未覆盖正式池，训练标签截止在 `2026-01-27`，没有用4月30之后收益训练4月30决策。
- 原因：这是准实盘必须具备的数据流程校验；它减少的是回测到实盘的时序错配，不是在历史结果上追涨杀跌。

## 继续价值反思

- 运行前判断：有价值。若月度AI池不能按完整月末更新，影子盘会沿用过期品种池，准实盘报告会失真。
- 运行后判断：有价值，且应继续。
- 原因：现在已经能区分“日线数据更新”和“AI源归因更新”两层链路，下一步可以把月度池生成纳入固定SOP。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等影子盘SOP稳定后统一整理。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；若正式接入月度池SOP再写入总账。
