# Stage154：离线规则覆盖映射实现，等待root唯一actual

- line_id：`futures_full_market_long_signal_ai`；2026-10-19 01:15 CST；非重要突破。
- 已读registry/LINE、153 root决策、152固定账户与规则catalog、153 source_overlay。范围由root明确为候选覆盖映射，不是账户期限资格引擎。
- 仅新增本stage、`tools/stage154_rule_coverage.py`、`tools/test_stage154_rule_coverage.py`。本实现者**没有启动actual，没有读取真实mothers或任何价格/SQL/模型/现金**；不改LINE、registry、153、旧物或root protocol。
- 新fit/cash/SQL均0，累计397fit/206cash。新回测参数/结果新增、修改、删除均0；新权益、收益、DD、Sharpe、总滑点、次数、胜率均N/A。

## 输入和输出合同

输入固定为：Stage265 `futures_metadata.json`、Stage266 `csv_inventory.json`（只用epoch身份）、041 `economic_projection.json`（只用身份日期及来源状态）、152 `account_contract.json/rule_source_catalog.json`、153 `source_overlay.json`。没有读取metadata内价格或经济费率列的计算；仅复用日期与来源。原metadata归一沿265全YYYYMM身份合同，目录是metadata真实epoch与clean inventory并集，不取今天存续集。

root已同意保留低成本单遍母域投影。`--include-mothers`只流式选择129 `mothers.csv.gz`的六列：`sequence_index/event_id/product_id/reference_epoch/u_date/u_index`。压缩文件必须顺序解码，其他列不进入计算或输出；不读取actions、COMMON、labels、预测或独立价格文件。空reference母行保留，不能inner join丢掉no observation分母。

| 输出 | 主要字段/用途 |
| --- | --- |
| epoch_coverage.csv.gz | 完整epoch/product/所/普通F/金融商品分类；metadata listed/maturity/de_listed及交割起止；has_clean_observations；rule_group、candidate_formula/expression标记、source_refs/evidence_grade、temporal_applicability及缺项 |
| mother_coverage.csv.gz（可选） | 六列原identity加对应coverage状态、当u的metadata状态、候选公告时钟提示；空reference或目录不匹配明确保留 |
| coverage_summary.json | 全目录、完整母域及2020+母域的分母；按所/普通F/资产类/规则/证据等级/时间状态/metadata存续状态分组；候选表达、缺metadata、无观察和严格ready分别计数 |
| started.json / terminal.json / manifest.json | fresh输出、真实成功/失败、耗时、实际数量；输入小资产与输出绑定、源码身份；失败不自动retry |

`strict_account_cutoff_ready`和`temporal_applicability_official_known`始终false，不生成或认证任何逐epoch账户清零日。`known_lifecycle_snapshot`只是原有字段回显，另标2026快照，不改名为账户期限。has_clean_observations表示曾在clean inventory出现，不保证当u或退出日有价、能成交。

候选公式与严格ready分开：普通/F、EC/股指现金与国债/实物分支独立；SHFE/CZCE等保留其部分历史来源层级；GFEX PS缺明确本品种条款时formula为unknown。INE SC8独立，LU/NR旧8、BC旧3与2311后5只作broker候选切点，不能由当前端点倒签历史。有reference epoch时按候选合约月分支描述；无epoch的LU/NR/BC仅列8或5、3或5的条件表达，不武断选某一偏移。全部严格未ready不等于候选证据等级、可表达范围及经济身份毫无差别。

root补充已核官方RQData文档/GitHub及原instruments.pk：本地原文件也仅19字段，不是导出时丢失settlement_method/个人cutoff。证据由root保存于`outputs/stage154_rule_coverage_protocol/raw_metadata_field_probe.json`；本实现不重复读pk或核该probe。调研判断沿152/153分级来源，代码不新增网页搜索、不把snapshot或broker切点升级。

## TDD与有限验证

按root限定只运行6个新fixture，未运行旧全套或任何金融。先写测试，首次实际输出**6个明确FAIL**，原因均为实现文件缺失而非导入error；实现后**6/6通过**。交付前在同一INE fixture追加“无epoch不可默认旧偏移”的字面断言，实际1 FAIL后作两行修正，最终**6/6通过，0.021秒，exit0**。

六项实际行为：普通/F不合并；CZCE同短码跨十年保留两epoch；symbol-only缺metadata不复制donor且保留；INE2311不晋为officialKnown并保持SC8；现金分支不套实物清零；无观察母行保留并参与分母。另CLI `--help` exit0；补丁阻止数据文件open/read的导入检查确认数据IO0；已有输出目录在读输入前抛FileExistsError、目录内容仍空。没有为验证再跑实际metadata覆盖。

独立agent仅静态核查新源码/schema，已报Critical/Important=0/0（不冒称全表actual复审）；最后两行无epoch语义delta另已通知其核对。actual之后由root安排一次完整输出独审。

| 最终源码 | bytes | SHA256 |
| --- | ---: | --- |
| stage154_rule_coverage.py | 21386 | 46987a2b1a2ef85f31937e041e03cb308603477ee7c0b85c1fd0858996373348 |
| test_stage154_rule_coverage.py | 7458 | ee310004a3e83f5fbb1fa61cd6e0837a9caf8a7b6456d76d43952ab950f29a51 |

## root唯一实际启动

代码导入无副作用；本轮只交付以下命令，**未执行**：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage154_rule_coverage.py --output research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage/actual_run1 --include-mothers
```

actual预期核对10880epoch/98代码、metadata10862、缺metadata18、clean9520、六所与精确F metadata42，并在母域输出后核399252行。它们当前只是固定输入合同断言，**不是本实现者新跑出的actual成绩**。任一失败保留terminal及部分输出，不自动重试，不用删掉行来凑数。源码不包含SQL、网络下载、模型或资金入口，不hash大DB；实际仅绑定所读JSON和本轮输出，mothers保留上游身份引用且不为hash额外重读。

开始/结束新增按收益调参过拟合：**否**，候选来源与分支沿既有固定合同，没有价格/收益输入、退出天数寻优或未来stale筛选。继续此有界覆盖量化：**有价值，实施准备已足够，交root运行**；直接由候选映射证明全历史资格、生成清零日或启动金融：**否**。完整全市场高质量long目标仍active，无alpha或增加投注资格。

## root实际完成补记（2026-10-19 01:28 CST）

root唯一启动session34171、exit0；terminal耗时13.810574500秒，外层13.877147458秒。本实现者只读回小terminal/manifest，没有重跑或重读大源。完整目录10880/98、缺metadata18、无clean1360；F总45为精确metadata42加symbol尾期3。全母域399252行、no reference186400；2020+161014行、no reference44788；已观察reference缺metadata0。候选公式可表达10852，PS28缺本品种公式；strict ready0，生成新截止日期0。0fit/cash/SQL/价格，累计397/206不变。

结果由[manifest.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage/actual_run1/manifest.json)与[terminal.json](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage154_rule_coverage/actual_run1/terminal.json)绑定；terminal232B、SHA e6ff89588b8171b2d482112218a580d19a0f30fcff9d312a6347d25a47d2ab9c；manifest3949B、SHA eb4299a708fe1b670593cb6f6d82745a69d573ee90f6cbbdddd88acc458bee5d。root后续155结案记录说明独立全新输出复审11.181442125秒、C/I/M0/0/0；本补记不冒称自己重审该表。候选覆盖有价值，严格期限仍未认证，不据此自行实施下一金融政策。
