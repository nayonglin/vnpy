# Stage016 同连接订单恢复与最终生产发行身份封口

- line_id：futures_weekly_short_ma_slope_gate；实际执行/封存时间2026-10-31 17:53 CST（文件1755为本次封存标签）。
- 接续1745 V4与1723 V3；不覆盖任何旧源码hash、日志、manifest、独审或checkpoint。资金schema仍v2；无alpha/风险/15万比例变更。
- 重要突破/A-B：否；production_qualified=false。未真实连接CTP/银行/SMTP，未运行金融回测，未创建真实registry/key/qualification，未动生产/Git index/commit。

## 调研与执行合同

- 上游[官方vnpy_ctp gateway](https://github.com/vnpy/vnpy_ctp/blob/main/vnpy_ctp/gateway/ctp_gateway.py)及本机6.7.2.1均在native onRtn*内部生成vnpy Object；query恢复不得把normalized Object倒标为原始CTP，也不得把onRspQry*伪称onRtn*。
- 实读931 owner当前新增稳定列：planned_direction/offset为原始long|short/open|close，planned_volume为父计划；broker_order_volume为实际物理child请求。SHFE parent2、child1的不同合法，原callback.volume只能是成交量，不能当原订单上限。
- provider fold现在优先planned_direction/planned_offset，保留各明确cap；native订单cap按broker_order_volume→order_request_volume→planned_volume，broker与order_request二者同在须一致，父planned可以更大。逐event语义冲突仍拒绝，原计划/实际child不混称。

## 同连接query恢复公开入口

- load_warm_broker_events(transport_context, derived_bindings, **与load_warm_broker_snapshot相同policy) -> {fills,orders,apply_order:['fills','orders'],native_source_sha256,source_qualified,production_qualified:false}。
- 先执行同连接已冻结native epoch/signed warm ref/registry/typed capability全部门，再复核读取的冻结bundle未漂移；不连接、不另起query。derived_bindings必须先由公开derive_order_intent_bindings生成，不直接传完整event ledger。
- 复用provider唯一native order→原planned/delivery intent/真实broker offset/status桥；fills实际qty/price/执行时间来自唯一raw Trade及OrderSysID匹配，不取caller completed量。订单累计traded只在真实fills先消费后应用。
- fills保留source_callback=onRspQryTrade，orders保留onRspQryOrder。重复同native TradeID/同order语义跨query_reqid保持稳定业务ID，采集rawSHA可不同；稳定身份内容冲突仍拒绝。原生SHFE closeYesterday/Today与业务close同时保留。
- 该入口供startup与fresh_bundle恢复；native hook仍通过onRtn*原始证明，二者不混淆。真正actor durable apply和931接线由root/executionowner负责，本组件不代为声称运行已验证。

## 发行身份误判纠正与严格门

- root最初把material.manifest.source_commit与production release-manifest.source_commit混为一体，误认为严格HEAD门会阻断合规promotion；读底层后已明确撤回该判断。此处记录纠正，不执行祖先放宽，也不假传current_commit=qualifiedCommit。
- 正确两轮：candidate qualification供activation/promotion准备；fresh remote-master clone重新生成最终production qualification与production release manifest，两者source_commit必须实际production stable HEAD。材料包material_source_commit独立保留历史身份，可不同。
- registry create新增production_release_manifest={path,sha256原字节}和production_activation_receipt={path,sha256原字节}，不接受布尔资格或仅caller commit。FULL qualification/source closure验证后，再独立核实际stable checkout路径、actual git HEAD==最终production qualifiedsource、active material、production release validator current_commit=actualHEAD、qualification evidence ID、created_at/critical源集合、每个HEAD critical blob与manifest SHA，以及activation绑定与artifact前后复读。
- registry记录qualified_source_commit==production_source_commit；material_source_commit来自active material loader另记，不复制给runner。load会重新FULL核上述所有真实门；Stage174 runner.source_commit必须实际production_source_commit。传候选/材料qualification或旧productionHEAD会拒绝。
- 为避免validator先漂移再放行，CAPTURE_AUTHORITY_SOURCE_FILES从V4的9补直接语义依赖official_live_release_manifest、Stage914 activation validator、official_baseline_identity，当前强制12源；CAPTURE_SOURCE_FILES仍5。全传递闭环由root发行critical pin继续覆盖。
- 当前没有真实registry，故不迁移历史authority。新增真实门是可审查代码路径，不是已经跑过的真实生产正样本。

## 验证与剩余具体门

- TDD新增SHFE parent/child接缝先RED，修后GREEN；warm query recovery API缺失先RED，partial/duplicate/错plannedID/sourcequalification/跨reqid/SHFE恢复后GREEN；registry生产ref与commit区分2组先RED后GREEN。
- 最终provider50 + warm13 + funding61 + Stage174旧22 + account旧25 =171项unittest GREEN；Python compile与git diff --check GREEN。原8x8冷并发资金IO仍在61内，旧39独审cash等外部反例不由此冒称重跑。
- 精确命令、完整输出、锁源SHA见同前缀manifest.json及unittest.txt；1745资金initial-observation记录仍独立有效，本次funding.py SHA未再改变。
- 尚缺：最终fresh生产资格/registry；本次版本实际同连接原始CTP captures与已有readonly qualification的真实源链复核；真实银行TransferSerial样本与最终日结statement accepted parser/continuous cashflow证明。缺任何门保持source/生产资格不成立，不能用fixture、raw SHA、自报qualified:true或clock>=close替代。
- 银行load_cashflow_day_close仍明确missing_statement；资金初始观察不意味着日切永远可放行。root可准确报告blocked并保留已知cash状态，减仓不由资金建议误锁。
- 未运行金融研究，期末权益/收益/回撤/Sharpe/滑点/交易次数/胜率/PF不适用；没有新增/删除业绩结论。后续独审单独留证，root统一release/promotion/install。

## 反思

- 运行前/后过拟合：否，只修证据、ID、物理请求cap和发行身份，没有按收益改策略。
- 运行前/后继续价值：是，真实source门与同连接恢复必需；本轮封存后暂停加需求，下一步是独审和真实证据，而非继续堆fixture。
