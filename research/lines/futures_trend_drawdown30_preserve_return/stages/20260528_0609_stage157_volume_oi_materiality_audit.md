# Stage157 volume/open_interest 字段物料性审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-05-28 06:09 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：字段物料性反事实；不新增策略、不修改 Stage079/C3 交易规则
- 是否重要突破：是。动态反事实证明 `volume` 和 `open_interest` 都会改变 Stage079/C3 路径，Stage156 的 `volume` 全0不能被降级忽略。
- 是否触发A/B：否。没有形成新策略候选，也不接入正式版本。

## 外部调研与判断

- 参考资料：
  - TqSdk `get_kline_serial` 字段参考：`https://docfork.com/shinnytech/tqsdk-python`
  - TqSdk 官方 `TqBacktest` 文档：`https://tqsdk-python.readthedocs.io/en/latest/reference/tqsdk.backtest.html`
  - 期货成交量与持仓量区别参考：`https://www.pfolio.io/academy/futures-open-interest`
- 我的判断：
  - 成交量描述期间成交活动，持仓量描述未平仓合约存量；二者在期货趋势策略中不能互相替代。
  - 当前问题不能靠“代码里有引用”或“字段缺失就先置零”判断，必须看动态路径是否变化。
  - 反事实显示字段置零会改变交易序列和权益，所以 Stage155 的 strict OHLCVOI 要求继续成立。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage457_volume_oi_materiality_audit.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage457_volume_oi_materiality_audit_v1`
  - 反事实版本：`baseline`、`volume_zero`、`open_interest_zero`、`volume_open_interest_zero`
- 修改参数：无策略参数修改。
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30。
- 账户规模：C3 下单资金 `500,000`，Stage079 账户口径 `615,000`，外部现金 `115,000`。
- 成本口径：沿用 C3/Stage079 同日收盘正常成本口径。
- 样本过滤：无日期/品种筛选；只对 BarData 字段做反事实置零。
- 策略/归因口径：
  - `baseline`：原始 Stage079/C3。
  - `volume_zero`：所有日K `volume=0`，保留 `open_interest`。
  - `open_interest_zero`：所有日K `open_interest=0`，保留 `volume`。
  - `volume_open_interest_zero`：`volume/open_interest` 同时置零。

## 结果

| variant | Stage079期末权益 | 总收益 | 最大回撤 | Sharpe | Ulcer | 交易次数 | 相对基准期末差 | 最大权益差 | 交易序号差异 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 31,040,650 | 4947.2602% | -29.7007% | 1.6220 | 15.1468 | 757 | 0 | 0 | 0 |
| volume_zero | 29,968,220 | 4772.8813% | -29.8108% | 1.5879 | 15.2302 | 757 | -1,072,430 | 1,077,830 | 303 |
| open_interest_zero | 31,469,885 | 5017.0545% | -29.6798% | 1.6083 | 15.0123 | 757 | +429,235 | 1,115,395 | 477 |
| volume_open_interest_zero | 14,498,780 | 2257.5252% | -34.4752% | 1.3795 | 16.1329 | 747 | -16,541,870 | 17,041,470 | 663 |

风险模式分布：

| variant | risk_mode | candidate_count | selected_volume_sum |
| --- | --- | ---: | ---: |
| baseline | regular | 962 | 117,808 |
| baseline | volume_open_interest_surge | 22 | 3,167 |
| baseline | open_interest_surge | 41 | 6,349 |
| baseline | open_interest_decline | 58 | 4,629 |
| volume_zero | regular | 978 | 117,112 |
| volume_zero | open_interest_surge | 47 | 7,429 |
| volume_zero | open_interest_decline | 58 | 4,517 |
| open_interest_zero | regular | 1082 | 130,788 |
| volume_open_interest_zero | regular | 1084 | 73,485 |

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_report_stage457_volume_oi_materiality_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_summary_stage457_volume_oi_materiality_audit_v1.csv`
- risk_mode：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_risk_mode_stage457_volume_oi_materiality_audit_v1.csv`
- trade_diff：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_trade_diff_stage457_volume_oi_materiality_audit_v1.csv`
- daily_diff：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_daily_diff_stage457_volume_oi_materiality_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage457_volume_oi_materiality_audit_decision_stage457_volume_oi_materiality_audit_v1.json`

## 结论

- 本阶段结论：`volume_or_open_interest_material_keep_strict_ohlcvoi_requirement`。
- 是否进入下一步：进入数据源下一步，不进入策略候选晋级。
- 不按目标的独立判断：
  - 不能晋级任何新版本。
  - 也不能把预收盘一致回放规格降级成 `OHLC+OI` 或 `OHLC-only`。
  - Stage156 的 `volume` 全0是实质阻断，不是可以忽略的字段缺口。
- 下一步：
  - 优先找冻结时点前真实分钟 `volume` 来源，或确认 TqBacktest 是否存在可切换字段/接口获取真实成交量。
  - 若不能取得可靠分钟成交量，应暂停一致预收盘真实回放工程；继续做 alpha 优化会重新落入不可执行口径。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只做字段置零反事实，没有筛日期、品种、阈值或收益窗口；结论反而收紧了晋级条件。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但方向收窄。
- 原因：它明确排除了“忽略 volume 缺口继续回放”的捷径。下一步只值得做真实分钟成交量源验证；不值得继续在同日收盘口径上做 3/6 个月优化。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage157 后的执行约束。
- 是否更新 `research/registry.md`：是，最新关键阶段从 Stage156 更新为 Stage157。
- 是否追加根目录 `memory.md/back_log.md`：是。本阶段改变了后续数据工程方向，属于重要合入摘要。
