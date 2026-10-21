# Stage180 固定历史仓单原文归档实现

时间：2026-10-19 03:23 CST；line_id `futures_full_market_long_signal_ai`。先读registry/LINE、178完整方案、172简洁fetch与179冻结协议。本分工只新增本stage、`tools/stage180_warehouse_archive.py` 和专属test；未改LINE、registry、179、178、旧原文或金融资产，未启动actual、网络、规范化或依赖安装。0新fit/cash/SQL/标签/价格；累计409 fit / 218 cash，金融指标N/A，非重要突破。

179 protocol为5113 B，SHA256 `a67cf844699c8b2d1b34cc3cd66ac88eaae0c6bedd5621796d886f129cfbb0c5`；硬绑178 plan 82071 B、SHA `06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8`。本轮不另搜网络/GitHub或重探真实raw schema，直接落实已调研/接受的固定source方案；维护者代码不执行。root与181负责静审、root唯一actual，后续181独立核全新归档。

## 固定范围和实际行为

`build_actions`只从plan的完整dates及reuse_by_date重建五字段 `sequence_index/date/format/url/action`，canonical JSON采用ensure_ascii=false、sort_keys=true、separators=(',',':')、UTF-8；分别核dates、完整actions和new_get集合SHA，以及数量/年份/格式/复用身份。已小元数据核179 expected_domain与178一致，不加载母表、价格库或模型。日期为2014-05-19—2026-10-16共3018日；2798 JSON+220 HTML，9复用/3009新GET。已完成研究终点不因未来calendar延长，不按品种/年份/收益再筛选。

CLI导入无I/O；执行入口先核179固定SHA、plan bytes/SHA、预算及domain。输出目录必须fresh，拒绝覆盖/自动resume。所有9份既有body在第一GET前各读一次，核bytes/hash并在同一内存核envelope和显式日期；旧raw只引用，不复制、重新下载或替换。任一复用失败即停，新GET为0；本执行者未提前读这9份原文。

真实网络只一串行Session，trust_env=false避免环境代理/netrc凭证读取，每请求前清cookie；TLS=true、redirect=false、默认无retry，无登录/替代来源。两次实际GET派发起点至少间隔1秒，不强制请求结束后再加1秒。最多3009新请求，connect8/read20秒；35秒/篇及4小时/批为阻塞调用前后monotonic守门，**不是声称requests能系统级中断DNS/底层阻塞**；请求timeout、实际耗时及overrun字段如实保留。首次HTTP/网络/重定向、envelope/明确正文日期冲突、预算或I/O失败即停，不更换URL、格式或日期、不自动retry。

原文以plain字节流保存，不重编码；HTTP headers保留，Accept-Encoding请求identity，读取并计量的是requests/urllib3解码后的entity字节，basis在记录中明确。每次read最多剩余额加1 sentinel，单篇5 MiB、全批新增body512 MiB；触界最多多1字节即停，已收到的失败/截断前缀也保存bytes/hash，不丢弃。即使网络在body前失败，也保存明确complete=false的零字节前缀。元数据总上限64 MiB，逐写入计数、预留当前最终date list和小终态空间；预算不能通过截断后假称完整。

JSON只检查top o_cursor为list，显式日期只取top report_date/o_tradingday；HTML只用标准库HTMLParser读取content_intro可见文本，不执行JS、不取script/仓库行日期。日期缺失为absent，可归档但不补造；明确异日conflict停止，显式字段无法解析也保守停止为unparseable。新格式/envelope不通过即保留原文停止，不临时修源或扩endpoint。旧WGHTUNIT/WHTYPE代码未知不影响忠实归档，也不被解释或单位回填。

## 输出接口与失败保留

根指定专属fresh目录 `outputs/stage180_warehouse_archive/actual_run1/`。预建完整3018条date_manifest.pending身份，journal每次追加flush/fsync；GET前写get_dispatch_pending，完成记录保存实际派发起点，崩溃时pending事件不是已成功证明。最终所有未尝试日改not_attempted_after_stop；完整成功才status=completed，否则stopped/exit1，绝不把失败批标成连续历史完成。

