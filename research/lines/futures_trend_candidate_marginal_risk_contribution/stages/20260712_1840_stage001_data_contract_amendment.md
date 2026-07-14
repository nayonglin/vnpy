# Stage001 数据合同审查修订：改用 actual-contract returns

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 记录时间：`2026-07-12 18:40 CST`
- 阶段性质：回测前独立 explorer 审查导致的数据合同修订
- 是否运行回测：否

## 独立审查发现

- explorer `Gauss` 证明 Stage020 产品集合为旧18+jd，和 current-AI 19产品不一致；并且 Stage020 把换月日收益写成0，不适合协方差。
- explorer 同时指出，本地 `TqContCalendar` 历史主力表只有当前字节快照，没有逐日发布版本，规则上PIT但本地证据无法严格闭合。
- explorer `Plato` 确认最安全 hook 是 Stage847 子类在 `super()._plan_flat_entry_candidates()` 返回后做batch缩手；baseline 自身存在固定顺序消费，但MRC计算可单独做到排列不变。

## 修订

- 撤销“用主力连续产品收益做MRC输入”；主力映射仍属于A baseline identity，但不再进入新风险特征。
- 改为当日真实持仓合约和计划开仓合约各自的严格 T-1 日线收益。每个暴露直接使用 actual `contract_vt_symbol`，不拼接历史主力，不跨合约计算收益，不存在换月零填充。
- 日线固定来自只读 `.vntrader/database.db`；数据库缺失的 `fu2005/fu2009/fu2605` 继续用三份固定 Stage462 分钟文件聚合日盘最后close。
- 独立复算 current-C9 2020锚点 `265` 个真实 would-open batch：actual-contract共同63日覆盖 `264/265`；唯一失败仍为 `2021-04-09 lh2109.DCE`，只有 `58` 个共同有效日，按原预声明整批 unavailable/no-op。
- 候选方向、整数手数、价格、乘数和T-1合约价格缺失均为0；现有持仓方向必须取 `current_pos` 正负号，不取 planner 后才 reconcile 的 state.direction。

## 判断

- 这不是收益后调参：尚未运行任何Stage001回测，修订来自PIT证据审查，且降低了自由度与映射风险。
- 当前过拟合判断：否。
- 继续价值：有；actual-contract输入解决主力映射历史版本问题，且264/265 batch具备精确63共同日。

