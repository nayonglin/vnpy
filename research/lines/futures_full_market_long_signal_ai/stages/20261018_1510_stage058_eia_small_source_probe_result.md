# Stage058结果：两份历史Table1真实下载成功，官方目录转入060

- line_id：`futures_full_market_long_signal_ai`；记录时间2026-10-18 15:10 CST。
- 本阶段不是策略/回测，模型fit=0、现金账户=0、SQL=0，所有金融指标N/A。完整目标active未完成。
- 原先057证据仅为两旧期HTML的Table1 CSV入口可见，不是已读CSV；058随后两次web click观察到精确目标，但工具因application/octet-stream不能给内容。root改用已授权联网的urllib对这两个精确CSV请求，均GET200且真正保存了内容。
- 前置失败不抹去：沙箱3URL DNS错误；批准联网后3份HTML各20秒读取timeout；这是通路/资源区别，不应概括为所有EIA数据都不可用。两静态CSV分别1.55/2.31秒成功，CSV阶段一次2请求，无模型重跑或自动重试。

| 来源 | HTTP | 字节 | CSV行数 | SHA256 |
|---|---:|---:|---:|---|
| table1_20110803 | 200 | 5937 | 55 | `1f191f63c587ba4eda6ea84ebd58a9b5845f04aaa0595a57925bfe79a46a0b6d` |
| table1_20200103 | 200 | 6097 | 55 | `c89231385239d8ff65fbeb5d8011ea4947474b04908d5f4a2510a22e6aae5fb5` |

- 2011-08-03 issue的CSV统计期为2011-07-29，2020-01-03为2019-12-27；具体周不等于可得日期。所需Commercial (Excluding SPR)、Total Motor Gasoline、Distillate Fuel Oil三行真实存在且能读取current/prior/Difference，不取SPR总量或下半表流量。
- 官方[Table1表头](https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf)的库存单位为million barrels，规范化到thousand barrels必须×1000；不能沿用DNAV的thousand口径去直接解读原CSV小数。059已明确单位换算，060继续做格式/量纲与current-prior差值验证。
- raw CSV只存excluded_raw_sources，不登记Git；派生观测会按需要保存复现角色。来源/终态：`outputs/stage058_eia_small_source_probe/csv_probe_receipt.json`，并保留两失败收据与两source probe脚本。
- 已冻结新的全市场EIA信息设计与实施计划059，6fit/12现金是后续单次预算，当前实际0。三臂全family同事件资格；4油品只诊断，不缩交易池。过去sham严格用已知过去，实际发布后首个China源close才决策，防夜盘日标签泄漏。
- 060数据agent已开始TDD；其第一条新route archive/index.php通过curl+Chrome UA取得真实174833B官方目录，原目录读取timeout仍保留。此状态只是agent实时进展，完整source导入结论须以060实际manifest/terminal为准。
- 开始/结束新增按成绩选参过拟合：否；未有新策略成绩。继续价值：是，已证明小型历史发布载体可真实取得，下一步直接一次导入并进入固定信息比较，不能将源成功冒充alpha或持续绕着源盘点。
