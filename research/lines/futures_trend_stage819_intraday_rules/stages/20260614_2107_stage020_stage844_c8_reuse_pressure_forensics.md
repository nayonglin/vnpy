# Stage020 Stage844 C8释放资金与风险压力归因

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-14 21:07 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因；读取 Stage830 C4 与 Stage843 C8 已生成产物，不重新回测，不修改正式版、不修改候选配置、不连接 CTP、不调用下单。
- 是否重要突破：否。属于 Stage019 失败后的机制拆解，不构成正式候选。
- 是否触发A/B：否。C8 未通过 C4 闸门，且本阶段没有产生可接入正式版的新策略版本。

## 外部调研与判断

- 参考资料：
  - CME futures order types：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/futures-order-types
  - CME position and risk management：https://www.cmegroup.com/education/courses/things-to-know-before-trading-cme-futures/position-and-risk-management
  - CFTC stop-loss order education：https://www.cftc.gov/sites/default/files/Stoploss_final_ada.pdf
  - vn.py GitHub：https://github.com/vnpy/vnpy
- 我的判断：
  - 止损本质是执行纪律，不是趋势判断本身。CME/CFTC 资料都支持预先定义止损与组合风险控制，但不支持把单次止损事件直接解释为趋势失效。
  - vn.py 的策略、成交、风控、持仓事件分层也说明，本阶段应拆“单笔止损直接贡献”和“止损后组合如何重新使用资金”，而不是继续调 S3 连续根数。
  - Stage844 因此只做 frozen C4/C8 路径归因：如果风险来自后续资金复用或低权益分母下的 broker10 放大，就不能继续沿 `2/3/4根`、OR长度、R倍数做救参。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage844_stage843_c8_reuse_pressure_forensics.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2018-01-01` 到 `2026-05-29`。
- 账户规模：沿用 Stage819 候选 `300,000` 口径；本阶段不重新计算组合成交。
- 成本口径：沿用 Stage830/Stage843 已生成曲线、closed lots 与事件文件中的成本、滑点、交易次数口径。
- 样本过滤：只比较 C4 `stage830_stage819_c2_broker10_100_cap` 与 C8 `stage843_stage819_c4_s3_two_stop_side_closes`；不按年份、品种、方向过滤。
- 策略/归因口径：
  - 直接贡献：C8 structural exit lot 与 C4 同 open_key 的 PnL 差。
  - 复用贡献：每个 C8-vs-C4 增量/缩减 open_key 只归因到最近的前序 S3 事件，窗口固定 `1/3/5/10/20` 个交易日。
  - 压力窗口：每个 S3 事件后的 `0/1/3/5/10/20` 日 C8-C4 日度 PnL、broker10、drawdown 差。
  - K线视觉：选取 20 日压力最坏的 S3 事件生成分钟K atlas，标记 entry、0.5R、exit、trigger。

## 结果

- 期末权益：C8 `33,052,106.4`；C4 `30,523,910.8`；C8-C4 `+2,528,195.6`。
- 总收益：C8 `10917.3688%`；C4 `10074.6369%`。
- 最大回撤：C8 `-51.4922%`；C4 `-50.7900%`；C8 比 C4 恶化 `0.7023pp`。
- Sharpe：C8 `1.3872`；C4 `1.4519`；C8 比 C4 下降 `0.0647`。
- 总滑点：C8 `2,312,880`；C4 `2,079,430`。
- 总交易次数：C8 `686`；C4 `677`。
- 胜率：C8 `52.5699%`；C4 `53.6294%`。
- 其他关键指标：
  - 决策标签：`stage844_c8_diagnostic_reuse_positive_but_pressure_worse`。
  - C8 direct structural lots `43` 笔，直接 PnL 差 `-3,168,065.0`；其中 `18` 笔修亏损 `+1,344,365.0`，`25` 笔误杀赢家/加亏 `-4,512,430.0`。
  - 20日 nearest reuse：增量 C8 暴露 `89` 行，增量风险 `+2,445,213.4`，增量 PnL `+3,361,304.0`；说明 blanket cooldown 不成立。
  - 20日 event window：重叠口径累计 PnL 差 `-2,226,229.6`，中位 PnL 差 `+5,040.0`，负贡献事件 `20/43`。
  - 20日 event window 最大 broker10 差 `+43.8475pp`，中位最大 broker10 差 `+7.0449pp`，最差 drawdown 差 `-19.0226pp`，`6` 个事件窗口内 C8 broker10 超过 `100%`。
  - C8 broker10 峰值在 `2022-07-07` 为 `135.6309%`，同日 C4 为 `115.4012%`。
  - C8-C4 broker10 最大差在 `2021-02-23` 为 `+43.8475pp`，C8 `104.4144%` vs C4 `60.5669%`。
  - C8-C4 最差回撤差在 `2022-03-02` 为 `-19.0226pp`，C8 `-19.4461%` vs C4 `-0.4234%`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_report_stage844_stage843_c8_reuse_pressure_forensics_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_reuse_summary_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
- orders：无，本阶段未生成订单。
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_daily_delta_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_decision_stage844_stage843_c8_reuse_pressure_forensics_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_open_delta_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_direct_structural_lot_delta_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_reuse_attribution_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_event_windows_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_event_window_summary_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_pressure_days_stage844_stage843_c8_reuse_pressure_forensics_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_path_chart_stage844_stage843_c8_reuse_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_reuse_chart_stage844_stage843_c8_reuse_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_event_atlas_page001_stage844_stage843_c8_reuse_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_event_atlas_page002_stage844_stage843_c8_reuse_pressure_forensics_v1.png`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage844_stage843_c8_reuse_pressure_forensics_event_atlas_page003_stage844_stage843_c8_reuse_pressure_forensics_v1.png`

## 结论

- 本阶段结论：
  - C8 不能因为期末权益更高就晋级。它的 S3 直接退出本身净负 `-3,168,065.0`，主要问题是误杀右尾大于修复左尾。
  - 止损后释放资金的 20日增量复用 PnL 为正 `+3,361,304.0`，所以不能做“止损后全局冷却”或“同品种一刀切冷却”。
  - C8 的真实问题是组合路径风险：释放资金后增量风险提高 `+2,445,213.4`，同时 broker10 峰值、broker10 差、回撤差显著恶化。
  - S3 分支停止。不要继续扫连续根数、OR长度、R倍数、品种、方向或年份。
- 是否进入下一步：进入下一步只读研究，但不沿 S3 救参。
- 下一步：
  - 优先做入场侧质量控制或组合复用闸门的只读低自由度形状，例如“释放资金后禁止堆到同一压力簇/同一方向簇”的机制归因。
  - 若要进真实引擎，必须先证明它不是用少数压力事件反推的产品/年份补丁。

## 过拟合反思

- 运行前判断：否，本阶段不做优化，只用冻结 C4/C8 输出做固定窗口归因。
- 运行后判断：否，当前结果本身不是新规则，只是解释 C8 失败机制；但如果把最坏 K 线 atlas 事件反推成专属品种/时间规则，就会过拟合。
- 原因：窗口固定为 `1/3/5/10/20`，不扫描 S3 参数，不筛年份/品种/方向；结论指向 broad mechanism，而不是局部补丁。

## 继续价值反思

- 运行前判断：有价值。Stage019 显示 C8 “多赚但更危险”，需要拆清直接退出、资金复用、broker10 压力三个层次，否则容易误判为 S3 还可调参。
- 运行后判断：有价值，但只限于机制迁移，不继续 S3。Stage844 说明直接退出负、复用正、压力差这三者同时成立，下一步应转向复用纪律/入场质量，而不是止损形状。
- 原因：结果把“止损是不是错”拆成了两层：单笔 S3 直接伤右尾，组合复用又确实贡献收益，但风险预算和保证金压力没有被约束。这个结论可指导后续低自由度研究。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新 Stage020 状态和后续方向。
- 是否更新 `research/registry.md`：否，本阶段没有新增研究线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选、重要突破或路线迁移；只在本线记录。
