# Stage637：纯K日旧root与原新月意图的支持接口

- 2026-10-21 10:52 CST；先读registry，本线 `futures_full_market_long_signal_ai`。非重要突破；只写本stage与637小交接，不改LINE、registry或冻结旧源。
- 本阶段只查627/632/157三份小manifest及有限131/156/157源；读取四账户positions/fills/reservations/daily/capacity_audit共20个CSV header，另signal/lineage/choices三个header，合计**23次header-only open，0数据行**。157/627小manifest为提取精确绑定，在初次长打印截断后各重读一次，未隐瞒为载荷读取；没有重新hash账本。无334MB actions、full score、模型、native、SQL或新Y。
- 结论：**字段足以做一次分阶段、只读的结构支持探针；当前没有新替换单≥1lot可执行资格，也没有支持行数结论。** 原账户持仓可由position-days直接取，不能用潜在标签冒充。

## 已核字段与身份

精确绝对路径/bytes/hash、四本账ledger绑定及header版本见 `outputs/stage637_K_replacement_support/input_handoff.json`。157 manifest为72159B/SHA `0c27edef98e636032404272dda9e067e2794d7b7cf49e4ca5401b8b3ea34c7a4`，状态 `completed_with_metadata_continuation`，真实新账户4个；不是新版现金重跑。四账户是同main模型的2020/2023冷启动×base/stress，不是四个独立统计样本。

- **原候选：**157 `signals_VOLUNTARY_RESELECT.csv.gz` 583263B，SHA `c7546f99a0ce40adbc2a1772cb1ea66eb280e1ab98303c3d7b4ddbd7f35f9732`。原156正分＋pureK main胜者4365，627/629已核保留；本轮没重数4365行。`make_signals`只写selected，signal `event_id`实际上是**action_id**，另有mother_event_id。未来probe按原行使用，不读E重新选择。header有u/D、实际epoch/entry anchor、score/cutoff、N/low20/u_close/容量及source/K/effective来源全列。
- **旧root：**131 `root_id=account_id+'_'+action_id`；fills与position-days的event_id接signal.event_id，不能拿母event直接连root或猜underscore片段。position-days明确date/root/epoch/qty/mark_state/stale_days/force_next/reduce_to_next，是完成u日交易和标记、再写次日请求/减量后的真实本账户收盘存量。
- **纯K来源：**signal同时保存source_lifecycle_index、voluntary_boundary_index、effective_lifecycle_index、effective_boundary_origin，lineage只是这些字段的冗余小sidecar，无需再读。只有origin=`voluntary_calendar`且K<source才是纯K；相等来源不是纯K。旧root来源缺失/歧义一律unknown。
- **重要遮蔽：**`anchor_request`先在next_day>=expiry返回lifecycle_exit，之后才查已有force和当前canonical。因此lifecycle字符串不足以证明纯K/无别的原因，必须独立核旧product在u的当前canonical等于旧entry anchor；不得拿新候选anchor替代旧product canonical，更不要求实际非front epoch等于anchor。
- **stale/deferred：**position-days没有独立deferred列。原冻结131中，缺u bar必标stale/deferred；旧deferred遇有效bar会在snapshot前立即退出。故仍活跃且mark_state=native_close、stale_days=0的u行可由该源不变量证明当前非deferred；缺字段/其他状态保留unknown。减量由reduce_to_next与reservation交叉核，账户insolvent/stale冲突单列。
- **header变化：**某些reservation文件没有root_id/existing_qty/target_existing_qty列，其他账户有。它们应为可选schema，不能无条件索引；遇有减仓类型但无root来源仍unknown。原entry reservation的round_lot可与BUY/root当前qty联核旧lot，不能由此推新lot。

## 最小分阶段probe建议（待639冻结，尚未实施）

1. 原signals、calendar及四本position/fill/reservation/daily各一次流读＋同时hash，保存必要literal给638。四类账共3052262B，signal583263B、calendar100858B，先行总3736383B。只连真实u持仓与原u同family m1意图，不计算新路径或收益。
2. 旧entry来源纯K、D=K、u活跃非stale/deferred、force_next=lifecycle_exit、无reduction/insolvency冲突；原同u新winner须另一真实epoch，D<new K且D<source lifecycle，metadata一致。无新月winner就是无此原意图，不找次优。
3. 若已知old-pureK或same-u不同epoch匹配为0，直接结束，**跳过母表及capacity**，并明确没有canonical资格结论；来源未知另计，不能悄悄当没有机会。否则一次读627 `mother_identity.csv.gz` 的oldproduct/u/index/reference列，仅留请求的refs给独审，缺失/歧义为unknown。该cache实际**19563157B**（SHA `2c401aaa866cd2cdb29b8e8fdb769bdffb8d91c46f157affe52b1c280161d4f0`），与原母19.55MB相近，瘦字段只节省RAM，不宣称省去19MB读取。
4. 将u可知的计划支持与**事后D事实**分栏。核原同root D完整SELL、reason=lifecycle_exit、卖尽u qty且无部分/别因混合；这不代表D信息在u可知，也不代表新leg成交。若结构/canonical仍有match，可一次读四份capacity_audit共223190B核旧leg固定cap/unknown；没match则跳过。全部上限约23522730B，没有E26MB、actions334MB或native。
5. 只输出事实链、计数、unknown与skip；0已知结构支持就停止。即使正支持，也只是允许后续另冻旧槽预算设计，**不能宣称≥1新lot、原子成交、PnL改善或可上线**。原occupied与D closed_today两阻断均保留，当前没有修改引擎。

