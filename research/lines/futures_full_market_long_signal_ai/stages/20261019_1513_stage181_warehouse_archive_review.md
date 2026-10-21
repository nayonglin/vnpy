# Stage181：历史仓单归档独立复核

记录时间：2026-10-19 15:13（Asia/Shanghai）。所属研究线：`futures_full_market_long_signal_ai`。本阶段是 Stage178/179 固定范围内的 source-only 独审，不是重要 alpha 突破，也不是归一化、特征或金融实验授权。

独立结论：Stage180 对冻结的 3,018 个日期完成了来源归档；本次唯一复核实际退出 0，`C/I/M=0/0/0`、`errors=[]`。接受其日期身份、URL、响应字节及哈希、报告 envelope、明确 body 日期、journal、预算和来源绑定一致性。物理单位、类型代码含义、历史首次可得时点、跨版本数量语义及训练资格仍未认证。

## 固定范围与实际执行

- 事前读取并沿用 registry、Stage178、Stage179、Stage175 的范围；不更新 LINE/registry，不调整源日历，不以结果挑选日期。
- Stage180 的唯一源进程由 root 通过同一 exec session18442 的 `write_stdin` 取得权威 `exit0`（chunk1d7d96）；不是把 launch handle 或观察延迟作为进程终态。其终端为 `completed`，结束于 `2026-10-18T20:18:35.123647+00:00`，耗时 `3081.803255292s`。
- root 在源终态后明确授权本次独审。冻结 reviewer/test 后，仅启动一次 `.py311/bin/python`，exec session6430，`exit0`，独审 receipt 计时 `7.689078166033141s`。无自动重试、续抓、替换 host、策略回放或复跑旧 suite。
- 逐个打开并独立计算 3,009 份新 body 的 SHA256/bytes，同时做 envelope、报告日期和轻量结构诊断；每份新 body 只读一次，合计 `233,164,015B`。输出逐 body 观察缓存并在全 body pass 后保存 checkpoint，再完成全域 accounting。
- 9 份复用 body 在本 reviewer 中读取次数为 0。20200102/20230103 继承 accepted104 probe/verification，20251113/14/17/18/19/20/21 继承 accepted174 全七源独审，并核 Stage180 对应旧 body 绑定及 preflight 证据；不重复旧七份原文审读。
- 复用部分共 `1,005,802B`，新旧归档合计 `234,169,817B`。数量值解析、归一化、网络、SQL、fit、cash 均为 0；未 import Stage180 作者计算。累计仍为 `409 fit / 218 cash`。

唯一 CLI（已经执行，不用于重跑）：

```text
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage181_warehouse_archive_review.py --manifest research/lines/futures_full_market_long_signal_ai/outputs/stage180_warehouse_archive/actual_run1/manifest.json --manifest-sha256 9d30a82c92ba52e25f753926a6a5595d31ba8eb007fad36fab50c2a7832cf285 --output research/lines/futures_full_market_long_signal_ai/outputs/stage181_warehouse_archive_review/actual_run1
```

## 全域一致性结果

固定范围为 20140519—20261016 的 3,018 个原日历日期，完整保持 sequence/date/format/URL/action 五字段及顺序，不把周末、任意自然日或产品观察缺失混成请求缺日。

| 项目 | 独立结果 |
| --- | ---: |
| 全日期身份、最终 response metadata | 各 3,018 |
| journal event | 6,028 |
| 实际新 GET start 记录 | 3,009 |
| 新 `http200_expected_envelope` | 3,009 |
| 旧 `reused_binding_verified` | 9 |
| 新 body 明确报告日期与请求匹配 | 3,009 |
| not_attempted / failed / metadata truncated | 0 / 0 / 0 |
| stop | null |
| metadata_bytes_before_terminal | 13,074,085B |
| 独立最终 metadata inventory | 18,511,031B |

所有 journal date terminal 与最终日期行、每日 response 文件内容及绑定一致；新 body 文件集合与 manifest 不多不少。实际 GET 起点间隔至少一秒、串行请求、单 report 及全局 bytes/metadata/time guard、9 份复用 preflight 在首次新请求之前等约束全部通过。计时约束依 Stage179 为阻塞调用前后的单调时钟守门，不冒称操作系统可硬中断请求。本次无失败前缀、未完成 body 或停止后日期。

独立重建的 scope 哈希：

