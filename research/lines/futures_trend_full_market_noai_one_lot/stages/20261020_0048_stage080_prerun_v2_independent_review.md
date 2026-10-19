# Stage080：v2强减规划修复独立预审

时间：2026-10-20 00:48（Asia/Shanghai）；研究线`futures_trend_full_market_noai_one_lot`。本代理未参与078/079实现，仅只读代码、比较差异和运行合成验证，不改金融工具/旧源/LINE/Git，不运行金融。

**结论：PASS WITH LIMITS PREFLIGHT V2。最终078/079当前未发现P0/P1阻塞，可以开始已授权的一次新v2完整回放。** 本次不是实际金融结果认证；v1的FAIL及两P1/P2记录永久保留，不能因预审通过称新运行已成功。

## 两P1及快照的修复核验

078放在079 FeeStrategy最前MRO。强减触发后，未同步OPEN意向按原priority整单取消，先于任何原Close reason、计划Pnl或streak；取消活动OPEN/目标/纯未成交层，保留真实同步层、真实pending CLOSE和实际资金。原风险/周授权以archive保存，诊断标记单独取消原因，不重写原授权，也不制造cash close。

forced循环限定的保证金投影为**实际量−有效已承诺pending CLOSE量+未成交OPEN量**。pendingClose方向、数量及真实余层均校验；native减仓候选只允许已同步实际余层。`_stage078_forced_planning_active`仅在try/finally内替换估算函数，异常亦恢复；外部账户/保证金路径仍走003实际持仓floor。Native trigger/target/priority/max reductions不变。

独立重现v1的“实际5手、margin550、权益750，本应减2手却排[2,2,1]”边界，新最终079 MRO只承诺2手，重复同日及跨日不增加；实际仍5手、实际margin至少550，直到真实2手CLOSE成交后才变3手及330。已有RSI pending2或全生命周期pending5不会再排同一量。原未成交17手双向意向取消无fake close/Pnl/streak，混合实际/未成交、旧合约pendingClose+新合约意向、无今日报价但可用因果缓存等覆盖通过；未来报价/缺mark/不一致状态hard fail。

预留按`_reserve_intrabar_entry`本日真实delta记账，取消只释放该意向delta，不从total/cluster实际占用移走资金。当前shape rollover启用，走该覆盖路径；add-only的`_reserve_intrabar_margin`不在ledger内，但当前adds三项均关闭，不是本次活动路径。native每日reset对跨日预留的语义保留，旧pending state本身仍进入强减projection。

079相对070差异限078 MRO、v1协议hash绑定、执行状态政策披露、完整取消收据CSV、增强strategy级失败快照和完整native强减事件CSV。新snapshot覆盖actual/targets/states+synced/授权/pending/forced，解决v1 on_bars异常快照为空。`forced_margin_deleverage_events.csv`显式19列表头，即使无事件也有header，进入manifest hashes，支持新实际逐事件核算ceil目标，而非只看Close数量。

## 参数与基线

N manifest仍`859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`；v1协议SHA256 `74bf1c2a7003155cbc4369f59ac8e8f245fa45a9eb3456ef0f048e3fc4708184`。预算068、账本069、pending074、周门075均与v1预审冻结hash相同。总权益×0.005、整手向下、整单原授权不缩单、止损已穿越拒绝、所有long exact-contract周双相位、short/close/env不加周门、取消1手帽但不加仓全部不变。原forced trigger0.95/target0.8/broker1.65/priority largest_margin/max100未调整；数据、运营deadline和经济阈值未按失败收益择优。

## 独立新鲜验证

- 完整本线正常模块discover：**332 tests / 28.747s，OK**。
- 单独078（含最终079 MRO及原分平转移）：41项，OK。
- 独立投影oracle：36组双向actual−pendingClose+未成交OPEN直接数量×保证金公式，以及6次同日/跨日幂等，共42项；实际account margin始终保持floor，全部OK。
- 079最终只追加19列CSV诊断后，2项runner MRO/strategy级snapshot测试再次OK；078 hash不变。这里明确区分最终纯诊断hash的2项复核与此前完整suite，不冒称最终诊断字节已跑同一完整命令。

078最终SHA256：`a3b8477c949fb8321690401c6a9721394cd0ec0950b3599fbf826ba4eaa4f604`。
079最终SHA256：`26a9bbff7e9eaf0ad433d0b8442e1a25ce11449d2723d8b1808914fccda7cd4e`。

全部核心hash见同名JSON。没有金融重跑；当前无v2 manifest，所以顶层source_manifest_sha256为null。新实际源预期`outputs/run_20261020_contract_weekly_risk05_v2`，完成后另写Stage080_actual精确绑定新manifest/source commit，独立核所有金额、手数、分平、周证据、时钟、费用/MTM、到期、取消及forced规划事件；若失败仍先审失败，不把partial当绩效。

## 限制与反思

继承Stage073的日线近似、静态费用/保证金/规格、研究主力、C2/C9及供需授权停用、量仓有争议的execution-only退出报价、V>=qty非真实容量/排队/冲击等边界。计划close的native realized/streak字段仍不是到账现金。固定0.5%不是gap损失上限。预审通过不保证完整运行必完成，也不支持正式晋级或生产资格。

过拟合：**否**，这是两项可复现执行边界修复，未扫阈值/品种/日期；同样本后验研究非样本外。继续价值：**是**，新冻结后一次完整v2能检验多手研究合同。新增/修改金融绩效结果无；权益、收益、DD、Sharpe、滑点、胜率均不适用。
