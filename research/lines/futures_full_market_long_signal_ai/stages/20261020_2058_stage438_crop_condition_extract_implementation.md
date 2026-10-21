# Stage438：原 Crop Condition 有界提取器实现完成，actual 未执行

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-20 20:58 CST。
- 本阶段仅实现，从 registry、LINE 当前头部、431 和 root 冻结的437承接。根 scope SHA256 为 `8a2cdd97ff0bf76ab4ced7377ce17e90d4911a219031dbc2954f6fc0c74309c5`。不修改 LINE、registry、旧代码、原数据、模型、账户、生产或 Git。
- 资料与判断：沿用437已核 NASS 原五档/修订政策、术语定义及维护者 rnassqs；本阶段没有新增联网、安装或资料搜索。全国 GE 只代表评级比例，原文可修订且非市场预期差；此实现仅回答已有源是否有可提取的原发布内容，不证明做多方向、alpha 或金融资格。

## 实现边界

`tools/stage438_crop_condition_extract.py` 为纯标准库有界工具，导入不做 I/O。actual 需 root 的授权 JSON 严格绑定冻结 scope SHA、代码 SHA 和全新绝对输出目录；授权缺失 CLI exit2，不建输出目录。输出目录已存在则拒绝，禁止自动续跑或自动重读失败源。

前置仅核437列明小型 metadata/index/manifest 身份与 schema、数目和来源身份；309份唯一原 Progress TXT 在 actual 中各只读一次，并从同一字节对象核 size/SHA，再解析两作物。缺表、缺档、非数字、非唯一标题/表头/全国行、合计不100、原文发布日期缺失/冲突等均保留 unknown、候选原行与行号，严格不从文件名、HTTP或档案时钟猜日期。coverage未印不填数且不自动否决五档。

保存 Corn / Soybeans 五档、GE、全国标签/原行、参考周、唯一正文 release 与metadata比较、coverage原文、同报 previous-week/year、原修订/发布时间政策段落及行号。标题别名仅按三个样例的 `Corn`、`Soybean`/`Soybeans` 识别；未知日期留unknown。root明确同意：仅该表原注写明 `- Represents zero.` 时将原token `-` 按源定义为0，并保存token与定义行号；未明示则unknown。

相邻变化只用立即前一原报告的 current GE；要求两端已知、参考周同年且差7日。中间缺表不能跳过；跨年、非7日、同release多个原版本均unknown。同release多版本的后继也不能任取路径作为前版。修订诊断比较完整五档，GE相同仍可记录类别修订；同报 previous-week若明确印日期，必须与前原报reference相同，否则诊断unknown。不会用同报 previous-week代替原上一版。

## 小型验证与例外

使用已读取的 TDD 技能先写五个重要方法：缺实现时5个预期失败；初实现一处 fixture手写行号10应为字面第9行，人工数行后修正。按root/439要求补同发布日期多版本、明确previous-week日期两项：对应缺失行为先失败，再最小实现，最终7/7通过，0.023秒。没有扩大套件或遍历309正文。

metadata preflight 首次在一条不存在 `status` 的原401源记录上 KeyError 终止，raw读取0；追踪确认是 `2020-08-31` 的 `reused_exact391_original_no_GET` 已有复用模式。只接受其 `ok=true`、TXT角色、与 original391_body 相同SHA/bytes身份，不读旧391原文/headers/receipt，不新GET。最终前置 exit0：总index319、Progress309、唯一body309、重复release0，308 HTTP200＋1该复用，raw读取0。

原格式检查严格只限431指定三份TXT，各1次、唯一3份：2018-07-23、2020-08-24、2024-09-03。没有后续重读。格式上的注意点：大豆原题是单数 `Soybean Condition`；两作物全国行用 `18 States` 而非 `United States`；`-` 的原文零定义只能就本表识别；2024-09-03 为周二原release、参考周9月1日，不能硬编码每周一。2018 Corn/Soy GE 72/70、2020 64/69、2024 65/65是431既有三例格式证据，不是本轮309份提取数量/结果。

## 文件身份与 CLI

- 代码：`tools/stage438_crop_condition_extract.py`，29960 B，SHA256 `0734570ce5e0f29199a9e068419f2a400345a53714b5b1ba2a67d91d7381f870`。
- fixture：`tools/stage438_crop_condition_fixture.py`，7999 B，SHA256 `469c45fad856fc7a0e50c2391165dcb0a15b9f562066f2e48b52db1849cdc29c`。
- 验证：`outputs/stage438_crop_condition_extract/implementation_preflight/preflight.json` 与 `implementation_verification.json`。

root实际命令（本agent未执行）：

```sh
.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage438_crop_condition_extract.py --scope research/lines/futures_full_market_long_signal_ai/outputs/stage437_crop_condition_scope/scope.json --authorization <root签发授权绝对路径> --out <授权绑定的全新绝对输出目录>
```

最小授权字段为 schema=`stage438_crop_condition_extract_authorization_v1`、authorized=true、authorized_by=`root`、scope_sha256、script_sha256、output_dir、max_original_body_reads=309、one_actual_run=true、financial_authorized=false。各字段严格类型和值相等。

实际输出：`startup.json` 和 `terminal.json` 各1份；`reports.json`保留309报告及每份两作物；`crop_rows.jsonl`保留618报告×作物行（含unknown）；`summary.json`按release year×crop列总数/已知/相邻变化数，并列共享release、GE/变化分布、缺失冲突、完整五档修订例子、原weekday/reference gap、原firstseen unknown及操作计数；前置身份另存。实际计数与分布目前仍未知。

## 操作与反思

本阶段 actual启动0、terminal0、actual raw读取0；探索格式样例读取3且唯一3。HTTP/市场API/SQL/价格Y-score/fit/cash/futureD/旧原文写入均0。新增/修改/删除策略参数和回测结果均0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、胜率均N/A。

开始/结束新增按收益调参过拟合：否；只实现收益前冻结的原源定义，不读新收益。长期自适应择题与历史复用风险仍存在。继续价值：是，仅限root另行签发的一次309本地原文提取及独立源审查；来源不足即停，不扩天气/空间/下载工程、不拿来源工程当收益进步。下一步由root运行actual，另agent独审新提取；价格、经济假说、训练、现金、生产仍需各自既有约束，完整高收益低回撤目标尚未完成。

## root实际终态补记（2026-10-20 21:10 CST）

root随后已按冻结脚本单次执行actual_run1，exit0、0.961223秒。原正文309份各读一次，同读SHA/bytes校验309；618槽，corn190/current与180/原相邻，soy172/current与162/原相邻；无新增HTTP、市场API、SQL、价格/Y/score、fit、cash或未来D。source439单次8原文/14582项有限独审完成，remaining_core_problems=0。原作者implementation阶段actual0描述保留为当时事实；当前实际以root_completion_receipt.json及439终态为准。
