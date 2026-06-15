# Stage048 Stage872 C9右尾保护与利润锁定代理审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-15 05:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读代理审计 + 分钟K视觉复盘；不改官方正式版 Stage372/20w，不改 Stage819 候选配置，不连接 CTP，不调用下单。
- 是否重要突破：否。固定止盈被反证；利润锁定只有上限价值，还不是可接正式候选的真实引擎结果。
- 是否触发A/B：否。没有形成可接官方候选或正式版的策略版本。

## 外部调研与判断

- 参考资料：
  - Turtle Trading 原始规则强调趋势跟随要让利润奔跑，并用止损纪律控制风险：https://oxfordstrat.com/coasdfASD32/uploads/2016/01/turtle-rules.pdf
  - Backtrader stop / StopTrail 示例说明追踪止损是可执行订单语义，但必须在真实回测中验证是否误杀趋势右尾：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/
  - Backtrader order execution 文档用于校验 stop / limit / stoptrail 的成交语义边界：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
- 我的判断：趋势系统的第一性矛盾不是“赚一点就走”，而是右尾高度集中、左尾必须实时切断。先用 C9 全周期逐笔数据做固定止盈和利润锁定上限审计是有价值的；但代理不能替代真实逐分钟引擎，因为真实追踪止损会在途中洗出一部分最终赢家。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage872_c9_profit_lock_proxy_audit.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - 只读固定止盈代理：`1R/2R/4R/8R` 到达即止盈。
  - 乐观锁盈上限代理：`+1R 后保本`、`+2R 后保本`、`+4R 后保本`、`+2R 后锁 +1R`、`+4R 后锁 +1R/+2R`、`+8R 后锁 +2R`。
- 修改参数：无正式策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：读取 Stage870 C9 closed lots 共 `401` 笔；有效代理样本 `230` 笔，valid entry year 覆盖 `2020-2026`。
- 账户规模：沿用 Stage819 候选 30万口径。
- 成本口径：沿用 Stage870/C9 真实引擎输出；C9 总滑点 `3,607,030`，总交易次数 `786`。
- 样本过滤：仅要求逐笔风险额有效且能匹配 Stage861 完整分钟K路径；不按年份、品种、方向、盈亏或大赢家筛选。
- 策略/归因口径：只读代理，不形成真实下单规则。固定止盈按触及目标R即以目标R替代最终PnL；乐观锁盈只在最终低于锁定位时把PnL抬到锁定位，不计算途中回撤洗出赢家的代价，因此只能视为上限。

## 结果

- 期末权益：C9 源版本 `50,637,144.6`
- 总收益：C9 源版本 `16,779.0482%`
- 最大回撤：C9 源版本 `-42.6313%`
- Sharpe：C9 源版本 `1.6312`
- 总滑点：C9 源版本 `3,607,030`
- 总交易次数：C9 源版本 `786`
- 胜率：C9 源版本 `53.5299%`
- 其他关键指标：
  - C9 源版本 max broker10 `114.3987%`，p95 broker10 `61.5244%`。
  - Stage872 valid proxy sample PnL `49,601,777.3`；big winners `21` 笔，big winner PnL `35,808,560.0`。
  - 固定止盈全线净负：`1R` delta `-29,726,373.8`，`2R` delta `-22,984,986.4`，`4R` delta `-23,201,181.6`，`8R` delta `-6,116,950.8`。
  - `8R` 固定止盈仍会触发全部 `21` 个 big winners，winner cut `-20,831,746.8`，说明简单止盈破坏 C9 的右尾来源。
  - 乐观上限里 `+2R 后锁 +1R` 最强：触发 `45` 笔、big winners `0`、delta `+16,002,662.8`；`+1R 后保本` delta `+14,564,811.8`；`+2R 后保本` delta `+8,807,729.6`。
  - MFE 桶显示 `8+` 桶 `47` 笔贡献 PnL `58,243,690.0`，含 `21` 个 big winners；`0-1` 桶 `75` 笔 PnL `-13,531,300.9`，利润锁定无法触发这类低 MFE 左尾。
  - 年度拆分显示固定止盈在 2022 低迷年局部看似有利，但会明显破坏 2021、2023、2025 的趋势右尾，不具备穿越周期价值。
  - 分钟K视觉复盘：大赢家样本如 `OI309.CZCE long`、`jm2509.DCE long` 的利润释放依赖持仓后延展，固定止盈会提前截断；锁盈样本如 `cu2307.SHFE long`、`OI205.CZCE long`、`SM205.CZCE long` 确有先达到 `+2R` 后回落的形态；低 MFE 亏损样本如 `ru2409.SHFE long`、`lh2411.DCE long` 没有给利润锁定触发机会。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_report_stage872_c9_profit_lock_proxy_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_proxy_summary_stage872_c9_profit_lock_proxy_audit_v1.csv`
- orders：无，本阶段不生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_yearly_proxy_summary_stage872_c9_profit_lock_proxy_audit_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_lot_features_stage872_c9_profit_lock_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_mfe_bucket_summary_stage872_c9_profit_lock_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_summary_chart_stage872_c9_profit_lock_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_atlas_manifest_stage872_c9_profit_lock_proxy_audit_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_atlas_page001_stage872_c9_profit_lock_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_atlas_page002_stage872_c9_profit_lock_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_atlas_page003_stage872_c9_profit_lock_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_atlas_page004_stage872_c9_profit_lock_proxy_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage872_c9_profit_lock_proxy_audit_decision_stage872_c9_profit_lock_proxy_audit_v1.json`

## 结论

- 本阶段结论：决策为 `stage872_fixed_takeprofit_rejected_profit_lock_upper_bound_promising_needs_real_engine`。固定止盈明确否决；利润锁定有真实引擎验证价值，但当前只是乐观上限，不可作为收益承诺或候选升级依据。
- 是否进入下一步：是，但只允许一次冻结真实引擎验证，不继续扫 R、小数阈值、品种、方向或年份。
- 下一步：Stage873 可验证一个冻结版本：以 C9 为基础，当逐分钟持仓先达到 `+2R` 后，把保护位推到 `+1R`；保护出场后是否允许同日重试需沿用 C9 既有重试纪律或明确固定为不新增重试，不得再同时扫描多组锁盈参数。

## 过拟合反思

- 运行前判断：不是过拟合。原因是本阶段只做全样本代理归因和视觉复核，阈值为粗粒度 canonical R，不按年份、品种、方向或盈亏挑样本。
- 运行后判断：固定止盈结论不是过拟合；利润锁定路线存在轻微选择偏差风险。
- 原因：`1/2/4/8R` 和保本/锁盈组合本身构成了少量扫描，不能把最好的代理直接当策略。下一步必须只冻结 `+2R 后锁 +1R` 这一条第一性规则做真实引擎，若失败就停止，不再救参。

## 继续价值反思

- 运行前判断：有继续价值。C9 已经证明 stop/retry 能保留一部分右尾，但 broker10 和回撤路径仍不够干净，右尾保护/生存线是合理方向。
- 运行后判断：固定止盈没有继续价值；利润锁定仍有一次继续价值。
- 原因：固定止盈破坏 `8+ MFE` 右尾，是趋势系统的大忌；但有 `45` 笔先达到 `+2R` 后最终低于 `+1R` 的样本，且分钟K视觉上能看到真实回吐形态，值得用真实逐分钟引擎验证是否能在不洗掉大赢家的情况下改善左尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage048 状态和下一步约束。
- 是否更新 `research/registry.md`：否，本次不新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、正式候选、路线废弃或跨线合并。
