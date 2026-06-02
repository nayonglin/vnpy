# Stage197 一致预收盘完整bar真实回放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 14:55 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行口径真实性审计 / Stage196 数据前置后的真实回放
- 是否重要突破：是，完成了从“预收盘数据准备度”到“统一替换当日日K + 同窗口成交”的关键反证
- 是否触发A/B：否，没有可晋级候选

## 外部调研与判断

- 参考资料：
  - TqSdk 文档：`https://tqsdk-python.readthedocs.io/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：
  - TqSdk 的历史K线与回测接口可以用于构建冻结时点之前的分钟序列，但“信号bar”和“成交bar”必须在同一个时间语义下闭环。
  - Stage141-153 已证明只替换成交价、只替换 close、T+1 open 或多种分钟语义混用都不能作为晋级依据。
  - 本阶段使用 Stage196 已补齐的 strict full preclose OHLCVOI，对当日日K输入和 `14:55-15:00` 成交窗口做一致回放；这一步不是调参，而是验证候选是否仍具有真实可执行性。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage497_consistent_preclose_full_bar_replay.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增审计口径 `stage079_consistent_preclose_full_bar_fill_first_open`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`，即 Stage079 `50万C3下单 + 11.5万外部现金`
- 成本口径：正常 1x；另复核 2x / 3x / 5x 滑点压力
- 样本过滤：不做日期、品种或交易筛选
- 策略/归因口径：
  - `stage079`：Stage403 baseline
  - `stage079_rerun_same_day_close`：同日收盘复刻
  - `stage079_consistent_preclose_full_bar_fill_first_open`：用 Stage196 synthetic preclose OHLCVOI 替换当日日K输入，并用同一窗口 `fill_first_open` 成交

## 结果

### 核心对比

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252日DD30破例率 | 504日DD30破例率 | 年度DD30通过率 | 季度DD30通过率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000 | 0.0000 | 100.00% | 100.00% |
| Stage079 same-day close rerun | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000 | 0.0000 | 100.00% | 100.00% |
| Stage079 consistent preclose full bar | 12,093,735 | 1866.4610% | -33.3154% | 1.0513 | 16.5440 | 0.1000 | 0.2533 | 60.00% | 54.55% |

### 3个月 / 6个月持有体验

| 版本 | 周期 | p05收益 | 中位收益 | 正收益率 | 年化低于5%率 | 最差窗口回撤 | DD20破例率 | DD30破例率 | Ulcer P95 | P95水下天数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 3个月 | -11.4702% | 13.5435% | 73.4804% | 29.4012% | -29.1988% | 18.5052% | 0.0000% | 17.7786 | 88 |
| Stage079 | 6个月 | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 35.7109% | 0.0000% | 19.9011 | 167 |
| Consistent preclose | 3个月 | -15.2190% | 8.8149% | 67.0419% | 35.1193% | -31.4510% | 21.6569% | 2.0261% | 16.1301 | 88 |
| Consistent preclose | 6个月 | -13.4246% | 21.6138% | 82.7780% | 20.6945% | -33.3154% | 50.3989% | 6.3351% | 20.7431 | 167 |

### 成本压力

| 版本 | 滑点倍率 | 总收益 | 最大回撤 | 是否不劣于Stage079压力口径 |
| --- | ---: | ---: | ---: | --- |
| Consistent preclose | 1x | 1866.4610% | -33.3154% | 否 |
| Consistent preclose | 2x | 1710.3472% | -35.3936% | 否 |
| Consistent preclose | 3x | 1554.2333% | -38.9006% | 否 |
| Consistent preclose | 5x | 1242.0057% | -55.1320% | 否 |

### 交易与数据使用

- Stage196 synthetic required key：`26,380`
- 回放实际使用 Stage196 key：`26,249`
- 未使用 Stage196 key：`131`
- Consistent preclose 交易次数：`777`
- 其中 `stage196_fill_first_open`：`741`
- fallback 到 `order_price`：`36`
- fallback 交易全部为平仓，分散在多日期多合约，不是单一合约数据缺口。
- 总滑点：`960,100`
- 非零日胜率：`49.4263%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_report_stage497_consistent_preclose_full_bar_replay_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_summary_stage497_consistent_preclose_full_bar_replay_v1.csv`
- gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_gate_stage497_consistent_preclose_full_bar_replay_v1.csv`
- horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_horizon_stage497_consistent_preclose_full_bar_replay_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_cost_stress_stage497_consistent_preclose_full_bar_replay_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_daily_stage497_consistent_preclose_full_bar_replay_v1.csv`
- trade_usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_trade_usage_stage497_consistent_preclose_full_bar_replay_v1.csv`
- bar_usage：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_bar_usage_stage497_consistent_preclose_full_bar_replay_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage497_consistent_preclose_full_bar_replay_chart_stage497_consistent_preclose_full_bar_replay_v1.png`

## 结论

- 本阶段结论：`stage079_consistent_preclose_full_bar_fill_first_open` 不晋级。
- 失败原因不是 3/6 个月体验局部不足，而是长期硬约束直接失败：
  - 总收益从 `4947.2602%` 降到 `1866.4610%`
  - 最大回撤从 `-29.7007%` 恶化到 `-33.3154%`
  - Sharpe 从 `1.3188` 降到 `1.0513`
  - Ulcer 从 `15.0874` 升到 `16.5440`
  - rolling252/504、年度、季度、成本压力全部不通过
- 是否进入下一步：不作为策略候选进入下一步。
- 下一步：
  - 不应救这个版本的小参数。
  - 若要做最终执行口径审计，可补齐 `36` 笔平仓 fallback 对应的成交键，把 `required key` 从信号键扩展到所有实际成交键。
  - 若继续追求 3/6 个月体验改善，应回到全新低自由度、低相关风险源，而不是继续围绕同日收盘或预收盘替换口径救援。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有调整交易规则、阈值、品种、日期或资金，只是把历史同日收盘代理替换为更严格的同一时点信息与成交口径。失败结论反而降低了过拟合风险，因为它阻止了在不真实的执行口径上继续优化。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：对本形状继续优化没有价值；对执行基准清洁化仍有价值。
- 原因：一致预收盘回放已经大幅失败，不值得用小参数救援；但 fallback 暴露出 `required key` 应覆盖所有实际成交键，这对最终执行审计仍有工程价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage197 执行口径反证。
- 是否更新 `research/registry.md`：是，最新关键阶段改为 Stage197。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要路线废弃与执行口径经验。
