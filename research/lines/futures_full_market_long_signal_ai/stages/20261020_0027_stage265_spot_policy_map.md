# Stage265 固定现货参与政策覆盖（0 cash）

- 时间：2026-10-20 00:27（Asia/Shanghai）。本线 `futures_full_market_long_signal_ai`；不是重要收益突破。
- 来源与判断：沿已完成的原始网页/维护者方法调研及 Stage257/262 接受的字面来源链，执行冻结264，不再联网或重审原页。262 `status=completed/core_blockers=0`，收据 SHA `39ad63ad332603cf386968072d0b3d099817db9f557ce43f1f4a05290f7254fd`。
- 改动：新增 `tools/stage265_spot_policy_map.py`、3项合成检查及政策覆盖输出；不修改旧工具、LINE、registry。没有新增、修改或删除策略参数，固定沿264的55精确普通名称映射，排除聚乙烯；全98产品保留。
- 规则：249全部3833规定日先验证唯一再升序，取严格早于u的21日；21日必须全为正Decimal、同一literal unit ID且逐日无重复。`newest > oldest`通过；有效且不通过只取消原已选机会；未映射、缺口、空页、缺报价、单位不明/切换及duplicate均继承。不得压缩至最近21个有效报价，不填0、不前填、不在入场D更新。
- 合成验证：3方法 RED→GREEN，GREEN 0.001秒。覆盖交错日历与缺口、Decimal精度及严格u前端点、重复/单位/非正未知、缺失继承、完整信号身份与262 gate。0 fixture fit/cash、0旧suite。证据：`outputs/stage265_spot_policy_map/implementation/fixture_terminal.json`；源码绑定在同目录 `source_bundle.json`（SHA `51d24c186c7b0db8821467343bfc52bcb6a0fd3c5b36c9bda55512c9026708f9`）。
- 唯一actual：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage265_spot_policy_map.py --execute`；session30181，exit0，4.660999秒。21,326,768字节新CSV仅为本次实际特征变换读一次，同一读校SHA；未读raw、价格cache、标签、金融表现或完整mothers。

| 域 | 完整行数 | 窗口可用 | 不可用继承 | 实际取消 | 实际保留 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 选择母行（98产品） | 161014 | 73211 | 87803 | 1108 | 159906 |
| 完整原信号 | 4365 | 2782 | 1583 | 1108 | 3257 |

母行中有效规则通过36254、不通过36957；未原选中的母行只报告规则结果并保留原无入场状态，不新增或改选机会。信号窗口有效通过1674；不可用1583由无映射1420、缺报价16、不可用页147组成，全部继承。

| u年份 | 原信号 | 可用 | 取消 | 保留 |
| --- | ---: | ---: | ---: | ---: |
| 2020 | 253 | 112 | 14 | 239 |
| 2021 | 1050 | 876 | 447 | 603 |
| 2022 | 1310 | 938 | 348 | 962 |
| 2023 | 228 | 141 | 57 | 171 |
| 2024 | 334 | 46 | 23 | 311 |
| 2025 | 223 | 56 | 9 | 214 |
| 2026 | 967 | 613 | 210 | 757 |

- 输出：`outputs/stage265_spot_policy_map/actual_run1/` 内 `choice_map.csv.gz`、`signal_map.csv.gz`、`coverage_summary.json`、`receipt.json`、`terminal.json`、`manifest.json`；保留原身份与端点/unit证据，按年、品种、原因聚合。manifest SHA `45f8b9d71f407e51811a9b1d55150b53e9f36776cd2f817dd6a99066c007a169`，receipt SHA `98601e0a1eae8912f315c526c1df7f93d35bf2e0b44da2a11d1d9fd388ea6450`。已送267新源独审；此处core0为作者运行守恒检查，不冒充267结论。
- 新增/修改/删除回测结果：均无。期末权益、总收益、最大回撤、Sharpe、滑点、交易次数、胜率和费用不适用；0新fit、0新cash、0network/SQL/raw/native price，累计439 fit / 234 cash。
- 过拟合反思：新增按成绩调参否；长期同史选题适应性风险是。覆盖只证明固定规则改变1108个原机会，不证明alpha、PIT、物理同质性或经济优势。
- 继续价值：有，取消数非零且来源未知严格继承，足以交给已冻结的一次经济证伪；不增加窗口、方向、阈值或映射。后续只由root依据267结论推进266四本现金；本作者止步0cash。
