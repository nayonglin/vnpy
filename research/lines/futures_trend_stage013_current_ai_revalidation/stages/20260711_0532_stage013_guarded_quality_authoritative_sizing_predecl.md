# Stage013 正确账本 + guarded quality 25% 唯一候选预声明

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 预声明时间：`2026-07-11 05:32 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Stage012 失败后跨研究线可行域审计选出的唯一正交真引擎候选
- 是否重要突破：待真引擎结果
- 是否触发 A/B：否；三锚点全部通过后才允许讨论扩样本

## 外部调研与判断

- 前序 drawdown feedback/动态 floor 文献支持使用账户历史高水位约束风险，但不能告诉我们哪些信号值得恢复右尾；本阶段不再调整账户回撤公式。
- 上游 `futures_trend_rebuilt_c9_15w_v2_optimization` 的 Stage013 guarded quality proxy 固定为 `AI rank 1-8 + selected_volume>1 + risk_multiplier<2`，按 `25%` 增加风险；Stage014 证明 floor 可实现且不会像 ceil 一样系统性超配小手数，但两者都只是 proxy。
- Stage058 是 quality+OI 两腿真实引擎，不能回答 guarded quality 单腿；它失败后已禁止继续扫描 OI、rank 和比例。
- 我的判断：guarded quality 单腿是现有证据中唯一没有被单独真实引擎证伪、又可能在 Stage012 正确账本上恢复右尾的结构。它不是根据 Stage012 三个结果新调出来的参数，因此允许一次冻结证伪。

## 固定三臂

- A：Stage012 已复用的旧 current C9 目标参照；只作为用户原目标的收益/回撤基准，不能称正确账本策略。
- B：Stage012 全局权威权益 sizing；直接复用 `62/62` manifest 冻结产物，不重跑。
- C：B + guarded quality 25% floor 单腿；新进程真实组合引擎运行。
- 三臂统一起点 `2020-01、2021-01、2022-01`，终点 `2026-06-30`，初始资金 `150,000`，当前 AI 月池、品种池、成本、止损重试、退出和保证金参数一致。

## 唯一规则

- 只处理 `candidate_status=opened` 的新 `flat_entry`。
- 入场当时可见条件必须同时满足：`AI rank 1-8`、原计划 `selected_volume>1`、`risk_multiplier<2`。
- 动作：`after=floor(before*1.25)`；只有 `after>before` 才应用。
- 不使用 RSI、OI、xsmom、年份、月份、品种、方向、事后盈亏或未来路径。
- 不使用 ceil、不强制最小加 1 手、不修改已有仓、加仓、换月、反手或退出。
- Stage013 account-state gate 与 Stage010 ramp 继续关闭；Stage012 正确账本保持开启。

## 绩效硬门

- C 三个锚点都必须正收益。
- C 相对 A 的收益保留三个锚点都必须 `>=70%`，不得用中位数掩盖 `2022-01`。
- C 相对 A 的全期最大回撤三个锚点都至少改善 `3pp`。
- C 的三个 2022 account-history 最大回撤都必须优于 A。
- C broker10 峰值不得高于 A。
- C 相对 B 的总收益三个锚点都必须提高，证明 quality 单腿确实恢复右尾而非无事件。
- 任一门失败即 `fail-close`；不改 `25%/rank/risk_multiplier/floor`，不加 OI，不扩 13 起点。

## 语义硬门

- Stage012 源 manifest、Stage013 upstream proxy 源文件 hash 和当前 tool/test hash 必须落 lineage。
- 每个 C 锚点的权威权益 reconciliation、即时成交 correction、同日候选 sizing、正式日结恒等式全部通过。
- 每个 quality 事件逐行验证条件、floor 公式、整数增量、候选打开状态和 `before/after`；三锚点都必须有事件。
- Quality event 必须与最终 entry candidate 的 signal date、产品、方向和 selected volume 唯一映射；缺失、重复、歧义为 0。
- A/B/C AI normalized hash 必须一致，missing signal date 和未来日期违规为 0。
- Stage013 gate/ramp/OI/ceil 事件必须为 0。
- 独立 agent 必须复核实现顺序、账本、事件映射、A/B复用、公平性、数字、图表和过拟合边界；有 P0/P1 不得形成结论。

## TDD 与执行计划

1. 先新增 `tools/test_stage013_guarded_quality_authoritative_sizing_engine.py`，覆盖 floor25 正例、rank/risk/小手数/non-flat/disabled 负例、事件审计 fail-closed 和输出目录边界。
2. 用 `.py311/bin/python -m unittest` 观察测试因模块/函数缺失而失败。
3. 新增 `tools/stage013_guarded_quality_authoritative_sizing_engine.py`，继承 Stage012 策略，只实现单腿 quality overlay 和审计，不复制 OI。
4. 先让 focused tests 通过，再运行 Stage005-013 全测试。
5. 运行三个 C 真引擎，复用 A/B 冻结产物；生成 summary、A/B/C pair gates、quality events/audit、reconciliation、sizing、AI、curves、chart、decision、lineage、report 和 manifest。
6. 先机械复核，再拉独立 agent；审查完成后更新 stage 结果、`LINE.md`、registry 和 `back_log.md`。

## 运行前反思

- 过拟合：低到中等。规则来自本轮之前冻结的跨起点 proxy，不是看到 Stage012 结果后扫描出来；但 quality selector 本身来自历史法证，必须由三锚点正确账本真引擎证伪。
- 继续价值：有。Stage012 的主要缺口是右尾不足，而不是 broker10；guarded quality 单腿恰好只恢复已有 AI 高位、非双倍风险候选，机制与继续调账户回撤阈值不同。
- 停止边界：本次失败后不再运行第二个 quality/OI/xsmom/rank/比例变体。

