# Stage035：B_TS 已知触发价预算的最小只读风险合同建议

- line_id：`futures_trend_triple_screen`；2026-10-18 03:30 CST；独立复核者：`ordered_execution_review_independent`。
- 来源 HEAD：`ed41e3578aa4fd64606b481a74003f9855d1fad5`。已读 registry（仍未列本已存在研究线，不另建重复线）、Stage034 全文及末尾 u-known-trigger 追加、真实 qmt/804/830/planner/reserve 源码和 Stage031 实际参数；未读取收益明细选规则。
- 唯一新增此文件，不改 LINE、registry、源码、测试、金融产物或 C_TS fixed-q 合同；无金融、preflight、模型推断/训练、联网或旧 suite 重跑。
- 结论：**建议采用一套 B 专属事前合同：u 用已知 T 贯穿原 sizing/cap/model 数值输入；原 allocator 完整返回后，对已经 admitted 的 plan 只缩量执行一次最终硬预算钳制，再冻结 q/T/S。** 原分数/排序/已拒候选不重算，缩掉的预算和 slot 不回收分配。不是多个候选方案，也不关闭或调节 volume tilt。

## 调研、判断与实际代码事实

按 root 明确分工不做泛搜；沿 Stage034 已核 CMT/LEAN/Backtrader 的机制资料，判断依据是本地真实 producer/consumer。经典三重滤网不保证收益，本次只消除“在已知触发价下预算仍用旧 close”和“原排序后的 tilt 可突破前序限量”的合同歧义。

`qmt_roll_portfolio_strategy.py:5792` 的 `_calculate_entry_sizing` 没有 entry-estimate 参数，risk-budget 分支先按原 risk recipe 产生 `risk_amount`，随后用 close 与 S 算 `risk_per_contract`、`contracts_by_risk`，再算 margin、单笔资本、max position、cluster/heat/env 等限制。`830:94` 的 wrapper 之后按 `reserved_margin_before`、u 权益、`margin_per_contract` 和原 broker 参数限量。`qmt:4098` 的 candidate builder 随后还做 correlation/AI/供需等原逻辑，`4670` planner 算分、排序、slot，**`4704` 调用 volume tilt**。

tilt 的 `qmt:4637—4664` 直接 `round(base_volume * multiplier)`，写回 `sizing.selected_volume` 和 `plan.volume`，没有重验 `risk_amount/contracts_by_risk`、单笔 margin、830 或 cluster 上限。后面的 incremental gate 不等于这些最终硬限制：默认关闭；即使开启，也只管自身 margin budget，并可有 protected rank。不能把旧 `stage830_margin_cap_selected_volume_after` 或 `risk_cluster_selected_volume` 等前序快照称为最终 q 已过闸。

实际接受设置为 `fixed_size=0`、`min_position_size=1`、`max_position_size=500`、830 开启、broker multiplier=`1.65`、cap ratio=`1.0`、risk-cluster margin cap 开启、correlation gate 开启、long tilt strength=`0.15`、short=`0`。新增 B 仍用这些已接受参数及 class defaults，不新增数值阈值。`risk_amount` 取原 generic OI 模式、连败、已启用 directional boost 等完整 recipe 的最终值，不能自行换成一条新的固定风险百分比。

## 一个最小可核验合同

**第一处接合：原 sizing 算术之前。** 同意 Stage034 的研究专属 pricing 基类建议：实际 MRO 必须让 830 的 `super()` 进入这个方法，且 `_entry_stop_price` 仍经 804 long override/原 short 方法。显式传递或按 `(u,contract,direction)` 读取合法 T，只改局部 entry estimate 与风险/保证金算术；S 始终调用原真实 u bar/history。缺 T、非有限/非正的 T/rho/margin/权益或所需预算字段须 fail-closed，不回退 close，不修改 bar/history/signal 身份。保留原 generic filters、OI risk mode、AI 字节、模型算法、保护止损和持仓路径。实际 fixed_size=0，其他 fixed-size 模式不在本次资格范围。

定义 `rho_i=max(abs(T_i-S_i)*size_i, 原min_risk)`、`m_i=T_i*size_i*原margin_ratio_i`；上述字段从本方法贯穿 830、模型 margin/equity 特征和原 planner。模型分数可以随 T 的数值输入自然变化；“保持原排序算法”不等于必须复刻 close 版 rank 数值。不能先按 close 算分/过 cap，最后只换一列 T。

**第二处接合：B `_plan_flat_entry_candidates` 中 `super()` 完整返回之后、改成 conditional_pending/冻结 intent 之前。** 只处理此时 `candidate_status='opened'` 且 q>0 的原 admitted 集合 A；按原 allocator 的 `selection_pairwise_rank`/原稳定序逐个处理，不重新调用 planner/模型/tilt，不将 skipped/AI拒绝/不合格 plan 纳入。不改变 held/add/reverse/roll 或 C_TS。

