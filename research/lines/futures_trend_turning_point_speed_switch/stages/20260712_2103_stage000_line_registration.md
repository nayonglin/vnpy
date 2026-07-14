# Stage000 转折点速度切换研究线注册

- line_id：`futures_trend_turning_point_speed_switch`
- 当前模式：`day`
- 记录时间：`2026-07-12 21:03 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：新研究线注册、跨线反证、外部调研；未运行回测
- 是否重要突破：否
- 是否触发A/B：否；Stage001 先只读归因

## 外部调研与判断

- `Momentum Turning Points` 将慢/快趋势信号的同向、correction、rebound、bear 状态分开，说明转折点是慢趋势的结构性弱点，动态速度选择与统一空仓不是同一机制。
- AEA 公开材料给出 slow/fast 状态组合的明确分解，但状态权重来自样本优化，不能直接复制到本地商品。
- `Trend-Following Strategies via Dynamic Momentum Learning` 支持在 turning point 动态组合速度，但其分类器自由度过高，本线不复制机器学习部分。
- `pysystemtrade` 支持多规则分层和 forecast diversification；同时提醒权重与相关性估计存在校准风险。本线不估计权重，只先做固定快慢状态的可见性审计。
- 我的判断：产品级 T-1 turning-state 是与候选缩手、账户暂停和固定快慢混合不同的结构；值得先做只读归因，但没有资格直接进入回测。

## 跨线反证

- 固定快/慢 MA 及 NAV 混合已由旧 Stage356 反证，不重跑。
- high-vol/account hard pause、cold-start ramp、reserve、Stage372 sleeve、MRC、同向质量卫星、carry/xsmom、期限结构和外生 veto 均已关闭，不在本线叠加。
- 只有“快信号在慢趋势转折点提供跨时期、严格 T-1 的新增信息”尚未被当前 C9 真路径直接验证。

## 参数与结果

- 新增研究参数：正式速度 `5/10/20/40`；快速度 `3/6/12/24`；均为既有固定整数周期。
- 修改参数：无。
- 删除参数：无。
- 期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率：N/A（未回测）。

## 结论

- 本阶段结论：创建独立研究线；Stage001 先做数据与因果可见性归因。
- 是否进入下一步：是，仅进入只读归因。
- 下一步：冻结 Stage001 统计门并独立审计数据/hook；未过门不得写真引擎。

## 过拟合反思

- 运行前判断：直接从 MRC 失败结果调参数会过拟合；新结构预注册不会。
- 运行后判断：否；尚未观察 turning-state 收益。
- 原因：周期来自正式规则与历史固定 fast 组，不按2022或新结果选择。

## 继续价值反思

- 运行前判断：有；总体目标仍需真正不同机制。
- 运行后判断：有，但仅限只读归因。
- 原因：若快信号不能跨时期识别转折，能在不消耗真引擎回测的情况下及时关闭路线。

## 合入建议

- 更新本线 `LINE.md`：已创建。
- 更新 `research/registry.md`：需要登记。
- 根目录 `memory.md/back_log.md`：暂不追加；尚无回测或路线结论。
