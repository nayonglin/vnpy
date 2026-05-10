# Stage220 第78 50万关闭100万sizing封顶多周期曲线反事实

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 14:33
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：资金约束反事实实验
- 是否重要突破：是，确认100万sizing封顶是50万收益率被压低的核心原因之一
- 是否触发A/B：否，本轮是风控约束反事实，不直接接入正式基准

## 外部调研与判断

- 参考资料：
  - 仓位上限和回撤上限是组合风控的核心防毁灭机制。
  - 关闭仓位上限后，必须同时观察收益、最大回撤、交易次数、滑点和尾部路径。
- 我的判断：
  - 用户提出的“100万最高资金限制”是关键线索。
  - 本轮应通过 `sizing_equity_cap=0` 关闭封顶验证，而不是修改正式第78基准。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/run_qmt_roll_stage218_stage78_30w_multiperiod_equity_curves.py`
- 新增CLI参数：
  - `--sizing-equity-cap`
- 运行参数：
  - `--capital 500000`
  - `--sizing-equity-cap 0`
  - `--model-tag stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_v1`
  - `--output-prefix qmt_roll_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves`
  - `--report-stage Stage220`
- 修改策略参数：临时覆盖 `sizing_equity_cap=0`
- 删除参数：无

## 回测口径

- 策略版本：`official_stage78_defensive_v1`
- 初始资金：`500,000`
- sizing资金封顶：关闭
- 基础风险：`0.045`
- 数据库：项目级 `/Users/bytedance/Desktop/person/vnpy/.vntrader/database.db`
- 运行目录：仓库根目录
- 门禁：Stage196哨兵数据检查通过
- 执行模型：同日收盘撮合
- 交易起点：每个窗口显式设置 `trade_start_date`
- 曲线：每个窗口从周期起点按 `NAV=1.0` 归一化，并输出回撤曲线

## 起点至今结果

| 起点 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 交易次数 | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 | 25,542,885 | 5,008.5770% | -40.0607% | 1.1295 | 880 | 1,968,150 |
| 2021 | 14,050,620 | 2,710.1240% | -39.3585% | 1.1105 | 673 | 1,115,240 |
| 2022 | 5,398,595 | 979.7190% | -36.5970% | 1.0468 | 471 | 404,340 |
| 2023 | 4,390,645 | 778.1290% | -36.2713% | 1.2223 | 369 | 308,580 |
| 2024 | 2,730,890 | 446.1780% | -36.2377% | 1.2052 | 258 | 171,660 |
| 2025 | 2,041,395 | 308.2790% | -26.3196% | 1.6146 | 145 | 98,950 |
| 2026 | 450,540 | -9.8920% | -28.5861% | -0.6975 | 27 | 4,660 |

## 独立阶段结果

| 阶段 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 交易次数 | 总滑点 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-2021 | 3,415,465 | 583.0930% | -39.2765% | 1.4760 | 362 | 179,520 |
| 2022-2023 | 1,118,940 | 123.7880% | -28.2421% | 0.9279 | 204 | 49,400 |
| 2024-2025 | 2,592,585 | 418.5170% | -36.2377% | 1.3392 | 216 | 139,830 |
| 2026最新 | 450,540 | -9.8920% | -28.5861% | -0.6975 | 27 | 4,660 |

## 与50万有封顶Stage219对比

- 2020起点至今：
  - 有封顶：期末权益 `5,884,710`，收益 `1,076.9420%`，回撤 `-39.2765%`
  - 无封顶：期末权益 `25,542,885`，收益 `5,008.5770%`，回撤 `-40.0607%`
- 2022-2023独立阶段：
  - 有封顶：收益 `129.6980%`
  - 无封顶：收益 `123.7880%`
- 2024-2025独立阶段：
  - 有封顶：收益 `349.7350%`
  - 无封顶：收益 `418.5170%`
- 2026独立启动：
  - 有封顶：收益 `-9.8920%`
  - 无封顶：收益 `-9.8920%`

## 观察

- 关闭100万sizing封顶后，长样本收益显著恢复，说明此前50万收益率被封顶压低是真实存在的。
- 影响主要出现在权益突破100万之后，因此 `2026` 短窗口没有变化。
- 无封顶并非所有独立阶段都更好，`2022-2023` 反而略弱，说明资金放大不等于所有状态都更优。
- 总滑点从Stage219的 `303,620` 放大到Stage220的 `1,968,150`，执行成本压力大幅增加。
- 最大回撤从 `-39.2765%` 扩大到 `-40.0607%`，表面增幅不大，但绝对回撤金额从 `570,470` 放大到 `6,240,400`。

## 输出文件

- HTML资金/回撤曲线：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_report_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_v1.html`
- Markdown报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_report_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_v1.md`
- 汇总CSV：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_summary_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_v1.csv`
- 曲线CSV：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_curves_stage220_stage78_50w_no_sizing_cap_multiperiod_equity_curves_v1.csv`

## 结论

- 用户判断成立：100万sizing封顶是50万本金长样本收益率下降的核心原因之一。
- 但关闭封顶不能直接作为正式基准，因为它显著放大成交规模、滑点和绝对回撤金额。
- 更合理方向不是完全关闭封顶，而是做动态sizing cap：例如权益低于100万正常放大，超过100万后按回撤/保证金压力逐步释放到150万或200万。

## 过拟合反思

- 运行前判断：有轻微过拟合风险，因为用户指定关闭一个保护性约束，可能被收益诱导。
- 运行后判断：不能直接合入。收益显著变强，但这是以暴露更大执行成本和绝对回撤为代价。
- 原因：资金上限是风控骨架，不是单纯收益限制器。

## 继续价值反思

- 运行前判断：有价值。它能解释50万收益率为何低。
- 运行后判断：有价值，且应继续做动态封顶实验。
- 下一步：
  - `50万 + sizing_cap=150万/200万/动态释放` 对照。
  - 同步跑滑点压力和蒙特卡洛，确认是否只是回测收益被放大。
  - 对最大绝对回撤路径做品种/方向/风险模式归因。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续整理时加入“100万sizing cap确认是资金效率天花板”。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：建议正式确认动态封顶方案后再追加。
