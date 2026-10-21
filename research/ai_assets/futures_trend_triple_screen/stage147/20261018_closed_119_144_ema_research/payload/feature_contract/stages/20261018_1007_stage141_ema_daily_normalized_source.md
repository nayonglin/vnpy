# Stage141：同源真实合约日线的一次无损规范化候选

- line_id：`futures_trend_triple_screen`；时间：2026-10-18 10:06—10:07 CST；工作区：`/Users/mac/Desktop/fian`。
- 性质：执行root Stage139的一次可逆七列投影，非重要突破、新策略、新资格、feature build、金融readiness或正式实验臂。沿138已读registry/LINE及121/123/124/126/127；本线已有但未入registry，本次不修索引。
- 仅新增本文及 `outputs/stage141_ema_daily_normalized_source/`；没有修改旧源、LINE/registry、135/136、模型、行情、Git或其它研究线。不派子agent。

## 调研、继承边界与判断

沿Stage138唯一一组[TqSdk官方文档](https://doc.shinnytech.com/tqsdk/latest/usage/mddatas.html)/[官方GitHub API](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)调研，不新增搜索或策略idea。其语义说明不能替代本机资格，Elder机制判断沿121/123；本次无公式、窗口或执行参数选择。

按Stage139固定边界：候选拟接受依据是**已接受基准同源继承＋选定七列无损规范化＋138有限跨源样本**，并非116,394行都重新聚合分钟/独立验证价格。013的4,500 exact-key资格没有外推；全量原厂商零量行保留；不按未来后继筛掉合约最后bar，不补session、不前向填充、不拼接/调整价格。缺session仍由124/127按原日历重暖。138已经辨明native后补carry与DB真实键的区别，本次直接取DB，未调用loader。

## 唯一实际命令与快照安全

命令：`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage141_ema_daily_normalized_source/export_daily.py`。

真实工具终态：chunk `364151`，**exit 0**，1.611621875秒；`actual_terminal.json`保存命令及原工具输出，没有自动重试或第二次导出。

原DB只调用一次 `read_bytes()`，SHA先核为 `273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`，随后 `sqlite3.connect(':memory:')`、`deserialize(database_bytes)`、`PRAGMA query_only=ON`，查询仅对该已hash内存快照执行。没有hash路径后重新打开活动DB。112,726,016 bytes；读取前后DB大小/mtime完全一致，无WAL/SHM。

读取与027完全相同的 `interval='d'`、2019-06-01 00:00:00至2026-10-14 00:00:00、806个accepted metadata合约scope。参数继承A_OFF，并核其contract_sizes/priceticks与A0一致；日期按上海本地午夜日语义，未创建新calendar。manifest保存21项有限source bindings，包括A_OFF preflight/context/参数、A0参数、原calendar、027源/receipt/manifest、原下载器/导入器、执行tick源、138证据、139及实际502→827→840→847 carry源。未重hash7663级旧源闭包。

## 规范化结果与实际自检

输出 `daily.csv` 严格schema：`date,vt_symbol,open,high,low,close,volume`；UTF-8无BOM、LF、按 `vt_symbol,date` 排序，数字使用 `.17g` float64 round-trip。只对规定七列投影无损，不把省略的DB其它字段说成已导出。`exact_keys.csv` 仅存 `vt_symbol,date`，与daily逐行键完全一致，manifest只引用这一份key文件，不复制到每行未来feature。

| 实际检查 | 结果 |
| --- | --- |
| 行数/真实合约/原日历 | 116,394 / 533 / 1,786，与138相同 |
| metadata合约 | 806个，真实合约格式且排除alias；其中533个在规定scope有行 |
| 价格/量 | 所有选定OHLC有限、正价且形状合法；volume有限非负；无静默修复 |
| 精确键 | 116,394个唯一 `(vt_symbol,date)`；日期集合等于原global calendar |
| 零量 | 全部1,468条保留，没有正量筛选 |
| 序列化 | 每个float的`.17g`解析回float64位一致；实际写出CSV回读的键及五个数值标量指纹与内存源相同 |
| 源/输出标量指纹 | `60976debf28e9fd52d1ba596ce1590ca2a021b3507f99daeab62ae65d6fd52dd` |

这些是导出器的实际一致性自检，不是142独立来源审查、所有价格正确的独立证明或新的exact-key资格。没有新增镜像单元测试、旧suite或native运行。

## 全SHA与后续调用接口

| 产物 | bytes | SHA256 |
| --- | ---: | --- |
| `daily.csv` | 6,147,949 | `71dd740fb605e1ff8365fb6fc7236ab6d19f8d90a7f7be72c753d29733b7df5c` |
| `exact_keys.csv` | 2,625,366 | `5e8493067d422c27ba7e4512dfbb30ea74de11193b46d0a71547940ed3f48317` |
| `candidate_manifest.json` | 12,183 | `96eea70a16b7a5715f697aaa06a4e34107e328109849ca573eba88be78cc8b90` |
| `export_daily.py` | 13,779 | `f3966a2b55436d8f06c7d1757d54d5bec65cf1b64400132cfca405129bd1053b` |
| `attempt_started.json` | 184 | `156d0ce5641e94d6e6b554bea53b13b16044a94dc96451c1c2b9abd41c9bcf97` |
| `actual_terminal.json` | 904 | `6e67a1fd7979d27547500cef0c72b2f0d20ee0dba80938aea620f9d1fc2112d2` |

manifest保持 `status=pending_independent_source_review`、`candidate_only=true`、`qualification_granted=false`、`qualifier_sha256=null`。142需由另一作者对同源DB→CSV逐值无损、keys/源级边界与有限原CSV样本独立签研究级exact-key qualifier；141作者不能拿candidate manifest SHA冒充资格SHA。

142接受之后，127的输入形式才为：`load_bound_daily_csv(daily_path, sha256='71dd…df5c', qualified_keys=frozenset(exact_key_rows), qualifier_sha256=<142实际资格SHA>)`。本次没有调用该loader、`build_ema_rows`或任何feature build，38bar覆盖仍待固定feature build。原execution_tick源SHA `95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272`及139的12/6公告证据绑定已留manifest；未来按u已知D有效规则赋tick，未更改风险/成本tick，也未生成tick feature行。

## 参数、绩效与反思

新增/修改/删除策略参数均0，新增/修改/删除回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均 **N/A（未运行）**。feature/native/金融/模型/provider调用0；`financial_ready=false, production_qualified=false`。

开始及结束新增过拟合判断：**否**，源scope、零量保留、无损规则已由139在未知EMA收益前固定，没有收益筛选或救参。开始及结束继续价值判断：**是**，这一可逆投影已使142可以独立审查实际候选；141工作到此暂停，不自行重资格、继续清洗、取新行情或进入feature/金融。后续仅由root组织142独立审查，当前目标仍active、未达成。
