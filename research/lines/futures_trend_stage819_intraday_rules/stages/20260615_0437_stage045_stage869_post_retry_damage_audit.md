# Stage045 Stage869 retry_failed 后续同产品方向损伤审计

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：2026-06-15 04:37 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：研究线内只读事件后续归因与分钟K视觉复盘；只比较 C9 stop/retry 事件后的下一笔同产品同方向 entry；不改 Stage372 官方正式版，不改 Stage819 官方候选配置，不连接 CTP，不调用下单。
- 是否重要突破：否
- 是否触发A/B：否，`formal_ab_triggered=false`，本阶段是 Stage819 候选研究线内部只读审计，不进入正式 Stage78/Stage372 A/B。

## 外部调研与判断

- 参考资料：
  - vn.py GitHub：https://github.com/vnpy/vnpy
  - Backtrader order execution docs：https://www.backtrader.com/docu/order-creation-execution/order-creation-execution/
  - Backtrader stop/bracket examples：https://www.backtrader.com/blog/posts/2018-02-01-stop-trading/stop-trading/
- 我的判断：
  - 二次失败 `retry_failed` 是实时可知的信息，但它只说明当前入场尝试失败，不天然等于同产品同方向的后续趋势机会失效。
  - 如果要把它转成规则，必须先验证“后续第一笔同产品同方向 entry”是否系统性损伤；否则 cooldown 只是把事后亏损归咎于一个看似合理的标签。
  - 本阶段不扫 cooldown 天数、产品方向阈值、broker10 阈值、年份、品种或方向，只审计唯一低自由度形状：`retry_failed` 后阻断下一笔同产品同方向 entry。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage869_stage868_post_retry_damage_audit.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage868/C9 全周期 `START` 到 `END`。
- 账户规模：沿用 Stage819/Stage830/Stage847/Stage868 的组合回测口径。
- 成本口径：沿用既有 C9 回测输出；本阶段不重新撮合、不新增交易成本。
- 样本过滤：无年份、品种、方向过滤；仅使用 C9 已产生的 `121` 个 stop/retry 事件。
- 策略/归因口径：
  - 输入事件：Stage868 输出中的 C9 `stage847_stage819_c4_05r_stop_retry_once` stop/retry events。
  - 输入 entry：Stage865 C9 entry audit，含 matched closed-lot PnL、broker10、volume 等字段。
  - 输入分钟K路径：Stage866 entry path features 与 Stage861 full minute bars。
  - 审计规则：对每个 C9 stop/retry event，找事件日之后第一笔同 `product_vt_symbol + direction` 的 matched entry；按事件终态 `flat_no_reentry`、`flat_retry_failed`、`open_after_reentry` 分组。
  - proxy：`RF_NEXT1_block_first_same_pd_after_retry_failed`，即实时 `retry_failed` 后只阻断下一笔同产品同方向 entry。

## 结果

- 期末权益：不适用，本阶段不新增真实组合回测。
- 总收益：不适用，本阶段不新增真实组合回测。
- 最大回撤：不适用，本阶段不新增真实组合回测。
- Sharpe：不适用，本阶段不新增真实组合回测。
- 总滑点：不适用，本阶段不新增真实组合回测。
- 总交易次数：不适用，本阶段不新增真实组合回测。
- 胜率：不适用，本阶段不新增真实组合回测。
- 其他关键指标：

| event_final_state | events | next same PD found | unique next entries | unique next PnL | win rate | big winners | median days | median projected broker10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `flat_no_reentry` | 70 | 65 | 65 | `+4,834,948.3` | `46.1538%` | 5 | 97 | `39.8314%` |
| `flat_retry_failed` | 25 | 21 | 21 | `+11,000,934.0` | `33.3333%` | 3 | 146 | `39.1489%` |
| `open_after_reentry` | 26 | 25 | 25 | `+5,113,747.4` | `44.0000%` | 1 | 85 | `39.5695%` |

### Proxy 结果

