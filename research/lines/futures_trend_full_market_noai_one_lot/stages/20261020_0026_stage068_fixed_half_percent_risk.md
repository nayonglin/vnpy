# Stage068：总权益固定0.5%风险预算与多手授权

- 时间：2026-10-20 00:26 CST。
- line_id：`futures_trend_full_market_noai_one_lot`。
- 工作树：`/Users/mac/.codex/worktrees/full-market-noai-one-lot/fian`，分支`codex/full-market-noai-one-lot`。
- 性质：用户固定资金治理口径的新实现与纯合成验证，不是重要突破，不运行金融回放。
- 本阶段仅新增068模块、068测试和本唯一stage；不修改旧模块、LINE、registry、Git、金融源/旧产物或其他研究线。根任务独立负责069账本、070runner和075周门；独立审查agent负责074部分平仓队列适配。

## 用户已确认合同

用户选择上一轮当前真实交易合约自身周线N版（`e553d1703`，`outputs/run_20261019_contract_weekly_long_v1`）为本轮研究基线，取消每品种最多1手。用户已纠正初始笔误：**每笔风险预算是当时账户总权益×0.005，即0.5%，100万元对应5000元**；不是0.05%。本阶段实现直接用0.005，没有运行过0.0005金融版本。

多空采用同一风险公式，整手向下取整、不足1手不开；不加仓、无4品种上限。开多仍受exact traded-contract周MA5>MA10>MA20>MA40及原信号/开盘两相位证据约束，空头不加周门。保留原native保证金、环境、相关性、cluster/heat、ATR、生命周期等数量/资格门槛。070的实际保证金与全量风控接入由根任务独立负责，不以本模块纯函数通过代替完整runner验证。

开盘跳空导致整笔总风险超出预算时，根任务已确认**整单拒绝**。不缩单、不分批成交，不引入layer/target/diagnostic/receipt四套数量的部分同步。最小可承受手数只作为审计诊断。

## 只读设计核查与判断

原native公式使用limited_balance×riskmode比例，再经min_risk_per_trade=1000、max_risk_per_trade=50000000、streak/recovery/failure/OI倍率、overheat和30d方向倍率。N的streak配置全1、recovery_sleeve关闭，30dboost启用且配置1.5。仅把risk_ratio改0.005既不等于总权益口径，也可能被1000下限和其他倍率改变；super结束后仅替换risk_amount会保留旧contracts_by_risk及门槛先后顺序，错误。

采用cooperative hooks，在native计算contracts_by_risk**之前**提供唯一权威预算：

1. `_risk_amount_from_ratio` 返回实际marked `estimated_equity×0.005`，不读limited_balance作预算、不读_sizing_equity cap作预算、无base_capital回退。
2. overheat/30d快照保留原始字段和raw倍率诊断，但native实际货币乘数设为1。streak等原始风险倍率保留诊断，effective risk_multiplier为1。固定货币预算替换原金额floor/cap、riskmode比例和金额倍率，不额外把旧overheat降额变成新的数量门。
3. 从新预算算出的native数量照原顺序经过保证金、single-trade、cluster/heat、env/drawdown/volatility、ATR及Stage830等既有链路。最后再单调限制为不超过新预算可承受整手数，绝不恢复被原生门槛拒绝的量。没有复制native大函数、没有修改旧native。
4. 原始倍率保存在`stage068_raw_risk_multiplier/stage068_raw_overheat_scale/stage068_raw_directional_multiplier`；`stage068_active_currency_formula`明确显示唯一生效公式。
5. 实际权益<=0、NaN或inf提前返回拒绝，避免native的`equity or base_capital`回退和非有限资本转整数异常。

原039/041/059一手路径不能混入新实际MRO。068会主动拒绝包含`NativeRiskBudgetSizingMixin`的策略MRO；075已独立从新068和原始native基类组合，070应移除旧041并使用新多手执行适配。原`FullMarketNoAIOneLot`基类名称是历史命名，不代表其中存在新的1手经济cap。

## 新接口与授权

`stage068_fractional_risk.py`提供：

- `RISK_FRACTION=.005`、`UNBOUNDED_POSITION_SIZE=2147483647`（仅技术整数哨兵，不是经济仓位限制）。
- `candidate_overrides`设置fixed_size=0/min_position_size=1/max_position_size=哨兵/max_concurrent_positions=93/stage068_risk_fraction=.005，其余原参数保留；加仓仍关闭。
- `fractional_budget(equity)`与`whole_contracts(budget,risk_per_contract)`，预算采用十进制0.005；整手除法用Decimal并ROUND_FLOOR，无最少1手回退和放宽容差。
- `FractionalRiskSizingMixin`、`FractionalOpeningRiskMixin`与冻结的`FractionalSignalRiskReceipt`。

