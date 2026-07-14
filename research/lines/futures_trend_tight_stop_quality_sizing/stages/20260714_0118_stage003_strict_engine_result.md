# Stage003 严格引擎四锚点结果

- line_id：`futures_trend_tight_stop_quality_sizing`
- 当前模式：`research / day`
- 记录时间：`2026-07-14 01:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结规则真实引擎 A/B 修复后重跑
- 是否重要突破：否
- 是否触发A/B：是；仅研究 A/C，不接正式或 shadow

## 本次变更

- 新增脚本：无。
- 修改脚本：`tools/stage003_lower_half_stop_moderate_body_risk_transfer.py`。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无，继续冻结 `stop_atr14 <= 0.515281`、`0.312987012987013 < body_ratio <= 0.5525550867323019`、quality `1.25x`、other `0.75x`。
- 删除参数：无。
- 结果修复：严格 T-1、真实会话首分钟根开仓、引擎成交盯市账户权益、全候选/逐日对账、输入/输出 manifest 和 fail-close。

## 回测/归因参数

- 数据区间：`2020-01/2021-01/2022-01/2024-01 -> 2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：正式 broker10、滑点、增量保证金、`0.5R` 开仓日止损后一次重试，与 A 完全同口径。
- 样本过滤：正式 AI 月池保持原路径，新增 AI 特征 `0`；技术特征候选 `2,542`，覆盖 `100%`，quality `353`。
- 策略/归因口径：所有 flat-entry 始终 quality `1.25x`、other `0.75x`。

## 结果

| 起点 | A收益 | C收益 | 收益保留 | A最大回撤 | C最大回撤 | 改善 | A/C Sharpe | A/C滑点 | A/C交易数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 | 3345.2477% | 2762.3523% | 82.5754% | -65.3508% | -52.0645% | 13.2863pp | 1.2601 / 1.3207 | 1,712,120 / 1,044,170 | 793 / 770 |
| 2021-01 | 1373.0562% | 864.2336% | 62.9423% | -64.7817% | -49.1715% | 15.6102pp | 1.1671 / 1.1700 | 650,930 / 343,300 | 627 / 620 |
| 2022-01 | 83.0432% | 115.7315% | 139.3631% | -38.4513% | -33.3403% | 5.1110pp | 0.5856 / 0.7130 | 56,210 / 58,210 | 425 / 425 |
| 2024-01 | 73.4097% | 93.9493% | 127.9795% | -35.3049% | -23.1539% | 12.1510pp | 0.8409 / 0.9920 | 39,450 / 39,380 | 237 / 235 |

- 期末权益：C 分别约 `4,293,529 / 1,446,350 / 323,597 / 290,924`。
- 总收益：见表。
- 最大回撤：见表。
- Sharpe：见表。
- 总滑点：见表。
- 总交易次数：见表。
- 胜率：未输出统一闭合机会胜率，禁止用非零日胜率替代。
- 守恒：账户候选 `5,084`，权益/高水位/回撤最大误差 `3.73e-9 / 1.86e-9 / 6.11e-16`；根开仓 `1,616/1,616` 匹配；AI 月审计 `228/228 PASS`。

## 结论

- 本阶段结论：四锚点硬失败，原因是 `2021-01` 收益保留只有 `62.9423% < 70%`；全天候压低普通机会风险会在强趋势阶段切掉复利右尾。
- 是否进入下一步：否，不扩逐半年、不调阈值或倍率。
- 下一步：仅保留为机制对照；最终 reviewer 结论另写闭线记录。

## 独立 Agent Review

- reviewer：`Halley / 019f5c7c-8bb4-7d30-a2fb-e33a5308e797`。
- 结论：`P0=0/P1=0/P2=3/P3=3`；数值可信度 `99.9%`，无影响结果 P0/P1 的置信度 `99%`，关闭 Stage003 的置信度 `100%`。
- 独立复算：严格根开仓 `1,616/1,616`；0.5R 事件 `699`、synthetic 成交 `1,401`，价格/方向/手数/时序错误 `0`；账户成交盯市独立重建 `9,170` 个交易日最大误差 `6.52e-9`；AI 身份、T-1 特征和风险权重错配均为 `0`。
- P2：实际成交风险诊断仍按信号时间关联次日成交，`actual_risk_amount` 语义仍偏计划风险；C 组逐行 `minute_source` 未落盘；输入 manifest 仅为 8 个直接依赖而不是完整传递闭包。三项均不改变本次成交、PnL 或门槛结论，留档不改共享正式引擎。
- P3：完整会话优先级应显式契约化；缺产物级成交风险/C分钟源断言；review 时 LINE/result 记录未收口。本次已修复记录状态，测试缺口保留 TODO。

## 过拟合反思

- 运行前判断：是，高风险；规则来自同一历史归因。
- 运行后判断：是；虽然未扫参，但单一规则在重叠锚点上仍不能证明穿越周期。
- 原因：2021 锚点直接触发预声明硬失败，任何救参数都会加剧后验选择。

## 继续价值反思

- 运行前判断：是，可验证风险转移机制。
- 运行后判断：否，作为独立策略版本没有继续价值。
- 原因：机制信息已获得，继续微调只会围绕硬门做样本内优化。

## 输出文件

- report：`outputs/stage003_lower_half_stop_moderate_body_risk_transfer/tight_stop_quality_stage003_report_stage003_lower_half_stop_moderate_body_risk_transfer_v1.md`
- summary：`outputs/stage003_lower_half_stop_moderate_body_risk_transfer/tight_stop_quality_stage003_summary_stage003_lower_half_stop_moderate_body_risk_transfer_v1.csv`
- daily：`outputs/stage003_lower_half_stop_moderate_body_risk_transfer/tight_stop_quality_stage003_curves_stage003_lower_half_stop_moderate_body_risk_transfer_v1.csv.gz`
- quality：`outputs/stage003_lower_half_stop_moderate_body_risk_transfer/tight_stop_quality_stage003_feature_audit_stage003_lower_half_stop_moderate_body_risk_transfer_v1.csv`
