# Stage017 多头三倍放大与半量缩减风险全周期冻结门

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 冻结时间：2026-08-24 19:02 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 用户确认：2026-08-24，按最近10日成交量与再前10日成交量比较；多头严格低于 `0.5` 倍时风险 `×0.5`
- 阶段性质：Stage016 后新增独立 M 研究臂；先跑最小完整周期门
- 是否重要突破：否，结果未知
- 是否触发 A/B：是；风险倍率改变正式候选路径，必须同时对照正式 A 与换月 C

## 外部调研与判断

- CME 将期货成交量解释为市场参与度、流动性和换月迁移信息，同时明确成交量本身不能识别买卖方向：<https://www.cmegroup.com/education/courses/introduction-to-futures/what-is-volume>。
- `pysystemtrade` 将 forecast、position sizing、portfolio 与 accounting 分层，支持把本规则隔离在风险仓位层而不是改变主信号：<https://github.com/robcarver17/pysystemtrade/blob/develop/docs/backtesting.md>。
- 我的判断：低量减风险可作为参与度不足的防守假设，但精确 `0.5` 阈值没有普适理论最优性；本阶段只允许一次冻结验证，不允许失败后扫阈值。

## 冻结规则

- M 基于换月 C。
- 多头高量：30日价格方向同向，且 `T-9..T` 成交量总和严格大于 `3.0 × T-19..T-10`，原风险金额 `×1.5`。
- 多头低量：不要求30日价格方向同向；只要最近10日成交量严格小于再前10日 `0.5` 倍，原风险金额 `×0.5`，且优先于高量判断。
- 其他多头：原风险金额 `×1.0`；恰好 `0.5` 倍不减、恰好 `3.0` 倍不加。
- 空头：在价格和成交量历史检查前旁路，始终 `×1.0`。
- 价格或成交量历史不足、字段无效时保持 `×1.0`；不因缺数据减仓或加仓。
- 覆盖 risk-budget flat、reverse、rollover reopen、regular add、donchian add、post-quality add；fixed-size 不变。
- 倍率后仍向下取整；保证金、单品种、相关性、热度、回撤、波动率、AI、容量和 broker 硬门全部保留。
- 默认参数关闭；A/C/L 与正式默认行为不得变化。

## 实验身份与参数

- A：当前正式 C9/15万。
- C：A + 换月连续历史形态续仓。
- L：C + 多头30日同向且严格三倍量时 `×1.5`，其他 `×1.0`。
- M：L + 多头严格半量以下时 `×0.5`；空头仍 `×1.0`。
- A/C/L 复用 Stage015 已验证的完整周期同臂结果；仅 M 新跑一次独立真引擎完整周期。
- 数据区间：`2018-01-01 -> 2026-05-29`；初始资金 `150,000`。
- 新增参数：`enable_directional_30d_low_volume_risk_discount=true`、`directional_30d_low_volume_ratio_threshold=0.5`、`directional_30d_low_volume_risk_multiplier=0.5`。
- 其他成本、品种池、AI池、换月、止损、加仓、保证金与执行硬门全部继承 C/L。
- 运行时 `stage017_decision.json` 自动记录结果前 `candidate_freeze_commit`。

## 预声明晋级门

M 必须同时通过 `A_vs_M` 和 `C_vs_M`：

- 总收益不低于左侧基线。
- 最大回撤恶化不超过 `1pp`。
- Sharpe 不低于左侧 `0.01` 以上。
- 滑点不超过左侧 `105%`。
- 账户生存通过。
- broker100 严重度不比左侧更差。
- 风险合同必须同时出现多头高量、多头低量、多头基准和空头旁路；严格上下边界、倍率和目标风险金额逐行通过。

只有两个正式晋级对照全部通过，才允许讨论固定多周期；任一失败即停止，不扫描 `0.4/0.6`、`0.4/0.6` 风险倍率、上下窗口、方向、品种、年份或起点。

## TDD 与验证边界

- 策略 RED：低量独立于30日方向、严格半量边界和空头旁路共 `1 failure + 2 errors`。
- 策略 GREEN：最小实现后上述 `3 passed`。
- 诊断 RED：entry-risk 尚未持久化低量字段时 `1 error`；补齐字段后 `1 passed`。
- Runner RED：Stage017 尚不存在时 `3 failed`；实现身份、风险合同和双基线决策后 `3 passed`。
- 回测前运行相关策略与 Stage010/013/014/015/016/017 runner 回归、`py_compile`、`git diff --check`。
- 仅研究回测；不修改正式配置、正式物料、master、production、launchd、CTP、邮件或订单接口。
- 订单/撤单 API 必须为 `0/0`，`ctp_connected=false`。

## 运行前反思

- 是否过拟合：是，中高风险。M 在已失败的历史量能路线上新增精确低量断点和减仓倍率，属于额外自由度。
- 是否还有继续价值：有，但仅限一次性验真。它回答“极端缩量时主动降多头风险”能否改善 L 的尾部且不破坏正式 A/C 收益；失败后不做参数救援。
