# Stage326：一次历史末日快照与Wilder暖机适配

时间2026-10-20 03:09（Asia/Shanghai）；所属`futures_full_market_long_signal_ai`。非重要突破。按registry/324 next_scope及root实施授权，只新增本工具、同名test、唯一stage和本输出目录；不改320或任何旧源、LINE/registry。

**代码完成，当前真实读取仍为0。** 只读小manifest/源段与roster小asset，并对SQLite做2次schema PRAGMA（先误查不存在bars为空，再daily_bars；均无数据行SELECT）。未加载110MB cache/8MB经济投影、未跑真实日推断，0fit/cash/旧控制/旧suite/下载。真实read仅root另签327 exact授权后由root启动，不由作者执行。

## 最小接口与输入身份

`load_snapshot(authorization,*,output,core=None)`要求root精确source bundle/inputs、固定2026-10-16、development_only和cache1/econ1/同日dataSELECT1预算，输出fresh目录；门内才可加载。其normalized snapshot直接供325：dates/economics/products/series_by_epoch/warmup_state/market、u/date/index、D_context、model/scaler、clock、source_receipt/source/version/received_at；始终`development_only=True/frozen_at=None`。

[输入bindings](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage326_historical_snapshot/implementation/input_bindings.json)含真实132小manifest及110273488B NPZ（大SHA继承不重hash）、378552320B nativeDB stat、原5587日期calendar、原经济projection、004 roster小CSV、317原main2023 portable/scaler与单位合同；固定source数据read方案为：

```sql
SELECT contract_epoch_id,trade_date,open,high,low,close,volume,close_oi,
       quality_status,source_id,source_locator
FROM daily_bars WHERE trade_date=? ORDER BY contract_epoch_id
```

参数唯一2026-10-16。表列已schema核；严格same-day SQL与cache的全部epoch/OHLCV/accepted-quality逐值相同，否则失败而不改源或重取。实际cache unpack仅复用132 `restore_native_cache`必要格式（epochs/offsets及days/values5/accepted/valid/N/low20/run），不import132巨审或其CLI；实际必须核9520epochs/1552456rows、cache末日与固定日一致。全cache身份派生产品集和004 roster双向核exact98/95family，不读19MB mothers。

## 暖机与缺失

每个有精确u bar的epoch，直接取cached N/run/lastclose，seed从该valid-run起点头20TR按原逐项float顺序求，绝不以最近21bar重播N。lowqueue由同run最近20bar按原单调队列重建；history保留最近21bar与cached N/low20/run，当前closeOI来自唯一同日SQL，过往OI始终unknown/null、不填0。状态为320 `WilderState` strictJSON。

无u bar的旧epoch只给无当前行的array尾窗，不拿latest<u state当u报价；`market.bar`精确index，不carry。固定98父域交给320保留，来源known catalog超域由320报告unsupported，不宣称未来永久全市场覆盖。经济映射仍原static snapshot限制，无邻月代理或新资格证明。

独审证据足够328独立重算当日全pool/anchor/raw26而0二次cache/SQL：当前全部11列rows；仅当日有bar各epoch的21bar、前置Wilder checkpoint、cached参考N/low20/run和最终JSON状态；全部9520epoch inventory(lastindex/date/product/count)证明不carry。没有为无当日行为的旧epoch重复导价格。

D只来自原bound source calendar的真实后继；末日后继未被该calendar提供就confirmedFalse，不能自然日加一或凭之后另取报价编2026-10-19。clock source_completed_at与D_open_at在无proof时None，首发/PIT未知；received_at仅本次本机实际加载时刻，325 journal决定自身实际firstseen，不回填成当年可见。历史演练不得初始化真实forward账或推进真实D现金。

## 一组tiny与输出

唯一`test_cached_Wilder_continuation_and_missing_current_quote`含3子例：手算cachedN=2.69640284375、seed40/run26、JSON后续N=2.6615827015625；run起点不取gap前巨大close；stale月份不carry、完整产品/clock unknown、同日SQL/cache不一致必拒。先RED未实现；中间手填十进制cache与二进制递推末位差导致exact-dict断言失败，改为N重放1e-14并保留cachedN原值严格断言；随后断言None转float错误已修。最终仅此新组exit0/1test/3子例/0.227s；不跑320旧测试或其他suite。

最终[实现bundle](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage326_historical_snapshot/implementation/source_bundle.json)、[tiny终态](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage326_historical_snapshot/implementation/fixture_terminal.json)、[root授权模板](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage326_historical_snapshot/implementation/authorization_template.json)已落，模板authorized=False。实际source_receipt会写cache/econ/dataSELECT次数、源前后stat、当前rows/cache核对、currentepoch数与所有产品状态；失败则保留source_failed，不重试/隐式fallback。

新增/修改/删除策略模型参数、回测结果均0；权益/收益/DD/Sharpe/费用/滑点/胜率N/A。沿324已有官方预处理/维护者因果原则，不重复外网。本次不新增过拟合搜索，既有模型择题风险不消失；一次历史接线有价值，因为可发现真实输入暖机/身份问题，但不会变成forward或alpha证明。后续仅root exact授权运行后328独审，不启动下载、生产、定时或CTP。
