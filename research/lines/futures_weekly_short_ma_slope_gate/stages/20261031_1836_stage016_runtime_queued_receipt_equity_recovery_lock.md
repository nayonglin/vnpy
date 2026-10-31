# Stage016 queued receipt / 真实E恢复 / 最终源锁V2

记录时间：2026-10-31 18:36（上海）。本次继续原正式迁移，未改变alpha参数，565原class/function AST保持。未跑金融回测、未连接CTP、未下载行情、未操作Git index/commit/push/生产。是否过拟合：否，改动只闭合来源与异步状态边界；是否仍有价值：是，不能因现金证据/普通终态/自然权益恢复而丢失原保护或永远冻结同原周信号。

## 已先RED再修复的边界

1. queued day的decision绑定新receipt，但原currentReceipt未更新，实际PipelineStateStore拒绝origin。现在先设operational day/receipt再reconcile，异常restore，不调用on_bars。close retry与无quote参考带新target/newreceipt，lifecycle_origin_signal_receipt保存原周信号。反例通过实际Store initialize/read及weekly evaluate_intent执行门，不仅检查内部字段。
2. Friday E120k原生candidate无openplan，T未到，下一执行日经真实现金中性day-close proof后E151k/T0。旧API硬要求T增加而永久拒。现在在funding.assert_open_funding_ready通过后允许真实E>=150k恢复路径；R、T、receipts原样，不新建候选/request、不回放AM，原funding admission与一次批准cap幂等。未知Deposit与E149k/pending仍拒且actor不变。原真实T路径维持。
3. 已到期、非主力且无实际仓的offmain合约不可能有新bar。新的真实expiry packet可明确停更并单列receipt，保留旧历史；main/actualheld缺bar仍拒，post-expiry矛盾bar拒。否则月末可能错误要求伪造或永久block。

## V6 provider到runtime实际接缝

新增ProviderChildIntegrationTests，使用真实quota reserved完整子请求结构与beforeinsert checksum，按实际open2→close2 runtime身份重建；从原始CTP query Order/Trade fixture经public derive_order_intent_bindings/load_broker_fills/load_broker_order_updates进入runtime。SHFE child3 filled、child4 working后父剩1跨重启，新querygen第二actualfill后父完整结束、原outcome/streak一次；同query/fill/order重复稳定no-op。测试只fixture，不伪称真实broker来源/生产资格。

## 最终检查

全部weekly19组件343 tests/17.910秒绿；此前并行executionowner补quota事务时出现的中间态RED不覆盖、不当作终版缺陷。原565 AST等价仍绿。新代码公共API详见同目录20261031_stage016_runtime_final_api.md。

最终技术benchmark对当前source始末SHA一致：实际392382已批准日K、2093 AM，strict fixture账户与synthetic request/decision，0 on_bars/金融/CTP/下载。clone0.122745秒，完整revalidate3.809320秒；热export3.668507秒，完整restore26.646556秒且state SHA一致。单durable5090984 bytes；实际双state PipelineStore bundle10186712 bytes，initialize/fsync0.139724秒，read/validate0.531291秒，低于64000000限制。整个技术流程峰值RSS约2.984GB。该量测不授予总链路deadline、行情来源或生产执行资格。

## 仍需上游证明与明确边界

- 本线source锁/技术测试不等于release qualification/activation；所有本组件输出production_qualified=false。
- 真实市场下载、entitlement、实际provider authority与源capture闭包由父流程证明。本轮未实际下载。
- 同vt跨十年新physical epoch保守拒绝latest，需要另审epoch级scope及已owned/signal/spec复用；新未知vt的真实delivery/expiry+id0连续available history支持，法律上市未知独立标记。
- 假日周Thursday信号，父Friday可用同原admission/Thu receipt独立recommend canonicalFriday；本模块不重新on_bars、不造新funding candidate。
- 原研究59曲线未复跑；真实actual close后方向outcome/streak时点与研究计划价执行差异仍列明，brokerE不重复加close PnL。

## 源锁

- `examples/portfolio_backtesting/qmt_roll_weekly19_runtime.py`: `8df75a5464c5a6fd92d346cc168629153e40cddd18c897fe2cd4b09c186a89f5`
- `examples/portfolio_backtesting/qmt_roll_weekly19_data.py`: `3cf9ab9d1822390dfd32e1d8cb5bdfe7f8dc3bf621d1e05da1b375e6ad730eb5`
- `examples/portfolio_backtesting/qmt_roll_weekly19_data_update.py`: `f4ed5475649a873bd3698391dd99973385096f0fbdc1ccd108d2b828dd88e691`
- `tests/test_weekly19_runtime.py`: `08f0ea79f4898987bbc5644ee834be5cff2a917bf400881613909b6f6000f095`
- `tests/test_weekly19_strategy_equivalence.py`: `ef03927995ea9c7cec41f43952f08c58d99700b64f786017bfaf89c46ba025cd`
- `tests/test_weekly19_data.py`: `3bfa39d22ddb3f4b1d9cb7f46d0ab2a629de8523652eacb05b4ae2984a41de68`
- `tests/test_weekly19_data_update.py`: `6c561063c6d392f8668103a3baad5af2fcd259395caf604f66c730cc73fd2d50`
- `examples/portfolio_backtesting/weekly19_assets/source_manifest.json`: `b473e88f21d2d139615e638c9df0e0fac5358596d919624f55411438926a303c`
