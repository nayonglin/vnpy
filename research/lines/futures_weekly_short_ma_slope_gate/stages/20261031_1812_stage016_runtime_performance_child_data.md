# Stage016 runtime无损性能、真实子单聚合、数据更新器

记录时间：2026-10-31 18:16（上海）；本次不是重要alpha突破，不改变原C规则、不跑金融回测、不下载行情、不连接CTP、不提交Git、不写生产。是否过拟合：否，565个原class/function AST不动，仅解决执行与数据来源边界。是否值得继续：是，真实资金权威、普通异步终态和可恢复性是正式迁移必需条件。

## 变更与验证

- 保存schema不删任何AM/PositionState/Layer/风险/roll/pending字段。固定白名单sharedref仅指向用已验证calendar重建的weeks，digest与过去calendar prefix校验；strategy/engine使用标准库zlib+base64无损编码，解码有大小/digest边界、无pickle。老v1 inline快照可恢复；新strategy段不能脱离Runtime shared表直接_decode。
- sizing clone不调用构造器，完整保留全部产品/持仓/方向风险与组预算；仅共享不可变来源与completed AM历史，所有可变层/数组/risk/broker/intent状态独立。原sizing仍根据当前真实E/Available/quote重算，原批准量cap，真实actor不被推进。
- accepted_scope保留旧contracts与physical字段列，旧契约截止cursor的physical/spec/mapping/calendar语义不可改。仅从未owned/pending/原生signal的新vt合约在有明确交割年月/到期rawpacket、id0连续available history与真实SQL DTO时预热新AM。法律上市未知独立标记；不调用on_bars、不改资金、不回填历史open。此前cursor前尚未可用的新合约不虚构旧bar。
- SHFE 1+1物理子单有真实api_slot_reserved完整logical manifest和SHA，实际brokerID到达后逐child绑定；第一child filled/cancel不能提前结束父计划。未知/未发child保持pending；全child终态后仅真实remaining可retry；actualfill累计全部目标后原outcome/streak只调用一次，brokerE不加该PnL。manifest换绑/跨父brokerID复用拒绝。execution_batch_id与api_slot_batch_id一致别名可接。Provider V6必须从真实quota ledger重建名单；runtime不鉴定来源资格。
- 精确现金连续性allowlist处理沿用前记录：资金缺证只阻open，不消除原保护close。schema/foreign/stale/badaccount继续硬拒。

全部owned调用80次/9.158秒绿（含继承/重复reader测试），原565 AST等价绿。跨owner全套结果另单列日志，不以在建RED冒称全部完成。

## 实际数据技术性能（不是金融复验）

实际冻结19品种392382条已批准SQL/physical一致日K、2093 AM；严格fixture账户/未来执行日与明确synthetic sizing request/decision，只warmup，0 on_bars/金融/CTP/下载。

|指标|修复前|当前锁定实测|
|---|---:|---:|
|单durable JSON|247476098 bytes|5090958 bytes|
|sizing clone|154.085 s|0.123 s|
|当前E原规则revalidate|未完成独立计时|3.780 s|
|热export|31.636 s（前次第一次）|3.651 s|
|真实PipelineStore双state bundle|超64MB|10186660 bytes|
|双state initialize/fsync|不可用|0.137 s|
|双state read/validate|不可用|0.517 s|
|完整restore|未完成独立计时|26.863 s，stateSHA一致|

当前build8.364秒，纯warmup30.198秒，首次export8.890秒，技术过程峰值RSS约3.20GB。两份完整runtime+decision_origin通过实际PipelineStateStore写盘和读取，低于64000000 bytes。源文件SHA在锁定benchmark始末一致。该量测不构成真实行情、broker、订单、deadline整体资格或旧59曲线再次复验。

## 数据reader/updater

