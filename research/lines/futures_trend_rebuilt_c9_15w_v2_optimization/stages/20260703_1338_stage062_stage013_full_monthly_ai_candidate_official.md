# Stage062 Stage013 full-monthly-AI candidate official

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T13:38:50
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：候选正式化输入验收；不是交易参数突破
- 是否触发A/B：是；Stage013 被用户指定为候选正式版，需要进入晋级验收，但本阶段不再比较旧正式版

## 外部调研与判断

- 参考 pysystemtrade / walk-forward / overfitting 资料。判断：不能因为曲线好就改训练门槛补早期月池；必须保持 PIT、训练窗口和标签可得性。
- 本次执行判断：补齐所有当前逻辑可生成的月池；不能生成的 2020-01 到 2021-03 明确标为 cold-start，不伪造独立月池。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage062_stage013_full_monthly_ai_candidate_official.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增线内 candidate AI 文件路径 override
- 修改参数：无正式交易参数修改
- 删除参数：无

## 回测参数

- 版本：Stage013 account-state pilot candidate official
- 起点：`2020-01` 到 `2026-01` 逐半年
- 终点：`2026-07-02`，实际终点见 summary
- 资金：`150,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_candidate_ai_eligibility_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`
- AI hash：`f7f9b2d54301e170573df75a5f717b962503f3b44904389d5dbdab0226f499f5`

## 结果

- 期末权益/总收益：逐起点详见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage062_stage013_full_monthly_ai_candidate_official/rebuilt_c9_v2_stage062_stage013_full_monthly_ai_candidate_official_stage013_summary_stage062_stage013_full_monthly_ai_candidate_official_v1.csv`
- 正收益：`10/14`
- 最小/中位/最大收益：`-19.8589% / 17.9047% / 1097.0739%`
- 最差/中位最大回撤：`-46.6622% / -30.3543%`
- 总滑点：`479880.0000`
- 总交易次数：`3382`
- 胜率：本阶段未逐笔重算，保留待 promotion shadow 验收补充
- AI 覆盖：expected `78`，generated `63`，cold-start `15`
- AI 应用审计：standard `{'PASS': 546, 'NO_CANDIDATE_MONTH': 14}`；freshness `{'FRESH_MONTHLY_POOL': 516, 'COLD_START_PRE_MODEL_POOL': 30, 'NO_CANDIDATE_MONTH': 14}`

## 结论

- 所有可由当前 Stage182 逻辑生成的月池已经补齐到线内候选 AI 文件。
- 2020-01 到 2021-03 不是文件缺失，而是训练样本不足导致的模型冷启动；若要这些月也独立月更，需要更早的 PIT 源数据或改变训练逻辑。
- 本阶段不改正式配置，下一步应做候选版 shadow/邮件/执行链路验收，再决定是否晋级正式。

## 过拟合反思

- 运行前：否。本阶段只补齐 PIT 月度输入并验证单一候选 Stage013，没有新增交易参数或按结果调阈值。
- 运行后：仍然否。若后续因为个别起点表现差去改月份、品种或训练门槛，才会转为过拟合风险。

## 继续价值反思

- 运行前：有。候选版要晋级正式，月度 AI 输入完整性是必要条件，比继续纠结旧正式版恢复更有价值。
- 运行后：有。补齐后可以用同一候选版做 shadow/执行验收；冷启动边界也已被显式记录。
