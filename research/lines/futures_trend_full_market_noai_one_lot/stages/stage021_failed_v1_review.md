# Stage021：生命周期无限并发 v1 失败独立审查

- 审查时间：2026-10-18 20:45（Asia/Shanghai）。所属线：`futures_trend_full_market_noai_one_lot`。
- 审查对象：`outputs/run_20261018_lifecycle_unlimited_v1` 的冻结失败前缀、截止表、生命周期事件、源码快照及原始报价；本代理没有启动金融回放，也没有修改运行输出或运行时代码。
- 结论：**运行未完成，不能签发完整区间结果或收益结论**。2021-09-24 的硬失败正确暴露了清洗数据与执行报价之间的合同缺口。不是市场完全没有价格，也没有证据证明生命周期 close target 忘记发出。
- 重要突破版本：否；这是失败原因与下一步修复范围的审计记录。

## 失败链条与证据

AL202110 的元数据 maturity=2021-10-15、交割月=202110、Commodity；固定研究运营规则得 deadline=2021-09-24，exit_signal_date=2021-09-23。9/23、9/24 均有 `close_target_zero` 事件，实际仓位 long1。8/24 以 20420 开1手后，失败前缀没有该合约的平仓成交。失败时还保留 AL 的 CLOSE short1 委托（9/24 重挂），未伪造退出。

冻结实现先在9/23收盘发出强制 target0；原生 rebalance 对有真实 bar 的持仓与目标差送 close。9/24 accepted clean 缺整键，`cross_delayed_orders` 将缺真实正成交量 bar 的委托暂移出撮合，再恢复保留。因此 close 不成交，截止日末 `assert_flat_by_deadline` 抛出 `unresolved_lifecycle_position`。9/23 的独立订单回执未保存在产物中，故可直接证实的是及时 target0；具体送单路径由冻结源码支持，不能把推断写成订单回执事实。

## 真实缺价、清洗隔离与未送单的区分

SQLite accepted `daily_bars` 与 Stage002 市场输入在 SHFE.AL.202110 / 2021-09-24 均无整键。Stage266 quarantine 明确原因 `unresolved_cross_source_quantity_conflict`、动作 `exclude_entire_contract_day_all_sources`。这不是自然交易日空缺：直接读取官方原 XLS、RQ 原 H5 和旧 TQ 原 CSV 得到如下证据。

| 原始源 | 开/高/低/收 | 成交量 | 收盘持仓量 |
|---|---|---:|---:|
| SHFE 原 XLS | 23520 / 23635 / 22760 / 23115 | 191338 | 90833 |
| 旧 TQ 原 CSV | 同上 | 191338 | 90833 |
| RQ H5 AL2110 row232 | 同上 | 180549 | 87233 |

官方 XLS 为年度压缩包内 2021.09 报表，sheet「所内合约行情报表」，1起始行271；合约标记 al2110 在此前连续行段。该行另含结算价23205，本审查没有把结算价当成交价。原文件及 member 的 SHA256 记录在伴随 JSON。官方标准化行与原 XLS 一致；原 TQ volume/openOI/closeOI 也直接核验。这是**价格一致、量仓冲突导致整键隔离**，不是仅 OI 冲突，也不是 maturity 当日，不能套用此前仅到期日 OI-only overlay 的许可。

在线调研核对了[上期所历史数据入口](https://www.shfe.cn/reports/tradedata/datadownload/)与[官方日周数据说明](https://www.shfe.com.cn/reports/tradedata/dailyandweeklydata/)。其现行量仓说明不能倒推替代2021原行；本案判断以冻结原始2021报表为准。没有找到或采用第三方策略代码来绕过生命周期约束。

## 前缀完整性与来源绑定

独立逐笔重建 3,168 笔 fills：非1手=0、非法平仓/产品gross超1=0，最大实际产品数15，失败末仓与快照完全一致。所有 fills 均能匹配当时 accepted 或已授权旧expiry overlay 的真实正成交量 bar；成交价与当日开盘价最大误差0。这里仅检查执行一致性，不计算部分收益。

五份冻结源码均与 `code_start_hashes.json` 一致；protocol 的原始输入 hash 与 Stage002 输出 hash 均一致。失败日实际10个产品持仓，只有 AL 的 deadline 到达。没有最终 manifest/summary，伴随 JSON 的 `source_manifest_sha256=null` 是明确的失败边界，改以 protocol、failure snapshot 和全部失败文件 hash 绑定源；不能自动盖 PASS。

## 最小正确后续合同与限制

量仓冲突保持在 clean、训练、信号与主力映射合同之外。可以单独审查通用 execution-only 报价桥：按原始隔离原因筛选，逐合约逐日有独立可溯源官方/RQ/TQ 原行，OHLC 精确一致且所有成交量保守最小值至少1，价格冲突一律拒绝；只供既有真实仓位 CLOSE/估值，OPEN、AM、信号、选品与主力均不得使用。须排除 accepted 整键及已有 expiry overlay 重复；加载器校验 hash、唯一键、标记及正量，实际填单再硬禁 OPEN。

不放宽固定10T/2T或股指提前1T截止，不按后验最后成交日改政策，不建立 AL 白名单，不释放未成交持仓的实际保证金。不满足真实报价资格时继续硬失败；本次失败前缀不可接着续跑或补一笔假成交。新数据合同通过独立边界审查及合成测试后，只能用新 run_id 冻结重跑。

新增/修改/删除策略参数：无；新增/修改/删除绩效结果：无。期末权益、收益、回撤、Sharpe、滑点、胜率等不报告，因本次仅为失败前缀。对失败原因判断置信度高；9/23具体订单发送缺直接回执，是保留的可观测性限制。

开始与结束反思：不是过拟合，因为审查与建议围绕原始行情真实性、执行资格和固定因果截止，没有收益目标、缓冲扫描或品种例外。仍有继续价值，因为价格质量与量仓质量分离能避免把清洗隔离误当无可成交报价；必须先守住 execution-only 边界，再判断完整新运行能否成立。
