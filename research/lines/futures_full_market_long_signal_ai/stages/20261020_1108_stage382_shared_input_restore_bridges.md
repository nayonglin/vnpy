# Stage382：既有账户与同批输入的最薄只读接线

时间：2026-10-20 11:08 CST。所属线：`futures_full_market_long_signal_ai`。本阶段不是重要 alpha 突破；它补齐未来新旧模型比较所需的两个纯接口，不改变模型、特征、目标、资金规则、T0、T1、T_init 或 u20 采集窗口。

## 判断与范围

开始反思：本次没有新增按结果择参，故不新增结果驱动过拟合；既有研究的选择偏差仍然存在。继续有价值，因为真实370/378空态和固定357持久化定义已经存在，上一轮把全部盘前接线一律禁止的范围过紧。381明确允许有限桥接，不需要等待市场输入才检查既有账户的只读兼容性。它本身不证明 alpha 有效、未来盈利或正式资格。

已先读 registry 与381固定范围，来源4174B、SHA `793e44a108da1ba442aa4fa14892604aec8b03ed65fe3f0366fb3dfe10d1b587`。本次参考的是本机既有357、339、376、368、325/321/322固定源码；不提出新经济机制，没有额外网页查询、下载或数据研究。383独立复审者提供了最窄字段建议，未以猜造默认值代替原始321对象。

## 两个接口

`load_baseline_context(manifest_binding)` 从370原manifest、368初始化envelope/source_bundle解析原2023 model/scaler、clock_contract和真实T0。它保留原T_init、原初始化event、base/stress账户ID、原state内容与原model_journal。先确认journal的policy/index/objects已经存在，再用原321校验index链和对应初始化对象；缺失时拒绝，不能借ForwardJournal构造器创建替代账户证据。原初始化对象中的states、state_files、frozen_inputs、policy、T0须一致。kernel使用370原绑定131/070/042，校验SHA；最后交 unchanged376.validate_context。没有_initialize_profile、new_state或append。最新模型继续直接调用原376.load_context，不另造latest入口。

`restore_composed(manifest_binding)` 仅供实际361完成后调用。它从357结果里的input_receipt找到同批model_journal真实321 `input_snapshot` 对象，校验原index、对象SHA及canonical字节，原样取回source/version/source_receipt、D_context、clock和claimed adapter received_at。原source_receipt仍绑定manifest的inputs和capture，不把接线时钟当原行情完成时钟。

恢复器读取357保存的final warmup_state和完整epoch_inventory，用与376相同core的WilderState.from_dict/to_series。覆盖全部inventory：当前u状态作为state；非当前状态作为array；无state用原empty series。market采用原339 SnapshotMarket。绝不再append u20，也不读raw874、旧历史prices、label、训练数组或SQL。检查final state/index/date/current旗标和continuation final_state一致。

calendar、98产品/95family及original calendar338确认全部保留。economics按原357规则合并完整331+344：冲突拒绝，不覆盖；357的current_economics只是canonical子集校对，不能拿它替代full economics。完整clock_domains和unknown原样保留，aggregate必须与原321 clock一致，unknown不得变成已知时间。恢复后仅重建原core observations并对整个clean hash与保存observations比对，因此包含raw26；不调用infer_scores、selection或现金逻辑。

357未持久化的_row_dispositions、unsupported_catalog、product_states不凭空填空值。返回值显式标明是382恢复契约，development_only仍为True；它不是原composed内存字节的复刻。两模型将共享同一个恢复后的内存composed及其376 composed_identity/同一root acceptance。只有后续361终态、362独审、363接受证据齐备，原376才能生成accepted副本并运行各自325完整资金proposal；不得借用357未出资seal。

## 唯一组合fixture与证据

先写唯一public-interface组合fixture，RED为“382 public loaders are not implemented”，1 test失败，0.000秒。最小实现后GREEN 1 test/0.307秒；补只读路径和来源边界后同一组0.323秒GREEN；最终增加368固定helper来源guard，同一组0.325秒GREEN。未跑旧suite。

全部价格为合成值。fixture构造旧368形状manifest以及独立latest376 envelope，经公开入口加载；断言旧policy、T_init、账户、journal不变且两模型隔离。成功加载前后所有临时文件字节相同；在loader调用期间禁止new_state、journal.append、infer_scores和WilderState.append。final u状态恢复N=2.2、last_seen不增加，陈旧/空epoch不冒充当前bar。full economics的非canonical epoch仍存在，98/95及unknown completion clock保留；完整observations/raw26与保存的合成对象一致。缺失journal不创建替代物；缺失绑定、损坏321对象、错observations、inventory、clock和batch输入绑定均拒绝。每次GREEN的四个new_state、三个journal append仅为临时合成fixture setup，不是actual。

冻结源码：`tools/stage382_shared_input_restore.py`15907B，SHA `fcd567e8b7ab5c4c320306c3fc30d9adbe137c0c8183fa81c175a404792f27ae`；唯一fixture16108B，SHA `9eb68ded5aa518396b6568ee6488da07fe10f4b02399f5bf38ebe835e0b60a6d`。prepare1/source_bundle.json4219B，SHA `2c629b4247309d3e7ef2c95d8b613520070841f14e153f12402089146fee4356`。小收据在`outputs/stage382_shared_input_restore/fixture_receipt.json`。

## 结论与边界

作者实现与唯一fixture已完成，源码停止修改交383一次独审。actual context materialization/input restore/new_state/append/predict/fit/cash/API/SQL均为0。未改LINE、registry、359/360/370/373/375/376/378或任何策略参数；没有新增、修改或删除回测结果，权益、收益、回撤、Sharpe、滑点、交易次数、胜率均不适用，不能填0冒充金融成绩。

结束反思：没有新增过拟合；这次工作有必要但价值止于固定接口的可审查性。384最多一次真实小context binding materialization仍由root调用。actual361产物尚未出现，恢复资格及E2E readiness均为false。15:15—21:00原单批、无提前采行情/重训/旧回测/自动重试的安排不变；本阶段不生成额外研究待办。
