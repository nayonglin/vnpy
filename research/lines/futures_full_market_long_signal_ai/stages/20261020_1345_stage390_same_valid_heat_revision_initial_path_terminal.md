# Stage390：同未来区间热负荷修订，保留首轮路径失败并完成机械适配单例

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 13:45 CST汇总。先读registry、本次冻结protocol及388实际依赖manifest。
- 本阶段非重要策略突破，是有限物理数据样本；**金融含义未被检验。首轮对象路径失败，不等于天气机制被反证，也不等于这两个业务run不存在。**
- 原protocol：`outputs/stage390_same_valid_heat_revision/protocol.json`，SHA256 `e7ee6cb240cb74fcb251cbdec126ebd58dba59c6c59aba4cb2d3f16c0c84bfe9`，未改。

## 预先固定的科学定义与实际前验证

旧run `2020-08-30T00:00Z`，新run `2020-08-31T00:00Z`，同一未来区间 `[2020-09-02T00:00Z, 2020-09-09T00:00Z]`，原生每6小时29个结点。旧lead72—240、新lead48—216，单一 `gec00` control、2m TMP，阈值30℃先逐结点截断，再28区间梯形积分乘6/24，revision为new−old。任一结点缺失则该原生格点结果未知；必须同坐标、同scanning网格，不隐式重采样。只原生格点结果与固定IA/IL诊断，不做面积、产量、集合或金融聚合。

新增一个独立工具与一个最小fixture；没有跑旧suite：

- `tools/stage390_same_valid_heat_revision.py`，19,095 B，SHA256 `02e4b987c7b52325dfca1514011e6260924896186107e38dccb7d9af62d0fa00`。
- `tools/test_stage390_same_valid_heat_revision.py`，1,751 B，SHA256 `b59e97329895df4156db87796f0144ab78b3d737a87b00754080b536d480f132`。
- 唯一fixture先RED（integrator未实现），后GREEN：1个测试，0.001秒。独立手算路径 `[29,31,29]℃` 先截断再积分为0.25℃·日；验证正修订、new缺失不污染old但revision未知、坐标颠倒及scanning变化拒绝。此fixture只证明本次新物理计算核心，不证明外部档案存在或金融alpha。
- `prepare1/source_freeze.json`，1,841 B，SHA256 `365a7bc6b6c41db36471717061d6842067a2744dcbc17eb49f4e5463a49934b7`。实际前脚本/fixture/protocol/红绿/388依赖manifest绑定已保存；388既有模块与distribution RECORD哈希未变，无再次安装。

## 唯一actual与原始响应

实际进程handle `60892`，最终exit1，所有在途请求排空；没有因观察超时重启，没有自动重试、替换样本或扩展日期。

首批4并发idx请求均返回HTTP404、XML `NoSuchKey`：

| 固定请求key | S3 RequestId | 原始body SHA256 |
| --- | --- | --- |
| `gefs.20200830/00/gec00.t00z.pgrb2af072.idx` | `0PJ8XBBEQRK4XZYN` | `1f84853b264028afa0f83bd517aa07b046fb0555fc2de258d79175511eae1fb0` |
| `gefs.20200830/00/gec00.t00z.pgrb2af078.idx` | `0PJD2RDC324W9DND` | `9d02a3955da7ee67d4b8eb144e221bb167f14b8bc4b31d8295fbe1435c478e3b` |
| `gefs.20200831/00/gec00.t00z.pgrb2af048.idx` | `6DNVXKKACMWE0EGG` | `30e740155815c04fd02da5679e4f549498d2c76841b22aedbe705d0fdd2bc272` |
| `gefs.20200831/00/gec00.t00z.pgrb2af054.idx` | `0PJ6R9K35CMHXNYY` | `756992dca52894c0c3f0cbc854433add1aab6c939da8804323d0e0a7b5426b7b` |

每个原XML313 B，共1,252 B；全部原请求、headers/status、正文与哈希在 `outputs/stage390_same_valid_heat_revision/actual_run1/`。`manifest.json` 为13,401 B，SHA256 `5478c0201d1a292143cbce7273b458957d890afd140a49a6c4a75b63227095ee`。