load_weekly19_inputs显式五文件SHA前后与forwardcalendar前后hash；SQLite标准库readonly DTO逐行核验，不依赖不同字节的vnpy_sqlite driver。实际392382/392382 OHLCV+closeOI行一致、无missing/duplicate/mismatch；研究historical main reconstruction缺口仍保留。

update_weekly19_assets仅新private generation，fixed19+全部current tracked物理合约+显式实际持仓，TQ只读mapping helper显式19，raw serial必须close_oi，全部源packet保留，旧SQL全列EXCEPT/行数守恒，已批准CSV历史不覆盖。先完成新generation严格reader检查、全文件fsync/只读文件权限，再原子latest；失败latest不动。

无单独approved physical_epochs时，build_legacy_epoch_seed_from_approved只用已有explicit contract_yyyymm/epoch生成observed_min/max；listed/delisted unknown，不猜CZCE十年，不回填范围外旧history。新vt合约用真实delivery_year/month+expiry packet与id0连续0..N available history，legal listing保持unknown。

TQ日K无turnover时仅SQLite/DTO transport sentinel0；receipt turnover_unknown逐contract/day/rawSHA列未观察记录，turnover dependent策略不合格。OHLC、volume、closeOI、date、epoch不得用sentinel替代。

真实SDK下载尚未执行，entitlement和native capture source资格仍需父流程验证；fixture backend结果不授予production qualification。当前代码同vt跨十年新physical epoch仍保守拒绝latest，不能冒称全部未来epoch自动可用。未来需要epoch级accepted scope/已owned和signal记忆/metadata复用独审。

## 官方资料判断

TQ官方API说明delivery_year/month、expire_datetime及日K open_oi/close_oi，支持直接保留真实字段；本地旧datafeed将open_oi映射open_interest，因此更新器不能复用其save路径。复用Stage173仅fetch mapping参数化函数，不调用旧池/全局mapping/db入口。官方论坛id0建议可作数据起点，但我们只承认vendor available-first，不冒称法律上市或PIT完备。

- https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.api.html
- https://doc.shinnytech.com/tqsdk/latest/reference/tqsdk.objs.html
- https://github.com/shinnytech/tqsdk-python/blob/master/tqsdk/api.py
- https://forum.shinnytech.com/question/8501/

## 源码锁

- `examples/portfolio_backtesting/qmt_roll_weekly19_runtime.py`: `4bebf18e99df17abedcde3a55a2ee9d1e4061846049a3948419ed782cf2a21df`
- `examples/portfolio_backtesting/qmt_roll_weekly19_data.py`: `3cf9ab9d1822390dfd32e1d8cb5bdfe7f8dc3bf621d1e05da1b375e6ad730eb5`
- `examples/portfolio_backtesting/qmt_roll_weekly19_data_update.py`: `708f38c9380edbce93afe92dd67b532e646f2dfe7f6c4db324e7b30e434b1322`
- `tests/test_weekly19_runtime.py`: `1075f8d67b0e2c3f17d9ebdd4123f416f08922a91302147c02fe0238f47dde8e`
- `tests/test_weekly19_strategy_equivalence.py`: `ef03927995ea9c7cec41f43952f08c58d99700b64f786017bfaf89c46ba025cd`
- `tests/test_weekly19_data.py`: `3bfa39d22ddb3f4b1d9cb7f46d0ab2a629de8523652eacb05b4ae2984a41de68`
- `tests/test_weekly19_data_update.py`: `ce8fa92a28bcb96ef3308af3f941517ab25e552a67a269847b7d8bb97e1b37c5`
- `examples/portfolio_backtesting/weekly19_assets/source_manifest.json`: `b473e88f21d2d139615e638c9df0e0fac5358596d919624f55411438926a303c`

无新增/修改/删除alpha参数或金融回测结果。资金wrapper与执行实际价时点差异已明列：真实close完成后以actual累计PnL结算原方向outcome/streak；原C倍数全1且recovery False仍保留flags。production_qualified=false；不得复制旧59结果当live收益。
