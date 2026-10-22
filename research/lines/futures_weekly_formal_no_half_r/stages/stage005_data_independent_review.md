# Stage005 全市场数据准备独立预审

- 时间：2026-10-22 23:07 CST。审查者：独立agent；范围仅数据、准备代码和runner闸门，财务回放0次，未审E/F资金曲线、持仓、绩效或实际成交锚。
- 结论：`PASS_DATA_BINDINGS_WITH_COVERAGE_LIMITATIONS`。未解决P0/P1/P2阻断0；允许进入严格引擎研究，但不是全91品种逐日可交易行情已完整认证。
- 审查依据：`outputs/stage005_data/completed_manifest.json` SHA256 `72fedd9ef9ca6b5413436afa064f7226bd5445d9595674cb9afc5c1ef444cbf8`；独立机器证据`outputs/stage005_data/independent_review.json`。准备文件只读；本审查只写这两个审查文件。

## 身份、映射与旧键保留

- 91个唯一产品（含8金融、3个月均价F家族、pd/pt），2026-10-22有91行非空映射；映射日期/产品键无重复。不是按收益选品，不按亏损删除品种。
- 全部旧mapping键保持原主力合约，变更0；19处新旧Tq发布映射差异采用冻结旧值，未按成绩挑选。
- 原数据库所有键及OHLC、volume、OI、turnover逐键核验变化0。clean新增247095键逐值回accepted clean日线核验0差，CZCE按交割年月后三位还原native；F按l2602F这类末缀保存。clean文件stat与原数据准备receipt一致，dataset manifest SHA一致。
- 91行metadata的乘数/tick均有限正值。旧86行所有原字段保持，无新增费用或静默改变19池规格。5个新增产品乘数/tick回既有观测metadata核验：l_F/pp_F/v_F均5/1，pd/pt均1000/0.05；默认保证金0.15沿用预声明规则，不能当实际历史券商保证金。
- F三家族708行独立重算0差：仅用紧邻前一全局交易日真实正volume/正OI候选，按OI、volume、合约名固定排序，已知delisted_date筛选。未用未来最后观测日；与F_mapping_evidence完全一致。三家族各236有映射日，从2025-10-31至2026-10-22；上市后前两日无合格前日观测不补造。

## 原始数据证据与覆盖边界

- completed manifest的7项文件SHA全通过，审查后DB/mapping SHA仍一致。228次日线请求：168 complete、59 unavailable、1 failed（JR305 TimeoutError）；不将失败当已补齐。
- 168份complete原始parquet逐SHA复核；28466个验收日线记录的日期在新DB均存在；最新验收日期2026-10-22。原始快照中8929条零volume观测仍保留为观测，不能称成交证明。
- raw与优先accepted clean有1处量差：ag2612.SHFE/2026-07-20，raw volume59911，clean rqalpha AG2612 row141为59910；OHLC/OI一致。数据库保留clean59910，未覆盖，符合冻结优先级。
- 2020+非空映射共125180个产品日；真实正volume日线115436个，零volume3380个，缺日线6364个。缺口集中：LR1564、RI1155、JR1073、PM821、ZC707、WH592、RS243、CY154、bb55。最新10-22唯一缺日线为LR601.CZCE。未删除这些资格品种，也未用旧价填缺口。
- 因此“全市场”是91家族纳入信号资格，不代表91品种每天都具备41完整观察周、真实报价或交易能力。后续应报告实际ready、实际成交与各品种缺项，不能把不成交全部解释成信号失败。

## 两项预审P2已补闸

1. runner现在逐项校验completed manifest里的文件SHA，并在连接后核`PRAGMA database_list`实际path等于stage005_data/daily.sqlite，导出actual_database_binding.json。这里确认代码闸门，实际运行证据由财务独审再核。
2. runner对实际持仓/成交日另外核volume>0，不满足就拒绝绩效；weekly adapter不接收volume<=0来凑完整周。daily_coverage原有真实close/日期核验保留。

## 限制与反思

- 未发现金融路径或订单调用混入准备工具；三模块关闭、日线执行、完整周和41观察门槛不变。新增首分钟session适配只扩新增品种，原19会话行为冻结，真实锚缺失仍报错；本审查没有证明每个潜在成交锚已具备。
- 旧86产品级规格快照、新5规格和F到期信息都不等于历史逐日PIT；手续费0、静态/默认保证金和一tick类滑点仍属研究假设。不能从本审查推导生产资格、容量或可晋级结论。
- 开始/结束过拟合判断：本数据阶段未按财务成绩调参数或删品种，未见新增择优调参；历史存在性产品集合、供应商修订及反复同窗研究的选择偏差仍在。继续价值：有，严格全市场回放可回答扩池效果；若真实持仓行情/成交锚失败，先修数据证据，不能改策略救结果。
