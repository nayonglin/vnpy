# Stage000 Lag-1 Granger 动量溢出外部假设审计

- line_id：`futures_trend_lag1_granger_spillover_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-13 00:26 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：外部资料、GitHub 与仓库去重审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：arXiv:2501.07135、arXiv:2308.11294、2026 commodity Granger-causality network 论文、statsmodels 0.14.6 官方文档与 GitHub 实现。
- 我的判断：跨商品 momentum spillover 是仓库尚未等价测试的结构性信息源；它可能补充单品种趋势，而不是缩掉原仓。但完整 NMM 的 DTW/图优化和样本内 Sharpe 网格自由度过高，当前不应复制。先用固定 lag-1、132日、global BH-FDR 与半窗同号做无收益资格审计；失败即关闭透明子路线。
- GitHub 结论：没有找到两篇 NMM 论文作者可直接复用的官方策略仓库；statsmodels 的 Granger 与 multitest 实现可复用，避免手写统计检验。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无正式参数；仅冻结待实现研究口径。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：计划覆盖 Stage131 事件所需的严格 T-1 历史，事件 `2018-01-15 -> 2026-04-30`。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：Stage131 全365事件、full-market eligible57；不按收益筛选。
- 策略/归因口径：只做 lag-1 Granger network qualification，不构造交易信号。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：`0`。
- 胜率：不适用。
- 其他关键指标：仓库 `rg` 未发现 `network momentum/lead-lag/spillover` 既有实现；本地 `statsmodels=0.14.6` 可用，`cvxpy/tslearn/dtaidistance/fastdtw` 不可用。

## 输出文件

- report：本 stage 记录。
- summary：`LINE.md`。
- orders：不适用。
- daily：不适用。
- quality：不适用。

## 结论

- 本阶段结论：注册新线，只允许最小透明资格门；拒绝直接移植复杂 NMM。
- 是否进入下一步：是，进入 Stage001 预声明与实现。
- 下一步：按固定合同实现 TDD 和无收益审计，结果后不救参。

## 过拟合反思

- 运行前判断：完整 NMM 有高过拟合风险；透明资格审计风险低。
- 运行后判断：尚未运行数据或收益，不构成结果后过拟合。
- 原因：参数来自论文/标准统计口径并在看结果前冻结，且不读取策略 PnL。

## 继续价值反思

- 运行前判断：有，但必须先过数据与稳定性门。
- 运行后判断：有资格进入一次 Stage001；不代表值得回测。
- 原因：这是当前少数未被仓库历史等价反证、又不依赖新增付费数据的结构性信息源。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是，登记新线与当前限制。
- 是否追加根目录 `memory.md/back_log.md`：否；尚无结果或重要突破。
