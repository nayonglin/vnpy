# Stage127 Stage103产业链价差Overlay审计

- 时间：2026-05-28 01:21 CST
- 工作模式：day
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：A/C 固定结构审计；固定 Stage079 与 Stage103，不修改 C3、Stage079、Stage103 规则，不增加账户资金。
- 是否重要突破：否。重要边界是：产业链价差均值回归在 Stage079 目标口径可通过，但不能打赢 Stage103，因此不晋级主执行版本。
- 是否触发 A/B：是。已按 `skills/version-ab-experiment/SKILL.md` 处理，A=Stage079，C0=Stage103，C1/C2=Stage103+产业链价差 overlay。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage427_stage103_pair_spread_overlay.py`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage427_stage103_pair_spread_overlay_report_stage427_stage103_pair_spread_overlay_v1.md`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage427_stage103_pair_spread_overlay_chart_stage427_stage103_pair_spread_overlay_v1.png`

## 外部调研与判断

- 外部调研参考：
  - Springer `Strategy diversification: Combining momentum and carry strategies within a foreign exchange portfolio`：趋势/动量之外叠加不同风险源有理论意义。
  - Morgan Stanley `Managed Futures - Beyond Trend Following`：managed futures 体系内不只有趋势，也可包含 carry/relative-value/spread 类风险源。
  - GitHub `chrism2671/PyTrendFollow` 等趋势跟随框架可作为流程参考，但没有可直接迁移到本地中国商品、保证金、整数手、Stage079 资金口径的产业链价差实现。
  - SSRN `All that Glitters Is Not Gold` 与 PBO/Walk-forward 思路提示，多候选筛选不能只看回测最高分。
- 本阶段判断：产业链价差/market-neutral spread 是值得试的不同风险源，但必须低自由度。若固定 pair、固定120日 z-score、固定一手暴露不能胜过 Stage103，就不应继续扫 pair、阈值、窗口或行业组合。

## 版本变更

- 新增参数：
  - 固定价差对 `5` 组：`rb.SHFE/hc.SHFE`、`FG.CZCE/SA.CZCE`、`MA.CZCE/SA.CZCE`、`rb.SHFE/jm.DCE`、`hc.SHFE/jm.DCE`。
  - `LOOKBACK_DAYS=120`
  - `ENTRY_Z=1.0`
  - `BROKER10_MULTIPLIER=1.10`
  - 暴露形态：`best1` 每日只取 `abs(z)` 最大的一组；`all` 持有所有触发价差。
- 修改参数：无。
- 删除参数：无。
- 规则说明：当 z-score 高于阈值时按均值回归方向做一手价差；所有信号均使用前一日可见数据；无信号日清仓并计入换手成本；若 C3+xsmom+价差保证金按 `1.10` 倍超过上一日权益，则跳过当日价差 overlay。

## 回测结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 总滑点 | 总交易次数 | 日胜率 | 非零日胜率 | 3个月分 | 6个月分 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 1,556,750 | 757 | 36.2924% | 48.3478% | 100.0000 | 100.0000 |
| Stage103 broker10_guard | 31,730,915 | 5059.4984% | -28.9792% | 1.3681 | 14.3132 | 1,569,265 | 1,217 | 43.0809% | 50.3432% | 121.2041 | 134.4513 |
| Stage103+pair_mr120_best1 | 31,677,485 | 5050.8106% | -28.6331% | 1.3707 | 14.2989 | 1,584,735 | 2,011 | 48.6292% | 49.9665% | 123.1761 | 132.5812 |
| Stage103+pair_mr120_all | 31,637,095 | 5044.2431% | -28.5433% | 1.3633 | 14.3069 | 1,594,125 | 2,469 | 49.0862% | 50.4359% | 123.8037 | 127.0921 |

补充结果：

- `best1` 相对 Stage079 通过硬闸门与 3/6个月目标闸门，但相对 Stage103 失败项为 `total_return_not_lower_than_stage103`。
- `all` 相对 Stage079 通过硬闸门与 3/6个月目标闸门，但相对 Stage103 失败项为 `total_return_not_lower_than_stage103,sharpe_not_lower_than_stage103`。
- `best1` 新增价差腿全周期净 PnL `-53,430`，新增价差滑点 `15,470`，新增价差换手 `794` 手。
- `all` 新增价差腿全周期净 PnL `-93,820`，新增价差滑点 `24,860`，新增价差换手 `1,252` 手。
- 多起点冷启动：所有版本 `dd30_pass=1`，未发现回撤30%失败窗口。
- 成本压力：两个价差版本在 `1x/2x/3x/5x` 滑点下均不差于 Stage079；但 `5x` 下相对 Stage103 已没有优势。
- 保证金压力：价差 overlay 有执行闸门，但 absolute broker10 历史重构口径仍存在穿线日。`start_2020` 下 Stage079 自身已有穿线，Stage103 与价差版本也有 `1` 天左右穿线，因此本阶段仍只能做 execution-relative 判断，不能升为 absolute deployment。

## 决策

- 决策：`stage079_objective_only_candidate`。
- 主执行相对候选仍是 Stage103 `xsmom_vt10_q_momq_round_half_true_broker10_guard`。
- `Stage103+pair_mr120_best1` 可作为 paper 观察项：它改善最大回撤、Sharpe、Ulcer 和 3个月体验，但牺牲全周期收益与6个月体验，不适合作为主版本替代。
- `Stage103+pair_mr120_all` 不保留为主候选：回撤更浅但收益、Sharpe、6个月体验均弱于 Stage103，且换手更高。
- 后续禁止继续围绕本价差形状扫 `lookback`、`z-score`、pair 组合、all/best 权重、日期或保证金小数；否则会转为过拟合救参。

## 后续规划和 TODO

- 当前优先级仍是 Stage103 工程化复跑、paper/影子盘和真实券商保证金接入。
- 若继续寻找理想短持有体验，不应救产业链价差 MR120；只能换新的低自由度、低相关风险源，或者明确另立“愿意牺牲部分收益换更低回撤/更高3个月分”的体验线。

## 反思

- 运行前过拟合判断：不是过拟合。原因是本阶段从外部 managed futures / relative-value 框架出发，预声明 pair、窗口、阈值和暴露形态，没有用坏窗口反推规则。
- 运行后过拟合判断：不是过拟合；但如果继续调 pair、z-score 或窗口来补收益，就会转为过拟合。当前应停止该形状。
- 运行前继续价值判断：有价值。原因是 Stage104 已证明剩余缺口主要来自 C3 本体路径，尝试非趋势、相对价值风险源合理。
- 运行后继续价值判断：产业链价差 MR120 主动优化价值低；总目标仍有价值，但应回到 Stage103 落地或寻找新的结构性风险源。
