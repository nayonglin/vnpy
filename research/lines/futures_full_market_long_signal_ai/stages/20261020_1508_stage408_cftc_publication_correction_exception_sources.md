# Stage408 CFTC 发布、停摆补发与更正例外来源面板

- line_id：`futures_full_market_long_signal_ai`
- 当前模式：有界官方来源准备；只落本阶段工具、原件、机器表和唯一记录。
- 记录时间：2026-10-20 15:08（Asia/Shanghai）；原 HTTP 实际下载 14:53—14:55，完整本地面板编译 15:07 结束。
- 阶段性质：Stage406/407 的发布时钟与修订范围事实资产，非策略实验。
- 是否重要突破：否；补全来源不代表 PMPU 有增量价值。旧 Stage243/245 对已有 MM/PMPU 标量与 release 库迁移的价值 NO-GO 不由下载工作解除，也不等于 PMPU 已实测金融失败。
- 是否触发 A/B：否。本阶段不读 Y、不训练、不做现金回测，不进行新版本推广或加注资格判断。

## 外部调研与判断

本次实际读取 CFTC 两个官方入口及七个必要补件，共 9 次原 HTTP GET，全部 200，正文合计 459,252 B。单 worker、并发 1、每请求 30 秒、0 retry、0 重复 URL，未触发 403/429；低于授权的 16 GET、8 MiB 总量、单实体 2 MiB 上限。没有代理、镜像或替代域绕行；没有读取 Stage407 的 index/ZIP。网页均为真实保存的 HTML，不是 web-derived 文本冒充原响应。响应头、URL、实际 2026 下载时钟及正文 SHA 留在 `actual_http1/receipt.json`。

来源为：