对每个 i 先保存原返回量 `a_i=plan.volume=sizing.selected_volume` 与全部前序快照。为了严格不回收因钳制释放的资源，定义一次固定的 gross 前缀：`P_i=sum(a_j*m_j)`，j 为同一原 admitted 集合中排在 i 前的 plan；`P_i,c` 只累加相同 risk cluster。**前缀使用钳制前 a_j，不使用缩量后的 q_j，不因前项缩到0而补位。** 这是研究候选预算的保守记账，不建立 phantom position/order，也不把它记成真实持仓 margin。

令 R 为原 `sizing.risk_amount`，L 为原 `limited_balance`（已含基础 reserved margin 后的可用资本），K 为原 `single_trade_capital_limit`，E 为 **830 当时使用并须显式保存的 u 权益**，B 为原 `reserved_margin_before`，b/c 为原 830 multiplier/cap ratio。cluster 开启时 C/H 为原 `risk_cluster_cap_amount` / `risk_cluster_reserved_margin_before`。最终只允许：

```
n_risk   = floor(R / rho_i)
n_margin = floor(max(0, L - P_i) / m_i)
n_single = floor(K / m_i)
n_broker = floor(max(0, E*c/b - B - P_i) / m_i)    # 原830开启时
n_cluster= floor(max(0, C - H - P_i,c) / m_i)      # 原cluster cap开启时
q_i = max(0, min(a_i, n_risk, n_margin, n_single,
                原max_position_size, n_broker, n_cluster))
```

关闭的 gate 不增加对应约束，不借本设计打开开关。`contracts_by_risk` 必须已经等于按 T 算出的 `n_risk`；`contracts_by_margin`、`contracts_by_single_trade_cap` 也须与 T 字段一致，否则是 pricing 接合错误，不能用最终 min 静默掩盖。不能仅复用 830 的 `max_affordable_volume`：它在原 batch 前按基础 reserved margin 计算，不含当前其他 admitted plan；同理启用的 cluster cap 要扣同 cluster 的 gross 前缀。最终不得因 protected rank 放宽上述已声明硬上限。

原 correlation/heat/env/供需/AI 等逻辑继续按原先后顺序作用，最终仅裁剪其原 admitted a_i，不重新把这些权重乘第二遍，也不新增用它们挑参的门。这里承诺的是已启用硬风险/资本 cap，不能把原先先折扣后 tilt 的软权重描述成另一个未声明的硬比例。

若 `0<q_i<原min_position_size` 则设0，不能向上补手数；q=0 的 admitted intent 取消并记录 `b_ts_final_budget_zero`，不得消费 setup、发单或补候选。`plan.volume` 与 `sizing.selected_volume` 必须同时写最终 q，避免一侧为0另一侧用 `or` 取旧量。其余候选的 q 永远不超过原 a_i。

冻结最终 q/T/S/原rank、rho/margin 及预算快照。仍在原产品 snapshot 循环的位置调用一次 `_reserve_intrabar_entry`（`qmt:3373`），它消费最终 q 与 T 的 `margin_per_contract`；不要在 planner 内提前真实 reserve，也不要 reserve 两次。gross 前缀只防同批 intent 回收，不应伪造实际 margin。现有持仓/add 的产品循环顺序和原规则继续保留；本合同不把被缩掉资源再分给另一个 B 初始 intent，D 也不重分配。

这是 B 收益前**新增的最终一致性约束**，使用原阈值，但不能称为 A/C 原算法本已保证的性质。R 仍是每候选原 recipe 的预算；没有因此创建一个新的“全组合 stop-risk 总和上限”。如需组合总风险政策，那是另一项研究，不在此最小合同里增加。

建议新研究 helper 名称为 `_b_finalize_admitted_budget(plans)`（这是待实现的新 helper，仓库没有可直接调用的同名方法），由 B planner 的 `super()` 返回后只调用一次，返回最终 plans/审计，不触碰 machine 或真实 reserve。原字段精确映射：`risk_amount`/`risk_per_contract`/`margin_per_contract`/`limited_balance`/`single_trade_capital_limit`/`reserved_margin_before`；broker 用 `stage830_broker10_margin_cap_enabled`、`stage830_broker10_margin_cap_ratio`、`stage830_broker_margin_multiplier`；cluster 用 `risk_cluster_cap_enabled`、`risk_cluster_name`、`risk_cluster_cap_amount`、`risk_cluster_reserved_margin_before`。`min_position_size/max_position_size` 从 u 原参数冻结，不能取 D。

