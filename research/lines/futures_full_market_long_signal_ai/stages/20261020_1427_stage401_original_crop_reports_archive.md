# Stage401：一次完成2017—2025原始全国作物报告归档

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 14:27 CST汇总。开始前已读registry和root冻结 `outputs/stage401_original_crop_archive/scope.json`。
- **已取得319份整份原TXT：309份全国Crop Progress、9份真正Crop Production Annual Summary及2019年1月改期通知1份。** 全部原报告保留所有作物、州和原页文，不裁切成大豆专用原件。
- 本次是可复用数据资产的实质推进，非已证策略重要突破；fit/cash/行情API/SQL/GRIB均0，未获得加注资格。

## 来源人口与一次有界采集路线

数据范围在看收益前由root固定：2017—2025每年4—11月原national CropProgress全部发布；2017—2025原AnnualSummary（对应priorQ2016—2024）。没有按天气、价格、收益或表是否好用挑周。

真实来源入口：

- [官方Crop Progress原档](https://esmis.nal.usda.gov/publication/crop-progress)。实际HTML表单为 `method=get`、参数 `date=YYYY-MM`；月份选项和分页均来自原HTML。每个报告行直接含整份原TXT锚点，未猜一串URL或逐条钻详情页。
- [官方Annual Summary原档](https://esmis.nal.usda.gov/publication/crop-production-annual-summary)。用已观察到的下一页链接覆盖2017年，完整原报告链接直接出现在列表中。

初始两根页由实际session `92474`并行取得并持久保存；后继主进程 `86101`复用两页、不重复GET，从14:19:09至14:24:59 CST完成全范围枚举、TXT获取及离线解析，真实exit0。一条逻辑harvest、两个互不重复URL的程序调用，不把初始发现页另算成未记账probe；全部累计同预算。

预算上限80 locator、400 TXT、480 GET、200MB、最多4并行、单源2MB/30秒、0自动重试/0重复URL；真实执行：

| 项目 | 实际 |
| --- | ---: |
| 官方locator GET | 74 |
| 新原TXT GET | 317 |
| 全部GET | 391 |
| HTTP200 | 391 |
| 请求失败 | 0 |
| source正文网络字节 | 26,306,297 |
| exact URL复用旧391原TXT | 2 |
| 唯一整份原TXT总数 | 319 |
| 自动重试 / 重复URL GET | 0 / 0 |

复用原391的annual2020和progress2020-08-31时，核对exact archive URL和原body SHA，复制为401原件并绑定原391 body/headers/receipt，不重下、不覆盖旧源。每个新请求有独立headers/status/raw-body/hash与URL；所有目录/原文及元数据保存在 `outputs/stage401_original_crop_archive/actual_run1/`。不会因为其中个别条目失败回头重试或全局改源；本轮实际没有发生网络失败。

## 官方原档事实触发的两个边界

1. Annual 2019-01-11原行实际上链接 `01-30-19_Report_Reschedule_ASB_Notice_Final.txt`，不是有生产数字的年报；真正同系列 `cropan19.txt` 在官方2019-02-08行。root在下载前以 `annual_schedule_amendment.json` 明确允许这条已观察到的Feb08原年报，并保留Jan通知，所有其他范围/预算不变。这是原发布日程适配，不按收益换样本。prior2018只能在Feb实际公布之后使用，不能倒填Jan。
2. 2025-10没有原生月份选项。保留 `unknown:no_native_date_option`，没有伪造当月报告、拼月份或拿最新修订表补洞；不据此推断所有历史渠道都不存在该月资料。

按已枚举原释放标签统计：

| release年 | CropProgress整份数 |
| --- | ---: |
| 2017 | 35 |
| 2018 | 36 |
| 2019 | 35 |
| 2020 | 35 |
| 2021 | 35 |
| 2022 | 35 |
| 2023 | 35 |
| 2024 | 35 |
| 2025 | 28 |

这些是实际原档发布人口，保留假日与修订条目，不用“应该每周一”推算应有数量。2018多一份或2025较少均不依据收益删改。9份真正annual均按其实际年份表头绑定prior2016—2024，Jan2019通知另存无表状态，未混入数字。

## 离线解析、原字段证据与所有未知

新增单一采集工具 `tools/stage401_original_crop_archive.py`（17,050 B，SHA256 `962ceb165c4552c754bda87e9b143d1eb4ebcb890afdb1d867b6147880c290d9`），以及独立离线工具 `tools/stage401_parse_original_crop_reports.py`（16,824 B，SHA256 `a776828b2cae9f59888bd2dd5d3e56991163a7606c112eba5fbc20a0c5119e41`）。原.py311解释器/环境未改，无SDK安装或旧suite。离线parser由子agent并行实现，只读原文与元数据，不联网，不按模型/金融结果调整来源。

每份解析保留原header、原表行号/raw line、各列原token、当前列位置、实际year/date列和source body/locator SHA。原百分比NA/D/X/Z、未知schema或缺表不补零；横线只有同份原报告明确说明 `Represents zero` 时才解释为已报0。当前阶段不做阶段100继承或气象事件选择，这些由402预声明规则另行处理。

319份均离线解析完成，运行时解析error0；原表覆盖为：

- 309份Progress中，pods原表存在且明确schema88份，缺表221份；leaves存在且明确schema72份，缺表237份。缺表是该季节/原文覆盖信息，不是假设的0，也不是整批失败。
- 9份真正Annual原soybean production表均解析，含原表列出的全部州/其他州/US、原单位1,000 bushels和实际年列；Jan2019改期通知原产量表不存在，保持unknown。
- 全319份中308份有唯一完整正文Released日期标签。其余11份为9份Annual、Jan2019通知及2018-09-10进度表；它们保留实际官方列表标签和正文原header，明确没有完整body Released标签，不伪造日/小时。没有body标签与官方日期明确冲突的样本。
- 原列表常见的`12:00:00Z`存为archive metadata，**不是历史实际到达时刻**。原文时间/发布政策原段均保留，未把政策最早发布时刻当最晚可得时刻，也未猜假日周一。

parser实现中的两项本地预检问题（2020年报无完整Released日标签、NorthCarolina单个点leader）在全批实际解析前修正；不增加网络、未替换数据或科学窗口，未跑金融。全批没有再次调parser或重复执行319份解析。原文当前下载仍不证明历史从未修订/首次发布的字节留存，不把现代QuickStats的最终修订结果代入原年报。

## 终态物料与下一步

| 物料（均在actual_run1） | 字节 | SHA256 |
| --- | ---: | --- |
| `harvest_manifest.json` | 1,321,595 | `c0ed6221f899567bb3c61402033a8663b11266c47fa496b5c2ddce7189dae4b1` |
| `metadata_inventory.json` | 345,516 | `da29ec2684b04276c5dfb987a738fb0adc6d8b92691aa35ca13a0a765d015e0e` |
| `reports_index.json` | 1,448,049 | `0508ef5ecdcc69fb2e5f885c49923285d95047ad20a41bdba4ab9802075112d4` |
| `parsed_original_tables.json` | 9,275,912 | `770b0611d801ae5358523904f7bc3766b358258e54734deed98fc7647d5dcc7b` |
| `terminal_source_summary.json` | 5,063 | `7aca158db6a0b8b8e2c0d4233aff1939c31923c14a5665883fe704dffeb475d1` |

402消费者已收到确切schema、绑定和全部源终态，可直接做一次离线事件资格表，不需要重下或再解析原文。后继必须先看实际joint-report支持是否达到400盲设计的30train/15held最低量，再决定是否获取天气；不足则本规格0weather/0fit，不能删年救样本。归档原件作为全作物资产仍保留。本文作者不代替后继数据/逻辑独审，未自行启动天气批次、模型或资金实验。

版本/参数账本：只新增401工具、输出与本文；正式策略、390/397、LINE/registry、模型/账户、原98产品/95家族、CTP/订单/邮件/定时任务/Git均未改。金融参数/回测结果新增、修改、删除0，fit0、cash0、金融partial0、marketAPI0、SQL0；期末权益、总收益、最大回撤、Sharpe、总滑点、交易次数、胜率全部N/A。

**开始/结束过拟合判断：本次没有按收益/温度筛年、周或表内容，完整原来源人口取数；长期自适应择题偏差和历史首见不足仍然存在。继续价值：是。** 已将零碎单周样本扩为9年整份原报告，并把发布/缺表/修订边界保留下来，为真正跨年增量验证提供输入。数据齐备不等于AI已会识别高质量long，亦不构成成本后优势、小止损加注或完整目标完成。
