# Stage005 换月连续历史续仓多周期资金曲线与稳健性审计

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-21 23:44 CST`
- 预声明 gate 提交：`91aa8d81e212e50891931829177a6eae64665840`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：在 Stage004 正式晋级失败后，用冻结的 1/2/3 年独立滚动窗口和完整周期再次比较正式版 A 与实验版 C
- 是否重要突破：否；它扩展了反证覆盖并确认不晋级，没有产生可替代正式版的新结论

## 外部调研与判断

- QuantConnect 官方期货 Security Master 文档说明，连续期货适合研究与指标连续性，而交易需要落到当前 mapped underlying contract：`https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-futures-security-master`。
- 判断：`backwards_ratio_continuous` 用于同产品换月形态具有工程合理性，但连续历史不能掩盖真实合约迁移后的账户回撤、成本和保证金风险；因此仍须按独立冷启动窗口审计，而不能只看完整周期资金曲线。

## 版本变更

- 新增工具：`tools/stage005_multicycle_equity_comparison.py`。
- 新增策略参数：无；实验版继续冻结 `enable_rollover_shape_same_volume_reopen=True`、`rollover_shape_history_mode=backwards_ratio_continuous`、`rollover_shape_volume_policy=shrink_to_allowed`。
- 修改策略参数：无。
- 删除策略参数：无。
- 新增评估：每年 1 月和 6 月独立冷启动，完整 1 年 `15` 窗口、2 年 `13` 窗口、3 年 `11` 窗口；每个周期另有一个距数据末端不超过 `7` 天的临近完整观察窗口，不进入决策；加完整区间共 `43` 窗口、`86` 个 A/C 真引擎运行。
- 新增门：各周期收益胜率、中位收益差、DD 非劣率、DD50 失败数、Sharpe 非劣率、聚合滑点、账户生存和 broker100 失败数；完整区间另设收益、DD、Sharpe、滑点和生存门。所有门在结果生成前固化到提交 `91aa8d81e`。
- 冻结 provenance 以该提交的实际时间 `23:24 CST` 为准；最初 manifest 的 `20:30` 是计划时间且已在结果记录阶段校正，结果于 `23:44` 生成，窗口与 gate 内容未变。
- 修改回测结果：无；Stage001-004 产物不覆盖。
- 删除回测结果：无。
- 正式配置、正式物料、master、生产：均未修改；CTP 未连接；订单/撤单 API `0/0`。

## 回测参数

- 数据区间：`2018-01-01` 至 `2026-05-29`。
- 账户规模：`150,000`。
- A：当前正式 C9/15万策略原样。
- C：A + 换月后使用点时 backward-ratio 连续历史判断 MA/MACD，并在硬风控容量内按原手数优先、容量不足缩手续接。
- 数据、费率、滑点、AI eligibility、broker10、0.5R stop/retry-once 与 Stage003/004 相同。
- 所有滚动窗口均为独立引擎冷启动，不是从完整周期资金曲线事后裁切。

## 完整周期结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易 | 非零日胜率 | broker100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| A 正式 | `13,071,214.10` | `8614.1427%` | `-56.2069%` | `1.3622` | `1,525,590` | `808` | `52.5841%` | 通过 |
| C 实验 | `13,338,365.80` | `8792.2439%` | `-56.9876%` | `1.3627` | `1,517,200` | `825` | `52.6812%` | 失败，最大 broker10 保证金/权益 `100.4112%` |

- C 相对 A：期末权益 `+267,151.70`，总收益 `+178.1011pp`，最大回撤恶化 `0.7807pp`，Sharpe `+0.0004`，滑点减少 `8,390`，交易增加 `17`，胜率 `+0.0971pp`。
- 完整周期预声明 gate 本身全部通过；broker100 作为额外账户风险证据单列，不用事后添加的新门改写冻结决策。
- 后续若重新开启新的晋级审计，须在运行前把完整周期 broker100 纳入硬门；本次不事后改门，但多周期门已独立否决候选。

## 多周期聚合结果

| 周期 | 完整窗口 | C 收益胜率 | 收益差中位数 | DD 非劣率（恶化不超2pp） | Sharpe 非劣率（差不低于-0.05） | 滑点 C/A | DD50 失败 A/C | 周期结论 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1年 | `15` | `60.00%` | `+1.6267pp` | `93.33%` | `66.67%` | `101.7899%` | `0/0` | 失败：Sharpe 非劣率低于 `80%` |
| 2年 | `13` | `53.85%` | `+0.7867pp` | `76.92%` | `76.92%` | `99.9635%` | `1/2` | 失败：DD、DD50 与 Sharpe 三门失败 |
| 3年 | `11` | `63.64%` | `+7.5663pp` | `81.82%` | `81.82%` | `101.2561%` | `4/4` | 通过全部预声明周期门 |

- 1 年关键反证仍含 `2018-01`：C 收益差 `-6.1133pp`，Sharpe 差 `-0.3471`；另有 `2019-06`、`2020-06`、`2023-06`、`2024-06` 未达 Sharpe 非劣门。
- 2 年最强反证为 `2020-06`：C 相对 A 收益 `-204.4657pp`，最大回撤从 `-41.5800%` 恶化到 `-50.9333%`，恶化 `9.3533pp`，并新增一个 DD50 失败。
- 2 年 `2022-01` 回撤从 `-39.9820%` 恶化到 `-46.0696%`，再次复现 `6.0876pp` 的压力期风险。
- 3 年虽通过聚合门，但 `2020-06` 和 `2022-01` 仍分别有 `3.5503pp`、`6.0876pp` 的回撤恶化；聚合通过不能覆盖 1/2 年周期失败。

## Gate、资金曲线与结论

- 决策：`confirm_do_not_promote_after_multicycle`；完整周期通过、3 年通过，但 1 年与 2 年失败，所以 `all_multicycle_gates_pass=false`。
- 资金曲线：完整周期、1 年、2 年、3 年逐窗图和多周期汇总图均由同一份 `stage005_equity_curves.csv` 生成；蓝色为正式 A，红色为实验 C；标题带 `*` 的临近完整窗口只观察不投票。
- 图形目视检查已通过；初版顶部标题与图例拥挤，已只调整布局并基于同一曲线 CSV 重绘，未重跑或修改任何回测指标。
- 不修改正式配置、不生成/发布正式物料、不合入 master、不激活生产。

## 输出文件

- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage005/stage005_window_summary.csv`
- comparison：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage005/stage005_window_comparison.csv`
- aggregate：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage005/stage005_cycle_aggregate.csv`
- equity data：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage005/stage005_equity_curves.csv`
- decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage005/stage005_decision.json`
- charts：`stage005_full_period_equity.png`、`stage005_equity_curves_1y.png`、`stage005_equity_curves_2y.png`、`stage005_equity_curves_3y.png`、`stage005_cycle_aggregate.png`

## 反思与后续

- 运行前过拟合判断：否。周期、1/6 月起点、完整窗口数量、临近完整观察规则和全部阈值已在结果产生前提交冻结，没有看结果挑窗口。
- 运行后过拟合判断：规则工程本身低，但若只引用完整周期或 3 年聚合优势强推正式就是选择性报告和过拟合；1/2 年失败必须保留。
- 运行前继续价值判断：有。Stage004 的反证可能是个别窗口，也可能跨周期；多周期检验能够区分二者。
- 运行后继续价值判断：历史主动优化没有价值，固定规则 forward shadow 仍有价值。后续不围绕 `2018/2020/2022` 扫 MA、MACD、复权方式、品种、起点、方向或手数比例；只等新增自然 OOS 换月样本后重新审计。
