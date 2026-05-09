# Stage78月度AI品种池SOP

## 定位

- 本SOP服务于第78正式趋势基准的准实盘/影子盘月度选品。
- 它不是新策略，不修改Stage78正式参数，不自动覆盖正式 eligibility 文件。
- 目标是确保每月AI品种池使用“上一个完整月末”的可得数据生成，避免沿用过期池，也避免用月中不完整数据做正式池。

## 运行频率

- 每月第一个可用交易日之后运行一次。
- 如果当月初数据源尚未补齐，可以等日线、主力合约、AI源归因文件都更新后再运行。
- 日度影子盘可以每天跑；月度AI池不需要每天重算。

## 默认时序口径

- 生成5月池：使用4月最后一个有完整数据的交易日，例如 `2026-04-30`。
- 生成6月池：使用5月最后一个有完整数据的交易日。
- 不使用当前月月中日期，除非明确传入 `--allow-incomplete-month` 做诊断；诊断结果不能直接作为正式影子盘池。
- 训练标签必须早于 live eval date 的未来收益窗口，当前Stage182会用 `training_label_cutoff` 控制，不允许用4月30之后的未来收益训练4月30决策。

## 月度流程

1. 确认当前模式和研究线。
   - 读取 `work-type.txt`。
   - 读取 `research/registry.md`，确认当前线是 `futures_trend`。

2. 确认日线和主力合约数据已更新。
   - 若日度影子报告还缺最近交易日，先跑数据缺口检查和数据更新。
   - 目标不是追求当天一定有信号，而是保证月末评估日的数据可得。

3. 刷新AI选品源归因文件。

   ```bash
   .py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage183_ai_product_pool_source_refresh.py --analysis-end YYYY-MM-DD
   ```

   - `YYYY-MM-DD` 通常填当前已更新到的最近交易日。
   - 输出前缀默认是 `qmt_roll_stage183_ai_source_floor35`。
   - 该步骤只刷新源归因文件，不覆盖正式Stage78 eligibility。

4. 生成月度 live inference 品种池。

   ```bash
   .py311/bin/python examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py --source-prefix qmt_roll_stage183_ai_source_floor35
   ```

   - 默认使用最新完整月末作为 `eval_date`。
   - 如果今天是5月9日，且源数据已到5月7日，则应生成 `eval_date=2026-04-30`。
   - 不传 `--allow-incomplete-month`，除非只是诊断。

5. 检查输出。
   - `eval_date` 必须等于上一个完整月末。
   - `source_max_date` 必须不早于该完整月末。
   - `training_label_cutoff` 必须早于 `eval_date`，且留足未来收益标签窗口。
   - `safety.overwrites_official_stage78_eligibility` 必须是 `false`。
   - `safety.uses_future_label_for_eval_date` 必须是 `false`。
   - `safety.real_order_enabled` 必须是 `false`。

6. 记录阶段文件。
   - 写入 `research/lines/futures_trend/stages/YYYYMMDD_HHMM_stageNNN_short_slug.md`。
   - 记录源数据最大日期、eval date、Top9品种、是否覆盖正式文件、是否有未来标签泄漏。

## 核心输出

- Stage183源刷新报告：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_report_stage183_ai_product_pool_source_refresh_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_summary_stage183_ai_product_pool_source_refresh_v1.json`
- Stage182月度池报告：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_report_stage182_ai_product_pool_live_inference_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
- Stage182月度池：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`

## GO/NO-GO检查

| 检查项 | GO | NO-GO |
| --- | --- | --- |
| eval date | 上一个完整月末 | 回退到更早月份且原因不明 |
| source max date | 不早于完整月末 | 早于完整月末 |
| official overwrite | false | true |
| real order | false | true |
| future label | false | true |
| Top9 | 有9个品种，含固定 `fu.SHFE` 卫星 | 少于9个且无解释 |
| 记录 | 已写stage文件 | 未留痕 |

## 异常处理

- 如果生成的 `eval_date` 比预期早一个月，先查 Stage183 源文件最大日期，不要直接强制传 `--eval-date`。
- 如果源文件最大日期没更新，先跑 Stage183；仍不更新时，检查日线和主力合约数据。
- 如果只想看月中诊断，可以使用 `--allow-incomplete-month`，但结果只允许标记为诊断，不允许进入影子盘正式月度池。
- 如果 `fu.SHFE` 已在Top8中，不重复添加；否则作为第9个固定卫星加入。

## 是否抽象成skill

- 当前结论：暂不抽象成全局skill。
- 原因：这套流程强依赖本仓库第78、Stage182/183、固定输出路径和 futures_trend 记录规范，做成全局skill会过早泛化。
- 后续触发条件：
  - 连续跑过2到3个月，命令、输出和异常处理稳定；
  - 日度影子盘、CTP只读、月度AI池三个SOP边界稳定；
  - 同类流程开始在其他研究线复用。
- 到那时再抽象为 repo-local skill 或 Codex skill，内容只封装流程判断和检查清单，不封装策略参数。

## 过拟合与继续价值

- 过拟合判断：否。SOP只规定数据时序、源刷新、输出检查和留痕，不根据结果反向调参。
- 继续价值判断：有价值。月度池如果不进入固定SOP，影子盘会出现“日线已更新但AI池过期”的隐性风险。