代码在首次错误后停止发新任务；原首批4请求已在途，故终态恰4 idx、0 Range、0 decoded field。预算中的116请求不是必须花完的数量。`body_reserved_bytes=16384`是为4条错误响应各预留4096 B的安全预算；**实际网络正文是1252 B**，不能将预留值冒充下载量。

## 判断、变更账本与后继边界

[NOAA开放登记](https://registry.opendata.aws/noaa-gefs/)和[维护者README](https://github.com/awslabs/open-data-docs/tree/main/docs/noaa/noaa-gefs-pds)的既有调查与387/388实物证明：不同年份可能有不同目录层级，旧README模板并非所有年份精确key合同。本轮只证实root冻结的旧flat模板对应4个2020 idx key不存在，**没有S3该run目录证据，不能把这四条404泛化为“2020档案缺失”**。

按root预先指令，立即提交具体路径失败证据，由root决定是否允许一次保持科学定义不变的有界机械定位；本agent没有先查询替代目录，也没有修改protocol、日期、成员、变量、阈值、积分法或网格规则。若批准适配，必须另记录来源定位与新的实际调用边界，原actual_run1失败永久保留，不能覆盖成成功。

- 新工具2个；金融参数新增/修改/删除0；金融回测结果新增/修改/删除0；原388、模型、370/378账户、LINE/registry、行情/SQL、生产/CTP/委托/邮件/定时任务/Git均未改。
- 本轮fit0、cash0、prediction0、行情API0、SQL0，金融partial0；这是天气取数失败，不是资金回测partial。期末权益、收益、最大回撤、Sharpe、滑点、交易次数、胜率均N/A。
- **开始/结束过拟合判断：本次未用收益择日期、阈值或路径，未发生金融救参；长期同史自适应择题偏差仍存在。目录适配不能变成挑一个成功日期。**
- **继续价值判断：是，限定为原两个run的机械路径事实定位。** 这是原来源物料问题，当前还没有热负荷数值结果；不因只出现404否定经济机制，也不因fixture通过声称源已接通。完整目标未完成、无加注资格。本轮后继动作暂待root按原授权边界裁决，不重复取数。

## 后继root授权的4次有限目录定位（13:43 CST）

Root随后明确允许只同两个00run、最多4次ListObjectsV2小XML（各maxkeys20、32KiB、0retry），定位原A产品，不读idx或GRIB。本agent执行恰4次，原文/headers/hash保存在 `locator1/`：

1. `prefix=gefs.20200830/00/` 与 `prefix=gefs.20200831/00/`，各HTTP200、431 B、KeyCount2且不截断；都明确包含 `pgrb2a/` 和 `pgrb2b/`。
2. 在已知A目录下查询原文件名的精确prefix：旧 `gefs.20200830/00/pgrb2a/gec00.t00z.pgrb2af072`，新 `gefs.20200831/00/pgrb2a/gec00.t00z.pgrb2af048`，各HTTP200、311 B，但KeyCount0且不截断。**空精确prefix不是整个pgrb2a目录为空。**

因此已证原flat模板漏了A目录层，同时原文件名模式仍未定位；没有借HTTP200声称exact keys已找到。locator总正文1,484 B，新增idx0/GRIB0；合计本390已发8个source请求、2,736 B。目录预算已耗尽，终态为 `A_directory_confirmed_exact_filename_unresolved`，未自行追加目录请求、修改科学定义或重跑actual。已向root说明如果再定位，需要各1次A目录本身的maxkeys20小list，而非继续猜测文件名；完整后继上限将由124增至126，须root先调整有界授权。原失败与全部目录响应均保留。

## Root明确扩为126次source预算后的机械适配与完整物理单例

Root随后授权最后2次plain A目录list，见同样两个run的 `pgrb2a/` 本身，各maxkeys20/32KiB/0retry，并允许在只涉及目录/零填充时直接冻结amendment执行一次fresh run2，不必再次确认。13:45两个目录都真实返回20对象且截断，原XML各5,292 B，SHA分别 `627dc3dc5207dfafb77074797ff921af73550448a5990f9f0334a4977241b5c8`、`32fcdfe72607e6ca19d1a5a30bd07663136323a4106f99edd4583e84887e6f90`。

实际basename含 `gec00.t00z.pgrb2af06`、`gec00.t00z.pgrb2af102`，所以原A/control的正确locator模板为：

```text
gefs.{YYYYMMDD}/00/pgrb2a/gec00.t00z.pgrb2af{lead:02d}
```

改的是A目录与lead最少2位宽度，既不选择另一分辨率，也不改变任何物理/金融假说。冻结与原证据保全：

- `locator_amendment.json`：3,021 B，SHA256 `fa88fd90097ba85276f730a246c657f17aeb5418a5548ea029a97a7243c06143`。
- 原源码在 `prepare1/source_snapshot/stage390_same_valid_heat_revision.py` 原样保存，19,095 B及原SHA不变；原protocol、actual_run1、source_freeze1不覆盖。
- 新脚本19,516 B，SHA256 `c123cacdd13b467c71734281877cc642e69baeeea9c2a9dcc830b202a7201b12`；`prepare2/source_freeze2.json` 2,873 B，SHA256 `ce008c93514926501a2f84de360fb3227e731569293470dbb7643dfae9f8fae7`。
- integrate/paired/grid/decode/summary五个函数的AST与原源码逐一相同；没有重跑fixture。除locator仅改变fresh run2物料路径、amendment绑定及累计请求/字节约束。

唯一获本次amendment授权的 `actual_run2` 在13:46:55—13:47:38 CST执行，真实session `65736` 返回exit0，耗时约43.294秒；116请求（58 idx +58单条TMP Range）、2,944,422 B。58字段全部通过：单GRIB2头/长度/7777终结、精确idx偏移、HTTP206、K/2m/instant/控制成员、起报/valid-time/lead身份、全部格点坐标和scanning一致。actual grid为 `regular_ll`、1°、360×181=65,160点，所有结点缺失0。没有整GRIB对象下载、插值或换源。

`actual_run2/manifest.json`：215,260 B，SHA256 `f1ec08e06afef1e41f8c5f6887c5dba0af866a96d367c3cca58dae8b67be5935`。

`actual_run2/native_heat_revision.npz`：2,806,504 B，SHA256 `eee2b814cdefd8f7f2454face3a2c2bd75bf48ab8d22ec577701c8ee7e0c229a`，保存完整原生格点的old/new/revision EDD、各自missing mask、经纬度以及共同29 validtime；原始58单条消息与idx可独立重解码。

| 固定诊断位置 | old EDD（℃·日） | new EDD（℃·日） | new−old（℃·日） |
| --- | ---: | ---: | ---: |
| IA：42°N，93°W原生格点 | 0.475 | 0 | -0.475 |
| IL：40°N，89°W原生格点 | 0.1875 | 0 | -0.1875 |

所有65,160原生格点的old范围0—75.2875、新范围0—72.42、revision范围−11.07875—+13.81℃·日。**这些全域范围包括海洋和无作物区域，仅作数值诊断；不是面积加权农业损害、产量损失或做多分数。** 两个锚点在此样本预测的过热负荷降低，不能据此推出国内期货必跌或给定旧52之外存在可交易增量。

起报后37小时的历史重建假设仍明确保留；实际数据对象LastModified在2020当日，而idx后制于2024，不能把它们当严格历史first-seen。单control的预测热负荷也不是集合预期损害。尚无连续历史、全作物暴露或金融资格。

最终合并账本 `combined_source_ledger.json` 合并4阶段，**126 GET = 原失败4 + locator1四次 + locator2两次 + run2字段116**；HTTP404四次、HTTP200六十四次、HTTP206五十八次；实际正文2,957,742 B。2次实际程序调用如实保留（首次错路径失败、root明确授权机械修订后成功），不冒充第一次直接成功，也不称自动重试。预算未超，未增加数学fixture执行，fit/cash/金融partial/行情API/SQL均0。

结束判断更新：本次继续有价值，已从单个温度时点推进为同一未来区间的原生热负荷预报修订实物；没有按收益调参或补挑赢家。它支持下一步独立核对已发布作物暴露与是否值得有限历史样本，仍不构成成本后alpha、小止损或增加投注资格。数值原件提交root指定389 reviewer独立终态复核一次，作者不代替独审结论。
