# Stage142：日线规范化候选独立资格与固定EMA标量缓存

- line_id=`futures_trend_triple_screen`；完成时间：2026-10-18 10:12 CST；独立reviewer=`off_wait_delta_review_stage142`，不是141导出作者。
- 开始读registry、139根裁决、138证据、141实际候选/导出源码及132接受的127模型。沿已有但尚未入registry的本线，不修LINE/registry；唯一新增本文及`outputs/stage142_ema_daily_qualification_and_features/`。
- 非重要策略突破，无新策略参数、回测结果或金融readiness。调研继承138的TqSdk官方文档/GitHub API、121/123的原著边界及139的337号公告时点证据，没有新联网、价格搜索或收益择源。

## 结论与限定资格

**P0=0、P1=0、P2=0。接受141全部116,394个精确research keys的日线研究资格，并在实际签资格后调用已接受127模型一次构建固定13/26特征。** 接受依据为139预先裁定的“已接受基准同源继承＋七列无损规范化＋有限跨源样本”，`raw_same_baseline_source=true`、`fully_independent_market_repricing=false`。

真实独立资格文件为`../outputs/stage142_ema_daily_qualification_and_features/daily_source_qualification.json`，SHA **`553b07a161a7b05cd1d161e541accbf8fcb489af0786af6a3bba2b02ce1ef592`**；`new_data_qualification=true`、`qualified_research_data=true`，`financial_ready=false`、`production_qualified=false`。它绑定原141候选manifest、daily.csv及exact_keys.csv的路径/SHA，构成独立reference pair；原manifest仍保持pending、无自签资格，字节未改。

这不是将013的4,500键资格扩到116,394，不是所有日线重新分钟聚合或全市场独立厂商价格认证，不证明策略收益。原provider零量、合约末bar及同源置信度限制全部保留，不因未来是否有后继而删条，不补价/前填/拼接/调整价格，也未新建calendar。

## 一次独立日线源审查

`review_and_build.py qualify`只用标准库；对DB路径实际仅一次`read_bytes()`，先核SHA `273f0bc18de3070e4e085e4d6585fba71d6e1bb1256e3c7fb5adfc6532836a54`，随后把同bytes `sqlite.deserialize`至`:memory:`，开启`query_only`查询。没有hash后重开活动DB；读取前后DB大小/mtime一致，无WAL/SHM。

- 141 exporter的实际同bytes快照保护位于`outputs/stage141_ema_daily_normalized_source/export_daily.py:114`，内存只读连接`:125`，没有native loader；本审查独立查询相同2019-06-01至2026-10-14、`interval='d'`及原806 metadata合约scope。
- 新CSV严格七列`date,vt_symbol,open,high,low,close,volume`；116,394个键逐个与同DB完全相同，五个float64数值逐位相同，数字合法且键唯一；CSV与exact_keys逐行精确相等，日期集合等于原1,786日global calendar。
- 533个实际有数据真实合约、全部1,468条volume0原样保留；没有OHLC修复或正量筛选。源/CSV规范标量摘要均为`60976debf28e9fd52d1ba596ce1590ca2a021b3507f99daeab62ae65d6fd52dd`。
- 核141的21项有限source bindings：A_OFF preflight/context/参数、A0参数、原calendar、027身份/有限review、下载器/导入器、138/139、141 exporter、真实502→827→840→847 carry源及DB。没有重hash7,663级旧源闭包，也没有运行native或旧suite。
- 继承138已辨明的carry边界：502 `new_bars`后补只进engine内存，原DB导入器逐行保留厂商日线；16个旧carry诊断键全未进入本DB/CSV精确键。未将零volume当成carry。
- 仅核3个已绑定原CSV标量样本：`AP101.CZCE/2021-01-14`原厂商零V、`fu2101.SHFE/2020-06-29`原CSV、`sp2611.SHFE/2026-10-14`旧013 qualified CSV。五值与候选逐位相同。AP样本沿138证据复用，不把下一CSV日期冒称provider serial完成证明，更不外推其余1,467个零量记录均被独立认证。

