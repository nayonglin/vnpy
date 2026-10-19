# Stage063：逐笔周K仅用交易合约自身的只读转换

- 时间：2026-10-19 20:16 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 重要突破：否；响应用户纠正周线身份，属于展示合同修复。
- 新增：`tools/stage063_contract_weekly_recap.py` 及对应 test。本阶段不改金融代码、旧工具、LINE、旧输出或其他线。

## 计算合同

读取一份完整冻结 source 和 canonical parent；实际链按根任务约定 `025 raw→045实际初始风险R→063自身合约周图→020 reviewed`。全源文件及代码snapshot hash、parent全产物/hash/metrics/embedded records、canonical文件hash全部核验，输出必须隔离且不存在。

来源复用 `market_daily.csv`、`contract_metadata.csv` 的真实 vt_symbol/product_vt_symbol/listed_date，以及新冻结 `trading_calendar.csv` 完整独立交易日历。每个 closed long/short 的自身合约独立计算全历史：

1. 只有 execution_only 显式False、quote_class=accepted_clean，并且非显式 allow_new_open=False 的本合约真实有效OHLCV。allow_new_open缺省/NaN不误杀clean，与058一致；不借主力/其他合约或退出执行报价。
2. 复用纯 `WeeklyContractTrend` 本地合约完整周格/EOW有效性（与source058代码快照绑定），然后逐字调用 canonical `_weekly_from_daily` 聚合自身OHLCV。
3. 按完整本地交易周格 reindex，EOW无效则整根OHLCV缺失；未上市/无历史不补价，缺周不删除。有效EOW、周中不全时仅聚合可用本合约日。`partial_sessions` 为自然周交易会话未覆盖数，含上市边界，不都代表数据缺口。
4. 逐字调用 canonical `_add_moving_averages` 在全历史、保留NaN周的格子上计算MA，再按父页label裁显示窗。逐个核对058特征表的close/MA；MA仅属于本合约，不拼其他合约预热。
5. 每笔保留原weekly.label/x/width，替换OHLCV和MA。仅meta新增明确 `weekly_contract_display`；其余所有payload、排序、成交坐标/标记、R及非周线周期不变。

HTML仍调用canonical `_html`；不复制图表实现。保留其余周期原合同，明确它们可含背景主力/执行报价，不能混作新的合约周门槛证据。chart_manifest只新增周来源/合约/缺周/未覆盖会话说明，其余CSV单元格保留；closed_lots/all_trade_episodes及其他父产物原字节复制。

## 验证闭合

- `non_weekly_payload_hash` 只排除weekly及唯一新增meta字段，覆盖其他全部block和meta、list排序；转换前后必须一致。
- 原weekly label/x/width单独hash前后必须一致；坐标不为新行情重算。
- 全量validator逐周槽核对5项OHLCV和4项MA与完整精确表，输出检查计数；同时核对source冻结的058 feature weeks。
- 输出后重新读取 records.json，并从新HTML提取embedded records，再分别全量核对所有周值、非周hash及坐标hash。结果写 `weekly_contract_display_manifest.json` 和summary。
- 输出 `weekly_contract_chart_features.csv` 供所有展示合约（含未被金融long查询的short图）独立审计；该表为只读数据聚合，不是金融再回放。
- 生成器、canonical、001/042/055/058/062全部代码依赖hash，以及source/parent全部hash均保留并在生成后复核。

TDD：入口缺失时先RED；新增全量值验证/依赖闭合断言也先观察失败，再实现。Stage062/063合计 **10 tests PASS，1.841 秒**：同品种两合约反向趋势不混价，准确OHLCV/MA40；坏EOW整周缺失、满40周窗口不压缩；未上市/短历史不能借主力，allow_new_open NaN保留/显式False拒绝；篡改单一周值会被全量validator拒绝；完整临时fixture转换后非周块hash不变、closed CSV字节不变、冻结输入不变、重复输出/篡改来源拒绝。全线 **216 tests PASS，27.321 秒**，`git diff --check` 通过。

Stage063 SHA256：`935f9a827e9d31db2886ba2b487dd26e77ba2106044af7b2e2c3a4b12fb236be`。

