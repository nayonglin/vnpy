# Stage056 Stage037 AI Top14非fu+固定fu 全周期A/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：用户指定master m0016 Stage037离线研究对比；六身份不一致，结果不构成合规正式基线A/C
- 记录时间：`2026-08-29 17:25 +08:00`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/stage056-ai-top14-plus-fu` / `codex/stage056-ai-top14-plus-fu`
- 阶段性质：基于正式 Stage037 的单变量AI池宽度实验
- 是否重要突破：否；收益提高，但回撤、Sharpe、broker10与成本同时恶化
- 是否触发A/B：原计划是；独立review发现生产仍为Stage021-Q后，降级为非合规离线A/C诊断。A为master m0016 Stage037 Top8非fu+fu，C为Top14非fu+fu

## 外部调研与判断

- 参考资料：DeMiguel、Garlappi、Uppal《Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?》（NBER）；更宽的横截面可能提高分散度，但估计误差和权重/容量约束会让“更多品种”并不自动等于更优组合。
- 我的判断：本次只冻结 `Top14` 一个点，不扫描Top10/12/16/18，能回答容量和横截面扩展是否有真实效果；不能把单次全周期更高收益当作最优TopN或可晋升证据。

## 本次变更

- 新增脚本：`qmt_roll_candidate_stage056_stage037_ai_top14_plus_fu_config.py`；`stage056_stage037_ai_top14_plus_fu_ac.py`；`test_stage056_stage037_ai_top14_plus_fu.py`
- 修改脚本：无正式策略源码修改；Stage037 alpha、风险、换月、出场和资金参数均不变
- 删除脚本：无
- 新增参数：`MODEL_NON_FU_COUNT=14`、`TOTAL_PRODUCT_COUNT=15`、`FU_PRODUCT=fu.SHFE`
- 修改参数：AI池由每月Top8非fu+固定fu改为Top14非fu+固定fu
- 删除参数：无
- AI物料：保存完整候选 eligibility、每月成员审计、全18品种评分/排名审计及上游文件SHA256
- 历史缺口：`2026-03/04/05` 正式历史仅保存Top8成员，没有原始9–14名分数；采用 `membership_locked_score_fill`，锁住当时正式Top8，再用同模型时点重放排名补6个，并显式标注来源

## 回测/归因参数

- 数据区间：`2018-01-01` 至 `2026-08-28`，首交易日 `2018-01-02`，共2101交易日
- 账户规模：`150,000 CNY`
- 成本口径：真实引擎原口径，risk multiplier `0.4`
- 样本过滤：2019-12-31 的 `static18_pre_ai_boundary` 原样保留；2022-01以后按月点时选择
- 策略/归因口径：A/C唯一override差异为 `ai_product_pool_eligibility_path` 和 `ai_product_pool_strategy`；策略行为差异只有池成员宽度
- 数据绑定：日K数据库截至 `2026-08-28`；主力映射与Stage861完整15分钟数据均按SHA256固化

## 结果

### A master m0016 Stage037离线基线 Top8非fu+fu

- 期末权益：`16,859,940.60`
- 总收益：`11,139.9604%`
- 最大回撤：`-39.9147%`
- Sharpe：`1.538821`
- 总滑点：`1,659,555`
- 总交易次数：`734`
- 胜率：非零交易日胜率 `53.2310%`
- 其他关键指标：broker10峰值 `93.5807%`，超过100% `0` 天

### C Stage037 Top14非fu+fu

- 期末权益：`19,095,929.80`
- 总收益：`12,630.6199%`
- 最大回撤：`-44.7340%`
- Sharpe：`1.500060`
- 总滑点：`2,577,090`
- 总交易次数：`920`
- 胜率：非零交易日胜率 `53.4286%`
- 其他关键指标：broker10峰值 `111.8003%`，超过100% `2` 天，DD40失败

### C相对A

- 期末权益：`+2,235,989.20`
- 总收益：`+1,490.6595pp`
- 最大回撤：恶化 `4.8193pp`
- Sharpe：`-0.038761`
- 总滑点：`+917,535`，为A的约 `155.29%`
- 总交易次数：`+186`
- 非零交易日胜率：`+0.1976pp`
- broker10峰值：恶化 `18.2196pp`，新增2天超过100%

## 输出文件

- report：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage056_stage037_ai_top14_plus_fu/stage056_report.md`
- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage056_stage037_ai_top14_plus_fu/stage056_summary.csv`
- orders：无；订单/发单/撤单API均为0
- daily：`stage056_equity_curve.csv` 与 `stage056_equity_ac.png`
- quality：`stage056_decision.json`、`stage056_membership_audit.csv`、`stage056_full_ranking_audit.csv`、`stage056_candidate_eligibility.csv`
- 复验身份：decision同时保存日K数据库SHA/最新日、Stage183两源SHA、主力映射SHA、15分钟数据SHA；数据库最新日为`2026-08-28`

## 结论

- 本阶段结论：数值上候选产生真实收益效果，但回撤、Sharpe、成本和broker容量四个方向均比master Stage037基线更差；并且稳定生产 `09aa96a/m0015/Stage021-Q` 与master `a7d8599/m0016/Stage037` 不一致，本次不能作为合规正式基线A/C；`protocol_invalid_production_identity_drift_keep_offline_diagnostic_only_do_not_promote`
- 是否进入下一步：不直接晋升；若用户仍关注该方向，下一步应做固定Top14的多周期/容量约束验证，而不是继续扫描TopN
- 下一步：保留研究产物；不修改正式Stage037、正式AI池、master、生产或CTP

## 运行异常与处理

- 第一次在A计算前因稀疏工作区缺主力映射文件失败关闭；第二次在A计算前因缺Stage861分钟数据入口失败关闭，均未生成半成品结论。
- 将隔离工作区数据入口绑定至主工作区同一份只读数据目录，并增加关键输入存在性与SHA检查后，A/C完整成功。
- 首次成功结果后仅增强报告字段、评分审计和风险gate，策略/候选池/数据不变；机械重跑数值逐值一致。
- 独立review先关闭风险结论P1，再发现身份P0；runner已补严格六身份前置，当前生产漂移下未来运行会在候选池和A臂计算前停止。P2复验缺口已补数据库与Stage183两源SHA；发布测试已增加真实m0016 Top8逐月交叉验证。
- 最终独立review：`P0/P1/P2/P3=0/0/0/0`；接受口径仅为“master m0016 Stage037离线诊断、协议无效于正式A/C、不可晋升”。

## 过拟合反思

- 运行前判断：中等；Top14是用户指定的单点，但属于看过既有Top8表现后的后验扩容想法。
- 运行后判断：仍为中等，不上调为高；本阶段没有扫描多个TopN，且A/C唯一变量合同通过，但只有一个全周期起点，收益差仍可能由少数新增品种复利路径主导。
- 原因：更高期末权益伴随更差回撤、Sharpe和容量，说明它主要增加风险暴露，尚不能证明穿越周期的新增alpha。

## 继续价值反思

- 运行前判断：有；能隔离检验选品池宽度与组合容量。
- 运行后判断：有诊断价值，但没有直接晋升价值。
- 原因：结果明确证明Top14带来真实交易与收益变化，也明确暴露broker100和DD40失败；继续价值只在固定口径多周期/容量审计，不在继续调TopN救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加Stage056结论
- 是否更新 `research/registry.md`：否，研究线未变
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段不是正式候选或重要突破
