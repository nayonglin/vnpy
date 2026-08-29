# Stage059 Stage056 与 Stage037 多周期对比

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：用户明确指定的离线 Stage037 / Stage056 研究比较，不构成当前生产 A/C
- 记录时间：`2026-08-29 18:05 +08:00`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/stage056-ai-top14-plus-fu` / `codex/stage056-ai-top14-plus-fu`
- 阶段性质：冻结 AI 池宽度单变量的多周期稳健性验证
- 是否重要突破：否；Stage056收益优势不能通过回撤、Sharpe、成本与容量稳健性门
- 是否触发A/B：研究 A/C；生产身份不一致，因此不可自动晋升

## 外部调研与判断

- 参考资料：沿用 Stage056 已记录的 DeMiguel、Garlappi、Uppal 关于更宽分散与估计误差/容量约束并存的研究结论；本次不新增 TopN 参数搜索。
- 我的判断：只比较已经冻结的 Top8+fu 与 Top14+fu，跨多个独立起点检验收益优势是否稳定；如果失败，不按个别窗口调整阈值。

## 本次变更

- 新增脚本：`stage059_stage056_vs_stage037_multicycle.py`、`test_stage059_stage056_vs_stage037_multicycle.py`
- 修改脚本：无正式策略源码修改
- 删除脚本：无
- 新增参数：1/2/3年窗口；1月和6月独立冷启动；固定五图输出
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-08-28`
- 账户规模：每个窗口 `150,000 CNY` 空仓独立启动
- 成本口径：Stage037/Stage056 原真实引擎成本口径
- 样本过滤：只保留完整 1/2/3 年窗口；分别统计 combined、January、June
- 策略/归因口径：A=Stage037 m0016 Top8+fu；C=Stage056 Stage037逻辑 Top14+fu；唯一变量为AI池路径和策略名

## 结果

- 状态：成功；43个窗口、86个臂窗口完整，Stage056全周期复用并逐值校验，另外84个独立真引擎运行，检查点生成84、复用0
- A Stage037期末权益：`16,859,940.60`；C Stage056期末权益：`19,095,929.80`
- A Stage037总收益：`11,139.9604%`；C Stage056总收益：`12,630.6199%`
- A Stage037最大回撤：`-39.9147%`；C Stage056最大回撤：`-44.7340%`
- A Stage037 Sharpe：`1.538821`；C Stage056 Sharpe：`1.500060`
- A Stage037总滑点：`1,659,555`；C Stage056总滑点：`2,577,090`
- A Stage037总交易次数：`734`；C Stage056总交易次数：`920`
- A Stage037胜率：非零交易日 `53.2310%`；C Stage056胜率：非零交易日 `53.4286%`
- 全周期其他关键指标：C相对A收益 `+1,490.6595pp`，回撤恶化 `4.8193pp`，Sharpe下降 `0.038761`，滑点比 `155.29%`；broker10峰值由 `93.5807%` 升至 `111.8003%`，新增 `2` 天超过100%
- 1年combined：16窗；预声明 `C>=A` 比例 `62.50%`，收益差中位 `0.0000pp`，DD非劣率 `62.50%`，Sharpe非劣率 `56.25%`，滑点比 `119.11%`
- 2年combined：14窗；预声明 `C>=A` 比例 `78.57%`，收益差中位 `0.0000pp`，DD非劣率 `57.14%`，Sharpe非劣率 `78.57%`，滑点比 `117.11%`
- 3年combined：12窗；预声明 `C>=A` 比例 `58.33%`，收益差中位 `0.0000pp`，DD非劣率 `50.00%`，Sharpe非劣率 `58.33%`，滑点比 `116.26%`
- 解释性严格口径：AI池实际产生差异的窗口每个周期均为9个；严格正收益胜率分别为1年 `3/9=33.33%`、2年 `6/9=66.67%`、3年 `4/9=44.44%`。预声明gate使用 `>=`，会把零差窗口计为胜，故不能单看名义胜率

## 输出文件

- report：`artifacts/stage059_stage056_vs_stage037_multicycle/stage059_multicycle_report.md`
- summary：`stage059_window_summary.csv`
- orders：无；订单/发单/撤单API必须为0
- daily：`stage059_equity_curves.csv` 与五张固定图片
- quality：`stage059_decision.json`、`stage059_window_comparison.csv`、`stage059_cycle_aggregate.csv`
- 单一复现入口：`PYTHONPATH=$PWD .py311/bin/python research/lines/futures_trend_rollover_shape_same_volume/tools/stage059_run_and_publish.py`；固定先跑真引擎/检查点，再执行 `stage059_multicycle_review_annotation.py`，补充严格胜率、OFFLINE标签和review注释，不改变策略结果或冻结gate

## 结论

- 本阶段结论：`offline_research_multicycle_has_hard_fail_keep_stage037`。Stage056在全周期有更高期末权益，但所有1/2/3年及January/June聚合组都至少有硬失败；主要失败项是DD非劣率、Sharpe非劣率和滑点比，3年还新增DD50与broker100失败
- 是否进入下一步：不晋升Stage056；保留Stage037。该结论仅是离线研究比较，当前稳定生产仍是Stage021-Q/m0015，生产身份问题不在本阶段处理
- 下一步：不扫描TopN救参；如继续研究，只做新增六品种的收益/回撤/保证金归因或先引入组合级容量约束，再作为新假设另起冻结阶段

## 独立评审

- 最终结论：通过，`P0/P1/P2/P3=0/0/0/0`
- 复算范围：43窗/86臂、Stage056全周期逐值身份、84个checkpoint合约与SHA、comparison/aggregate/gate、五图OFFLINE标签、严格胜率、单一复现入口及生产安全边界
- 关键确认：78/84条滚动路径与全周期切片不同；其余6条均为2018-01同一冷启动，路径一致符合预期。生产目录干净，订单/发单/撤单API为0，CTP未连接
- reviewer接受边界：仅可作为“离线诊断、不可晋升”的研究产物；Stage056多周期硬失败，保留Stage037

## 过拟合反思

- 运行前判断：中等，不是高。
- 运行后判断：仍为中等；本次多周期本身没有新增过拟合，但Stage056不应因全周期收益更高而被保留为候选。
- 原因：只验证一个已经冻结的Top14单点，没有TopN扫描；多周期暴露了全周期复利路径掩盖的回撤、Sharpe、成本与容量不稳定。若据失败窗口继续调TopN，过拟合风险会升高。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：本次验证有价值；继续扫描TopN没有价值，做风险来源归因仍有有限价值。
- 原因：多起点冷启动已经识别出全周期更高收益并不穿越回撤、Sharpe、成本和容量门，核心问题不是缺少一个更好的TopN数字。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录Stage056多周期硬失败并保留Stage037
- 是否更新 `research/registry.md`：否，研究线未变
- 是否追加根目录 `memory.md/back_log.md`：仅在形成正式候选或重要突破时
