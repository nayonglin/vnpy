# Stage001 当前重建版 C9/15w 二期优化线立线

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-02 02:32 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：研究线初始化
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu：The Probability of Backtest Overfitting，PBO/CSCV 框架。
  - Hurst、Ooi、Pedersen：Demystifying Managed Futures，趋势跟随长期价值来自分散化和右尾捕获。
  - pysystemtrade / Rob Carver：capital correction，账户资金暴露调整必须和真实资金路径一致。
- 我的判断：
  - 新线必须先隔离恢复法证和后续优化，避免把“删除后重建是否可信”和“新优化是否有效”混在一个总账里。
  - 当前优化的最大风险不是想法不够多，而是多次回测后的 winner-picking；因此每个候选必须先写假设，再冻结验证口径。
  - 趋势策略的核心不是单次信号命中率，而是跨周期右尾；防守优化不能通过压掉恢复段右尾来换局部平滑。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增记录：
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/LINE.md`
  - `research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/stages/20260702_0232_stage001_line_initialization.md`
  - `research/registry.md` 新增本研究线登记。

## 回测/归因参数

- 数据区间：本阶段未回测。
- 账户规模：本阶段未回测。
- 成本口径：本阶段未回测。
- 样本过滤：本阶段未回测。
- 策略/归因口径：以当前功能性重建 C9/15w 为后续母本，Stage167 为主基准，上游恢复线 Stage001-081 为只读参考。

## 结果

- 期末权益：本阶段未回测。
- 总收益：本阶段未回测。
- 最大回撤：本阶段未回测。
- Sharpe：本阶段未回测。
- 总滑点：本阶段未回测。
- 总交易次数：本阶段未回测。
- 胜率：本阶段未回测。
- 其他关键指标：完成独立研究线初始化。

## 输出文件

- report：无。
- summary：无。
- orders：无。
- daily：无。
- quality：无。

## 结论

- 本阶段结论：已将“当前重建版继续优化”从上游恢复/法证总账中拆出为独立研究线。
- 是否进入下一步：是。
- 下一步：先做目标几何与路径缺口审计，明确离“任意起点、周期大于一年正收益、收益保留80%+”差在哪些路径段，再决定优化方向。

## 过拟合反思

- 运行前判断：不涉及回测和参数选择，当前步骤本身不过拟合。
- 运行后判断：不过拟合。
- 原因：本阶段只做研究线隔离、基准声明和验证纪律声明，没有根据历史窗口调规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：旧恢复线已经包含大量恢复、法证和失败路线，继续在同一线追加优化会降低可读性；新线能把后续优化的假设、证据和失败经验独立沉淀。

## 合入建议

- 是否更新本线 `LINE.md`：是，已新增。
- 是否更新 `research/registry.md`：是，已新增本线。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是立线，不是重要突破、正式候选或路线废弃。

