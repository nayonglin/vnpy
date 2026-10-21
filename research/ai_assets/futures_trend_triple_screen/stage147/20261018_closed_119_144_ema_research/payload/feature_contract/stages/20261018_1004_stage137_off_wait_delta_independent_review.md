# Stage137：新135复用层代码与真实159份交付的有限独立联合审查

- line_id=`futures_trend_triple_screen`；审查时间：2026-10-18 09:57–10:04 CST；reviewer=`off_wait_delta_review`。
- 先读registry、135设计、134最终独立收据及audit-only snapshot、136实施记录、新两源与原061/021实际源码。registry尚未列入已有本线，本审查不修registry/LINE；唯一新增本stage及`outputs/stage137_off_wait_delta_independent_review/`。
- 非重要策略突破，不是新金融臂或实盘候选。调研继承121/123原著与GitHub有限调研；本次判断来自原061/021接口和实际已签bytes，没有新alpha假说，未新增网络检索、provider或行情重聚。

## 结论与资格范围

**P0=0、P1=0、P2=0；接受新135层为限定精确键的研究数据层。** 新入口保持真实065/B_OFF身份，兼容原061的通用数据schema；没有冒充063/B_TS终态，也没有使用134收据替新dataset自签。原manifest继续保留`frozen_pending_independent_review`、`new_layer_qualified_research_data=false`，未修改任何字节。独立资格由本次另行生成的收据绑定原manifest SHA，原061 loader已真实只读接受一次。

独立收据：`../outputs/stage137_off_wait_delta_independent_review/review_receipt.json`，schema=`stage061_independent_wait_delta_review_v1`，SHA **`b3fbb16d219484bdac9329e6c4f12db18a3b762de3adbea7b79710c79f8dee68`**。其中`qualified_research_data/exact_rights_confirmed/old_key_values_unchanged=true`均有以下限定事实依据，不代表全市场、完整金融账户或生产资格。

| 判断项 | 结论及依据 |
| --- | --- |
| 新135代码与真实来源 | 接受；public入口固定最终134 snapshot/review SHA；133真实exit1、065 context/preflight/failure/capture、087 owner及原run路径完整绑定；capture只核bytes，没有解pickle或读partial PnL |
| 实际交付选择 | 接受；仅159个原gate commit与159个accepted resolver pointer，集合及receipt/data四身份完全相等，原owner input_fingerprints、request canonical/file SHA、fingerprint、sequence、response、021收据和完整source闭包均闭合 |
| 冻结数据与权利 | 接受；独立从159份已签data bytes重建36,391键并逐七值核新overlay；rights的full/anchor和每键proof_requests均精确相等，未将anchor升full |
| 旧键不变 | 接受原事实证据；159次原021严格等值gate commit的`old_keys_changed`均为整型0，且134已独立绑定；本次没有重建global RAM或全市场基底，未来append仍须走原equal-only拒绝冲突 |
| 最后CF505请求 | 排除；digest `7422216c316b1eeea381af05e31318dfbea8903ffe77c31c6c9b6c7cf2c087eb`仅prepare，无response/commit，未进入source闭包、overlay或权限 |
| 旧190层、151/8既有资格 | 继承；旧061190交付及两anchor只核身份引用，未合并、重存、重审。151及8份原021/134完成bar、daily与来源资格是继承，没有重新认证全市场 |
| 完整B金融或新金融readiness | 未接受；原B真实exit1及11attempt/4accepted保持；未读或解释partial绩效，未构建金融readiness、runner或新账户 |

## 代码审查的具体位置

- `tools/stage135_accepted_off_wait_delta.py:38`：新origin validator独立处理134审计projection及真实065失败，不调用原061旧终态校验器；`66`只绑定压缩capture bytes；`128`明确旧190层仅身份继承。
- 同文件`:158`：用实际resolver/gate双记录选择commit；`:175`核四身份；`:179`及`:193`原owner/source与fingerprint；`:184`canonical请求；`:197`response；`:201`021与source闭包；`:208`精确requirement；`:217`七值跨receipt冲突拒绝；`:230`计数及134范围比对。
- 同文件`:239`排除无commit失败；`:247`发布前源漂移检查；`:256`17g序列化，原061 loader`:413`用round_trip读取；`:260`作者manifest保持pending且无自签；`:273`新目录存在即拒绝；`:280`actual SHA钉死；`:294`runtime.OUTPUT转临时目录并恢复。
- `tools/test_stage135_accepted_off_wait_delta.py:187`及`:217`：静态审查两个有意义fixture组合，来源/终态/闭包/同bytes poison、相交scope/七值冲突/full-anchor/失败排除/原容器接合均有覆盖。继承作者已存在GREEN证据`f4b5b3/exit0`，**没有再次运行这两个方法或旧suite**。
- 上述是接受理由和审查定位，无剩余可行动P0/P1/P2，不要求作者为审查再改源码或追加测试。

