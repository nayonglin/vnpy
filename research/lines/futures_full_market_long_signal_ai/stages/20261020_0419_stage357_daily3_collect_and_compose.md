# Stage357：单批三根日线与纯组合接口冻结

- line_id：`futures_full_market_long_signal_ai`；2026-10-20 04:19 CST；非重要alpha突破。
- 作者仅新357工具/test、implementation与本stage；0实际API/凭证读取/原始行情/原cache/SQL/原8MB经济表/fit/cash/T0创建，不改LINE/registry或旧冻结源。实际由root另目录、exactauth执行。

## 范围与接口

按当前registry、352 next_scope、355双域及356实际clock_contract实现；复用335/347已核[官方Tq API](https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html)与维护者[API源码](https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py)，本次没有重复联网研究或实采。此处不新增金融方法或资格。

[工具](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage357_daily_collect_compose.py)的唯一root入口是`run_batch(authorization, output)`，adapter自行创建freshout。CLI：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage357_daily_collect_compose.py --execute --authorization ROOT_AUTH --output FRESH_OUTPUT`。

`collect_from_api`仅已存874个真实月、一次显式TqSim连接、每symbol一次86400秒/3根独立serial；继承336 public异步订阅/ready/断路/脱敏，不重查catalog/calendar/quote、不重试重连、不取分钟或历史补暖机。硬窗口20日15:15至21:00前；global600秒、连接45、80symbol批、ready40、close8，另受21:00截止限制。归档原始native值/类型/literal及逐symbol缺失/错误，raw仅本地文件，journal只存binding与实际UTC321 receipt，不dump私有配置或SDK对象。

`compose_snapshot(raw_items,*,warmup_states,epoch_inventory,dates,calendar,identity_map,products,economics,prior_overlay,sessions,clock_contract,source_receipt,core,execution_dependencies=())`是纯内存接口，返回snapshot、canonical_rows、normalization_audit、prescore_observations、clock_domains。直接调用342精确float整秒恢复、339追加与原320资格。u19只用于overlap，不回放指标；u21形成中只保raw/排除记录，不进入u20特征。

factor1仅在原已见产品域、同一新SDK批次存在精确u19 OHLCV+closeOI见证时有限继承。原accepted symbol缺失或冲突overlap则隔离该symbol；没有产品见证/新产品单位仍unknown，不补证全历史。354当前显式身份可用于新接收日，原354对象的model_input_eligible=False与旧历史known状态不回写。unknown经济不按产品代理，341/351倍率缺失不补0、不替换旧单位。

小输入固定为344 warmup757/inventory9520/overlay726、344经济726与331经济744的精确epoch union、354身份874/353候选时段、338已存calendar/catalog、旧小source-calendar/roster/model/scaler。共有经济键内容不等即报冲突，不能按接收新旧覆盖。作者只继承小receipt中的数据binding；331经济766537B/SHA912dc47f…沿356已hash值继承，未另读或解析内容。实际加载每个compact一次，无原cache/经济projection、旧actions/labels/scores或旧控制。

runtime为357→336/342/339/325；325→320/321/322（322仅import，未调用资金方法）；320按原七AST源042/070policy/129/004/156/130/157提取纯函数，凭证与脱敏沿两份既有公开源码。353作为候选时段重现证据绑定，不在357 runtime调用；330/331/346/354 runner和旧131均不加载。完整路径/bytes/SHA见bundle。

## 两域与未注资研究封存

356完整合同逐字对象采用：完成域是全部实际accepted u20因果bar/母参考/peer，加显式既有state所需价格；不能先按入场资格删月份。D域在score/K/positive/family winner之前，以**新u20原资格全集、资格未决及显式position/pending依赖**重算。只有原已知历史不足、生命周期拒绝、已知容量不足等0可排除，陌生reason保unknown依赖，不升级为eligible。当前明确execution_dependencies为空仅因states=None，不能推断未来空仓；没有使用u19的427或两赢家。

源完成取全部必须输入确认session_end的最大值；D截止取全部执行依赖first_open最小值。任一所需clock未知，相应域为unknown，两个域独立保留；354严格全726 diagnostic不改。source_completed不能赋receipt，vendor_finality/firstpublication仍unknown；日程采用356已冻operational解释，不声称排除所有临时例外。

`observe_composed`只调用325 observe_only，原result保持active=False/states=None。完整obs/scores/selection/economic evidence及原receipt链先封存一个321 `unfunded_research_decision`对象，再用**该对象真实recorded_at**另算research_clock，不在append前手填seal，不把325原clock改为通过。此分类不授予交易或资金资格。

auth.freeze_event可None；若已有真实T0，仅接受root359小envelope exactbinding，核321 kind=`research_reference_freeze`、非零eventhash及同closure_manifest/clock_contract binding，以receipt.recorded_at为T0。357不会创建、回填或更换T0；晚收仍late，source完成<=T0仍历史。

## 唯一tiny与冻结物

先RED：新357文件缺失；随后同一个integration方法GREEN，最终1 test/0.279s。组合真实342/339/325/321及synthetic bars，覆盖float日期、未来bar排除、Wilder续接/缺口重启、unknown单位不代理、overlap冲突隔离、source域保留不合格peer、D原资格未决、缺时钟独立unknown、before/late、硬采集窗口、完整未注资封存与0cash。未跑旧suite或增加第二组。

- 源码28199B SHA `65d18a5c39e8df5442eafc2f5e2fd782f9bb492743339dc6cb5b013c91877e87`；test7806B SHA `57245f327472d2ad25f942112ad18b42621fed25923f1623a352357e1265b35f`。
- [fixture](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage357_daily_collect_compose/implementation/fixture_terminal.json)：1279B SHA `2fcf2bcc9ce4ae1f153faa6ad0e7eeb282ab5543f462db32cdc4977af787ce0e`。
- [source bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage357_daily_collect_compose/implementation/source_bundle.json)：8173B SHA `4b9b7de194f74b4646bfb8443bdc01a056f341428f28e93505e0349e331c2f50`；[输入绑定](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage357_daily_collect_compose/implementation/input_bindings.json)4781B SHA `746bd98b4dbb0cb4eb5dac304d8c3042bff5356166bd829f06bdb92bb1d92e3d`。
- [root模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage357_daily_collect_compose/implementation/authorization_template.json)：6470B SHA `3611fe6e31ee60ee92ed268397e45389f4bdf317c2bb698904f84a789bfef75f`；authorized=False，freeze_event/closure_manifest待root实际精确填写。已交358独审，356可绑定最终源；作者停止，不追P2零缺口。

开始/结束反思：无收益调参，非新增这种过拟合；旧政策历史择题风险不解除。新样本薄接线有继续价值，重取metadata、旧资格/金融包没有。新增/修改/删除金融参数和成绩均无；权益/收益/DD/Sharpe/滑点/次数/胜率N/A，累计453fit/246cash及旧1金融partial不变。完整高收益低DD/高质量long目标仍未达。