- 日期序列：`0753e5f80227d3f6d7c73c8b8aae968d04e294d1f09dd4bdf5b5f08adbf3e8fc`。
- 全 action：`00b512f50ee5003d62066e8788a385e3dac0ba94210bdeee16b3ffec403c16d8`。
- 新 GET action：`3df6da82c92e72e54cae1a737a1ee29ad0979dd68347c25a182ccac8a028c387`。

“冻结日历上的源报告归档已齐”仅指这一归档范围；不等于每品种逐日有库存观察、不等于 2010+ 全史覆盖，也不等于数量已经可直接入模。

## 同一次 body pass 保留的源结构

新 body 中 2,793 份 JSON、216 份 HTML；连同复用部分，全归档是 2,798 JSON、220 HTML。结构组仅纳入完整、成功的 expected envelope；不以 partial/error body 生成正常 schema 组。本次无 partial/failed 日期。

新 JSON 的 `o_cursor` 均为非空 list，未发现 non-object 行。共 `899,785` 个原对象，逐日报告行数范围 177—479。没有 empty cursor 日期；即使出现空 list，reviewer 的定义也只是“空报告结构”，绝不会推断为零库存。

三代 row keyset 是实质后续解析边界：

| 新 JSON 范围 | 新报告数 | 原对象行数 | 结构 |
| --- | ---: | ---: | --- |
| 20140519—20231116（扣除两份旧复用日） | 2,312 | 690,733 | 11 字段：REGNAME、REGSORT、ROWORDER、ROWSTATUS、VARNAME、VARSORT、WGHTUNIT、WHABBRNAME、WHROWS、WRTCHANGE、WRTWGHTS |
| 20231117—20240320 | 82 | 32,860 | 在上述 11 字段中加入 VARID、WHTYPE，共 13 字段 |
| 20240321—20251112 | 399 | 176,192 | 10 字段：REGNAME、ROWSTATUS、VARID、VARNAME、WGHTUNIT、WHABBRNAME、WHROWS、WHTYPE、WRTCHANGE、WRTWGHTS；不再有 REGSORT、ROWORDER、VARSORT |

这说明不能把 2025 JSON 所见 VARID/WHTYPE 反投影给 2014—2023 旧对象；旧 `WGHTUNIT` 字段实际存在，代码语义仍须另证，不能说旧源无单位字段，也不能从后来的 HTML“吨”倒猜旧代码。

另有 7 组 top-level keyset，完整日期清单见结构输出：

| top-level 组的首末新日期 | 新报告数 | 主要变化 |
| --- | ---: | --- |
| 20140519—20150522 | 249 | 仅 o_code/o_cursor/o_issueno/o_msg/o_totalissueno/o_tradingday |
| 20150525—20180920 | 817 | 加 print_date/report_date/update_date |
| 20180921—20190702 | 185 | 加 singlenote_cn/en |
| 20190703—20191030 | 80 | 再加 showlength |
| 20191031—20240320 | 1,062 | 无 singlenote_cn/en；20220602 单列下一组，不含该日 |
| 20220602 | 1 | 上一组额外有 o_remark |
| 20240321—20251112 | 399 | 有 o_remark，无 print_date |

报告日期核对采用正文明确的 report_date/o_tradingday 或 HTML 可见 content_intro，排除脚本和仓库行日期。top-level update_date、HTTP headers 及本次 retrieval 时钟只归档，不据此签历史首次发布。

新 HTML 有 3 个 header/table 结构组：

- 20251124—20251204：9 份，34 tables，其中 33 份报告表头；“厂库/地区/期货/增减”2 个，“地区/厂库/期货/增减”7 个。
- 20251205—20260723：152 份，34 tables、33 份报告表头，上述两类分别为 4 个和 5 个。
- 20260724—20261016：55 份，35 tables、34 份报告表头，上述两类分别为 4 个和 6 个。

三个组均另有“地区/交割仓库/本日数量/增减”1 个、“地区/仓库/期货/增减”23 个。此处只识别物理 header 和表数，不合并厂库/仓库，不推断新增表代表何品种，不解析单位或数量。复用的 20251118—21 由 accepted174 保留其原参考，不为形式一致重新生成。

## 证据闭包与交付

文件均位于本线；下表 SHA256 均为完整值。