- `YYYYMMDD.dat/html`：仅净新原文或明确失败前缀；旧9份不复制。
- `YYYYMMDD_response.json`：本次或复用验证的完整记录；date_manifest的response binding指向它，文件本身不自含自身binding。
- `date_manifest.json`：完整3018原序list，保留五字段identity、state/attempt、HTTP headers/status、获取起止/耗时、date evidence/state、body path/bytes/hash/complete/truncated_prefix/reused及archive时点。复用另外保留original body binding、original_fetch_metadata/evidence，当前核验时点不冒充原首次发布。
- `journal.jsonl`：batch_started、复用/请求终态、get_dispatch_pending、必要archive_failure事件；date_terminal中含最终record，已成功日期不重做。若元数据本身超预算，只写明确truncated的紧凑失败证据和原record bytes/hash，body不删除/替换，不宣称headers完整资格。
- `started.json/terminal.json/manifest.json`：schema分别stage180_warehouse_archive_started_v1、stage180_warehouse_archive_terminal_v1、stage180_warehouse_archive_manifest_v1；manifest含inputs protocol/plan/source、started/date_manifest/journal/terminal binding、完整summary和budget。每份body均由date_manifest逐日绑定。terminal记录attempt数、完整成功/复用/未尝试/失败状态、总body字节及真实时钟；strict_PIT=false，全部金融授权false/调用0。

## 有限TDD与交付冻结

先写5个合成fixture并观察5个RED（实现缺失）；实现后复用path fixture抓到 `/var` 与 `/private/var` resolve差异，改为原样保留原binding路径后GREEN。最终命令 `.py311/bin/python -m unittest discover -s research/lines/futures_full_market_long_signal_ai/tools -p test_stage180_warehouse_archive.py -v`：**5/5通过，0.025秒**，未跑旧suite、真实raw或网络。fixture覆盖固定domain/hash/格式；全部复用先验、无GET回退与GET起点间隔/fresh输出；首个HTTP/网络/envelope/日期冲突停止；缺日期/冲突及intro排除脚本/仓库日期；单篇/全局流式预算及最多1 sentinel的失败前缀/hash。transport与clock为合成替身，文件/持久记录、hash与解析逻辑实际执行。

冻结实现 **24421 B**，SHA256 `0982cda1ae7d8979265fd6d8d5122e462983c95f4b7f5715bf4e2ef3254fc9f5`；测试 **10502 B**，SHA `fe420857db7ec0335d7230c66ccfba021c7bc451ba8d19922a54277c283bf791`。181已收到接口及最终静读候选，本agent不自行actual或再改源。

唯一实际CLI由root调用：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage180_warehouse_archive.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage179_warehouse_archive_protocol/protocol.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage180_warehouse_archive/actual_run1`。失败保留，不自动重试；既有成功日未来也不能静默重抓，续取必须root另签。

开始/结束新增过拟合：**否，本轮只实现已冻结完整日历归档，不消费收益、标签、价格或择赢家调参**；历史修订/择题风险仍在。继续价值：**是，限root一次固定source实际采集和181独审**；物理单位、类型、跨年代/格式、coverage与首发PIT以后仍须另审，归档成功不是alpha或金融资格。完整long目标未达成，不加注。

## 03:26 actual前静审必要修正与最终冻结

181与root静读指出两项阻断，旧0982源码候选**尚未运行actual**，不是新增金融/历史采集失败。沿接收代码审查技能核对后，只修这两点：原HTML仅tables>0可能把HTTP200普通错误页当缺日期合法日报，现改为content_intro元素存在，且至少一个非intro表的同一header行具有明确地点列（仓库/厂库/交割仓库及已知地区合并文字）与数量列（期货/本日数量）。只读header文字，不规范数据/单位；日期仍只从intro可见文字提取，合法日报缺日期仍absent，generic table则unexpected并停止。174现成基准确认黄金特殊合并在数据行而非header，无额外别名，不重读raw。

另一项是在HTTP200 inspect_body计算和记录之后立即追加guard(report_start)，正文解析耗时超过35秒也转failed_bound_or_budget，不再仅展示overrun却继续成功；完整已收到body仍保留。现有HTML fixture补generic negative及合法缺日期positive，新增一个仅模拟36秒解析耗时、真实解析仍执行的clock反例；修改前实见两项RED，最小修正后同一专属命令 **6/6 GREEN，0.031秒**，没有扩旧suite/网络/真实raw/格式工程。

**最终生效冻结身份替代上文首候选：source 26096 B，SHA256 `2915357de51e456cc38f485510ab3380886d1b81e58643c43fc2f7406a82a62a`；test 12510 B，SHA `0fe770724f3b467b3016291ac8627c51c7b2b4d882e6ef873cb93bff5ca1a2b7`。** 179/178字节、范围、预算、CLI与金融0授权均不变，181只复核本diff/有限fixture，root之后唯一实际启动；本agent仍0actual/network。当前修正为实际前安全性修复，不涉及按结果调参，归档继续价值不变，累计仍409/218。
