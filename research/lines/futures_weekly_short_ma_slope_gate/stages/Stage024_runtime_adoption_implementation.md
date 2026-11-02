# Stage024 真实现仓新管理cohort Runtime接管候选

时间：2026-11-02T14:43:00.652969+08:00。所属线futures_weekly_short_ma_slope_gate；重要突破：新cohort接管边界工程候选，非金融回测/自然晋升。只写runtime、新pure adoption、合成tests和本记录；backend/pipeline/provider/manifest由root负责，资金由资金owner负责。

## 冻结接口

```python
build_carry_in_seed(*, operator_decision, broker_snapshot,
    raw_position_evidence, contract_metadata_evidence, metadata, now) -> dict
bootstrap_weekly19_runtime(settings_asset, metadata, session_calendar,
    physical_epoch_daily, broker_snapshot, confirmed_cash_state, *,
    carry_in_seed, warmup_batches, clock=None) -> Runtime
```

pure模块qmt_roll_weekly19_adoption.py；factory位于qmt_roll_weekly19_runtime.py。首次显式初始化才用factory；恢复仍原build_weekly19_runtime+durable_state，不能通过新seed吞掉后来未知仓位。

operator_decision schema=weekly19.operator-carry-in-decision.v1，精确字段schema/account_key/material_release_id/operator_decision_id/management_start_date/completed_day/adoption_scope/broker_account_raw_sha256/broker_positions_raw_sha256/raw_carry_in_positions_sha256/contract_metadata_raw_sha256。scope固定all_current_positions_new_management_cohort，不接受operator给qty/cost/stop/旧峰值。root外层private startup authorization限定原始scope和metadata文件引用；这里的decision只是source-bound记录，不伪称个人签名或production authority。

## Pure来源与成本边界

- raw持仓envelope为weekly19.ctp-carry-in-positions.v1，native_positions来自同cohort实际CTP query；绑定snapshot normalized positions SHA及rawcapture SHA，核原BrokerID/InvestorID/TradingDay/方向/数量与完整查询/新鲜度。
- 仅从原OpenCost聚合，aggregate cost=ΣOpenCost/(实际qty×真实contract size)，不使用PositionCost、原生price=0或operator价格fallback。允许同contract/direction的today/history真实行求和，拒重复行、净额/对冲、同产品多contract和未知非零仓。
- 原发送/网关执行仅Speculation1，因此HedgeFlag仅1可接管，其余拒，不扩新执行路由。
- metadata envelope schema weekly19.contract-metadata.v1/source_kind=tqsdk_quote_capture，校验rawSHA、原instrument ID/ins_class/size/tick/expiry/explicit delivery年月，size/tick必须与accepted runtime metadata相符；不把fallback产品参数直接当权威。外层file reference由root loader固定校验。
- 非terminal broker order拒；provider all_traded终态合法。管理日<=native TradingDay且<=实际wall日，夜盘可native下一交易日；CF cold必须等管理日，不能把CTP交易日伪装管理起始日期。

## 初始化与原保护

默认constructor对未知非零仓仍unprotected_broker_position拒。显式factory保留实际snapshot（绝不fake-flat），纯AM预热到指定完成日，只有source/protection全部校验后才建完整base layer、实际pos_data、等量target及新cohort root/cycle/position identity，再首次实际broker reconcile。没有send/fill/order ID造作，没有historical on_bars、资金建议、邮件或旧周追单。

完成日必须是权威calendar里管理日之前最后交易日；管理日本身须在calendar且有forwardcoverage，再核持仓contract最近完整周源/physical explicit delivery epoch。不能自选过期旧周10/23代替应有的10/30。

层entry_price是已核aggregate cost，entry_price_synced=true；entry_date明确是管理起点而非旧OpenDate。初始stop调用原_weekly_initial_stop_qualification/原周公式，方向不合法或缺完整周直接拒；旧stop/峰值/old profit lock/history risk memory均unknown。新管理extrema两端以最近完整周close作为已声明参考，不冒称切换tick或历史peak；max_profit_pct=0。未来仍原更新/周退出/换月/实际fill协议。

已知接管E0是新cohort起始high-water、estimated/settled及volatility last-equity参考，不是额外现金。return/overheat历史保持空，不编历史收益。后续原_refresh等方法完全不改。首次bootstrap还硬核fund opening.broker_account.raw SHA及observed E0与本次真实snapshot/seed相同；同operator ID但另一fresh account baseline不允许混接。普通durable恢复允许真实E变化，不重置起点或重写opening对象。

export保存carry_in_receipt/完整sourcebound seed/保护basis与unknown字段，warmup_cursor完成日、last_processed_day空、days={}，input_cursor为完成日。m3普通无carry state不新增空receipt字段。每次reconcile接资金assert_opening_equity_forward，opening不可删改；E始终真实Balance，不加浮盈/closePnL/T，R仍场外。

未来实际平仓风险outcome沿原规则使用真实成本与实际成交，不因此证明接管前收益来自策略，也不把该PnL再加broker E。

## TDD与独审反例

首次9RED为新模块/API未实现；实现后首次run被原broker夹具缺query终态/CurrMargin挡，完整保留日志，仅补新合成fixture，不放宽core，9GREEN。

独审随后证明三P1，均原RED保留并经root授权最小修复：启动E0高水位遗漏；HedgeFlag2/3实际执行不能保留；可自选过期保护周。root另要求night/all_traded与首次opening snapshot硬绑定，均新增反例。最后owned16+原equivalence6共22/1.708s绿；独审原peak3/0.336s、hedge3/0.006s、stale-week2/0.220s不改断言绿。原565 class/function AST与原周信号/底20/保护等价测试通过；冻结模块未改。原runtime整回归由root后续一次完整CI统一执行，不把本22例当完整生产资格。

## 合成边界与后续

Git只含合成fixture，不写实际账号、资金、成本或原始仓位。source_qualified=false/production_qualified=false。未CTP/SMTP/金融回测/生产/index/commit/push，不改变m1/m2/m3。此候选供root接显式initialize，再整CI/独审/新m4冻结；不得隐式用启动授权接管后来未知仓。

过拟合：否，未改alpha/参数；本轮是经用户授权的新管理边界，不声称原历史金融轨迹复验。继续价值：是，避免无层现仓或假成本/假peak进入执行，后续需要root完整来源/资格与新发布流程。金融指标/收益/回撤/Sharpe等本轮不适用，没有金融回测。