| 文件 | bytes | SHA256 |
| --- | ---: | --- |
| outputs/stage179_warehouse_archive_protocol/protocol.json | 5,113 | a67cf844699c8b2d1b34cc3cd66ac88eaae0c6bedd5621796d886f129cfbb0c5 |
| outputs/stage178_warehouse_history_plan/plan.json | 82,071 | 06129933ce2c892d6855ae7ba499a63b36b1b4bc4503c0163e4ee9cbc83d69b8 |
| tools/stage180_warehouse_archive.py | 26,096 | 2915357de51e456cc38f485510ab3380886d1b81e58643c43fc2f7406a82a62a |
| tools/test_stage180_warehouse_archive.py | 12,510 | 0fe770724f3b467b3016291ac8627c51c7b2b4d882e6ef873cb93bff5ca1a2b7 |
| outputs/stage180_warehouse_archive/actual_run1/manifest.json | 3,367 | 9d30a82c92ba52e25f753926a6a5595d31ba8eb007fad36fab50c2a7832cf285 |
| tools/stage181_warehouse_archive_review.py | 28,423 | cf395530c7915aba248a8a27b4c6d1589ebc9fb54a8526ce05e03da6580a11f7 |
| tools/test_stage181_warehouse_archive_review.py | 4,529 | 366ee26d3888b81b9db2e5032ba062d8f9abc39e62874b50602216ebe0c59a74 |
| outputs/stage181_warehouse_archive_review/actual_run1/receipt.json | 55,260 | da3524a88959b8c73a6499d7c9cf1137e336529e8519c016a248559523fddac7 |
| outputs/stage181_warehouse_archive_review/actual_run1/body_pass_checkpoint.json | 827 | bc3bdb1fc6ed077609658cb2951ab1ed0ec8c88eae4d2c91793d46e8473e13a5 |
| outputs/stage181_warehouse_archive_review/actual_run1/new_body_observations.jsonl.gz | 190,767 | 45bc521100947f053594bc622a2a8a70270731a6e1ef0710409a64d9a3560f33 |
| outputs/stage181_warehouse_archive_review/actual_run1/source_structure_groups.json | 123,324 | 1e56463571b56ab78b1d1bf7de338cedfbeadc7ec7a6d3e944c129032382d4dc |

复用接受链：accepted174 receipt `520c9aea78dc30fe08c5fcf0b77dd3b35bbebececbf88e6914f4001f08fa7022`；accepted104 verification `bca8ac6a4c1847513c3538d95e6ac78619cedf9c703a8dc33da77caaa6719304`、probe `6fb9d0eb617692326af5333cf861b55bbb8ae240bd76037ee844aca2c4c24a7b`；Stage175 decision `5fa28fd439ca77981140f6831d1101e9886459d56a5b364e2464907c7f79c116`。receipt 逐项保留路径、bytes、SHA 和旧日期继承归属。

复核工具的有限合成 fixture 覆盖空 cursor/错误 cursor、各 row keyset/non-object、HTML 真表头与通用错误表拒绝、日期冲突/absent、失败后继续成功拒绝、partial 不混入正常结构组。此前 5 个缺实现 RED→GREEN；第 6 个 partial 反例实测 FAIL→修正→6 GREEN（0.019s）。root 全静读后锁源授权，actual 未为此再跑 fixture 或旧 suite。Stage180 在唯一请求前也已修正 generic-table envelope 和 inspect 后时钟守门两处静态阻断，最终 6 fixture GREEN；这些均是实际 GET 之前的修正，不记作源重跑。

## 研究判断、限制和下一边界

现有维护者实现与官方两个公开 URL 分支的调研结论由 Stage171/178/179 继承，本轮按授权不再联网。独立实现不接受其静默 numeric coercion，也未把稳定 URL、HTTP200 或文件哈希当作历史原始发布 vintage。当前归档是本次抓取可见的官方报告快照；历史修订、Last-Modified、update_date 和首次公开时间的关系仍 unknown。

开始和结束反思均为：本阶段不是过拟合，因为未读金融结果、未拟合模型、未选择方向或优化标量，按事前固定全部日期只核来源。继续有限 source 研究有价值，因为完整日历和三代 JSON/三类 HTML 结构已明确，下一步能够据实判断归一化的必要缺项；但本轮终点就是归档接受，不擅自启动数量归一化或训练。

不新增/修改/删除策略参数或回测结果。期末权益、收益、最大回撤、Sharpe、总滑点、交易数、胜率均为未计算，不用 0 或旧成绩填补。物理单位、WGHTUNIT/WHTYPE codebook、仓库/厂库及汇总层级、跨格式可比性、连续产品覆盖、严格 PIT、特征映射、现金/生产资格仍是分开的未知；`C/I/M=0/0/0` 不能消除这些研究边界。下一步范围由 root 决策，本 reviewer 不自动扩 URL、重扫全 body 或继续旧 q。