## 一次完成的真实数据重建

自有`review_actual_data.py audit`不导入或调用135 builder，不调用原021 parser或价格聚合；按相同冻结数值栈独立解析159份已签data bytes。JSON/CSV解析均使用本次已核SHA的同一bytes；原request、receipt与source来源保持原资格。必要source集合独立构造后与新manifest **2,783项逐项完全相等并核SHA**，没有遍历重hash capture的7,663个全市场fingerprint。

| 实际结果 | 数值 |
| --- | ---: |
| accepted deliveries / unique keys | 159 / 36,391 |
| qualified full / qualified anchor | 36,345 / 36,391 |
| explicit anchor-only | 46 |
| 原实际appended / existing request keys | 31,703 / 4,688 |
| 七值或权利不一致 | 0 |
| 实际交付间重复键出现次数 | 0（冲突保护由代码及既有tiny fixture覆盖，未伪称实际存在重叠） |
| 必要来源SHA核验 | 2,783 |

逐键七值、full/anchor及proof的独立规范摘要SHA为`e31c6ebe05c74ff1b34d955e2d543ec3f15521409c40030bdf54a47d6f6a2048`；独立必要source map规范摘要SHA为`6c60cbb7df9b7fd57288fd6a630292684043ad8081bf5ddce3a0a2471ec39555`。机器证据`actual_data_audit.json` SHA **`12820f705a16b61e42798762ccb60e5a8ad901ce1e6ad64dc88c69f8f4286b5b`**，含159份逐交付身份和计数。

## 实际命令与一次原loader接合

命令前缀均为`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage137_off_wait_delta_independent_review/review_actual_data.py`。所有运行的runtime.OUTPUT重定向至reviewer自有临时目录，使用原022冻结数值栈，未写历史022 runtime。

| 实际命令/动作 | chunk | 真实终态 | 含义 |
| --- | --- | --- | --- |
| `audit`首个review-only前置断言 | `8dd1ed` | exit1 | reviewer误将134 upstream中的source_bindings身份元数据也要求原样复制到135 snapshot；按135明确过滤该表的合同修正自有断言，在159交付循环前已退出，实际data解析0，非作者缺陷 |
| `audit` | `baa7b6` | exit0 | 10:02:25完成唯一一次159份实际七值/rights重建与必要闭包核验 |
| 证据通过后签限定独立收据 | `f0f0b5` | exit0 | 新dataset接受由独立reviewer签发，非builder自签 |
| `load-once` | `851d27` | exit0 | 10:03:11未改的061 `load_accepted_delta`实际接受上述manifest+本独立收据一次；36,391/36,345/36,391，未append或调用market loader |
| 最后pinned source/artifact稳定检查 | `ed06cc` | exit0 | builder、test、manifest、四artifact、134来源和本收据SHA均未变；不重跑suite |

loader按原合同重核2,783必要source，再加manifest、独立receipt与四artifact，返回2,789个实际绑定；这不是新增市场来源或再次原行情聚合。`loader_acceptance.json` SHA **`1507edbfcd5f43efbf29bca4c253c9d76f0035e2803580c9bc3445ddd39de524`**；`command_evidence.json` SHA `2ec2d4e6c347e94472b686a72245f1cae9f3bc3fc944105b6e37f1b29c73ebe9`；review-only脚本SHA `902b8ab2912502ff2711f12766f0aff21c9eba431b2c54006ced112adc11f81c`；`final_stability.json` SHA `ec7e4e47c545a60638378737ee6ef4bdf1e9fcf2c471cc0f145ffc74d2278311`。

候选manifest保持SHA **`563556d9a70a4f841f606e6b668c6422ae11c7f28f0dcc9203451c20ab2e694a`**；builder保持`e128a199deddf728b24a58ee4511bdb781121fe668945249351a1ed573cc5977`，test保持`4c990835b19ea6852d05e637d37fa3bfa4a854f0ca17130549045e02e4bca735`。

## 限制、记录与反思

未修改作者源、原manifest/交付、LINE、registry、HEAD/index或旧源码；未派子agent；旧suite、作者两测试重跑、新金融、训练、predict、provider、网络、guard/readiness执行均0。没有解pickle或读partial PnL；没有把数据成功算成新增accepted金融臂。新增/修改/删除策略参数和完整回测结果均0，期末权益、收益、最大回撤、Sharpe、总滑点、交易次数、胜率均**N/A**。

开始与结束新增过拟合判断均**否**：固定实际已消费scope，不按PnL选数据、不修改策略或寻优；不消除此前研究本身的偏差。开始与结束继续价值判断均**是，且此有限步骤已完成**：独立资格可减少后续重复等待，价值在可复用数据而非alpha。此后不继续循环micro review，不据此自动启动金融；原预算与失败终态保持。
