# Stage006 Stage013 权威权益对账修复 A/C

- 时间：`2026-07-10 20:57 CST`
- line_id：`futures_trend_stage013_current_ai_revalidation`
- 是否重要突破：待独立 review；本阶段先修复 Stage005 P0 账户状态语义，再重新评估冻结 Stage013。
- 当前决策：`stage006_continue_halfyear_if_independent_review_passes`
- 代码：`research/lines/futures_trend_stage013_current_ai_revalidation/tools/stage006_stage013_reconciled_equity_engine.py`
- 测试：`research/lines/futures_trend_stage013_current_ai_revalidation/tools/test_stage006_stage013_reconciled_equity_engine.py`
- 输出：`research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage006_stage013_reconciled_equity_engine/`

## 修复内容

- 新增策略参数：无。
- 修改策略参数：无；继续冻结当前 AI、C9、`30%/1个持仓/1手`、退出、0.5R 止损重试、broker10 和 forced-margin。
- 删除策略参数：无。
- 不修改官方 C9 基类和内部账；A 继续原 C9，C 仅让 Stage013 gate 读取隔离的权威权益。
- P0 根因恒等式：旧内部账在每次成交后比正式日结多计 `signed_volume * (今收-昨收) * 合约乘数`。
- Stage006 对每笔成交在线累计该重复项；在每日收盘决策前计算 `authoritative_equity = legacy_equity - cumulative_duplicate_pnl`，独立维护高水位和回撤。
- 当日成交由 next-real-open/Stage847 分钟止损重试在 `on_bars` 前完成；权威权益在当日收盘决策时读取当前 close，不引用未来日期。
- 旧 Stage013 plan 被显式绕过一次，再使用相同冻结 helper 只应用一次权威回撤 gate；基础 C9 其他账户逻辑仍与 A 相同。

## 测试过程

- 先写 3 个失败测试：开仓重复项、正式日结恒等式、开平仓符号。
- 最小 helper 实现后 `3/3 OK`。
- 2020 上半年 C-only 烟测：正式日线/权威审计 `117/117`，缺失/重复 `0/0`；权益最大误差 `5.82e-11`，回撤误差 `2.91e-16`；45 笔 correction 求和与累计值完全一致，未来交易引用 `0`。
- 完整回测后重新运行独立 pandas 复算，指标误差清单为空。

## 全周期结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 非零日胜率 | 逐笔胜率 | broker10峰值 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 当前 C9 | 5,996,631.00 | 3897.7540% | -55.3701% | 1.3967 | 759,970 | 641 | 52.8302% | 45.8716% | 88.3398% |
| C 权威权益 Stage013 | 4,826,685.80 | 3117.7905% | -40.0046% | 1.4057 | 537,010 | 641 | 52.5763% | 44.9541% | 88.3322% |

- 收益保留：`79.9894%`，通过 `>=70%`。
- 全周期最大回撤改善：`15.3655pp`，通过 `>=3pp`。
- 2022 最大回撤改善：`12.0107pp`，通过 `>=5pp`。
- 固定压力窗 `2022-07-15 -> 2024-05-10` 改善：`22.8197pp`，通过 `>=3pp`。
- broker10 变化：`-0.0076pp`，未恶化。

## 权益与事件语义

- 完整正式日线/权威审计：`1571/1571`；缺失日期 `0`，重复日期 `0`。
- 641 笔 correction 合计和最终累计均为 `-2,114,110`，误差 `0`；未来交易日期违规 `0`。
- 权威权益/高水位最大绝对误差均 `2.79e-9`；回撤最大误差 `7.22e-16`，通过 `1e-8` 门。
- Gate 共 `58` 次，减少计划手数 `4,176`；正式同日回撤范围 `30.0305%-39.9675%`。
- `official/authoritative drawdown <30%`、非 `flat_entry`、未 applied、错误 reason、非 opened、after 非 1、active 超限、事件权益不一致全部为 `0`。
- 首个 gate：`2022-01-11 CF.CZCE`，计划 `39 -> 1` 手；首个实际权益差异为下一交易日 `2022-01-12` 的 CF 开仓，因果顺序正确。

## AI 与 A 复现

- A 与 Stage001 A 持久化核心日线 canonical hash 完全一致。
- A/C eligibility 都来自当前官方 AI，`504` 行、`55` 个 eval_date、normalized hash 一致。
- AI usage：A/C blocked 都为 `326`，missing signal date 都为 `0`；A/C candidate `839/838`、allowed `513/512` 的 1 行差异出现在持仓路径分叉之后，不是 AI 文件变化。

## 产物与边界

- manifest `36` 个产物，逐文件 bytes/SHA256 错误 `0`。
- lineage 新增 Stage013 源码、基础组合策略、Stage847 引擎、vn.py backtesting、测试、AI、live override 文件和 metadata 各映射 hash。
- 历史行情数据库只经过引擎 sentinel 检查，没有完整内容 hash；lineage 明确保留该 residual risk。
- 本阶段仍是历史回测，不是 shadow 或实盘验收。

## 独立 agent 审查

- reviewer：`Lagrange / 019f4c66-d939-7b02-a499-8380af02558e`
- 结论：`P0=0/P1=0/P2=3`；数值置信度 `82%`、语义置信度 `94%`，允许仅进入逐半年研究，不代表实盘。
- reviewer 独立确认：修正公式与 vn.py 日结恒等；C 绕过旧 Stage013 override 后只调用一次冻结 gate helper，无双应用证据；1571 日、641 笔 correction、58 次事件和 A/C 核心指标与落盘一致。
- P2-1：原测试未显式覆盖首日、同日 synthetic、多笔成交。已补 3 个回归测试：首日 previous=current 时修正为 0、同日等量开平修正相消、多笔成交线性累加；总测试由 `3` 增至 `6`。
- P2-2：未来函数审计只精确到日期。同日日线 bar 时间戳不表达真实收盘时刻，不能伪造时钟级证明；当前源码调用顺序是 engine 先完成当日已知成交/分钟止损，再在日线 `on_bars` 收盘候选规划前计算权益，且跨日未来违规为 0。保留为研究适配器 residual risk。
- P2-3：C 的 AI selector/profile 元数据名与 A 不同。行为输入已通过 normalized eligibility hash、blocked rows 和 missing signal date 审计；逐半年继续要求 A/C eligibility 完全同核，不能把 profile 名差异解释成 alpha 差异。
- reviewer 中断残余：未逐行重算全部 1571 日/58 事件和 trades；主 agent 已用独立 pandas 完整复算这些指标，误差清单为空，但该补充不替代独立 reviewer 的置信度边界。

## 反思与下一步

- 运行后过拟合：否。修复由账本恒等式和 P0 决定，没有看收益选择公式、阈值、月份、品种或方向。
- 整体选择偏差：中等。Stage013 仍来自前序研究，单一起点通过不能替代逐半年和后续 OOS。
- 是否仍有价值：有。修复后仍保留约 80% 收益并显著改善回撤，说明原 Stage013 的价值不完全来自错误触发。
- 下一步：独立 review 已无 P0/P1；按原冻结规则重跑 13 个逐半年冷启动，每条路径都新增权威权益 reconciliation 和事件语义硬门。失败则关闭，不调整 `30%/1/1` 救参。
