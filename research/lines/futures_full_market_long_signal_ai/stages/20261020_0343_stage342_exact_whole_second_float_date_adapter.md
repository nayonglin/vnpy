# Stage342：float64整秒日标签离线适配

时间2026-10-20 03:43（Asia/Shanghai）；所属`futures_full_market_long_signal_ai`。非金融突破。338一次真实接收已partial终态，原件874份永久保留，禁止重连/重下；本次只新342工具/test、唯一stage和自身implementation。作者未读任何338 raw文件，仅读授权/identity小metadata及对manifest/calendar做输入binding；0API/DB/旧cache/经济/fit/cash/旧suite。实际raw一遍解读须root另签授权执行。

## 真实问题与边界

336有意仅接受原生整数ns，真实SDK3.10.2的datetime列却为float64，故接收原件已到而日期均unknown。root小样本表明部分whole-second值具有可核精确性；337正在对同一338 raw保RAM独审。不能把这个事实推广为任意float纳秒无损，也不能重写336原严格判定或把338partial改成当时成功。

新增`recover_timestamp`对float64必须同时满足：file dtype和row type为float64、finite positive、is_integer、float(int(v))==v、int(v)%1e9==0、Decimal原raw_literal==int(v)、北京时间精确午夜、已存calendar该日True。只有全部成立才给`recovered_exact_whole_second_float_ns`和operational_midnight_label。0/负/非有限、非整数/非整秒、Decimal字面量不一致、非float64、非午夜或日历未覆盖/False全部unknown。原strict_integer_ns路径仍沿原精确整数与午夜/calendar语义；没有18点/周末或自然日期猜补。

float恢复只证明此已存字面值的整秒与该批次午夜标签，不证明vendor最终性、历史首发、所有任意ns精度或新资金资格。原始raw_ns/literal/type与source338引用同时保留，native_values复制全部原字段、单位不动、不乘1/2。

## 薄API与派生证据

`run_offline(auth,output)` / CLI `--execute --authorization --output`：adapter自建fresh输出，root只建父目录。精确绑定342source/test、338manifest、已存calendar、root explicit794map及其原receiver授权；确认map两份一致，按原338manifest每份raw仅读1次并校验其原binding。不得调用336、Tq、DB、旧缓存或经济投影。

- `date_rows.jsonl.gz`：所有raw行（含padding/unknown）逐行解读，source symbol/rawsha/rowindex、原literal/type、恢复ns/日期/原因、root794identity、全部native值/缺失标记、原321received_at。未知identity不代理，不删新fresh未知symbol。
- `raw_artifact_index.jsonl.gz`：全部raw文件binding、原321receipt/ready/transport status；338状态永久保留。
- `overlap_index.jsonl.gz`：仅已存calendar明确确认、日期<=10月16日的行索引，供337对331compact有限overlap；不自动授单位或source accepted。
- `coverage.json`：逐symbol/dtype/date/state/rejectionreason，unknown保留；manifest列raw读次数与派生bindings。失败保留partial与读计数，不retry。

`received_at`只继承338 actual321receipt；`decoded_at`是当前离线处理时刻，不是新firstseen，更不能作为source_completed_at。没有新session-end证据，因此完成时钟None；T0=None、activeFalse、units_status provider_raw_units_unverified、canonical_quality_status unknown、model_input_eligibleFalse。337/root另给显式accepted overlay后，339才可用原模型observe。

## 唯一新tiny与交付

唯一`test_only_exact_whole_second_float_and_confirmed_midnight_recovers`先RED未实现，最终exit0/1test/0.010秒。独立构造北京午夜，覆盖float64完整精确链、原int保留及原row不改；0/非有限/非整数/非整秒/字面量不符/float32/无calendar/非午夜拒绝；native/原received_at保留、完成和单位不升级。无旧receiver/warmup/金融组，未读取实际raw。

[新bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage342_offline_date_adapter/implementation/source_bundle.json)、[授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage342_offline_date_adapter/implementation/authorization_template.json)（authorized=False）、[tiny终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage342_offline_date_adapter/implementation/fixture_terminal.json)已交337差量审。root随后只授权这批一遍离线解读，不启动336重收、不改338/raw、336源码或LINE/registry。

此次不是新金融命题，沿335已核的operational午夜/calendar规则，仅收窄修实际日期类型；无外网新方法搜索或安装。新增/修改/删除模型/金融参数与成绩均0，权益/收益/DD/Sharpe/费滑/胜率N/A。无新过拟合搜索；继续价值是忠实利用已到原件，不能据此称新alpha、已启动forward或生产ready。
