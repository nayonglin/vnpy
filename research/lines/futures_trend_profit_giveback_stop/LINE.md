# futures_trend_profit_giveback_stop

- 中文名：期货趋势盈利回撤止盈研究线
- 资产/策略：商品期货趋势 / `78-1` (`official_stage78_1_defensive_50w_no_sizing_cap`)
- 研究定位：独立研究线，不修改 `78-1` 默认逻辑；仅评估“最大盈利回撤止盈（profit giveback stop）”是否具备跨周期收益-风险优势
- 当前状态：Stage001 启动（A vs C 单变量消融）

## 问题与假设

- 问题：趋势策略常见问题不是赚不到，而是大浮盈后的大回吐；盈利回撤止盈的目标是先确认“已经赚到足够多”，再在回吐时锁住一部分趋势利润。
- 假设：若只在“已有明显浮盈”后才启动，理论上它比过早分批止盈更不容易砍掉右尾，可能改善弱窗口回吐和风险路径。

## 当前研究边界

- 本次只验证“打开当前默认开关”：
  - `enable_profit_giveback_stop=True`
  - `profit_giveback_trigger_pct=0.08`
  - `profit_giveback_retain_ratio=0.70`
  - `profit_giveback_min_lock_pct=0.03`
- 不做阈值搜索，不复刻旧 `Stage128 best` 参数。
- 若默认开关都不稳健，则不继续做当前分支参数优化，避免过拟合。

## 历史上下文

- 旧仓库曾在更早 `Stage78` 口径下研究过 `profit_giveback_stop`（Stage128-132）。
- 但当前正式基准已切换到 `78-1`（`50w + no sizing cap + AI on`），因此旧结论只能作为“家族经验”，不能直接当成当前结论。

## A/B/C 设计

- A：`78-1` 基准（`enable_profit_giveback_stop=False`）
- C：`78-1 + giveback stop 默认开关`（显式 `True`，使用当前默认参数）
- B：不设（该模块脱离 `78-1` 信号逻辑不具备独立评估意义）

## 反过拟合约束

- 先做最小有效实验：主回测 + 多周期 + 滑点压力。
- 若 `C` 不能稳定优于 `A`，停止；不围绕 `trigger/retain/min_lock` 做阈值微调。

