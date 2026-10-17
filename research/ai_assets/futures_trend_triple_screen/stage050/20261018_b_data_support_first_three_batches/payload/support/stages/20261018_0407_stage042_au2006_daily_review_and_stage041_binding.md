# Stage042：au2006 实际日线独立签收及041 reference 接合

- line_id：`futures_trend_triple_screen`；记录时间：2026-10-18 04:07 CST；不是重要策略突破。
- 原B同一引擎已接受039交付，当前只处理实际request `2175ea018b1e88a029df76629ede0767636baa752ae2e3c04aea4f024bdeb65b`：`au2006.SHFE / 2020-01-08 / full_session / 555`，物理Jan7 21:00至Jan8 14:59。request文件SHA=`6ea9aaacb616e7da841ea93c020eaecab593dc8cc6160b0f16d44d5d64714fd7`；existing0/missing555。
- 原039、035、013、037、040、036及已签收产物不修改。041原先未启用的草稿按root明确授权在首个prepare前定稿；首个prepare后041/042代码、041协议与所有进入指纹的资料保持不可变。未来行为改动必须另建版本。

## 独立数据结论

只接受当前精确日线key，P0/P1/P2=`0/0/0`。独立收据 `outputs/stage042_exact_daily_review/request_2175ea018b1e88a029df76629ede0767636baa752ae2e3c04aea4f024bdeb65b/daily_review_receipt.json`，SHA=`0b215c102d9d4eaf0da67bf2c17748e1c4ee2ec3b643ddea102f9dc198bad0c8`。

013已绑定原始 `raw/SHFE/au2006.csv` 的SHA=`2f300473dc8f521fe59e3c678ecb0973de14e5c1fb7b2b9217e8ac1169db8d7f`，快照10000行。Jan8不在013旧qualified/audit集合内，所以本次重新独立签精确一日，不能宣称旧013已经签过这个key。

准确合约DB只读一行查询与原始日线比对：O354.6、H364.44、L354.52、C360.68、V253483、openOI145032，六字段差均0；closeOI157344由原始已完成SDK日线提供，DB.closeOI明确N/A。真实source_id161/ns1578412800000000000，对应Jan8；真实合法后继id162/ns1578499200000000000，对应Jan9。所有原始值、来源及后继均在 `daily_checks.json` 留证，SHA=`2fd94cf10050e5177fd9aae5963cf938b0e5c73c90fa62187ca448f0668a832d`。

继承原013已接受快照与parent原终态绑定；原provider exit1和两个被拒target完整保留，不能改称整批成功。只重查本次准确DB六值，不重算全DB SHA；没有资格其他raw日期、连续合约或未来理论需求。

独立日线工具 `outputs/stage042_exact_daily_review/review_exact_daily.py`，SHA=`69225d3e8114e455b04eade5ca443bc2880a7f7341e145d3f6f04849624e5ad3`。实际 `.py311/bin/python ... --request <当前实际绝对路径> --request-file-sha256 <上述SHA>`，exit0、0.286秒。当前工具仅单request的一项requirement，已进入preflight绑定，不再在原文件增加多key行为。

## 分钟真实缺失与必要采集

只读精确检查已签来源：s491_085（13275行，SHA=`90859b2d16e04ddf33bf89048eaeaf3bf88f16da6dfba9875a86d60347464cf7`）、local_0307/459（2235行，SHA=`6412a0611bc4b7f5228dcef180b9393064d3983a21e956d1c470bb19bf3c5e69`）、local_0308/462（4455行，SHA=`d5f22517bb90818d69c20f4697f620a1f633fef10e3e4e075180fbfb0de9876b`）。三源实际SHA匹配原manifest，与555 canonical grid交集均0，故真实缺失为全555，不能本地签分钟交付。

精确missing列表与来源检查另存 `local_missing_checks.json`，SHA=`50585a4786b8910e691557ab4f7736171d02eea69a3319b3eb75c9fcd8d01c18`。原037缺少这个新日线参考，直接重跑prepare会确定失败；因此另定稿041，只增加被显式指定独立日线收据的来源，不放宽资格。

## 041实现与有限验证

本agent实现041，所以不自称对041代码独立review；root已另行读取差异。最终工具SHA=`e4320208cc70d25959db7f66b80518ac0f6ceaaf3e6a61a97bdfc23f008bfa0d`，协议SHA=`bca57e3ae8011dba018eb68b8b59408f2584737f8398406103798aa09efce830`。对冻结037的完整diff在 `outputs/stage041_provider_binding/source_diff.patch`，SHA=`3f599dd5c00bbe65fb82e0675348886196fd720d1ad6362bb72ddaeb5dd2bac8`。

最小新增合同：prepare-only `--daily-review-path ABS --daily-review-sha256 SHA`；收据绑定实际request digest，接受key为实际requirements非空唯一子集，CSV/audit/checks身份及行数精确一致；独立六值/真实后继/DB.closeOI N/A必须齐全且全输入哈希绑定。不能覆盖原CSV、013原approved或rejected，其他targets仍沿原037选择。保留原每包最多8合约。packet保存review路径与SHA，run/worker只从该packet重新核验，不接受run-time新review flags。

原collector、正常SDK鉴权/端点、worker/run主体、570/600秒预算与父子闭环未改。full555全部canonical grid、完成后继及七值聚合要求不降；anchor只保留原单anchor权利，不提升为full。

实际compile通过。6项有针对性的纯reader fixture exit0/0.233秒：实际单key、多requirement的非空子集通过；错误request digest、越界key、缺六字段独立review、绑定但DB check数值不一致均拒绝。结果SHA=`b2b9aa5aa593f746cec652e43ab253462a6b9bbcc4f0a78f35fba7390edde2e2`。没有扩旧suite或1590来源重资格。

当前真实offline prepare exit0/0.463秒，packet为 `outputs/stage041_exact_daily_request_provider/request_2175ea018b1e88a029df76629ede0767636baa752ae2e3c04aea4f024bdeb65b/packet_000`，covers_whole_request=true、target_minutes555；preflight SHA=`35cf5874605684b32602c745c4cca364e0d12c750b121c7e04fa782e02bc63d2`。此处只证明离线接合与审查算法，没有实际分钟交付结论；root另审后自行正常网络run，真实terminal后再独立分钟签收。

## 参数、范围与反思

- 策略参数与金融结果新增/修改/删除均0；权益、收益、DD、Sharpe、滑点、交易数、胜率均N/A。本阶段金融/网络/模型/订单均0，reviewer不写engine response。
- 调研结论：沿已接受013/011/021/037本地来源与合同，未外网泛搜；新资料不能替代准确raw、DB及完成后继证据，故不扩大调研。
- 开始及结束过拟合判断：否；只处理冻结B当前真实请求，不选收益日期、重排请求或调参。
- 开始及结束继续价值判断：是；新参考与精确缺失已核清，允许root用原正常SDK补当前555；不构成收益、全源质量或promotion结论。
- TODO：root观察041真实terminal，再独立签当前555分钟；同一B引擎继续，完整终态由038另做金融审计。
