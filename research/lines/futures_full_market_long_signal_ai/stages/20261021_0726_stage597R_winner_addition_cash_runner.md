# Stage597R 重复赢家独立新批次：四现金runner实现

- line_id：`futures_full_market_long_signal_ai`
- 时间：2026-10-21 07:26 CST
- 协议：596 `3985c8fa70fdcb31f3712dc1fff58ea8d449579a0b31eff17ca2110b18fa894f`。
- 本agent范围：仅`stage597_winner_addition_cash.py`及必要runner fixture；机制kernel由549负责，不代写/改其文件。
- 阶段性质：source就绪，未actual；非重要突破，非新收益结果。

## 实现

复用157的原cached market、full mothers canonical参考、原報表、paired_statistics与fixed_gate。接受157的`completed_with_metadata_continuation`状态；4条原OWN A summary/daily/显式fills身份只读，不回放A，不碰旧575 capguard/source_diff。

完整原157 signals一次并逐u校验原cutoff，primary包含两段模型时期，不按账户固定cutoff截断。mother只取必要身份列；native缓存一次结合hash恢复；经济一次；两份原bootstrap数组一次。四C自己的预算/持仓/权益由kernel产生，本runner不重算entry或调参。

输出原完整C ledgers、add_audit、实际add根BUY/SELL、实际根费用/滑点年家族分组；fresh A/C身份对比排除实际add根，保留A_only但C同event为add的标记，避免把动作替代误叫完全错失。C原95家族逐年及合计含0、四A/C年度/主指标/原indices CI及原门均保留。根数、audit行数不是独立样本或因果PnL贡献。

material add_unknown与原entry/capacity/stale unknown并入C账户不确定性；原Aunknown保持。source_ready将绑定runner/kernel两组源码/fixture及各自真实通过回执，回执必须与当前文件绑定一致；root独立审后才唯一actual。fresh输出保留真实start/attempt/progress/失败terminal，不因观察超时重启。

## 合成fixture

3项runner fixture通过（exit0）：fresh overlap中实际add根排除及same-event替代、material add_unknown/实际根费用计数、跨2023原cutoff逐u校验不截primary。只有新必要fixture，不跑旧suite，不读实际大输入。红测曾是对应缺实现的3项预期失败。

- runner SHA：`7e6264aacda4984934e630d0f32ed2b940bcde24bd29da3cc18bf777c4a40f1c`
- fixture SHA：`ba0cb83d4d12cf5097dcb53a6d50dc81451982778f756eab2346635a7c4e14c1`
- 回执：`outputs/stage597_winner_addition_cash/runner_fixture_receipt.json`
- K source/receipt到齐后补总source_ready，不替549重跑测试。

## 计数与反思

本轮0fit/0cash/0A replay/0SQL/0GET/0真实大输入行。新权益/收益/DD/Sharpe/滑点/交易数/胜率均N/A；累计仍547fit/282完成cash及1旧partial。

新增参数：无策略参数；仅协议、source-ready/两fixture回执与fresh输出CLI。risk/stop/interval/unit数未改。

调研沿596已核原作者Turtle发布资料和vn.py维护源码；它们只解释机制与时序，不能证明加仓有效。开始/结束过拟合判断：本实现无新拟合或扫描，但长期历史筛选风险高；开始/结束继续价值：有，只因已冻结一次4C可以证伪全账户机会成本，不预设盈利，不单看新增根收益。

未改LINE/registry、Git、正式C9、生产。runner源码已先发598定向审；root唯一actual及598全审后再补新结果。

## 整体source_ready绑定完成

2026-10-21 07:29 CST：metadata-only `--check-source` exit0，输出`outputs/stage597_winner_addition_cash/source_ready1/source_ready.json`（SHA `d12881e6d5fbae5490b9449f63a52d62d8b57e1d108ea61a8a172b27229f8bc4`）。绑定R 3项/K 8项真实通过fixture回执，K源码`9b9ca580d3d5ffb9271b5af86dd82779ee03bbfe67dea8b507dc20b3308a1209`，K fixture`c93934978a26aa88910b48ac4da9668a246c624d87f1f0d479631d2a2358c891`。598已对R源审GO；root已有唯一actual CLI，K源审仍由598完成。本agent无actual，计数不变。

## preactual K修正后source_ready2

2026-10-21 07:31 CST：root/598指出K多出的actual_epoch=canonical gate不属于原131/596；549已仅删除该限制并把现有8fixture改为合法非canonical选择，8/8通过。K v2 SHA`66229dccd949f7721f61ed9af029ae7296cc0c4e9ca667d513a384665a64e6bc`，fixture`d78b418a3b3cba25d708fb20986c47beb7a37394d84b0797f970f23ca5602e55`。本agent保持R冻结，不重跑3Rfixture；metadata-only check-source生成`source_ready2/source_ready.json`，SHA`598bed04ec8de88f9c3108b246898da522ee0e27ed74ca2cab593e79c36c8ab1`，ready1保留不能用于新源码。全部修正发生actual前，0大源/0现金；root已获新唯一CLI。
