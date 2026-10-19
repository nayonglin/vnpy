# Stage025：量仓冲突价格共识 execution-only 层独立预检

时间：2026-10-18 20:51，Asia/Shanghai。研究线：`futures_trend_full_market_noai_one_lot`。重要突破：否，数据/执行合同修复审查。

结论：**当前受审数据与消费边界未发现必须阻塞下一次冻结运行的 P0/P1**；这只是 preflight，不是金融结果 PASS。Stage021 已保留前次失败原因与源绑定，不修改失败账本，不输出部分收益。本代理没有运行金融回放。

## 真实数据逐行审查

Stage023 产生669条、23产品的 execution-only 报价。独立校验283份 source_files、8份 source_inputs 与生成器源码 hash，均匹配；逐条 receipt 的源集合/记录数与 excluded observations 一致，没有只挑同价源而漏掉已存在的第三方异价。全部 present source OHLC 精确相等，canonical 每源成交量至少1，输出量为其保守最小值；OI/volume 不被宣称已取得真值认证。

另独立重读全部669行 RQ 原 H5、357行 TQ 原 CSV；669条官方 original proof 与 raw_quote/标准化行一致，152个原始压缩包 member blob hash 逐一核验。AL202110 / 2021-09-24 输出 O/H/L/C=23520/23635/22760/23115、minV=180549、展示OI=90833，execution_only=true、allow_new_open=false、quantity_certified=false，正是 Stage021 直接核验的源证据。官方原 XLS 的669行没有由本代理再次全部独立解码；生成器对每行做原始解析一致检查，本代理核验原 member hash及行proof并对AL原行直接重读，限度如实保留。

669条均属于数量隔离集合；与 accepted、price_conflict_quarantine、旧expiry overlay交集均0。1766候选中133条旧expiry重复、821条缺唯一RQ/官方、47条任一源价格不一致、96条官方单位未知被拒绝。没有价格冲突报价通过。本次不改 clean、原H5/CSV/XLS或训练信号资格。

## 实际加载器与消费边界

独立使用真实 Stage024 加载器拼接：809279条accepted + 133条旧expiry + 669条新层，唯一合约日期键，无重复；全部809279条accepted原列值保持一致。加载器校验CSV与receipt hash、行数、epoch、maturity、固定授权flag、有限正价格/几何、volume>=1及重叠；Stage018绑定metadata与旧expiry hash，并在结束重核overlay未变。

消费端 `BarData.execution_only` 在真实 OPEN 填单之前硬禁，真实 CLOSE 需存在可平数量且方向正确。报价不进入 `signal_bars`、AM、主力映射或新信号；已有仓位通过engine报价补权益holding leg，并在EOD会计边界推进 last_close，避免重复计价。成交CSV写 quote_class/evidence_id 标识可回查。

## 新边界 RED→GREEN

预检新发现：退出信号日若整批只有execution-only报价，生命周期虽设target0并排队pending-close，却跳过原生on_bars/rebalance，没有真实平仓委托。以真实FeeStrategy合成fixture复现RED，target0/actual1/pending1/active_orders={}。根实现随后仅对实际仓位非0且target0的close_bars，直接调用 `StrategyTemplate.rebalance_portfolio`；既不喂AM，也不让qmtwrapper补入其它待开目标。

本代理新增两个回归：quote-only信号日必须派真实CLOSE且不伪造成交；其它未持仓target1不得借此物化OPEN。原RED转GREEN，生命周期21项通过；最终全线82项合成测试通过。原Stage016与失败v1冻结快照字节一致，固定10T/2T/股指提前1T截止没有变化。

## 判断与后续

新增策略参数：无；原数据和既有accepted值：未修改；新增绩效结果：无。当前可按新run_id冻结代码、receipt与CSV后运行一次新全周期；实际完成或失败均须另做独立结果审查，不复用本预检盖章。没有新金融结果，期末权益、收益、回撤、Sharpe、胜率等均不报告。

调研判断沿用Stage021对上期所官方历史数据入口及本地原始2021报表的核验；不以当前网页单位说明覆盖历史原行。不是过拟合：修复按全部同结构隔离键执行，拒绝价格分歧，未按收益挑日期/品种、未放宽deadline或扫描buffer。仍值得继续，因为此桥仅恢复被数量冲突连带隔离的可溯源执行价格；日总量为正仍不能证明真实开盘订单必然可成交，daily-proxy边界继续存在。
