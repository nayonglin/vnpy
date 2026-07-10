# Stage173 - AI池历史月度截面缺口审计

## 基本信息

- 时间：2026-07-08 17:11 CST
- 研究线：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 实盘版本：`official_live_stage847_c9_15w_stage819_05r_stop_retry_once`
- 本阶段性质：实盘 AI 池历史截面只读审计；不改策略参数、不改正式 AI 池、不连接 CTP、不调用订单 API。

## 触发问题

用户追问：既然 broker 侧 `rb2610.SHFE short 11` 与当前 shadow=0 的差异来自 AI 池历史截面缺失，是否需要补充缺失截面，并确认到底缺哪些月份。

## 本地审计对象

- 当前正式实盘 AI combined eligibility：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_combined_stage78_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- 当前最新 Stage182 live eligibility：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage182_ai_product_pool_live_inference_eligibility_stage182_ai_product_pool_live_inference_v1.csv`
- Stage189 多月回填产物：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_combined_stage78_eligibility_stage189_ai_product_pool_backfill_multimonth_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage189_ai_product_pool_backfill_multimonth_eligibility_stage189_ai_product_pool_backfill_multimonth_v1.csv`
- Stage935 月更历史 summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage935_official_live_monthly_ai_pool_update_summary_*.json`
- 策略读取逻辑：
  - `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`
  - `examples/portfolio_backtesting/build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py`

## 关键发现

- 当前 Stage182 combined：
  - 行数：`477`
  - eval_date 数：`52`
  - 尾部 eval_date：`2025-11-28, 2025-12-31, 2026-01-30, 2026-02-27, 2026-06-30`
  - `2026-03-31` 行数：`0`
  - `2026-04-30` 行数：`0`
  - `2026-05-29` 行数：`0`
  - `2026-06-30` 行数：`9`
- 当前最新 Stage182 live eligibility：
  - 只有 `2026-06-30` 一个截面，`9` 行。
- Stage189 combined：
  - 行数：`576`
  - eval_date 数：`63`
  - 覆盖 `2021-04-30 -> 2026-05-29`，另含 `2019-12-31`。
- 当前 Stage182 combined 相对 Stage189 combined 缺少 `12` 个 eval_date：
  - `2021-04-30`
  - `2021-05-31`
  - `2021-06-30`
  - `2021-07-30`
  - `2021-08-31`
  - `2021-09-30`
  - `2021-10-29`
  - `2021-11-30`
  - `2021-12-31`
  - `2026-03-31`
  - `2026-04-30`
  - `2026-05-29`
- 当前 Stage182 combined 相对 Stage189 combined 多出 `1` 个 eval_date：
  - `2026-06-30`
- 与本次 rb broker/shadow 差异直接相关的关键缺口：
  - `2026-05-29`
- 与 2026 年 PIT 完整性相关、但对 `2026-06-16` 实盘冷启动不一定直接触发的尾部缺口：
  - `2026-03-31`
  - `2026-04-30`
  - `2026-05-29`

## 2026 尾部截面详情

当前 Stage182 combined 已有：

- `2026-02-27`：`si.GFEX, ru.SHFE, OI.CZCE, SH.CZCE, lh.DCE, AP.CZCE, SM.CZCE, MA.CZCE, fu.SHFE`
- `2026-06-30`：`ru.SHFE, si.GFEX, SA.CZCE, FG.CZCE, AP.CZCE, au.SHFE, jm.DCE, SM.CZCE, fu.SHFE`

Stage189 可回填版本中有：

- `2026-03-31`：`jm.DCE, SH.CZCE, FG.CZCE, ru.SHFE, cu.SHFE, SM.CZCE, SA.CZCE, si.GFEX, fu.SHFE`
- `2026-04-30`：`SA.CZCE, MA.CZCE, si.GFEX, jm.DCE, OI.CZCE, FG.CZCE, SH.CZCE, AP.CZCE, fu.SHFE`
- `2026-05-29`：`SA.CZCE, MA.CZCE, OI.CZCE, si.GFEX, AP.CZCE, FG.CZCE, SM.CZCE, jm.DCE, fu.SHFE`

但 Stage935 历史线上记录显示，`2026-06-23 -> 2026-06-29` 实盘月更检查看到的 `2026-05-29` 池包含 `rb.SHFE`，不包含 `SM.CZCE`：

- 初始线上顺序：`SA.CZCE, si.GFEX, FG.CZCE, MA.CZCE, OI.CZCE, jm.DCE, AP.CZCE, rb.SHFE, fu.SHFE`
- 后续线上顺序：`SA.CZCE, si.GFEX, MA.CZCE, AP.CZCE, FG.CZCE, OI.CZCE, rb.SHFE, jm.DCE, fu.SHFE`
- `2026-06-30 16:57:37` 后一次强制重建把 `2026-05-29` 改成了 `SM.CZCE` 版本。

## 代码层判断

- `qmt_roll_portfolio_strategy.py` 读取 AI eligibility 时要求列齐全：`strategy, eval_date, product_vt_symbol, score, score_rank, top_n`。
- 实际开仓过滤判断只看目标品种是否存在于对应 eval_date 的 `product_rows`，也就是 membership；`score/rank/top_n` 主要进入诊断与邮件字段。
- 因此，如果只为修复 shadow membership 路径，理论上可以用 Stage935 线上 Top9 补一个 `2026-05-29` replay 补丁；但这不是无损恢复，因为缺原始 score。
- `build_qmt_roll_stage182_ai_product_pool_live_inference_runner.py` 的 combined 逻辑每次只把当前 live eligibility 与静态 official Stage78 eligibility 合并，没有把既有 Stage182 historical live snapshots 合并保留下来；这解释了月更后为什么会丢历史 live 截面。

## 结论

- 是，需要补截面，但不能直接把 Stage189 全量覆盖到正式实盘 AI 池。
- 最小必须补的是 `2026-05-29`，因为它直接决定 `rb2610.SHFE` 是否是策略信号路径。
- 2026 年尾部应补齐 `2026-03-31, 2026-04-30, 2026-05-29`，避免 3-6 月回放静默回退到 `2026-02-27`。
- 如果目标是全历史 backtest PIT 完整性，还应处理 `2021-04-30 -> 2021-12-31` 这 9 个缺失截面。
- 但 `2026-05-29` 不能直接采用 Stage189 的 `SM.CZCE` 版本，因为它和 6 月 22 日实盘实际使用、Stage935 历史记录中能解释 rb 信号的线上版本不一致。

## 后续建议

1. 先修 Stage182 combined 生成逻辑：月更时必须保留已有 Stage182 live historical snapshots，不允许只拿静态 official + 当前月截面重写。
2. 增加 Stage901/Stage935 fail-closed 校验：如果回放区间内应有月末 eval_date 缺失，不能静默回退到更早月份。
3. 对 `2026-05-29` 单独恢复：
   - 优先寻找原始线上 CSV 或本机备份。
   - 找不到原始 score 时，只能生成明确标记为 `recovered_from_stage935_top_products_membership_only` 的 replay 补丁，并在报告里说明 score 非原始值。
4. 对 `2026-03-31`、`2026-04-30` 可先以 Stage189 回填产物为候选源，但仍应记录源文件 hash 和生成时间，避免把重建口径当作原始线上口径。
5. 修复后重跑 `2026-06-16 -> 当前` Stage901 shadow，再重新做 broker/shadow 对账；在此之前不应用当前 shadow=0 指导处理 rb 仓位。

## 反过拟合与继续价值

- 过拟合判断：否。本阶段只审计数据截面血缘和 PIT 完整性，没有调整策略参数、AI 排名逻辑、品种池规则或风控阈值。
- 继续价值判断：是。缺失月度截面会让实盘 shadow 回放改写历史信号路径，直接影响 rb 仓位接管、每日邮件结论和后续自动化对账。
