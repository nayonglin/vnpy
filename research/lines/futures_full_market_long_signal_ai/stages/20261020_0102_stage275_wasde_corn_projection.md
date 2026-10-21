# Stage275：WASDE World Corn 单次来源数量投影（0 fit/cash）

- 时间：2026-10-20 01:02 CST；研究线 `futures_full_market_long_signal_ai`。不是金融突破或PIT资格认证。
- 来源判断：沿271已读USDA官方原文/维护者源码研究和冻结274；本阶段不新增联网研究，不更换实体、年份、单位、Proj字样或日期解析规则以增加覆盖。原始数据确实支持部分预先规定数量，但这不证明独立预测增量。
- 新增：`tools/stage275_wasde_corn_projection.py`、`test_stage275_wasde_corn_projection.py`、本记录及指定275输出；不改LINE、registry、旧源码、金融或其他线。
- 新增/修改/删除策略参数：均无。严格保存所有精确Corn/World的16原字段及源CSV、ZIP member、1-based数据记录号、物理结束行号和继承SHA。quantity只取本期World Corn Supply and Use / Annual / 空ReliabilityProjection，Forecast年月等于真实release年月；先选最高严格YYYY/YY营销年，再要求精确`Proj.`，不退取旧年Proj。S/U为唯一Ending Stocks/Domestic Total、同Million Metric Tons、S>=0且U>0；重复、日期或口径冲突保留unknown。
- 日期与版本：仅显式ISO或US月/日/年；ReleaseTime原literal不变。release+2日纽约00:00转UTC只记候选延迟边界，非历史首见。V2原比值可留而eligible=false/correction_known_at=unknown；本批没有实际取得V2。

## 验证与唯一实际执行

3项有意义合成检查 RED→GREEN，GREEN 0.002秒：本期/重印及最高Est不能退旧Proj；两种日期与DST；重复、单位、缺项、日期冲突与V2未知。0旧suite、0真实原件rehearsal、0fixture fit/cash。`implementation/fixture_terminal.json`完整记录终端，`source_bundle.json` SHA `206bff62aa5987f7afa6d49554394b6d1e777bfd08cbe952b03a31157bb0e510`。工具SHA `4467590ea3f5f8d1bfbccc051698e4075d650e632c46e1dbb951d8802b6a9fda`。

root先明确确认22590实际exit0、handle completed；采集自身为stopped_early（不是完整71目标）。此后唯一命令 `.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage275_wasde_corn_projection.py --execute`，session9281 exit0，3.911381秒。

| 项目 | 实际结果 |
| --- | ---: |
| 成功原件 | 47（2 ZIP + 45 CSV） |
| 新增作者CSV/member流 | 47（两ZIP各一个CSV member） |
| 全源数据记录 | 843079 |
| 完整Corn/World原字段子集 | 3612 |
| 实际观测WasdeNumber报告 | 172 |
| 满足本冻结quantity | 163 |
| 最高营销年未满足精确Proj. | 9（2010年，保持unknown） |

逐年观测报告数：2010=9；2011=12；2012=12；2013=11；2014=12；2015=12；2016=12；2017=12；2018=12；2019=11；2020=12；2021=12；2022=12；2023=11；2024=10。`source_inventory.json`另含全部源行的MarketYear/ForecastYear/Unit/ProjEstFlag/AnnualQuarterFlag/ReportDate计数及每member header/行数。

- 原件缺口：4次传输失败为2023-01、2024-11、2024-12、2025-01；20项未尝试为2025-02至2026-10的真实目录目标（不含2025-10）。24项均列source_unknown_months，release_date=null，不carry、不补抓。
- 目录未列：2025-10单独保留，不当作HTTP不存在或一次失败请求。
- 归档名义跨度中未观测到报告的月份：2013-10、2019-01；只报告未见，不猜其原因、不制造release日期。

作者每成功CSV/member仅一次新完整提取流，不extractall，不为完整性重哈希原件；原件SHA继承273。另明确披露root先前字段发现：两ZIP各目录及首member前三行一次；2021-01 CSV前三行一次、另完整扫描一次用于schema/entity；273下载各body SHA一次；没有额外integrity重hash。各类读取不混写成作者新增0次读取。

输出在 `outputs/stage275_wasde_corn_projection/actual_run1/`：`corn_world_rows.csv.gz`（75662B）、`report_projection.csv.gz`（18517B）、`source_inventory.json`（92994B）、receipt/terminal/manifest。manifest SHA `96100663bbd66be4097e0638e28b477ef72b5f7d0dbadaca8fa7c15d08fe9ed8`；receipt SHA `5af513f94a5378dcbc866e695f5ba3bb9e92484fb5d220a880c5d31f6752ed73`。已将新源码、合成证据、全部Corn子集及小输出refs交独立276；当前不冒称276已接受。

新增/修改/删除回测结果均无，权益/收益/回撤/Sharpe/滑点/交易次数/胜率/费用全部N/A。0 network、0SQL、0native price、0labels、0fit/cash，累计439fit/238cash。未做任何期货连接、信号、窗口选择或持仓变更。

过拟合反思：新增按成绩救参否；长期同史择题适应性风险仍是。163只指冻结来源量可构造，不代表163个独立金融样本、严格PIT或可交易优势。继续价值是完成一次276独审并由root裁决该固定quantity；不得扩作物、国家、分量、修订、阈值或补齐来源工程。本作者止步source-only。