830 当前没有单独返回其 E，因此须在 B 的外层 sizing wrapper 用与 830 **完全相同**的 fallback 表达式保存 `b_ts_budget_equity_u = float(self.estimated_equity or sizing.get('sizing_equity') or self.base_capital or 0)`，且确认该方法内没有账户状态变化；不能拿 margin ratio 或 projected ratio 反推 E。T 已在更内层 sizing 正确使用，外层只补快照。最终新增字段建议统一前缀 `b_ts_final_budget_*`：`volume_before/after`、`gross_margin_before/gross_cluster_margin_before`、`contracts_by_risk/margin/single/broker/cluster`、`reason`、`predicted_risk_T/predicted_margin_T`；原 cap 快照仍保留。q=0 显式记录非 opened 状态及 `b_ts_final_budget_zero`，不改变原 native_openable/score/rank 供重新选择，也不补任何候选。

## 最少证据字段与 T / 实际 fill 的区别

保留前序 sizing/830/cluster/tilt 快照，注明其阶段；追加一个明确 B-final audit，至少包含 u/arm/contract/direction/T/S、size/tick/margin_ratio、R/rho/m、a/q、原rank、gross P 与同cluster P、上述各整数上限、原 E/B/L/K/cluster budget、缩量原因以及 `predicted_risk_T=q*rho`、`predicted_margin_T=q*m`。不能覆盖原830快照后假称原 wrapper 已按最终 q 再运行。新字段应进入冻结 plan、决策审计和运行 provenance，不只留在最终成交诊断；原 `_sync_entry_risk_diagnostic` 会用实际 fill 更新部分风险/保证金字段，不能因此丢失 T 预测。

T 在 u 已知，D 的首突破分钟/gap/不利 tick 才决定 F。非gap且有效 tick 兼容时 F 可等于 T；否则实际 `rho_F`、margin_F 可以更大。最终 q 仍冻结，不用 D 最终 OHLC/权益/映射再缩量或重分配；原 0.5R/retry 根据实际 fill 与冻结 S 计算。T 估价解决已知门槛与预算域不一致，**不保证实际 fill 风险/保证金不越界**；实际与预测差异、七门和资金存活仍须完整报告。保持原成本，不能把 price-stop R 宣称为含所有费用与尾部跳空的最大现金损失。

## 四个必要而尚未执行的反例

1. u.close=100、low=99、high=110、T=111、size=10：long S 仍为 `max(99,98)=99`，rho_T=120，不能仍用 close 风险10；R=1200 时 n_risk=10。改变 T 不改 S/bar/history/信号日；对应 short 方向镜像。无合法 T 的 B flat entry 拒绝，held/非B仍走原路径。
2. 同一计划原风险上限10手，tilt 10→12；最终最多10。另一个相同输入只让原 broker/cluster/单笔 margin 上限成为8，最终最多8；rank/score 与原 admitted 集合不变，不把旧830的前序 after 字段当最终通过证明。
3. 合成 u 预算 E=100000、b=1.65、c=1、B=0、m=15000，三个不同 cluster 各原 admitted 2手，原每 cluster cap 可容30000：前两项各2，第三项 broker gross 前缀60000后不足1手而归0。第一项若另因风险缩为1，第三项仍不回收该15000，skipped候补也不能补位。所有数值只是 fixture 算术，不是新增策略参数。
4. T=111、S=99、size=10，D gap 真实 fill=130：同一冻结 q 不变，实际 rho=310，高于 T 预测120，审计必须显式披露；毒化 D 最终H/L/C/账户不能改变 u 的 q/T/S。未触发无订单/费用，setup 不因最终预算裁剪或未触发被当作成交消费。

以上只是一套合同的有限必要反例，**尚未写测试或运行**，不能报告已GREEN或有B收益。后续只需真实 MRO/算术/最终 plan/reserve 的少量组合 hook 证据，之后按最终合同做一次 B；不扩出一组预算候选选赢家。

## 结论与记录

旧 C_TS fixed-q、Stage031/033 已接受的负结果及所有历史失败证据保持原样，不能用本合同重跑 C 救参。B 本来尚无代码/收益，其预算选择须由 root 在首个 B 收益前明确冻结。建议如上单一 min-clamp 方案；若不实现最终钳制，只能称原 tilt 继续具有上调权限，不能同时声称“最终 q 硬满足原风险金额/830 cap”。

是否重要突破：否。新增/修改/删除正式参数与金融结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。金融回放0、模型训练0、联网0、真实订单API0、production_qualified=false。

开始/结束过拟合判断：**否**，本次不根据 C 的亏损幅度选倍率/缓冲/品种，不新增数值门槛，只让 B 首次实验的已知 T 与原预算整数算术一致；既有选择偏差仍存在。开始/结束继续价值：**是**，B 尚无独立账户证据，先消除预算与预留歧义能让一次后续固定实验可解释。本文件不授权金融启动、不声称总目标完成。
