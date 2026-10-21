# Stage060：一次官方EIA归档导入，保留完整日历与原精确解析结果

- line_id：`futures_full_market_long_signal_ai`；记录时间：2026-10-18 15:52 CST。
- 工作区：`codex/ai-training-data-expansion` 当前checkout；没有新分支、worktree、commit、push或生产操作。
- 性质：收益前冻结057/059之后的公开来源导入；本源任务自身 `fit=0 / cash=0 / SQL=0`。是否重要突破：否，尚无新增金融成绩。
- 开始反思：本次不是按成绩救参，属于真正新增外生实物观测，值得一次固定证伪；历史多轮择题风险仍在。

## 调研依据与我的判断

沿用057已做的论文、[EIA官方归档](https://www.eia.gov/petroleum/supply/weekly/archive/)与[rOpenSci/eia维护仓库](https://github.com/ropensci/eia)调研，不安装wrapper或把API现代修订序列当首发旧值。本次实际从官方 `archive/index.php` 用现有curl和Chrome User-Agent，首次route即GET200：`text/html; charset=UTF-8`、174,833B、13.269967秒，HTML SHA `ebe7e59d7e3f0b114c6a733c9b0f434edc1bf374eb7637aa6e94704bb3225ad5`。因此没有使用后两route，没有生成每日日期盲扫。

归档将Release date与Data ending分列。只读并行结构检查发现2016/2017年11月末一组五个td缺少起始tr，actual前加入测试并保留该组，正确得到794条。2022-06-29与2023-11-15各有两份统计周，`_data`目录日期不是发布日期。官方数据周为2011-07-29至2026-10-09，发布日为2011-08-03至2026-10-15；未补造2010旧期。

判断：小表来源可执行；归档和中国日线的因果时钟必须先固定。官方库存公布可能早被价格吸收，来源可得不等于有alpha。

## 变更、测试和实际执行

新增 `tools/stage060_eia_report_import.py`（SHA `f40f1b07007d283b950187d05f144ec9954c125433eb130165285e1bac07d45e`）及同名test脚本。新行为先RED后GREEN，最终7项通过：跨年日期、延迟双期、隐式td、上半表库存精确标签和单位、完整ordinal/过去sham、DST/中国u与下一nativeD/同u superseded、显式null库存共同中性。只跑新测试，没有旧suite。

唯一actual为PID3442/session7320，2026-10-18 15:14:45—15:49:53 CST，exit0、2108.546619秒。794份报告中复用058两份已绑定CSV缓存，只新请求792份CSV，并发4、每份20秒、无自动重试；另有一次上述完整index请求。没有因小缺口重抓或重启。所有响应、响应头与不完整响应仅放 `excluded_raw_sources/`，未登记原始HTML/CSV/PDF到Git。

上半库存表的官方单位为million barrels，统一乘1000为thousand barrels；下半表为thousand barrels/day流量，不能混入。精确第一列只取Commercial (Excluding SPR)、Total Motor Gasoline、Distillate Fuel Oil，不将SPR或总原油替代commercial。CSV本身不重复单位标题，单位依据059绑定的[官方Table1](https://www.eia.gov/petroleum/supply/weekly/pdf/table1.pdf)。2011旧期commercial原354.975→354975千桶、delta0.950→950；2020-01-03期原429.896→429896、delta−11.463→−11463，统计周2019-12-27不提前可用。

## 原060结果与精度问题

- 794完整calendar；792 HTTP200（含2缓存）、2网络timeout；596份通过原精确解析、198份unknown；规范stock共2382行，未知仍为3分量空值行。
- 424个scalar可知、423个与past_sham共同可知；787唯一中国u事件、7份superseded、1份期末pending；2020+349个u中，原精确核仅41共同信息可知。
- 拒绝原因：194份 `current-prior-inline != published Difference`；2011-08-24、2022-01-20各一次20秒timeout；2019-07-03文件表头为06-21而归档期待06-28；2025-12-29用四位年份，原 `%y` 日期解析失败。均保留unknown。

原解析把打印数字要求精确相等，这对官方独立舍入资料过严。终态只读检查194算术拒绝中193份全部三个库存都落在各字段打印精度的独立舍入区间；2023-12-28三个残差−0.203/−0.094/−0.092 million，均超各0.0015界，不能恢复。原060没有悄悄放宽或重跑，完整产物保持原字节。这个系统性显示精度丢失不能被当成EIA信息无效；root已在任何新fit前冻结精度修正合同，065独立离线处理。

按年原known/报告数：2011为21/22，2012为52/52，2013为52/52，2014为53/53，2015为52/52，2016为51/52，2017为52/52，2018为52/52，2019为51/52，2020为28/53，2021为20/52，2022为22/52，2023为19/52，2024为26/52，2025为25/53，2026为20/41。完整原因及逐格只读诊断见 `source_rejection_diagnostics.json`，原年度覆盖见 `coverage_by_year.csv`。

## 因果与范围

只用实际release列，日期only固定纽约23:59:59，IANA DST转换为UTC；u是可得时刻后首个中国源交易日16:00，D是其后一个native源日。2026-10-16末端u保留pending，没有加载未来D价格。不会把周三晚公告放进实际周三21:00已开盘的名义周四nativeD。

52lag按全部官方calendar ordinal，不压缩缺值；delta用该期公布Difference，分母用上一归档报告current而非当期重修prior-inline。past sham仅取严格过去52个ordinal中可知scalar，并按固定SHA选择；任一臂缺失则两臂新槽共同0。所有report更新历史，同u仅最新data-ending/issue保留，缺值也保留该事件。没有建立四油品交易池，全部family资格留给后续。

## 输出与终态绑定

目录 `outputs/stage060_eia_report_import/`：`calendar.csv`、`normalized_stocks.csv`、`report_features.csv`、`event_map.csv`、`source_bindings.json`、完整逐次 `source_progress.jsonl`、coverage/年度表、manifest和actual终态；每项必要复现资产有declared_role，raw不纳入。

- manifest（6129B）：`00a964468d6fc2cd272d522ae1343227df13b05e3a17dc216305c890a30ba923`。
- coverage：`e92c59ad750fe3a1b99e8248ed52fb061661e772a454b97da3f12de3664ee129`。
- actual_terminal：`f7334b3392dfdc4d267a96b80595edc0cca33bd74c7d0ab485dfd5444b1be6c2`。
- 新增/修改/删除交易参数与回测结果：无；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率均N/A。

结束反思：新增按收益选参过拟合否；这是公开来源和测量精度处理，不能消除已有历史选择偏差。继续固定新信息实验有价值，直接用原精确核缺失矩阵下金融结论没有价值。下一步只以root签发的065两层规范化材料做新鲜源预检，再按059固定6fit/12账本，独立审查后决定信息是否有价值。归档不能独立证明首次发布字节PIT，当前研究close mark/静态规格及未知暴露限制仍在。

本阶段不改LINE、registry或根memory/back_log，不宣称完整AI目标完成；root后续模型/账户运行与本源任务0fit/0cash分别记录。
