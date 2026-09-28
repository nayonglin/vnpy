# Stage000历史镜像可成交宇宙资格预注册

- 时间：2026-09-05 02:27 CST
- line_id：`futures_trend_xgboost_pit_trailing_horizon_tradeability_universe`
- 是否重要突破：否；这是候选宇宙数据资格审计，不是模型或收益版本。
- 用户授权：后续研究操作默认授权；生产、CTP和订单继续禁止。

## 上游事实

- 严格滞后一日动态换约保留`54,876/56,272`条leg1可选路径，最终可成交`54,086`条；全输入资格率`96.115297%`，仍未通过全量硬门。
- `790`条失败路径中，映射失败`463`、完整路径真实价格失败`37`、真实容量失败`314`；容量失败主要为roll_close `285/327`。
- 所有映射/端点/容量失败集中于少数产品，但禁止按产品名单删除；新资格必须对所有产品、日期使用同一query-date可见规则。

## 外部调研与判断

- QuantConnect官方说明连续期货必须映射到具体实际合约，映射变化时需要平旧合约并开新合约；历史`SymbolChangedEvent`可按lookback读取：<https://www.quantconnect.com/docs/v2/writing-algorithms/datasets/quantconnect/us-futures-security-master>。
- QuantConnect官方期货宇宙文档区分连续价格与可交易的mapped实际合约，并把合约过滤作为独立宇宙步骤：<https://www.quantconnect.com/docs/v2/writing-algorithms/universes/futures>。
- CME官方交易指南把volume和open interest列为日级市场活跃度与流动性判断量：<https://www.cmegroup.com/education/files/a-traders-guide-to-futures.pdf>。
- CME对近月/远月流动性研究使用历史日成交量、持仓量及20日移动平均观察合约间迁移：<https://www.cmegroup.com/trading/agricultural/files/Variable_Storage_Rates_and_Wheat_Futures_Liquidity__07_22_10.pdf>。
- 判断：官方资料支持用历史实际合约换约和日级volume/OI做宇宙判断；“过去20日完整可执行预测未来20日标签资格”是本线的可证伪因果假设，不是外部资料给出的有效性保证。

## 冻结历史镜像合同

1. 输入窗口固定`56,272`行/`1,046` qid；动态合约映射算法、100/100、排序和到期单向推进完全复用上一线冻结实现。
2. 对每个`(query_date, product)`构造过去20个return leg：首个previous date为query date前第20个全市场交易日，最后return date精确等于query date。
3. 历史路径每个selection date必须是对应previous date前一全市场交易日；所有selection、endpoint和执行事件日期必须`<= query_date`。
4. 历史路径必须同时满足：20个映射完整、到期覆盖、端点volume/OI正数、entry/roll_close/roll_open/exit事件`volume >= 100`且`open_interest >= 100`。
5. 同时要求未来leg1映射在query date使用当日可见volume/OI成功选择entry date合约；该条件不读取entry date或更晚数据。
6. 仅历史镜像与未来leg1均合格的路径进入当期候选宇宙；未来20日的映射、端点和容量结果不得参与入池或重选。

## 冻结未来资格门

- 输入manifest、文件SHA、实现SHA和窗口身份稳定。
- `1,046/1,046` qid全部保留，每qid历史合格候选至少`30`个。
- 入池决定的最大使用日期不晚于query date；same-day/future历史泄漏为0。
- 每条入池路径精确产生未来20个leg；所有映射完整、严格滞后一日、到期不后退且覆盖return date。
- 所有未来端点volume/OI正数；所有entry/roll_close/roll_open/exit事件满足100/100。
- `close`读取、收益计算、标签读取、fit、predict、回测、holdout、CTP、订单和生产写入全部为0。

## 决策语义

- 全部硬门通过：`stage001_trailing_horizon_tradeability_pass_allow_label_value_preregistration_only`。
- 任一硬门失败：`stage001_trailing_horizon_tradeability_fail_close_no_label_values`。
- 失败后禁止重跑、改20日、降100/100或30、按产品/年份删除、调整动态映射、用未来资格补历史入池或按失败明细救援。

## 过拟合反思

- 运行前判断：风险中等，可控。
- 原因：假设由上一线结构失败提出，但窗口长度与标签持有期完全对称，且统一应用于全产品全年度；唯一执行前不查看该规则能否筛掉具体失败路径。

## 继续价值反思

- 运行前判断：有。
- 原因：若通过，可得到在打分时已知、无未来条件筛选的标签候选宇宙；若失败，则应关闭这组日线流动性标签执行路线，而不是继续调历史窗口或阈值。
