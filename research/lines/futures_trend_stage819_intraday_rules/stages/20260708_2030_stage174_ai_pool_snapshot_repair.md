# Stage174 AI池历史截面修复与实盘影子盘复验

- 时间：2026-07-08 20:30 CST
- line_id：futures_trend_stage819_intraday_rules
- 工作模式：day
- 性质：实盘执行一致性修复，不是策略 alpha 优化

## 本次调研和判断结论

- 外部资料/GitHub 调研结论：PIT 数据原则是历史回放只能读取当时可见的数据版本，不能用最新版本覆盖历史截面；这与 qlib 的 PIT database 设计一致。判断：本次问题不是“rb 信号本身不稳定”，而是 Stage182 组合 AI 池在月更时没有保留历史实盘快照，导致 2026-05-29 截面丢失，影子盘从 2026-06-16 回放时无法复现当时的 rb 入池状态。
- 当前仓库判断：`build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py` 原合并逻辑只拼接官方 Stage78 历史基线和本次 live eval_date，未读取并保留已有 Stage182 combined 文件中的历史实盘月度快照。后续每次月更都有继续覆盖/丢失历史 live 截面的风险。

## 代码改动

- 修改 `examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`
  - 新增 eligibility schema 对齐。
  - 组合 AI 池改为：官方历史基线 + 已有 Stage182 combined 中的历史 live 快照 + 本次 live 快照。
  - 同一 strategy/eval_date 只允许本次 live 快照覆盖对应月份，不再误删其他历史月份。
  - 保留边界收窄为 `stage182_` 和 `stage174_recovered_` score_type；官方基线仍从官方 Stage78 文件重读，避免把整份官方基线冻结在旧 combined 文件里。
- 修改 `examples/portfolio_backtesting/run_qmt_roll_stage935_official_live_monthly_ai_pool_update.py`
  - 新增最近 4 个完整月末 eval_date 连续性校验。
  - 对当前 2026-07-08 场景，要求 `2026-03-31, 2026-04-30, 2026-05-29, 2026-06-30` 均存在。
  - 若缺失，Stage935 check 会 fail-closed 为 `current_stage182_outputs_invalid`。
- 修改 `examples/portfolio_backtesting/analyze_qmt_roll_stage901_stage847_c9_2026_ytd_live_shadow.py`
  - 新增本次回放区间实际需要的 AI 池 eval_date 审计。
  - 报告中输出 required/missing eval_date，并给出 `shadow_replay_ai_pool_status`。
- 新增 `examples/portfolio_backtesting/repair_qmt_roll_stage182_ai_pool_historical_snapshots.py`
  - 一次性恢复缺失的 2026-03-31、2026-04-30、2026-05-29 三个月度截面。
  - 先备份原组合文件，再写入恢复后的组合 AI 池。

## 数据修复内容

- 备份文件：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv.bak_20260708_202829_stage174_ai_pool_snapshot_repair_v1`
- 修复前组合 AI 池：477 行，52 个 eval_date。
- 修复后组合 AI 池：504 行，55 个 eval_date。
- 新增恢复行数：27 行。
- 恢复截面：
  - 2026-03-31：SH.CZCE, jm.DCE, cu.SHFE, FG.CZCE, SA.CZCE, sp.SHFE, ru.SHFE, lh.DCE, fu.SHFE
  - 2026-04-30：SA.CZCE, SH.CZCE, FG.CZCE, si.GFEX, MA.CZCE, jm.DCE, rb.SHFE, AP.CZCE, fu.SHFE
  - 2026-05-29：SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE
- 说明：恢复的是当时留档的成员资格。`score` 列为恢复占位，不伪造原始模型分数；当前策略入池过滤使用成员资格，rank/score 主要用于诊断和邮件展示。

## 验证结果

- `python -m py_compile`：通过。
- 修复前 Stage935 check：
  - 状态：`monthly_ai_pool_update_needed`
  - blocker：`stage182_combined_missing_recent_eval_dates`
  - 缺失：`2026-03-31, 2026-04-30, 2026-05-29`
  - 下单 API 次数：0
- 修复后 Stage935 check：
  - 状态：`monthly_ai_pool_already_current`
  - validation：`valid`
  - 最近 4 个完整月末行数：2026-03-31=9，2026-04-30=9，2026-05-29=9，2026-06-30=9
  - 下单 API 次数：0
- Stage901 回放 2026-06-16 至 2026-06-22：
  - required eval_date：`2026-05-29`
  - missing eval_date：无
  - pending order：`rb2610.SHFE Short Open 11 手，price=3126`
  - 下单 API 次数：0
- Stage901 回放 2026-06-16 至 2026-07-08：
  - required eval_date：`2026-05-29, 2026-06-30`
  - missing eval_date：无
  - current_position_count：1
  - pending order：`rb2610.SHFE Long Close 11 手，price=3096`
  - 下单 API 次数：0

## 回测记录字段

- 是否重要突破版本：是，修复实盘影子盘 PIT 截面缺失，直接影响 rb 实盘/回测一致性。
- 新增参数：
  - `RECENT_COMBINED_EVAL_DATE_LOOKBACK_MONTHS=4`
- 修改参数：无。
- 删除参数：无。
- 新增回测/回放结果：
  - Stage901 2026-06-22 可复现 rb2610 short open 11 手。
  - Stage901 2026-07-08 当前回放缺口为 0，并显示 rb2610 long close 11 手待提交。
- 修改回测结果：无历史绩效参数调整；只修复 AI 池历史快照输入。
- 删除回测结果：无。
- 期末权益：149,700（Stage901 2026-07-08 当前 live shadow 片段）
- 总收益：-0.20%（Stage901 2026-07-08 当前 live shadow 片段）
- 最大回撤：-5.2472%（Stage901 2026-07-08 当前 live shadow 片段）
- Sharpe：-0.00384（Stage901 2026-07-08 当前 live shadow 片段）
- 总滑点：710
- 总交易次数：3
- 胜率：50.0%（nonzero daily win rate）

## 反思

- 是否过拟合：否。本次没有根据收益、胜率或某个品种表现调参，只恢复当时应被保留的 PIT 月度截面，并增加缺口校验。
- 是否还有价值继续做：是。下一步应把 Stage935 缺口检查纳入日常自动化健康检查邮件，让 AI 池缺口在交易前暴露，而不是等影子盘和实盘出现差异后才发现。
