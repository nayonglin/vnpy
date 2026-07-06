# Stage061 Stage013 frozen-AI promotion A/C

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-03T12:29:16
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 是否重要突破：否；Stage013 进入下一层验证，但不直接晋升正式版
- 是否触发A/B：是；A=Official C9/15w Stage847，C=Stage013 account-state pilot

## 外部调研与判断

- 参考：Bailey/PBO、pysystemtrade 和 walk-forward validation。结论是不能从多候选里挑最优曲线直接上线，必须先锁候选、锁输入、再做 A/C。
- 我的判断：Stage013 是账户状态风控层，结构上比 Stage010/014 proxy 更适合作为 formal candidate；但当前还只能进入 shadow/执行验证。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage061_stage013_frozen_ai_promotion_ab.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无交易参数；新增研究进程内 frozen AI path override
- 修改参数：无正式参数修改
- 删除参数：无

## 回测参数

- A：Official C9/15w Stage847
- C：Stage013 account-state pilot
- 起点：`2018-01` 到 `2026-01` 逐半年
- 终点：`2026-06-30`
- 资金：`150,000`
- AI 池：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage061_stage013_frozen_ai_promotion_ab/rebuilt_c9_v2_stage061_stage013_frozen_ai_promotion_ab_frozen_ai_eligibility_stage061_stage013_frozen_ai_promotion_ab_v1.csv`
- AI hash：`8f54218d5c1922ebd4e0a2a16ef6d80c4f4392d1aa6c8cddd3f6127ffca574e3`

## 结果

- 期末权益/总收益：详见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage061_stage013_frozen_ai_promotion_ab/rebuilt_c9_v2_stage061_stage013_frozen_ai_promotion_ab_pair_summary_stage061_stage013_frozen_ai_promotion_ab_v1.csv`
- Stage013 正收益：`17/17`
- Stage013 收益胜正式：`14/17`
- Stage013 回撤改善：`14/17`
- Stage013 最小/中位收益：`1.9011% / 238.3687%`
- Stage013 最差最大回撤：`-43.7940%`
- 总滑点/总交易次数：详见 A/C summary 文件；本阶段未重新逐笔计算胜率
- AI 审计：official `{'PASS': 858, 'PRE_AI_HISTORY': 60}`；Stage013 `{'PASS': 858, 'PRE_AI_HISTORY': 60}`

## 结论

- 本阶段结论：Stage013 可以作为唯一 formal candidate 继续验证；不建议今天直接替换正式版。
- 下一步：用同一 frozen AI 跑 latest shadow / 当前持仓对账 / 执行链路 dry-run，再由用户显式确认是否 staged promotion。

## 过拟合反思

- 运行前：有选择偏差风险，因为研究线已经看过多条候选；本阶段只锁定一个结构候选 Stage013，并先冻结 AI 输入。
- 运行后：未新增调参。若失败后继续按输的起点改日期、品种、阈值，就是过拟合；当前只允许进入下一层执行验证。

## 继续价值反思

- 运行前：有。Stage013 是账户状态层，不是新增预测因子，具备穿越周期的结构理由。
- 运行后：有，但价值在于进入更严格 shadow/执行验证，不是今天直接替换正式版。
