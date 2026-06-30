# Stage150 Stage182/183 当前输入确定性重建

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 21:20 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：误删 AI 池与源产物后的当前输入确定性重建、只读校验
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮主要复核本仓 SOP、`research/registry.md`、`work-type.txt`、Stage182/183/189/935 脚本与历史记录；没有引入外部策略代码或 GitHub 策略样例，因为这不是 alpha 设计，而是产物恢复与一致性校验。
- 我的判断：当前可见输入下可以把 Stage183 源表、Stage182 最新 AI 池、Stage189 多月 AI 池重新算到稳定状态；但没有删除前原始文件或删除前 hash 时，不能证明它们与被删原件字节级 1:1 相同。当前重建结果与旧 Stage128 记录仍有差异，因此它是“当前线上链路的确定性重建”，不是“旧历史快照的原样找回”。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数
- 修改参数：无
- 删除参数：无
- 新增记录：本 stage 文件

## 回测/归因参数

- Stage183 源表刷新：`--analysis-start 2020-01-01 --analysis-end 2026-06-30 --source-prefix qmt_roll_stage183_ai_source_floor35`
- Stage182 live inference：`--source-prefix qmt_roll_stage183_ai_source_floor35`
- Stage189 多月回填：62 个有效月末 eval_date，`2021-04-30` 到 `2026-05-29`，排除当前不应作为官方 AI 池的 `2026-06-30`
- 官方月更只读检查：`--mode check --as-of 2026-06-30 --data-ready-time 16:30 --email-policy never --disable-lock`
- 策略/执行口径：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，不连接 CTP，不读取账户，不调用订单 API

## 结果

- Stage183 源表刷新结果：
  - 数据区间：`2020-01-02 -> 2026-06-30`
  - 账户规模：`200000`
  - 期末权益：`2,570,930.00`
  - 总收益：`1,185.46%`
  - 最大回撤：`-33.04%`
  - Sharpe：`0.95`
  - 总滑点：`360,730.00`
  - 总交易次数：`1187`
  - 胜率：本轮未单独导出
- Stage183 核心行数：
  - daily：`1571` 行，`2020-01-02 -> 2026-06-30`
  - entry candidate snapshots：`1032` 行，18 个品种，391 个合约
  - position changes：`441832` 行
  - trades：`1187` 行
- Stage182 最新 AI 池：
  - eval_date：`2026-05-29`
  - live_rows：`18`
  - feature_count：`108`
  - train_rows：`1332`
  - Top9：`SA.CZCE, MA.CZCE, OI.CZCE, si.GFEX, AP.CZCE, FG.CZCE, SM.CZCE, jm.DCE, fu.SHFE`
- Stage189 多月 AI 池：
  - pool：`1116` 行，62 个 eval_date，`2021-04-30 -> 2026-05-29`
  - eligibility：`558` 行
  - combined eligibility：`576` 行，63 个 eval_date，`2019-12-31 -> 2026-05-29`
- Stage935 只读月更检查：
  - 状态：`monthly_ai_pool_already_current`
  - expected_eval_date/current_eval_date：`2026-05-29 / 2026-05-29`
  - resolved_target_date：`2026-06-29`
  - update_reasons：`[]`
  - order_api_called_count：`0`
  - cancel_order_api_called_count：`0`
  - real_order_enabled：`false`
  - email_status：`skipped_by_policy`

## Hash 与一致性

- 重建前后完全一致的核心 CSV：
  - Stage183 daily/daily_equity：`068883779040f58c838b8feffce5ac14754262127b57fe63297d9ecbe789b2bb`
  - Stage183 entry snapshots：`b62c0c217904958deaeae40cee7572425ea66da2e3ab3ed48e799e40f57a8576`
  - Stage183 position changes：`c618a798f3e09c990248db327ad92457a167c8c0e8224b701e063b13eaf3ccd3`
  - Stage183 trades：`ada1809b5cabc65f198c1550b4258757ea80278134163c09703e22b0397c7b3a`
  - Stage182 latest pool：`4dd99076a11457ab4f67839649bec95571bcce7d1974547db26f330b77a7dafd`
  - Stage182 eligibility：`d8bf77ca89237cc805a3475689ce038ef47cbfd1b438903617d1f26d715c536d`
  - Stage182 combined eligibility：`8f54218d5c1922ebd4e0a2a16ef6d80c4f4392d1aa6c8cddd3f6127ffca574e3`
- 新重建的 Stage189 核心 hash：
  - pool：`2a144a6657dd5780998f4751f82fd003d6dc86cd4150f243f0b1d2347f9ad05c`
  - eligibility：`0b84aecb31d34a109812a2a239299d41d54ce2c77eac16b35341f6311256ad96`
  - combined eligibility：`fc3daefa94420144ca5373c2c34d8fd9ae51bb1cfc9629f487fb1b7e1b778f64`
- 不稳定或会变化的文件：report、summary、HTML/chart 中含 `generated_at` 或绘图生成细节，重跑 hash 可变化，不作为旧原件 1:1 证据。

## 输出文件

- Stage183 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_summary_stage183_ai_product_pool_source_refresh_v1.json`
- Stage183 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage183_ai_product_pool_source_refresh_report_stage183_ai_product_pool_source_refresh_v1.md`
- Stage182 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_summary_stage182_ai_product_pool_live_inference_v1.json`
- Stage182 eligibility：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- Stage189 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_summary_stage189_ai_product_pool_backfill_multimonth_v1.json`
- Stage189 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_report_stage189_ai_product_pool_backfill_multimonth_v1.md`
- Stage935 latest summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage935_official_live_monthly_ai_pool_update_latest_summary.json`

## 验证

- `.py311/bin/python -m unittest tests/test_official_live_config_import.py`：通过
- `git diff --check`：通过
- Stage935 只读检查：通过，当前 AI 池有效且无需更新

## 结论

- 本阶段结论：已经完成当前可见输入下的 Stage183/Stage182/Stage189 确定性重建，核心 CSV 重建前后 hash 一致，官方 Stage935 只读检查也确认当前 AI 池有效。
- 重要边界：这不能证明被删原始文件的字节级 1:1 已找回；原因是删除前没有保留下来的原始文件、快照或 hash。旧 Stage128 记录里的最新池曾出现 `rb`，当前重建最新池为 `SM`，说明当前重建不能等同于旧历史快照。
- 是否进入下一步：是，但下一步应继续找原始备份或旧产物 hash，而不是调参逼近旧结果。
- 下一步：如需要继续追 1:1 原件，只能查 Time Machine/APFS 本地快照、云同步回收站、旧 worktree、外部备份或同事机器；当前 Git 远端无法恢复 ignored/generated 产物。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本轮只重建和校验已有产物链路，没有根据收益结果新增规则、筛选品种、修改参数或反向搜索 AI 池组合。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：当前实盘依赖 AI 池文件和官方月更检查，恢复到可运行且可校验状态有价值；但继续在没有旧原件/hash 的前提下宣称字节级 1:1 没有价值，后续要转向备份查找或明确接受当前确定性重建结果。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，避免和当前已有并行改动混合；如后续确认这是最终恢复结论，再整理进 `LINE.md`
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否；若后续确认原件不可找回或找到旧备份，再追加总账
