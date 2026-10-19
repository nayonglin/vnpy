# Stage039：恢复 native 风险预算的一手研究候选与信号快照

- 时间：2026-10-19 18:19 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 不是重要突破版本，不是正式晋升；用户明确新授权：恢复以前风险预算，一手风险超预算则不开仓。保持每品种最多一手、无加仓、无 AI、无四品种上限、全市场、已批准日线近似及供需边界。
- 本阶段新增金融回测次数 **0**，未读取账户、连接 CTP、报单或下载行情；不修改 Stage003/018、金融 runner、LINE、registry、官方源及任何旧输出。根任务负责新 Stage040/041 的实际开盘二次预算闸门与金融回放。

## 调研、实际接口与判断

- 外部核对：[vn.py 官方组合策略文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)、[官方组合策略模块](https://github.com/vnpy/vnpy_portfoliostrategy)。模板的目标/实际持仓及委托管理规范可复用，不能代替本仓库策略自己的初始止损和风险预算政策。
- 真实本地 `_calculate_entry_sizing` 的目标预算字段为 `risk_amount`，不是猜测的 `target_risk_amount`；每手风险字段为 `risk_per_contract`，包含实际 `_entry_stop_price`、合约乘数、tick×乘数与最小货币风险。Stage804 对 long 的 tighter initial stop 覆盖仍有效，不能改用统一百分比止损。
- `fixed_size > 0` 分支会把 `risk_amount` 留为 None；因此必须恢复 `fixed_size=0`，先执行完整 native sizing 和环境/连败/保证金/单笔/簇/broker 闸门，再在最外层追加只能缩量的一手预算判断。
- 当前 Stage003 的纯 overrides 包含 `streak_risk_multipliers=1.0,1.0,1.0,1.0`、recovery sleeve 关闭等真实值。没有凭历史记忆把它改成 `1,1,1,0.1`；新 runner 应保留最终正式 settings 合并结果。测试中的 0.1 连败档只是明确配置的合成行为用例，不是新增策略政策。
- native `_open_position` 内存在 `max(1, volume)`。即使 sizing 已返回 0，传入 0 也必须在新的候选入口截断，不能让这个兜底造成无预算持仓。

## 独立实现

新增 `tools/stage039_risk_budget_candidate.py`：

1. `one_lot_budget_allows(risk_per_contract, target_risk_amount)`：二者必须有限且严格大于 0，且 `risk <= budget`。相等允许，没有 epsilon 放宽、最小一手回退或缺预算默认值；bool、None、NaN、Inf、负数和非法值拒绝。
2. `candidate_overrides(universe_path, product_count=93)`：复用 Stage003，只将 `fixed_size=0` 并以产品自然容量设置并发参数；`min_position_size=1/max_position_size=1`。不改风险比例、最小/最大风险、环境、连败、簇或保证金政策阈值。
3. `NativeRiskBudgetSizingMixin`：供根任务放在既有 FeeStrategy 前组成 MRO；完整类 `FullMarketNativeRiskBudgetOneLot` 也可直接使用。native `selected_volume=0` 永不被恢复；通过预算后也最多为 1。
4. `_open_position`：passed volume、native selected volume 必须均为 1，并通过预算，再调用原生建层；0、超量和超预算均不调用 native 建层函数。
5. 原生新 pending layer 挂载 `layer.stage039_signal_risk_budget`，类型为 `frozen=True` 的 `SignalRiskBudgetSnapshot`，`dataclasses.asdict()` 可序列化。策略内序号使每层 `snapshot_id` 唯一；同一层 reissue 不重新生成快照。快照不是可变的 sizing dict 引用。

冻结快照包含：唯一身份、合约/产品、方向/信号/原信号时间、entry_context/risk_mode、原目标风险/单手风险/原止损、risk_ratio/risk_multiplier、overheat/30d 倍率、信号 limited_balance、原 min/max 风险、有效资本使用比、sizing_equity、单笔资本限额和已占用保证金。后续真实 open gap 风险由根任务依据此快照与实际报价重新核验，不能以新订单时间覆盖原信号预算。

## TDD 与验证

- 新增 `test_stage039_risk_budget_candidate.py`；初始 8 项 RED（缺实现），实现并修正真实 native 合成初始化后全部 GREEN；补充真实正式参数完整字段等价与 minimum-one 威胁覆盖后 **11/11 通过**。
- 大多数用例使用实际候选类的合成实例、`StrategyTemplate.__init__`、真实 native `_calculate_entry_sizing`、实际多空止损和 native `_open_position`，没有跑历史金融引擎。只有一项明确模拟“继承层强制最小一手”的返回值，用于证明外层 guard 确实能把 native selected=1 且超预算的结果压回 0。
- 覆盖：预算相等、超预算、非有限/非正/缺值；原生环境/单笔/簇/连败不复活；真实 formal 参数预算字段逐项不变；long tighter 与 short 止损不改；0 或超预算不能建层；快照不可修改、原 dict 修改不影响快照、快照 ID 唯一。
- 本线冻结后兼容验证：`MPLCONFIGDIR=/private/tmp/fian-stage039-mpl /Users/mac/Desktop/fian/.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_*.py'`。
- 结果：**113 tests，11.078 秒，全部通过**（包含根任务当时已保存的新测试）。`git diff --check` 通过。
- 模块 SHA256：`583da051b2be119e195ed9e0531bd4a5e3c4e3606b9825bc783768030bec57df`。
- 测试 SHA256：`6d2b2a5b628d283754583b2fd034b69d1d4b38653b7a1cd0ac7772cce77f5918`。

## 参数与结果记录、后续

- 修改：`fixed_size: 1 -> 0`，恢复 native 风险预算；保持 `max_position_size=1`，并发仍按已批准全市场产品自然容量。新增外层预算 fail-closed 代码与不可变信号预算证据，不增加阈值参数。
- 新增/修改/删除金融回测结果：均无；本阶段没有新的期末权益、收益、回撤、Sharpe、滑点、成交次数或胜率，不能把单元测试当绩效证据。
- TODO：根任务完成 Stage040/041 的原信号快照与实际 fill 绑定、开盘 gap 二次预算闸门、margin/cluster 当前持仓约束和不可变审计；金融回放后另请独立 agent 全面复核数据、结果、置信度和逻辑，再决定后续，不自行晋升。
- 开始与结束过拟合判断：**否**。这是用户预先给出的跨品种预算生存约束，没有对收益、窗口、品种或小数阈值寻优；旧正式策略的历史选择偏差仍存在。
- 开始与结束继续价值判断：**是**。固定一手并不等于等风险，恢复原预算能避免高波动或高乘数品种的一手风险超过原政策；是否改善收益/回撤必须由新冻结回放与独立审查回答，当前没有绩效结论。