数据资格签发依据及限定记录在`source_audit.json`，并由另一作者本reviewer实际生成独立receipt；没有调用127来代签源资格。

## 资格后唯一固定特征构建

模型源`tools/stage127_ema_limit_model.py` SHA **`6568f87ec74bebdb9afa730b3347c5eb52cdf31bd8f3ca3cc9208b1c55c2f7d6`**，保持132已接受字节；132独立收据SHA `bb4d79bd77a40475e98e0631737bc8b937d64ff609fc6d4771c48e06fd0e640b`。不改模型、不重跑unit、旧未来毒化或prefix反例。

签资格后真正调用`load_bound_daily_csv(daily.csv,sha256=71dd…df5c,qualified_keys=frozenset(116394 exact keys),qualifier_sha256=553b…f592)`一次，再调用`build_ema_rows(rows,原global_calendar,source_bindings=…)`一次。全期实际2019-06-03暖机至2026-10-14，每个 `(contract,asof)` 唯一；source_bindings及全部精确keys仅在feature manifest的`source_bindings.daily_source`中保存一份，CSV各feature仅存标量及`source_ref=daily_source`，没有逐行嵌套dump键集合。

| 覆盖统计 | 结果 |
| --- | ---: |
| feature行 / 合约 / 日历日期 | 116,394 / 533 / 1,786 |
| ready | 96,813（83.1770%） |
| not ready | 19,581 |
| warmup_ema / warmup_window | 6,387 / 13,194 |
| 至少一个ready的合约 | 525 |
| 保留零V行 | 1,468 |
| 最后日无下一执行session的feature | 29 |

| 年份 | 行数 | ready |
| --- | ---: | ---: |
| 2019 | 5,492 | 3,074 |
| 2020 | 13,697 | 11,391 |
| 2021 | 15,016 | 12,764 |
| 2022 | 15,231 | 12,652 |
| 2023 | 19,161 | 16,149 |
| 2024 | 20,021 | 16,731 |
| 2025 | 19,199 | 16,807 |
| 2026 | 8,577 | 7,245 |

有限标量接合仅两窗，没有复刻模型全套测试：AP005首个ready为2019-07-25、segment_start=2019-06-03，38真实bar，SMA13 seed=8790.153846153846；fu2101首个ready为2020-02-21、segment_start=2019-12-23，seed=2297。用加权收盘闭式展开独立核seed、最后EMA/前EMA、26个有效EMA bar的正穿透均值及正数分母，与真实输出在预声明float误差内一致。未来append前缀不变沿原127 unit/132证据继承，本次未重复。

## u时execution_tick与最后日边界

只从原A_OFF `effective_parameters['priceticks']`取configured值，再调用未改的`qmt_roll_intraday_execution.effective_pricetick(contract,D,configured)`；D为u已知原calendar下一session。执行源SHA `95de37e240ed5f34e8370cf9652e958c3c44fa3f36bef1d905c3e757a8304272`，没有把风险或成本tick替代执行tick。

lc变更的u-known证据沿139：337号原文12/6已公开（南华转发），12/17收盘后已知D12/18适用20。实际缓存有限边界核验：u2024-12-16→D12/17为50，u12/17→D12/18为20，两日各5个真实lc合约均一致。此检查只用已知规格和calendar，没有读取D价格或生成订单。

末日2026-10-14没有下一D：29行`execution_day`空、`execution_tick_order_usable=false`、`execution_tick_status=no_next_session_feature_only`；保留自身日有效tick作为feature解释值，明确不得用于order，没有造未来日期。其余行附u-known时点和`execution_rule_ref`；spec源、原参数SHA、公告URL与139记录统一绑定在manifest一处。

原execution模块导入前用022冻结数值runtime；`runtime.OUTPUT`指本142临时目录并在finally恢复，没有向旧022目录写runtime缓存。

## 真实命令终态与全SHA

