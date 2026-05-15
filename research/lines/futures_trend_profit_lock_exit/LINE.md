# futures_trend_profit_lock_exit - 期货趋势盈利锁定退出研究线

## 定位

- 资产：商品期货。
- 策略基准：Stage78-1 `official_stage78_1_defensive_50w_no_sizing_cap`。
- 研究对象：单笔/分层持仓的盈利锁定移动止损档位。
- 边界：不改 AI 月度选品、不改品种池、不改入场 alpha、不改 SimNow/实盘执行 SOP。

## 核心问题

当前正式版启用的锁盈档位：

- `收盘最大浮盈>=30% -> lock 20%`
- `收盘最大浮盈>=20% -> lock 15%`
- `收盘最大浮盈>=10% -> lock 8%`
- `收盘最大浮盈>=5% -> lock 3%`
- `收盘最大浮盈>=3% -> lock 1%`
- `收盘最大浮盈>=2% -> lock 0.1%`

这些档位来自经验设置。本研究线要回答的是：这些档位是否真的改善了趋势策略的退出质量，还是在部分趋势恢复/延续段过早截断利润。

## 反过拟合原则

- 不做逐档任意网格搜索。
- 不用全周期最优收益替换正式参数。
- 先做交易级归因：MFE、MAE、捕获率、回吐、离场后继续趋势。
- 候选必须是低自由度结构：统一保留比例、平滑曲线或少数分段。
- 任何候选必须通过 Stage78-1 A/B/C：全周期、起始年份、季度冷启动、弱窗口、滑点压力。
- 若候选只在某一两段行情好看，或需要继续补丁式调阈值，立即停止。

## 当前状态

- Stage001/Stage271：启动研究线，建立并运行交易级归因脚本。
- 初步归因显示：高浮盈档位样本少但并不差；低档位 `2%->0.1%`、`3%->1%` 更值得怀疑，但不能直接凭归因改参数。
- Stage002/Stage272：低自由度 A/C 验证失败；简单删除 `2%/3%` 早锁档位没有跨起始年份优势，不进入 Stage273。
- Stage003/Stage273：141 个低自由度候选 + 240 次 bootstrap。事件级最优为 `scale_current_1.65`，但 walk-forward/bootstrapping 不够稳，不能直接晋级。
- Stage004/Stage274：组合引擎反证中，`scale_current_1.65` 因回撤恶化被拒绝；`two_segment_l0.30_h0.90` 通过 engine gate。
- Stage005/Stage275：D 候选通过起始年份、季度冷启动、63/126/252短窗口与 5x/10x 滑点压力。
- Stage006/Stage276：D 候选逐笔归因失败，正贡献集中在 10 笔交易和少数品种；最终不替换正式 78-1。
- Stage007/Stage277：标准 Chandelier/ATR `22/3` 波动率自适应保护层做成交腿级机制屏。5% 激活版本覆盖 `444` 个交易腿、激活率 `22.97%`，但提前离场率 `0%`、weighted_delta_sum `0.0`，不进入完整组合回测。
- Stage008/Stage278：修正 Stage277 口径过浅的问题。深挖显示只替换固定盈利锁本身样本太少、正贡献高度集中；真正线索是 `prev2day_stop + 盈利锁` 组合可能在已锁盈趋势里过早退出。ATR/YoYo 替换诊断有收益线索，但 top10 正贡献占比超过 `93%`，不能直接改正式版。
- Stage009/Stage279：完整组合引擎验证“锁盈已激活 + MA20/MA40趋势仍强时跳过prev2day_stop”。该开关真实触发 `1754` 次，但全周期期末权益少 `7,759,470`、最大回撤恶化 `10.70pp`，仅 `1/6` 窗口胜出，判定 `reject_do_not_promote`。
- 当前不修改正式 78-1 参数；`profit_lock_tiers` 只作为实验入口，默认空值保持正式档位不变。
- 产物：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage271_profit_lock_trade_attribution.py`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage271_profit_lock_trade_attribution_report_stage271_profit_lock_trade_attribution_v1.md`
  - `examples/portfolio_backtesting/run_qmt_roll_stage272_profit_lock_low_tier_ablation.py`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage272_profit_lock_low_tier_ablation_report_stage272_profit_lock_low_tier_ablation_v1.md`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage273_profit_lock_effectiveness_and_search.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage274_profit_lock_engine_falsification.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage275_profit_lock_full_robustness.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage276_profit_lock_trade_drilldown.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage277_adaptive_profit_lock_mechanism_screen.py`
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage278_exit_geometry_deep_dive.py`
  - `examples/portfolio_backtesting/run_qmt_roll_stage279_profit_lock_trend_relaxed_prev2day_engine_screen.py`

## 下一步

1. 停止固定六档数值搜索，不继续微调小数阈值。
2. D 候选只保留为研究经验，不进入正式 Stage78-1/影子盘。
3. 标准 ATR/Chandelier “叠加层”不继续；它不能回答核心问题。
4. “锁盈已激活 + 趋势强度仍强时直接跳过 `prev2day_stop`”已被 Stage279 反证，不进入 Stage78-1/影子盘。
5. 若继续退出机制研究，只考虑更保守的降仓、延迟确认或账户层风险预算，不继续调 MA/触发阈值贴合历史窗口。
6. 正式 78-1 当前手工档位保持不变。