| proxy_id | affected entries | affected next PnL | proxy delta if blocked | loser saved | winner cut | big winner cut | big winners |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `RF_NEXT1_block_first_same_pd_after_retry_failed` | 21 | `+11,000,934.0` | `-11,000,934.0` | `+1,693,386.8` | `-12,694,320.8` | `-9,221,240.0` | 3 |
| `ALL_STOP_NEXT1_block_first_same_pd_after_any_stop_retry_event` | 111 | `+20,949,629.7` | `-20,949,629.7` | `+13,750,861.1` | `-34,700,490.8` | `-14,733,600.0` | 9 |
| `OPEN_RETRY_NEXT1_control_after_open_after_reentry` | 25 | `+5,113,747.4` | `-5,113,747.4` | `+3,178,202.6` | `-8,291,950.0` | `-155,530.0` | 1 |

- `retry_failed` 后下一笔同产品同方向 entry 不是系统性损伤源：虽然 `14/21` 是亏损，亏损修复空间只有 `+1,693,386.8`；但 `7` 笔赢家贡献 `+12,694,320.8`，其中 `3` 个 big winner 合计 `+9,221,240.0`。
- 年度上 2018/2019 小幅负，2020-2024 合计明显为正，不能按年份补丁化。
- K线视觉复核显示，后续第一笔 entry 的路径混杂：有 `lh/fu/MA` 这类继续失败，也有 `rb/jm/OI` 这类后续右尾；二次失败标签无法稳定区分后续“失效趋势”和“下一轮趋势启动”。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_report_stage869_stage868_post_retry_damage_audit_v1.md`
- event_next：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_event_next_entry_stage869_stage868_post_retry_damage_audit_v1.csv`
- state_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_state_summary_stage869_stage868_post_retry_damage_audit_v1.csv`
- proxy_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_proxy_summary_stage869_stage868_post_retry_damage_audit_v1.csv`
- yearly_summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_yearly_summary_stage869_stage868_post_retry_damage_audit_v1.csv`
- summary_chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_summary_chart_stage869_stage868_post_retry_damage_audit_v1.png`
- atlas_manifest：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_atlas_manifest_stage869_stage868_post_retry_damage_audit_v1.csv`
- atlas_pages：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_atlas_page001_stage869_stage868_post_retry_damage_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_atlas_page002_stage869_stage868_post_retry_damage_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_atlas_page003_stage869_stage868_post_retry_damage_audit_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_atlas_page004_stage869_stage868_post_retry_damage_audit_v1.png`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage869_stage868_post_retry_damage_audit_decision_stage869_stage868_post_retry_damage_audit_v1.json`

## 结论

- 本阶段结论：`stage869_retry_failed_next_same_pd_cooldown_rejected_no_engine`。
- 是否进入下一步：该 cooldown 分支不进入真实引擎，不进入正式候选，不触发正式 A/B。
- 下一步：
  - 不继续扫 cooldown 天数、产品方向范围、broker10 阈值、年份、品种、方向。
  - 不把 `retry_failed` 后续损伤包装成同产品方向暂停规则；它会砍掉更大的右尾。
  - 如果继续本线，必须换成“独立实时趋势恢复信号”或“持仓后组合风险治理”的新结构，而不是继续沿 stop/retry 的后续标签做派生 cooldown。

## 过拟合反思

- 运行前判断：否。规则是事件驱动的唯一形状：`retry_failed` 后下一笔同产品同方向 entry，不扫任何窗口和阈值。
- 运行后判断：本阶段不是过拟合；但若继续按 cooldown 天数、年份、品种、方向或 broker10 阈值救结果，就会是过拟合。
- 原因：失败不是因为阻断天数没选好，而是因为二次失败后的后续 entry 本身贡献显著右尾。继续拆小样本只是在试图躲开 `jm/rb/OI` 等大赢家。

## 继续价值反思

- 运行前判断：有继续价值。它是 Stage868 后一个更高一级、实时可观测的后续损伤假设。
- 运行后判断：retry_failed 后同产品方向 cooldown 分支没有继续价值；研究线整体仍有价值，但要换结构。
- 原因：阻断 proxy 会少赚 `11,000,934.0`，big winner cut `9,221,240.0`，远大于 loser saved `1,693,386.8`。这说明二次失败不能作为后续同产品方向失效的充分条件。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage045 否决结论，并停止 stop/retry 派生 cooldown 分支。
- 是否更新 `research/registry.md`：否，本线归属未变更。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是重要突破、不是路线合并、不是正式候选、也没有触发正式 A/B。
