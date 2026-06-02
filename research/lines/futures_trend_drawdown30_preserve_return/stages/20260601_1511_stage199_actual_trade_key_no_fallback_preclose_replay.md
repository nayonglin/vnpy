# Stage199 实际成交键补齐后的 no-fallback 一致预收盘回放

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 15:11 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行口径清洁化审计 / no-fallback 真实回放
- 是否重要突破：是，排除了 Stage197 的 36 笔成交 fallback 干扰
- 是否触发A/B：否，没有策略候选晋级

## 外部调研与判断

- 参考资料：
  - TqSdk 文档：`https://tqsdk-python.readthedocs.io/`
  - TqSdk GitHub：`https://github.com/shinnytech/tqsdk-python`
- 我的判断：
  - TqSdk 分钟K可以用于冻结时点重建，但必须让策略输入bar和成交窗口共享同一时间语义。
  - Stage197 的 36 笔 fallback 必须先补齐，否则无法确认失败来自策略路径还是数据缺口。
  - 本阶段只补实际成交键，不看收益调规则，因此不是过拟合。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage498_actual_trade_fill_key_readiness.py`
- 修改脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage497_consistent_preclose_full_bar_replay.py`
  - 修改内容：支持 `STAGE497_STAGE`、`STAGE497_MODEL_TAG`、`STAGE497_OUTPUT_PREFIX`、`STAGE497_PRECLOSE_VARIANT`、`STAGE497_PRECLOSE_LABEL`、`STAGE497_EXTRA_SYNTHETIC_PATHS`，用于追加 supplemental synthetic 并生成独立 Stage199 输出；默认参数保持 Stage197 兼容。
- 删除脚本：无
- 新增参数：仅新增脚本输出/输入参数，无策略交易参数
- 修改参数：无策略参数
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30
- 账户规模：`615,000`，即 Stage079 `50万C3下单 + 11.5万外部现金`
- 成本口径：正常 1x；另复核 2x / 3x / 5x 滑点压力
- 样本过滤：不做日期、品种或交易筛选
- 策略/归因口径：
  - Stage198：读取 Stage197 的 36 笔 `fallback_order_price_no_stage196_fill`，用 TqSdk 回补对应实际成交键的 preclose full bar。
  - Stage199：将 Stage198 supplemental synthetic 合并进 Stage196 preclose map，重跑一致预收盘完整bar回放，要求成交 fallback 为 `0`。

## 结果

### Stage198 实际成交键补齐

- 目标成交键：`36`
- ready：`36/36`
- gap：`0`
- 唯一合约：`36`
- completed minute bar rows：`721,875`
- 最少 preclose bar：`220`
- 最少 fill bar：`4`
- 决策：`actual_trade_fill_keys_ready_for_no_fallback_replay`

### Stage199 no-fallback 回放核心对比

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 252日DD30破例率 | 504日DD30破例率 | 年度DD30通过率 | 季度DD30通过率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000 | 0.0000 | 100.00% | 100.00% |
| Stage079 same-day close rerun | 31,040,650 | 4947.2602% | -29.7007% | 1.3188 | 15.0874 | 0.0000 | 0.0000 | 100.00% | 100.00% |
| Stage079 consistent preclose no-fallback | 12,095,040 | 1866.6732% | -33.2882% | 1.0497 | 16.5412 | 0.1000 | 0.2533 | 60.00% | 54.55% |

### 3个月 / 6个月持有体验

| 版本 | 周期 | p05收益 | 中位收益 | 正收益率 | 年化低于5%率 | 最差窗口回撤 | DD20破例率 | DD30破例率 | Ulcer P95 | P95水下天数 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage079 | 3个月 | -11.4702% | 13.5435% | 73.4804% | 29.4012% | -29.1988% | 18.5052% | 0.0000% | 17.7786 | 88 |
| Stage079 | 6个月 | -2.0393% | 33.9947% | 93.4772% | 9.0099% | -29.7007% | 35.7109% | 0.0000% | 19.9011 | 167 |
| No-fallback preclose | 3个月 | -15.2352% | 8.9518% | 67.0869% | 34.9392% | -31.4802% | 21.6119% | 2.0261% | 16.1038 | 88 |
| No-fallback preclose | 6个月 | -13.4360% | 21.6351% | 82.9188% | 20.5537% | -33.2882% | 50.3989% | 6.3351% | 20.7672 | 168 |

### 成本压力

| 版本 | 滑点倍率 | 总收益 | 最大回撤 | 是否不劣于Stage079压力口径 |
| --- | ---: | ---: | ---: | --- |
| No-fallback preclose | 1x | 1866.6732% | -33.2882% | 否 |
| No-fallback preclose | 2x | 1711.2569% | -35.3740% | 否 |
| No-fallback preclose | 3x | 1555.8407% | -38.6572% | 否 |
| No-fallback preclose | 5x | 1245.0081% | -54.8747% | 否 |

### 成交使用

- 交易次数：`777`
- `stage196_fill_first_open`：`777`
- fallback：`0`

## 输出文件

- Stage198 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage498_actual_trade_fill_key_readiness_report_stage498_actual_trade_fill_key_readiness_v1.md`
- Stage198 synthetic：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage498_actual_trade_fill_key_readiness_synthetic_preclose_bars_stage498_actual_trade_fill_key_readiness_v1.csv`
- Stage199 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_report_stage499_consistent_preclose_no_fallback_replay_v1.md`
- Stage199 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_summary_stage499_consistent_preclose_no_fallback_replay_v1.csv`
- Stage199 horizon：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_horizon_stage499_consistent_preclose_no_fallback_replay_v1.csv`
- Stage199 gate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_gate_stage499_consistent_preclose_no_fallback_replay_v1.csv`
- Stage199 cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_cost_stress_stage499_consistent_preclose_no_fallback_replay_v1.csv`
- Stage199 chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage499_consistent_preclose_no_fallback_replay_chart_stage499_consistent_preclose_no_fallback_replay_v1.png`

## 结论

- 本阶段结论：`stage079_consistent_preclose_full_bar_no_fallback` 不晋级。
- Stage197 的失败不是由 36 笔 fallback 造成；补齐实际成交键后，fallback 已为 `0`，但长期硬约束仍全线失败。
- 该方向不值得继续用小参数救援。
- 如果继续追求 3个月/6个月启动持有体验，应停止沿着“同日收盘代理/预收盘完整bar替换”做优化，转向新的低自由度、低相关收益源或风险源。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有改交易规则、没有调阈值、没有筛选日期/品种，只补齐实际成交键并复跑同一执行语义。结论是负面的，反而降低了后续在错误执行口径上过拟合的风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：对预收盘替换形状继续优化没有价值；对寻找新低自由度风险源仍有价值。
- 原因：no-fallback 后仍失败，说明问题不是数据 fallback，而是冻结时点信号路径本身无法保住 Stage079 核心指标。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 no-fallback 反证。
- 是否更新 `research/registry.md`：是，最新关键阶段改为 Stage199。
- 是否追加根目录 `memory.md/back_log.md`：是，属于重要路线废弃与执行口径经验。
