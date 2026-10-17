# Stage028：有序条件入场执行接合独立复审

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 02:49 CST；独立审查者：`ordered_execution_review_independent`。
- 审查来源 HEAD：`fe5e16a33d2685fd3c6f3b73afce360d2986837c`，覆盖当时三个未提交研究模块与测试；不修改实现、LINE、registry、正式源或其他研究线。
- 是否重要突破：否。有限代码与组合 fixture 通过，尚无本阶段金融回测结果。
- 审查结论：本次覆盖范围内剩余 P0/P1/P2=`0/0/0`。允许按固定合同启动**一次 C_TS 完整账户回放**并复用 A0；不代表晋级、收益有效或总目标完成。

## 合同、调研与判断

已读取 AGENTS、registry、本线 Stage028 执行合同/计划和 `20261018_0242_stage028_entry_day_holding_causality.md`，并核对 Stage027 独立收据。外部资料沿用合同在本轮收益前已核的 CMT Elder、LEAN ForceIndex 和 Backtrader 执行资料；按 root 明确分工，本独立代码复审没有新增网络请求、金融回放或原始数据重资格。判断：只固定执行时序与观察域、有真实订单/账务证据后做一次完整反证有价值；有限组件成功不能代替 alpha 证据。

开始过拟合判断：**否**。本次没有查看新收益、搜索阈值或改变策略规则，目标是独立核对收益前合同的因果实现；既有多轮历史选择偏差仍然存在。继续价值：**是**，真实有序入场尚缺一次有效金融对照，错误的订单身份或入场前极值会污染该对照。

## 最终绑定与具体核查

| 文件 | 最终 SHA256 |
| --- | --- |
| `tools/stage028_ordered_strategy.py` | `d4f870355796c98625031f233dfba31f97db10422c894076acf436279f141c48` |
| `tools/stage028_ordered_engine.py` | `f7d7450495bb09407dc85ce6fe73fd700b2732a2e57dc8f6185abf199967af23` |
| `tools/stage028_run_ordered.py` | `c05924175609c09ce0a44b451bcc97497be2b30012cb9c971886217c4960c6af` |

runner 的实现收据保留补充合同接入前的历史 SHA `b4697f...`；本独立收据明确绑定上表最新 runner，新增变化为 HOLDING_CONTRACT 的输入记录、快照及 SHA，不据此声称旧测试重跑。

静态核查：原 native allocator 完整执行后才过滤，不重新分配槽位；u 的 q/S/rank 保留；原产品 snapshot 循环只 reserve。条件初始单在共同 heap pop 时才调用真实 `_open_position`、建立订单并交给 `_fill_order`，实际 fill 后才消费准备。普通单与 roll 保留 canonical context；unknown 回退仍受原 C9 入场计划门约束。

数据门静态核查：intent stub 使用 `Offset.OPEN`，因此未触发的 D 也要求 Stage021 完整 session 资格；资格先于条件扫描。完整 session 检查不接受旧宽松分钟 flag。沿用 accepted stack/source859 用途限制；既有 cu anchor 只授权精确一根 anchor，不能升级为 full-session 权利。Stage029 与冻结 Stage023 差异恰为 docstring 及三个输出/请求/协议常量共四行，未执行 provider 或网络。

runner 静态核查：使用实际 C_TS scope/provenance、独立 feature SHA、A0 字节复用、实际 AI 资格字节及 strict prior eval；保留完整日期、实际 settings/parameters、吞异常捕获及失败收据。pending 证据仅投影可序列化标量，避免 BarData/DataFrame 破坏异常收据。actual gap 风险/保证金允许超过 u 预测，代码披露且审计，不声称 fill 时重新过 Stage830 cap。

## 新增唯一组合 fixture 与实际结果

