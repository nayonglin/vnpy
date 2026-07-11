# Stage011 2021锚点路径反馈与基础权益账本归因

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 归因产物时间：`2026-07-11 04:35 CST`
- 修正复核完成时间：`2026-07-11 04:58 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage010 唯一硬失败锚点的只读路径归因
- 是否重要突破：是；定位到当前 C9 基础 sizing 使用的内部权益账存在系统性重复累计
- 是否触发 A/B：否；只允许进入 Stage012 账户正确性实验，不允许从交易结果选规则

## 外部调研与判断

- 本阶段未新增外部策略资料；核心证据来自冻结的 Stage010 真引擎产物、vn.py 日结恒等式和实际撮合/`on_bars` 时序。
- 我的判断：Stage010 在 2021 锚点的失败不是 ramp 直接减仓本身造成，而是间接路径反馈覆盖了直接收益；更基础的问题是 A/C 都继续用重复累计的旧 `estimated_equity` 做 sizing，必须先修账户语义，不能继续调回撤阈值或手数公式。

## 本次变更

- 新增归因脚本：`tools/stage011_2021_anchor_path_feedback_attribution.py`。
- 新增测试：`tools/test_stage011_2021_anchor_path_feedback_attribution.py`。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增结果：路径信号映射、直接/间接 closed-lot 毛损益、谷底残差、候选日旧账误差和正式日结恒等式审计。
- 修改结果：独立 review 指出首次候选前权益比较错用了前一日正式权益；已改为同日 `account_equity`，并补同日日结恒等式测试后重建全部产物。
- 删除结果：删除首次错误的“前一日 pretrade equity”解释，不保留为有效证据。
- 实盘/CTP/邮件/launchd：全部未改、未连接、未调用订单 API。

## 归因参数与边界

- 来源：Stage010 `2021-01` 冻结 A/C daily、entry candidates、trades、closed lots、ramp events；源 manifest `64/64` 通过。
- 归因窗口：`2022-01-01` 至 C 的 2022 account-history 谷底 `2022-07-06`。
- 回撤口径：从 `2021-01` 独立起点累计的账户历史高水位；local-reset 不参与结论。
- 信号映射：取 A/C opened signal 并集，按 signal date、合约、方向、下一交易日开仓和 closed-lot 量守恒映射。
- 损益边界：只统计截至 C 谷底已结束的 closed-lot 毛损益；不含佣金、滑点、未平仓 MTM 和其他路径状态，不称可执行反事实。
- 候选时点：引擎先撮合旧订单再进入 `on_bars`，因此候选生成时旧 `estimated_equity` 与同日正式 `account_equity` 比较。

## 归因结果

- A 峰谷：`2022-03-09` 权益 `1,144,978.80` 至 `2022-06-02` 权益 `671,038.80`，2022 account-history 回撤 `-41.392906%`。
- C 峰谷：`2021-10-26` 权益 `1,075,926.00` 至 `2022-07-06` 权益 `608,386.40`，2022 account-history 回撤 `-43.454624%`。
- C 谷底相对 A 同日权益差：`-101,122.40`。
- 谷底前信号并集 `35` 个：`34` 个 A/C 双侧映射，`1` 个 A 缺失、C 映射；直接 ramp `19` 个，间接路径反馈 `16` 个。
- 谷底前已结束：直接 ramp `17` 个、间接路径 `14` 个；其余 `4` 个没有双侧都结束。
- 直接 ramp 的 C-A closed-lot 毛损益：`+109,980.00`，说明直接减仓总体有利。
- 间接路径反馈的 C-A closed-lot 毛损益：`-195,522.40`，覆盖了直接防守收益。
- 已结束交易解释合计：`-85,542.40`；相对权益差残差 `-15,580.00`，保留为未平仓 MTM、成本和其他路径状态，不强行分摊。

## 基础 sizing 权益账本

- A 候选日旧账偏差中位/最大：`233,360.00 / 289,740.00`；`55/55` 个候选日非零。
- C 候选日旧账偏差中位/最大：`357,960.00 / 417,870.00`；`56/56` 个候选日非零。
- 正式日结恒等式：`今日权益 = 昨日权益 + holding_pnl + trading_pnl - commission - slippage`。
- 恒等式最大绝对误差：`2.32831e-10`。
- 系统性根因：position-change 的昨收到今收 PnL 已由正式持仓盯市计入，但旧策略内部 `estimated_equity` 又按成交方向重复累计，进而影响后续 sizing、free capital、heat 和路径。

## 独立 agent 审查

- 首轮审查发现 P1：候选生成时点权益比较错用前一日正式权益；该问题已修复并重建。
- 修正后复审：`P0=0/P1=0/P2=2`；数字置信度 `99.8%`，语义/逻辑置信度 `98%`。
- P2 1：`-15,580.00` 残差未继续拆分，但报告已明确边界，不影响“间接路径覆盖直接防守”和“旧账系统性偏差”的结论。
- P2 2：`history_database_snapshot_complete=false`；冻结产物可审计，但未来数据库变化后不能承诺字节级重跑。
- 审查结论：允许且只允许 Stage012 三锚点全局权威权益 sizing 正确性测试；禁止根据品种、方向、日期或事后 PnL 选择规则。

## 输出文件

- report：`outputs/stage011_2021_anchor_path_feedback_attribution/stage013_current_ai_stage011_2021_anchor_path_feedback_attribution_report_stage011_2021_anchor_path_feedback_attribution_v1.md`
- decision：`outputs/stage011_2021_anchor_path_feedback_attribution/stage013_current_ai_stage011_2021_anchor_path_feedback_attribution_decision_stage011_2021_anchor_path_feedback_attribution_v1.json`
- chart：`outputs/stage011_2021_anchor_path_feedback_attribution/stage013_current_ai_stage011_2021_anchor_path_feedback_attribution_equity_and_legacy_error_stage011_2021_anchor_path_feedback_attribution_v1.png`
- manifest：`10/10` 文件大小、SHA256 和文件集合复核通过。

## 结论

- 决策：`stage011_global_legacy_equity_sizing_bug_stage012_correctness_test_allowed`。
- Stage010 的直接 ramp 在该窗口实际有利，失败来自更大的间接路径分叉；不能据此继续微调 ramp。
- 当前 C9 的研究回测内部 sizing 权益账存在系统性错误；本阶段没有审计 CTP 券商账户或正式实盘运行路径，因此不能外推成“券商实盘权益错误”。
- 是否进入下一步：是，仅进入 Stage012 三锚点账户正确性 A/C。

## 过拟合反思

- 运行前：低；只读解释唯一冻结反例，不选择交易参数。
- 运行后：否；结论由账户恒等式、撮合时序和全窗口路径映射得到，没有按收益挑品种、方向、日期或阈值。
- 风险边界：若从 35 个信号中选择赢家/输家规则，立即转为高过拟合，本阶段明确禁止。

## 继续价值反思

- 运行前：有，需要区分 ramp 直接效果与路径反馈。
- 运行后：有且范围明确；只值得验证全局正确账本，不值得继续救 Stage010 参数。
- 后续：Stage012 任一锚点硬门失败即关闭，不扩 13 起点、不参数救援。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：与 Stage012 一并更新。
- 追加根目录 `memory.md/back_log.md`：Stage011/012 完成后追加重要账户语义里程碑。