命令前缀均为`.py311/bin/python research/lines/futures_trend_triple_screen/outputs/stage142_ema_daily_qualification_and_features/review_and_build.py`。

| 命令 | chunk | 真实终态 | 次数/范围 |
| --- | --- | --- | --- |
| `qualify` | `c0a3e3` | exit0，2.454928375s | 一次同源DB/CSV独立无损审查，随后签真实资格 |
| `build` | `8834c1` | exit0，3.335035833s | 一次load＋一次build；两有限实际标量窗，不运行账户 |
| 最后有界source/model/candidate稳定检查 | `1e73c0` | exit0 | 候选三文件、非DB有限source/样本及模型SHA稳定；DB stat仍等于已hash bytes读取后的stat，无sidecar，不再次读/重hash DB |

没有失败重试或第二次导出/资格/build，没有循环micro review。141原actual仍为`364151/exit0`，未重新执行。

| 本142产物 | SHA256 |
| --- | --- |
| `daily_source_qualification.json` | `553b07a161a7b05cd1d161e541accbf8fcb489af0786af6a3bba2b02ce1ef592` |
| `source_audit.json` | `a39c3c4cac4d12a6d6f4f362a1b5fa66c1b61f97935e9e7899f1b7d395ad4729` |
| `features.csv`（24,577,313 bytes） | `d9d8fa958c5c52a329f977a5ee2fa6a146901608e6cc1fb53dd4d75d4d591245` |
| `feature_manifest.json`（7,985,023 bytes） | `3edc75693057d12cecffb5bddb7908d5e508f488dc18a08e36946488f3337c28` |
| `feature_build_evidence.json` | `6a5c60ae2dac0dd68419194a94462ce2e2bea23e57a7dbdffb95179eace3d0d3` |
| `review_and_build.py` | `160a2c28dd53a279e7f8c9d5afa81415e5f5dce1d86ea70368260d8ebce6b80b` |
| `command_evidence.json` | `d80aede4b4b39669ec9d5ee6854e1278dac875ac683f40f5a349ee71f0f9e37e` |
| `qualification_attempt_started.json` | `46992a03823406f73186589b095f48aaf1382515afdaf390aa17678048df42c7` |
| `feature_build_started.json` | `14b9917a72f041d1a8e93d03bec3ae35201f9b273d124a9738e2255f9c1bc144` |
| `final_stability.json` | `1e79f25ea2401e4b4522723a2bbc1f8be995482ba76d5d2fc50c711576c92115` |

141原候选manifest SHA仍`96eea70a16b7a5715f697aaa06a4e34107e328109849ca573eba88be78cc8b90`，daily仍`71dd740fb605e1ff8365fb6fc7236ab6d19f8d90a7f7be72c753d29733b7df5c`，exact_keys仍`5e8493067d422c27ba7e4512dfbb30ea74de11193b46d0a71547940ed3f48317`。

## 变更、限制及反思

没有修改141、127、旧源、行情、LINE/registry、HEAD/index/Git；未派子agent；旧suite、作者unit、新金融、native账户、provider、网络、模型训练、guard运行均0。原金融11attempt/4accepted不变。固定纯特征load/build各1次不属于训练或回测；未生成actual trades、PnL、新arm或financial readiness。

新增/修改/删除策略参数均0，新增/修改/删除完整回测结果均0。期末权益、收益、最大回撤、Sharpe、总滑点、交易数、胜率均**N/A**。ready只是因果特征覆盖，不是信号触发率、可交易率或收益证据。

开始与结束新增过拟合判断均**否**：139先固定同源、全量零V与无损规则，13/26来自已接受模型，没有按收益择源、删bar、选窗或改参数；历史研究选择偏差仍保留。开始与结束继续价值判断均**是，此有限源资格及缓存步骤已完成**：已把明确同源置信度的真实输入接到固定组件，后续可由root另行设计受限实验；本步骤不自动授金融或生产资格，不继续无限旧资格检查。
