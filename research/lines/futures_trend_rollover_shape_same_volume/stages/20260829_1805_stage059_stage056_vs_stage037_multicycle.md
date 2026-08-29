# Stage059 Stage056 与 Stage037 多周期对比

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：用户明确指定的离线 Stage037 / Stage056 研究比较，不构成当前生产 A/C
- 记录时间：`2026-08-29 18:05 +08:00`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/stage056-ai-top14-plus-fu` / `codex/stage056-ai-top14-plus-fu`
- 阶段性质：冻结 AI 池宽度单变量的多周期稳健性验证
- 是否重要突破：待回测与独立评审
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

- 状态：运行前冻结；结果待填
- 期末权益：待填
- 总收益：待填
- 最大回撤：待填
- Sharpe：待填
- 总滑点：待填
- 总交易次数：待填
- 胜率：待填
- 其他关键指标：43个窗口、86个臂窗口；全周期复用并逐值校验，另外84个独立真引擎运行

## 输出文件

- report：`artifacts/stage059_stage056_vs_stage037_multicycle/stage059_multicycle_report.md`
- summary：`stage059_window_summary.csv`
- orders：无；订单/发单/撤单API必须为0
- daily：`stage059_equity_curves.csv` 与五张固定图片
- quality：`stage059_decision.json`、`stage059_window_comparison.csv`、`stage059_cycle_aggregate.csv`

## 结论

- 本阶段结论：待回测与独立review
- 是否进入下一步：待定；无论结果如何都不自动晋升或安装生产
- 下一步：跑完固定窗口，检查预声明门，拉独立reviewer复核

## 过拟合反思

- 运行前判断：中等，不是高。
- 运行后判断：待填。
- 原因：只验证一个已经冻结的Top14单点，没有TopN扫描；但假设是在看过Stage037/Stage056全周期表现后提出，仍有后验选择风险。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：待填。
- 原因：多起点冷启动能识别全周期复利路径是否掩盖了阶段不稳定；失败后继续扫参数则没有价值。

## 合入建议

- 是否更新本线 `LINE.md`：结果和review完成后决定
- 是否更新 `research/registry.md`：否，研究线未变
- 是否追加根目录 `memory.md/back_log.md`：仅在形成正式候选或重要突破时
