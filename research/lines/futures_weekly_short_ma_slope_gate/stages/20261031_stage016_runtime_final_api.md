# Stage016 weekly19 Runtime / Data公共接口

只处理条件来源、产生intent与消费已验证实际回报；不连接CTP/发邮件/发真实订单，输出production_qualified=false。原31冻结模块及565 class/function AST不改；来源资格、release/activation与真实授权须由上游独立证明。

## Runtime构建与恢复

```python
build_weekly19_runtime(settings_asset, metadata, session_calendar,
    physical_epoch_daily, broker_snapshot, durable_state, confirmed_cash_state,
    *, clock=None, recovery_events=()) -> Runtime
```

settings_asset=DEFAULT_SETTINGS_ASSET，hash固定；资金V2，原生Balance是唯一E，Available仅额外cap，不加计划T/模型MTM/closePnL。

metadata必有product_symbols固定19、vt_symbols全部known physical/映射合约、source_symbol_by_contract、daily_mapping[完成日][产品]、sizes/priceticks/margin_ratios/rates/slippages各contract。session_calendar真实交易日覆盖历史及下一ISO周；bars/frame只到完成日。physical frame至少vt_symbol/date/contract_epoch_id/OHLCV/close_oi；全部approved source必须实际closeOI，无生产缺OI fallback，保留旧source原列。

broker_snapshot={account,positions,orders可选}；account/positions是原packet来源{raw_payload,raw_sha256}，含account_key/material_release_id/带时区observed_at/权威trading_day/generation_uuid/query_complete，同cohort。真实provider有更严格完整query来源门，不能从EVENT_ACCOUNT重造native packet。

durable_state=export_state()完整tagged JSON。shared_inputs.weeks由已验证calendar+digest重建；strategy/engine可能zjson无损编码，不可外部直接_decode(strategy)省略shared上下文。PipelineStateStore直接_decode(runtime)仍可。recovery_events仅有durable_state时允许，{kind:'fill'|'order',envelope,signal_identity?}，实际fills按时间/ID先消费、再orders，最后与未篡改fresh broker reconcile；新state不得导入外来仓。

## 方法

```python
runtime.warmup(real_bar_batches)
runtime.process_completed_day(day, bars, data_receipt, broker_snapshot, confirmed_cash_state)
runtime.apply_broker_fill(envelope, signal_identity)
runtime.apply_order_update(envelope)
runtime.reconcile_broker_snapshot(snapshot, cash_state, *, quote_snapshot=None)
runtime.export_state()
runtime.execution_state(intent_id)
runtime.revalidate_open_intent(intent_id, *, broker_snapshot, confirmed_cash_state, quote_snapshot)
runtime.replan_after_confirmed_funding(signal_identity, broker_snapshot, confirmed_cash_state, quote_snapshot)
```

warmup只冷启动前AM，不on_bars/资金/历史open。process_completed_day保留原daily风控与roll，周技术退出仅fresh completed week close。Decision.trading_date为完成来源日，intent.trading_date为真实下交易日；target_date/completed_target_date为来源完成日，不得混同。

pending执行期间只AM+queue；先绑定operational current_receipt_hash/last_processed_day，异常restore，不回放旧open。close retry用新target/new data_receipt_sha256，lifecycle_origin_signal_receipt保留最初周信号receipt，原signal_datetime/close原因/真实层不变。无fresh quote仅executable=false参考；retry只actual remaining。

quote={symbol（可同值vt_symbol）,observed_at带时区,bid,ask,session_id,trading_date}，runtime freshness≤15秒；executor仍独立验证MD journal、metadata/session、账户/持仓/orders资格。

## 当前E重算与同原admission重计划

revalidate在clone用当前E/Available/quote+原signal/history调用原parent sizing，全部产品层/风险/组预算保留、不推进真实AM/roll/risk。selected=min(当前原量,该intent原批准未成交量)，不默默放大旧intent。

replan使用funding_admissions[i].signal_identity（admitted_entry_id）；同执行窗口，未实际持仓/filled/broker-bound时显式替代unsent local plan。两条来源：真实T增加（funding_ready_reason=confirmed_transfer）；或资金连续性已通过且真实E≥150000（equity_recovered_without_transfer）。后者不改T/R/receipts，不把旧建议当债务；同原admission一次幂等cap，再执行前revalidate。original_funding_admission_id跨真T/自然恢复/delivery稳定，不重新recommend floor；过期不追单。

Thursday假日周原admission由父Friday建议任务用同IDs/Thu receipt独立recommend canonical Friday，不再on_bars。低E且R未到账deferred flag仍挡，真实E≥floor可清，不提前虚拟用R。