layer上的`stage068_signal_risk_budget`冻结snapshot_id、产品/真实合约、方向、信号、原信号时间、context、signal_equity、risk_fraction、target_risk_amount、信号每手风险、初始止损和authorized_volume。授权量是该次明确下单的原始整手量。订单量必须严格等于授权量和未成交layer量；不允许改成更小单绕过原授权。重发订单不能替换原信号时间。

开盘权威预算是`min(原信号budget, (当时marked opening_equity - 已实际成交费用)×0.005)`，不因账户权益上涨扩张旧授权。整笔初始风险=`volume×max(abs(open-frozen_stop)×size,tick×size,1)`；沿用原native tick/1元最小风险的保守口径。原始止损必须与未成交layer止损一致，已穿越止损、缺失/损坏授权、合约/产品/方向/信号/原日期不匹配、数量不一致均拒绝。拒绝会取消该未成交意向、把target还原实际pos、清理相应pending诊断；无实际仓位时清理未成交state与pending产品，防rebalance补回。

成交字段严格区分每手与整笔：

- `trade.stage068_entry_risk`：本次实际成交**整笔**初始风险。
- `trade.stage068_risk_per_contract`：实际开盘**每手**初始风险。
- `trade.stage068_budget`：开盘权威预算。
- `trade.stage068_signal_snapshot`：冻结信号receipt字典。
- open_budget_audit包含`total_risk/risk_per_contract/opening_budget/max_affordable_volume/volume`，不与旧stage041一手语义混用。

## 调研依据与判断

查阅[CME Position Size](https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size)及[vn.py官方组合策略文档](https://github.com/vnpy/vnpy/blob/master/docs/community/app/portfolio_strategy.md)、官方回测成交代码。判断：应先确定账户风险金额与止损距离，再算手数；风险预算和保证金是两类约束，不能把free balance误称总权益，也不能用每手风险冒充多手整笔风险。保留现有vn.py引擎回调，新增可审计授权，不另造撮合或下载依赖。

## 验证证据

先写10项核心行为测试并观察RED，全部明确失败于`fixed 0.5% fractional risk module is missing`；实现最小cooperative hooks与纯函数后10项GREEN。随后增加真实Confirmed引擎/native多手填单和清理覆盖；发现测试fixture仍继承旧FeeStrategy的一手pending查找，改为只在测试内提供原信号时间戳并调用真实native update_trade，生产070由根任务负责，未修改旧FeeStrategy。又新增损坏NaN授权回归，确实复现审计JSON序列化崩溃，修复后15项全绿：

```text
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/fian-risk05-mpl .py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p test_stage068_fractional_risk.py -v
Ran 15 tests in 1.392s
OK
```

重点覆盖：5000精确预算；100.00000001每手风险时只允许49手；native 250手先经过env0.5得到125手；streak/overheat0.1或2及30d0.5不改货币预算；sizing_equity cap=10万仍以实际总权益120万产生6000预算；env/margin/cluster零门不复活；env_probe无旧1手帽；冻结receipt、非法数量/MRO；实际多空50手×100风险=5000成交；跳空或权益降低全单拒绝并清state/target/pending；改小订单量/改止损/缺授权拒绝；重发保留原信号；NaN损坏授权安全拒绝而非审计崩溃。

本阶段不跑全线suite：070/074由其他工作区内agent并行先RED，根任务明确要求待所有实现稳定后统一运行。本15项不能替代最终070实际费用/保证金/075周门/074部分平仓与全部联合suite审查。

源码SHA256：`c795551c7b5b3457016397320d7d131a99b5a032cb4f7d8f3aa6e8fdf8073982`。
测试SHA256：`8d1d40864b9f307701decbe5d3a435300f89e43616f73f1bb89ae6bf3243a33c`。

## 金融结果、反思和TODO

- 新增参数：stage068_risk_fraction=0.005；max_position_size技术哨兵；固定货币公式。
- 修改参数：取消最多1手；原风险货币min/max、riskmode比例、streak/overheat/30d金额倍率保留诊断但不再参与该固定公式。
- 删除参数：无原参数字段删除。
- 新增/修改/删除金融回测结果：均无。期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均不适用。
- 开始与结束过拟合判断：**否**，用户固定总权益比例和整手执行合同，没有收益寻参或按品种/日期例外；仍是同样本后验研究，不能当样本外证据。
- 开始与结束继续价值判断：**是**，可检验单笔统一风险量纲与多手费用/保证金行为；不意味着相对N有收益改善，更不支持直接晋级。
- TODO：根任务070/075/074实际MRO、周门/授权别名、保证金整笔量与部分平仓联调；独立预审后统一联合测试，之后由根任务按授权进行一次新金融回放并独立审查数据/逻辑/置信度/bug。