调研：[pandas reindex官方文档](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.reindex.html)、[rolling官方文档](https://pandas.pydata.org/pandas-docs/stable/reference/api/pandas.DataFrame.rolling.html)、[pandas GitHub窗口文档](https://github.com/pandas-dev/pandas/blob/main/doc/source/user_guide/window.rst)。判断：必须先保留独立周格再做满窗口均值，不能dropna后滚动；沿用canonical实现并加真实合同的数据适配，避免新图改变金融输入。

## 参数、结果及边界

新增/修改/删除金融参数、回测结果：无。只有新展示入口/来源说明与周图身份变化；不改旧周图产物。尚未对新真实金融source运行063，等待根任务source/R parent完整冻结。174/216等测试通过不代表新真实图已经生成或浏览器已通过。

过拟合反思：本展示修复否，不改策略/阈值，也不根据收益挑图；金融周线条件仍是用户同样本后提出，不能据此认领样本外稳健性。继续价值：是，避免用主力周图误读交易合约门槛；下一步是完整冻结结果的逐点、JS、浏览器独审。

```bash
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage063_contract_weekly_recap.py \
  --source NEW_COMPLETE_CONTRACT_WEEKLY_RUN \
  --parent NEW_ACTUAL_R_RECAP \
  --output NEW_EXACT_WEEKLY_RECAP
```

未金融再跑、未下载、未生产访问；根任务负责后续020独审终稿、062真实总览及浏览器验证。

### 完整新源只读预核（20:18）

根任务确认唯一金融回放完成后，只读核 `outputs/run_20261019_contract_weekly_long_v1`：manifest SHA256 `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`，46项源文件/代码快照绑定全部PASS。新合约周policy、原native预算标志、上一主力C引用及三份周证据+完整calendar绑定精确正确；A与上一主力C的完整文件hash、参数、共用market/mapping/spec/039/041快照均相同。

只读摘要为期末1,205,102.81元、收益20.510281%、最大回撤-17.650750%、Sharpe0.161625、1,558完整交易、181次开多、周门违规0；它是根任务已完成的金融源，本阶段没有重跑。此时R parent尚未完成，因此没有实际生成063/062。新合约周收益仍低于原A，不据比较作晋级；具体金融独审由根任务承担。

### 20:25 真实精确合约周图已生成、另路独立验证PASS

根任务确认R parent完整后，使用冻结063生成 `outputs/recap_20261019_contract_weekly_long_v1_exact_weekly`，退出0。parent为 `outputs/recap_20261019_contract_weekly_long_v1_r`，summary SHA `1b00149b77f8311532c1b5b725f5cc2f03cd7e7995a4273f3c10c887e99ff497`；source manifest仍为 `859982f079da55aa1292154d5fc9b1004d1f0d5f23f75c4ec58ca892a102cb25`。源码/测试不变，没有金融重跑。

生成器内部检查与另路独立检查均PASS。机器报告：`20261019_2016_stage063_contract_weekly_actual_validation.json`。独立检查不调用063/058/canonical计算函数，直接从原market的自身合约accepted-clean OHLCV、listing及完整calendar分组，用NumPy满周窗口重算MA，再与输出对账：

- **1,558笔交易、1,182个展示合约、60,587个完整合约周表行、114,717个显示周槽**。源金融 `weekly_contract_features.csv` 的1857查询合约/93858周是独立scope，不应把展示合约数称为全metadata或全金融查询宇宙；生成器另外核对其中与展示相交的32,821周特征。
- **573,585项OHLCV + 458,868项MA**全量通过；OHLCV独立差值全部0，MA与独立NumPy均值最大差 `1.8189894035458565e-12`，为浮点均值算法末位差。没有改变金融阈值。
- **43,567个缺失周槽**原样保留为空，包含未上市/上市边界/历史不足/本合约缺报价等，不借主力补齐、不压缩窗口。
- 所有非weekly block、原meta、排序、R、成交标记逐值完全一致。非周payload前后SHA为 `98934ef90f004e56b28ca80c1e337953e7d8179a5deb78be4ea3bab5502e0a3c`；周label/x/width前后SHA为 `e1704758d8fadefbfb7c630162c0b8dbc3b72455a6f51a6940d95f08ecdfaba9`。
- chart_manifest全部旧列单元格不变；closed_lots/all_trade_episodes及其他旧产物字节不变；HTML内嵌records与records.json逐值完全相等。
- 69项源/parent/output/代码文件绑定独立复核通过；**2段JavaScript**经bundled Node `--check`通过。独立校验耗时12.097秒。
- pandas读取包含overlay可选字段时出现mixed-type DtypeWarning；execution_only/quote_class关键列无该警告。独立检查以low_memory=False重新读取、独立重算仍一致。未修改冻结源码处理此无害读取警告。

主要输出：

| 文件 | 字节 | SHA256 |
| --- | ---: | --- |
| index.html | 115,249,658 | `c5dfd416de3084e495ea638987c19f8911094d08cdd5438f9712f553d5ff41ec` |
| records.json | 110,249,439 | `47ed5feadc0d8205943238e780866bd1e3f6089168e118ce5c7939692df8dba0` |
| weekly_contract_chart_features.csv | 7,089,303 | `e10a399caa3540a5b4baf5fb29ad5f2b311e13a1e5cfee9060927a0a36c1df54` |
| weekly_contract_display_manifest.json | 3,570 | `b8cbef94db59b28cb29089836dfe36b260d1670a9884741c2380febbf8e67247` |
| chart_manifest.csv | 4,451,820 | `cbcfba8d198e544db76d2ae05898cd8e3a3e55bf0f811483a7acc560646c90ca` |
| summary.json | 178,813 | `ff9d6a7d350134e5ac326cea518e3ce3ca1ff0c09e3473a18068b6e725d87374` |

后续由根任务020生成reviewed最终页并做浏览器验收；本阶段机器报告标记 `browser_check=pending_root`，没有冒认交互已经通过。062正按明确reviewed parent生成，另记Stage062。

执行后反思：没有收益调参，没有新金融证据，属于有价值的合约身份纠正；新C仍不能凭同样本过滤条件认领可晋级或生产资格。未下载/生产/CTP/订单调用。