命令：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage028_execution_review/combined_native_hook_fixture.py`，最终退出码 **0**。仅新增这一个组合 fixture，没有重跑实现者的 11/9/6 项测试、Stage027、FI 全流或旧全市场资格。

该 fixture 使用真实 847 策略 constructor、真实原 `_open_position` / `_sync_open_trade` / 诊断 / target / update_trade / 成本/余额、Stage028 两个 adapter、真实 827 `_fill_order` 和合成交易 finalize；外部数据资格 callback 只记录调用，输入为完整合成分钟，不伪称真实签名数据链已复验。

四个确定性场景覆盖长短存活和长短同 bar 止损→下一分钟 retry→retry 失败，共 10 个真实 native fixture fills、4 个真实初始订单：

| 场景 | 实际 fixture 成交价格 | 费用一次记账 | 终态 |
| --- | --- | --- | --- |
| long 存活 | `111` | `33.33` | 一层/target `3` |
| long 同bar stop/retry失败 | `111,101,111,101` | `132.72` | flat/target `0` |
| short 存活 | `89` | `32.67` | 一层/target `-3` |
| short 同bar stop/retry失败 | `89,99,89,99` | `131.28` | flat/target `0` |

这些是**合成 accounting fixture 数值，不是策略金融结果**。逐成交断言费用与 settled balance 的独立公式；每场景只存在一个真实初始 OPEN，target 没有重复发单。真实 TradeData 的 `vt_orderid == signal_order_id`，命中条件首 bar 临时视图。layer 的真实价格已同步，state/layer 年龄保留 u=`20260106`，实际执行为 D=`2026-01-07 11:00`。同 bar stop 不使用入场前 open；retry 不早于下一分钟；原分钟 DataFrame 全值不变。

存活长单的 D 全日 low=`80`、high=`130`，持仓 context 变为后缀 low=`108`、high=`114`；短单后缀为 low=`86`、high=`92`。真实 `_update_dynamic_stops` 与 `_process_layer_stops` 没有因入场前极值误止损，原 bar/history 保留完整 D。普通/缺分钟及 C2 fallback 的各自有限证据来自实现收据和源码核查，本组合不将其冒充已独立重跑。

第一次运行退出码 1 来自 reviewer fixture 错把 native `_bar_date` 的 `YYYYMMDD` 当 ISO 日期，校正 fixture 期望后通过；没有修改实现或策略规则。另对三个最终模块执行 stdlib `compile()`，退出码 0；对 provider 四行差异做独立断言，退出码 0。

## 置信度、边界与后续

置信度：对已核接口和四个确定性因果组合为高，对未覆盖执行路径为中等；没有收益置信度结论。组合 fixture 直接调用持仓 hook，未跑完整 AM warmup / on_bars 市场回放，未穷尽所有 env、add、roll 开关。完整市场分钟价格、原始 DB 与 AI 数据资格沿既有接受身份及 runner 的 fail-closed 门复用，本次未重资格。

新增参数/修改参数/删除参数：无。新增/修改/删除金融回测结果：无。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、母信号胜率：均 **N/A**；本阶段金融回放次数 `0`，模型训练 `0`，联网 `0`，CTP/生产委托 API `0`，`production_qualified=false`。

后续 TODO：由 root 将此最终绑定落实为明确源码版本，启动一次 C_TS（run 内联 preflight）；若出现数据缺口，沿 Stage021 同 engine 等待独立签名资格，失败不接受部分收益。金融完成后另派独立 review 审查实际收益/回撤、成本/现金、母信号胜率、actual/forecast 风险保证金及七门；C_TS 结果不能替代尚未开展的独立 B_TS。

结束过拟合判断：**否**，没有新收益驱动选择；既有研究选择偏差仍须披露。结束继续价值：**是**，有限执行接合已足以让一次固定完整 C_TS 产生有信息量的金融证据；不得继续以组件准备代替该证据。

机器收据：`outputs/stage028_execution_review/review_receipt.json`；组合脚本与实际 stdout 数值归档同目录。该收据的 success scope 仅为代码与有限 fixture，不能解释为 promotion。