## V6物理子单回报

signal_identity四键={intent_id原业务计划,signal_order_id,signal_datetime,trading_date}；delivery intent另列。order schema weekly19.ctp-order.v1/source_kind=ctp_order_callback，source_callback onRtnOrder/onRspQryOrder，status accepted/working/partially_filled/filled/cancelled/rejected。trade schema weekly19.ctp-trade.v1/source_callback onRtnTrade/onRspQryTrade。查询不冒充push，batch先fills后orders。

business offset=open|close；broker_offset=open|close|closetoday|closeyesterday，native_offset_flag 0/1/3/4保留。未知/冲突拒。trade.volume是actual，order.volume/traded是单physical child累计。

真实quota在任意insert前完整持久化logical manifest，provider验证重建附：

```text
execution_batch_id == api_slot_batch_id（24hex，至少一个；两个必须相同）
api_slot_batch_count, approved_parent_volume, expected_children_sha256
expected_children=[{
 child_order_id, child_order_index（0-based）, volume,
 broker_offset, vt_symbol, direction（long|short）, trading_date
}]
child_order_id（当前child）, broker_order_id（实际回报后绑定，不预造后续ID）
```

同父batch/名单/digest/批准量不可变；sum children=approved volume。close覆盖父目标；open可执行cap，未发剩余仅全child终态后撤销计划层。真实brokerID唯一、每child actualfill守恒。第一child filled/cancel不结束父；未知/未发仍pending。全实际目标完成后原outcome/streak一次、brokerE不加PnL。全child终态未flat时仅actual remaining retry且保留保护。

order semantic13键保持account/release/原intent/signal_order/signal_identity/broker_order/symbol/direction/business_offset/native_offset/volume/traded/status。batchproof独立先核，再dedup；querygen/rawSHA变化同语义no-op，改变业务事实/manifest/绑定拒。

## 数据读取与更新

```python
load_weekly19_inputs(asset_root, *, material_release_id, target_date,
    forward_calendar, expected_hashes)
# -> metadata/calendar/physical_epoch_daily/bars_by_day/receipt/source_hashes_before/after
build_legacy_epoch_seed_from_approved(physical_daily_path, *, trusted_sha256)
update_weekly19_assets(base_asset_root, generation_root, *, material_release_id,
    target_date, held_contracts, expected_hashes, backend, now=None)
```

五hash为daily.sqlite/mapping.csv/physical_epoch_daily.csv/metadata.csv/receipt.json；calendar文件也需expected hash且前后检查。reader标准库SQLite readonly DTO逐条核验admitted OHLCV+closeOI，缺SQL bar不从CSV或0重建。仅conditional_read，不继承研究qualification/historical main重建结论。

新metadata含new_contract_history_admissions及new_contract_history_bars（实际SQL BarData列表，非普通JSON）；raw/metadata SHA、真实交割月/到期与id0连续available history可追溯，legal listing未知独立标记。仅从未owned/pending/signalled的新vt合约预热cursor前AM，不回写旧scope。同vt跨十年新epoch当前failclosed，需另审epoch级scope。

updater explicit19，main+current tracked physical+actualheld；TqReadOnlyBackend只复用Stage173参数化fetch_mapping及raw close_oi，不调用旧池/全局mapping/default DB/save。generation_root私有0700、Git外、与base分离；strict reader完成后全文件fsync/0400再原子latest，失败latest不变。真实packet证明已到期的非main/无实际仓offmain可停更并单列receipt；main/actualheld缺bar仍拒。

无registry时seed仅已有explicit YYYYMM/epoch与observed bounds，listed/delisted不造。新vt需真实delivery_year/month+expiry packet与id0连续0..N history，缺字段/id/断id拒。TQ缺turnover仅非策略transport sentinel0，receipt逐行列unknown，不冒称真实成交额；OHLC/volume/closeOI不得sentinel。

CLI qmt_roll_weekly19_data_update.py须显式base/generation/release/target/expected-hashes-json/held-contracts-json；默认plan-only，仅--execute才TQ只读fetch。本轮未下载、无金融结果或production qualification。

## 2026-10-31 20:02来源修复补充

当前入口OHLCV/closeOI全部有限并逐字段绑定approved source，校验OHLC关系/volume>0/OI>=0及本地完成时点；future/forming即使有source row也拒。updater所有known explicit epoch新增日均核native delivery年月，sameVT新decade仍拒。新source锁为runtime_data_bridge_source_lock_v3.json（旧v2保留）。同会话桥完整接线见20261031_stage016_runtime_session_bridge_api.md；桥不赋production qualification。