## 研究与判断

本轮沿635已真实核验的CME/QuantConnect官方与维护者GitHub：换合约需真实旧平/新开两腿，连续feed切换不能替代。这次本机事实以冻结source和header为准，不重复下载资料或假设海外执行规则适用于本线。现成632成本投影不需要读，因为它是潜在动作及K结果，不能提供真实账户u持仓；本轮只核其小manifest，没有借其Y作筛选。

开始/结束按新收益调参：否，没有读取新支持数或收益；长期同史适应性择题风险仍高。有限一次支持核查有价值，可在无结构机会时停止工程；继续预算/现金、改K/选月/stop或加仓参数当前无价值。新增/修改/删除经济参数及金融结果均0，期末权益、收益、回撤、Sharpe、滑点、交易次数、胜率全部N/A；0fit/cash/标签/新CI/新门，累计551/290+旧partial1不变。等待root冻结639后才写约200—300行独立probe与必要合成边界；实际仍由root唯一启动。

## 11:07 CST：639冻结后的实现与source-ready

本次只实现有界只读结构探针，非重要突破。依据639 `protocol.json`（17567B，SHA `455e3f33f548875bfe144e64225054f0a124b48ea0eb2f159290fa1091f07542`），新增隔离工具 `tools/stage637_K_replacement_support.py`，未改131/156/157/627、原交接文件或任何策略。上文接口阶段第4步的条件capacity读取已由最终639明确取消：**实际一律不读capacity_audit**，仅保留原fills.capacity_state；预算上限为23303979B。原input_handoff仍为31788B/SHA `c43f5550f31f2c390251cee1f47b2086b0e3c437165cadb9dd72815b22b6e2f8`，未改动。

实现将所有原账户u位置、成交、reservation、日账及4365原signals保存为literal瘦投影；calendar和family inventory原字节缓存供638独审，不只保留成功子集。u资格不读取D成交；D完整纯K平旧root作为独立事实列。只有全部前置结构条件成立而待canonical的请求，才允许一次母表流读；请求的旧product/u/index全key及missing/ambiguous状态均保存。若无请求则明确skip，不声称canonical已通过。已知false可关闭合取，结构unknown保留；newqty、新预算和两腿执行能力始终unknown，不用这些always-unknown掩盖结构支持，也不宣称新单≥1lot资格。

只运行6个新增合成行为case，覆盖无同u意图/同epoch的known-false、严格纯K/边界、未知来源/原entry关联、canonical缺失和变化、D独立完整/部分/混合平仓、真实旧lot及数值0减量阻断。TDD真实过程：首轮6 FAIL为新工具不存在；首实现轮6 ERROR为一处未闭合括号，定位后仅补该括号；相同6例最终GREEN，unittest用时0.105秒、exit0。未重跑旧suite，未预读历史CSV数据行，未启动actual。执行收据保留RED、该语法错误与GREEN，不能将中间失败隐藏为一次通过。

- 冻结源码23682B，SHA `c30bc65c75fce62c9135aeb69044090187053cf94285e8abd5632ed67658aa94`。
- 新测试 `tools/test_stage637_K_replacement_support.py` 6365B，SHA `f2799eee7e5efea6b7f366f483d4f33ae6a3afd8d04e7a5c9632aed2778b5a3b`。
- `outputs/stage637_K_replacement_support/fixture_receipt.json` 1435B，SHA `c112f2c037da824c4f0c84b2e46df5a47a4a9d0c42f5874a41a2b134a15e1f33`。
- `outputs/stage637_K_replacement_support/source_ready.json` 5826B，SHA `2a7a7d1b6ce0bb22677f5d0e09a3b5c4055412f1a2f8f0c97697d45ca0613fae`，绑定协议、源码/测试/收据、旧纯IO helpers、全部精确输入与缓存schema。

唯一实际命令已交root与638；须待638一次完整source GO，由root执行，作者未启动：

```sh
.py311/bin/python -B research/lines/futures_full_market_long_signal_ai/tools/stage637_K_replacement_support.py --protocol research/lines/futures_full_market_long_signal_ai/outputs/stage639_K_replacement_support_protocol/protocol.json --source-ready research/lines/futures_full_market_long_signal_ai/outputs/stage637_K_replacement_support/source_ready.json --output research/lines/futures_full_market_long_signal_ai/outputs/stage637_K_replacement_support/actual_run1
```

本轮没有新收益或支持数量结论；历史研究截止2026-10-16，本探针不等待今天收盘，与u20→D21前向任务分开。开始及source-ready结束判断均为：没有按新收益过拟合，但长期同史择题风险仍高；有限一次结构核查仍有价值，现金引擎/新预算工程尚未获数据支持。新增、修改、删除经济参数均0，金融指标全部N/A；0fit、0cash、0新标签、0新CI、0新门，累计551fit/290已完成cash＋旧partial1不变。后续仅root唯一actual及638独立literal复建，若结构为0直接停止。