1. [Release Schedule](https://www.cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)：通常 Friday 15:30 Eastern、通常上周 Tuesday 持仓，当前表明确是 **2026 tentative calendar**。
2. [Historical Special Announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)：2010—2025 年观察到的 90 条带日历日期公告已完整投影为 catalog；不以“无公告”推断没有更正。
3. [6745-13](https://www.cftc.gov/PressRoom/PressReleases/6745-13) 与 [6738-13](https://www.cftc.gov/PressRoom/PressReleases/6738-13)：2013 停摆不发布及 anticipated 恢复计划。
4. [7864-19](https://www.cftc.gov/PressRoom/PressReleases/7864-19)：2018 年末停摆后的 expected 补发计划及最后一次实际发布日期。
5. [9147-25](https://www.cftc.gov/PressRoom/PressReleases/9147-25) 与 [9138-25](https://www.cftc.gov/PressRoom/PressReleases/9138-25)：2025 年 12 月 9 日修订的 13 行 intended 表，以及 11 月 18 日原 17 行计划；两版都保留。
6. [About the COT Reports](https://www.cftc.gov/MarketReports/CommitmentsofTraders/AbouttheCOTReports/index.htm)：2000 年起每周发布、1992 年起第三个工作日发布的历史规则背景。
7. [8662-23](https://www.cftc.gov/PressRoom/PressReleases/8662-23)：2023 ION 延迟与最早恢复计划，只是当时的条件计划。

Stage406 已作公开实现与官方字段交叉调研；本轮没有重复抓 GitHub 或另起第三方归档梯队。判断是：**普通周规则可作为明确披露的回溯研究假设；它不是每个旧周的真实 first-seen 证明。既不应把当前 annual ZIP 的下载时刻当历史发布时间，也不应仅因无原始 vintage 永久否决一切回溯研究。**

## 本次变更

- 新增工具：`tools/stage408_cftc_publication_evidence.py`，负责有界来源保存和纯本地规范化。最终 `--compile-local` 不建立网络连接。
- 新增输出：`outputs/stage408_cftc_publication_evidence/`，包括九份原 HTML/派生文本、HTTP 总账、90 条公告 catalog、54 条发布事件、11 条重点更正/范围记录及候选例外范围。
- 修改/删除其他脚本：无；未改 Stage407、LINE、registry 或原有研究物料。
- 策略新增/修改/删除参数：无。新增的仅为来源解释字段，包括 `position_asof`、`original_scheduled_release_date`、`planned_release_date`、`confirmed_release_date/at`、`correctionKnownscope`、`research_available_at` 与候选边界假设字段。
- 数据区间：来源年度 2010—2025；2010 为后继既定 warmup，主研究期仍为 2011—2025。
- 账户、成本、交易过滤、收益阈值：本阶段不适用，未运行或改变。

## 核心事实与边界

### 普通周、假日与原始 vintage

普通 Friday 15:30 的规则和 Tuesday asof 只放在 `source_clock_rule`，明确标记 `retrospective_normal_week_rule_assumption_not_weekly_actual_confirmation`。当前 2026 假日表不回填 2010—2025。历史普通联邦假日表本轮没有完整归档，未默默用 `asof+4days` 推定真实发布。

`America/New_York` 负责 DST；明确 2014-07-04 15:30 EDT 的提前发布转换为 `2014-07-04T15:30:00-04:00`，明确 2012-12-05 15:30 Eastern 的更新转换为 `2012-12-05T15:30:00-05:00`。只有日历日期的事后确认，精确 `research_available_at` 保持 null；另外给出“确认日的下一纽约午夜”的**可选择回溯边界假设**，不将它伪装为原 first-seen 事实。原 annual ZIP 不是原版 vintage；未发现公告也不保证数据从未修订。

### 2013 与 2018/19 停摆

2013 公告确定当周不发布，6745-13 说预期 10 月 25 日开始补发原拟 10 月 4 日的报告、预期 11 月 8 日恢复；**这些是计划，不是完成确认**，原文没有具体 position-asof。候选范围按原计划发布日 10 月 4 日—11 月 8 日记录，端点仍标明只是 expected。不能宣称该区间每一周均延迟至同一日，也不能声称 11 月 8 日已实际恢复。

2019 公告事后确认最后实际发布日为 2018-12-21；明确 2018-12-24 Monday asof、原计划 12 月 28 日报告，**expects** 2019-02-01 发布，其后每 Tuesday/Friday 逐步补发仍只是预期。实际最终追赶日未知。为根后继决策给出的宽候选 evidence-gap 区间是 asof 2018-12-24—2019-03-25，终点来自随后 **asof 2019-03-26、published 2019-03-29** 的明文确认锚点；它不表示补发真的持续到 3 月底，不应被当作这个期间从未发布。

### 2023 ION：7 个事后发布确认

主文有 **7** 条 “Today, staff is issuing” 确认，先前交流里的“6 条”在本阶段纠正：

| 确认发布日 | 原计划发布日 | 原文明确的 position-asof |
|---|---|---|
| 2023-02-24 | 2023-02-03 | 2023-01-31 |
| 2023-03-03 | 2023-02-10 | 2023-02-07 |
| 2023-03-08 | 2023-02-17 | 2023-02-14 |
| 2023-03-10 | 2023-02-24 | 2023-02-21 |
| 2023-03-14 | 2023-03-03 | unknown |
| 2023-03-16 | 2023-03-10 | unknown |
| 2023-03-21 | 2023-03-17 | unknown |

后三行原文没有 position-asof，本表保留 null，只提供原计划日供后继和原 annual asof 对齐。所有确认都是 date-only，小时未知；2 月 16 日“as early as Feb24”及“by mid-March”不能替代上面的实际确认。3 月 17 日另有明确当日不发布的公告。公告列出的 OI 调整集中在利率、能源和指数合约，不能因此自动指控八个映射品种 PMPU/OI 全部错误；原文保存在对应事件证据中。

### 2025：13 个最新 intended 日期，0 个逐报告 actual 确认

12 月 9 日主文说明处理和发布在 10 月 1 日—11 月 12 日中断、恢复后已按时间顺序发布；但紧接着的表明确为 **intended**。最新 13 行覆盖 asof 2025-09-30—2025-12-23，包括 **2025-11-10 Monday**；新的计划发布日期跨 11 月 19 日—12 月 29 日。即使某表项日期早于公告日，也不因此升级为逐报告 actual 确认。11 月 18 日初版 17 行计划、12 月 9 日新 13 行都保存，新版只替代相应计划口径。

`confirmed_release_date/at` 对这 13 行全部 null。根可决定将 intended 日期作为披露的回溯时钟假设，或隔离这些行；这不是本阶段暗改实际确认字段的理由。没有为每个未知周展开无限搜档。

### 更正范围

重点规范化为 11 条；其他非映射市场或报告类别的原公告保留在 90 条完整 catalog，未把不相关公告丢失包装成“全市场没有更正”。对当前八个 Disaggregated FuturesOnly 映射，明确范围为：

- **2012-11-27 asof**：迟分类的账户转移、2012-12-05 15:30 Eastern 发布更新，广泛涉及全部报告分类，八个映射都作为潜在范围。
- **2017-03-28 asof**：2017-04-04 公布更新的原合约清单中，与映射交集是 Corn、Sugar。
- **2019-03-26 asof**：原 3 月 29 日发布、4 月 3 日新增 reportable positions，八映射交集七个，**不含 Copper**。
- **2019-10-15 asof**：原 10 月 18 日发布、10 月 24 日追加头寸，八映射交集 Corn、Soybean Oil、Soybean Meal。
- **2011-10-11 asof**：Corn OI 于原 10 月 14 日发布时已调整；这是 at-publication 调整，不能误写为后续覆盖修订。
- 2018 Legacy concentration 更正明确 Disaggregated/TFF 原值准确；2018/2014 期权与期货合并报告更正不自动污染本次 FuturesOnly；2010 Corn 公告明确新增 **options** positions，不仅凭代码相同就隔离 FuturesOnly Corn。
- 2015 Report Date/CSV 格式修正及 2022 Copper 名称缩短分列，不能包装成 PMPU 数值更正；085692 代码未变。

更正日只有日历日期时，原版和当前版的精确首次可用时刻仍为 unknown。候选 mask 只对明确 asof×code，或者允许披露的修订边界假设，不能无依据扩大到所有市场/年份。

## 结果与收据

- 90 条 2010—2025 日期公告；54 条规范发布事件（包括初版/新版补发计划，并非 54 个独立可交易事件）；11 条重点更正/范围记录。
- 2023 当日发布确认 7 条；2025 最新 intended 13 条、逐报告 confirmed 0 条。
- 网络 9 GET / 459,252 B / 全 200 / 0 retry / 0 URL 重复；新网络已终结。
- 本地完整编译前有两次终止：第一处正文/页脚同为 Washington 字符串导致锚点非唯一；第二处相邻 HTML 表格单元格将多个 `MM/DD/YYYY` 直接拼接，原 word-boundary 日期正则未取到新版表。只改本地锚点/日期分隔解析，原件和 HTTP 总账不变，两次 partial catalog 和原因在 `compile_preflight1_partial`、`compile_preflight2_partial`、`local_compile_preflight_failure.json` 保留。第三次完整编译 exit0；没有重下数据或金融重跑。
- 期末权益、总收益、最大回撤、Sharpe、滑点、交易数、胜率：**均未计算，不适用，不能填写为 0 或引用历史收益。**

关键产物（相对于本线）：

| 文件 | SHA256 |
|---|---|
| `outputs/stage408_cftc_publication_evidence/actual_http1/receipt.json` | `12ffc0c1443deaca9cf1dda2e87619d1610769bd0b0d0864e366835b15ee8941` |
| `outputs/stage408_cftc_publication_evidence/compiled/exceptions_panel.json` | `395305bc4e00cd2b7b51e4f2cf6ad9c3a0de7223351f0f536d0fdbfabb84851b` |
| `outputs/stage408_cftc_publication_evidence/compiled/publication_events.csv` | `fedfd445bc7c46c08123a11aebf1da4271009000dd23cd75de9d1b83818d51ea` |
| `outputs/stage408_cftc_publication_evidence/compiled/corrections_scope.json` | `578275ecbe044befba345ffa3f235e282f45ce5898566d47778659f19110dd49` |
| `outputs/stage408_cftc_publication_evidence/compiled/affected_ranges.json` | `41525d79876912fdbcf9dc608e617ae7ae4abd06a47b330c24a5ff9ad91aa80e` |
| `outputs/stage408_cftc_publication_evidence/compiled/announcement_catalog.json` | `8a2cbbce4727f4e157dc274d42dcbc9e35642b04bc7f36278f47921907360738` |
| `outputs/stage408_cftc_publication_evidence/compiled/source_panel_receipt.json` | `075fc7b208a6a5a092bdcce053cb62ff4444d124d536e7f9424f692e12e0ff83` |

## 结论、后继与反思

本阶段完成有限来源资产并停止联网，不宣称 alpha、全 first-seen PIT 就绪或正式/加注资格。源可用不等于已有 PMPU 标量值得再训练。后继如何处理普通周回溯规则、例外边界、旧价值 NO-GO，由根 Stage409 裁决；本阶段不制作 weekly 大投影、不计算 ≥400 独立 visible weeks 或 heldout 每年 ≥35 的过门数，不开金融预算，也不因已下载而自动开启 6 fit。Stage410 已收到终态物料做独立来源复审。

全市场母域仍是 98 产品/95 家族；本候选来源只有既定 8 个映射，另 90 个未映射产品保持 unknown，不填零，不据此缩为只做这些品种的策略目标。

- 运行前是否过拟合：**否**。工作对象为官方发布/更正事实，未接触收益、模型、交易目标或按盈亏选择时期。
- 运行后是否过拟合：**否**。补发计划与实际确认分层，未知未造值；候选隔离边界尚待根决定，不能靠样本数反向调时钟或救旧标量。
- 运行前是否值得继续：**是，仅指这轮有界来源补齐**，它能防止将持仓日当可见日及将计划冒充实际。
- 运行后是否值得继续：**本源准备已足够，继续无限搜档否**。已给可执行机器表、明确残余 unknown 和合理候选边界；新金融研究须首先通过已有价值否决的根裁决，不能靠来源工程代替科学增量。
- 合入建议：本 agent 不更新 LINE/registry，不追加根 memory/back_log；由根读取唯一 stage 后统一处理。本阶段结束，不扩展小元数据修补循环。
