# Stage148：单一 FX 对照四账户实现及唯一 actual 事实，149 独审在途

- line_id：`futures_full_market_long_signal_ai`；实现记录：2026-10-19 00:05 CST；actual事实追加：2026-10-19 00:19 CST；非重要突破版本。
- 下列“实现/未启动”段落保留00:05时的原始状态；唯一actual完成事实见文末，149仍在途。
- 先读 registry、本线 LINE、Stage145 固定计划及独审，最终协议 SHA 实核为 `be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270`。本次仅实现、合成测试与接口绑定；没有新实际 fit/cash/SQL/标签/下载/全库 hash，不改旧工具、LINE、registry、官方策略或其他研究线。
- 新增源码 `tools/stage148_fx_cash.py`：32147 字节，SHA `aeafaa60756966b67a7fde08bac634e1566ebe5e8dc46790dc571b5308d6d144`；新增测试 `test_stage148_fx_cash.py`：8244 字节，SHA `d20a2146eef6edd147886956afcb7852bb1cc5459cf8a5d835a6d4942f329e35`。

## 实现边界与判断

147 的全域 `choices_main` 含 CONTROL_REUSED/FX 各161014母行，148先保留完整母域身份并只取新FX实际选中真实child。送入accepted131 `make_signals` 的 B 仅为局部schema别名；输出 `arm/control_id=FX`，event_id为真实child，mother_event_id、canonical anchor、held epoch均保留。不会用旧B选中母行或正分月池作为新FX准入门，也不以未来label闭合/执行已知筛样；旧模块ARMS不变，无global monkeypatch。

仅新增 FX×2020连续/2023独立冷启动×base/stress四账户。只通过accepted132 `cash_only1/native_store_cache.json`与NPZ恢复既有native arrays、Wilder N/low20/run及原5587日历，不SQL、不重新导出行情或重算指标。复核源库stat，不hash大库。经济参数沿128绑定原market projection。accepted131全部源码/内核与原现金manifest source_bundle必须字节相同。100万元、0.25N初损、0.25%单族/2%总风险、25%margin/1.1buffer、u联合预留/D只减、1%毛周转/往返半容量、anchor与原退出规则完全不变。

旧四本131-B只读取exact summary/daily/diagnostics，保存为CONTROL_REUSED引用，不复播或重新审查旧八账户。四新本保存fills/reservations/daily/positions/closed/open/capacity_audit/entry_execution_unknown/rejections九表与summary。输出年度、95family含零归因、金融/商品、普通/F、最大盈亏、容量/entry unknown、开放/stale及零价场景。金融/普通F归因包含开放仓按原close mark的净贡献；滑点只归因，不在已经含滑点的成交价后再次扣除；费用仅按原账本扣除。

比较为FX减CONTROL_REUSED，严格同u/source日；直接绑定070原252日块/2000次indices，不重新生成seed。破产、非正或非有限财富不补epsilon、不删除路径，CI保持空。145门逐项固定：2020stress自身正收益、相对收益严格增加、回撤严格更浅、CI下端>0，其余三组自身正收益、相对收益/DD不恶化；两held完整前向known平均增量非负且保留未知。不同动作unknown不填0；历史stale/entry/capacity/differential-held未知不能变成通过。归档/PIT限制始终披露，goal/生产/加注资格保持false。

调研沿145已冻结ECB归档时钟、最终修订限制以及既有容量/现金文献与GitHub代码判断，本次没有新增经济假说或重复外网研究：这只检验单一保守滞后FX状态模型包，不能把全球q称为月份专属信息、因果冲击或普适alpha。

## 上下游与授权

147 manifest schema=`stage147_fx_fit_v1`，需 `status=completed/cash_eligible=true/protocol_sha256`、choices_main/held_diagnostic/bridge_preflight/terminal bindings。terminal必须完成6fit、0cash/SQL；bridge要求`status=passed/control_bridge_verified=true`。148 schema=`stage148_fx_cash_v1`，accounts为四条FX账户，每条含summary与九表bindings；baseline_books保留四条旧B来源身份和`source_only=true/replayed=false`。现金started/completed及失败terminal真实保留，异常不自动重试。

root cash auth为`stage145_exact_root_authorization_v1`，authorized_by=root、stage=cash、exact_source_authorized=true、最终145 SHA、fresh Stage148输出及 `source_bundle()` 14项逐文件绑定。exact input_roles为：actions、mothers、dataset_manifest、accepted_cash_manifest、accepted_review_receipt、native_cache_manifest、native_cache、execution_protocol、market_protocol、fit_manifest、choices_main、held_diagnostic、bridge_preflight。前八绑定145，market_protocol绑定128，后四绑定完成147。

实际命令（尚未执行）：`.py311/bin/python research/lines/futures_full_market_long_signal_ai/tools/stage148_fx_cash.py --protocol <145绝对路径> --protocol-sha256 be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270 --authorization <root cash auth绝对路径> --authorization-sha256 <auth SHA> --output <fresh Stage148目录>`。

## 验证、参数与结果

新增七个合成测试：仅FX四账户计划；全域FX可选旧控制未选母行且真实child/anchor不变；主2020stress DD必须严格改善；stale/执行/held未知不能通过或填0；原indices/严格共同日期/非正财富无log修复；金融/商品与普通/F包含开放净贡献且滑点不重复扣。测试先观察缺实现或缺字段的预期失败，再实现转绿；独审发现accepted042的write_json使用exclusive create，会令原同名cash_progress在第二账户冲突。仅改为cash_progress_01..04逐账户唯一收据，新增连续两次真实writer的fixture，先RED后GREEN；无策略或资金修改。最新`Ran 7 tests in 0.045s, OK`。py_compile和CLI help均exit0。只跑本次新fixture，未扩旧suite；合成测试不代表真实收益或新现金账户。

新增参数：仅schema/arm别名、auth绑定与四账户固定排程，无新增经济、止损、容量、风险、费用参数。修改/删除参数0。新增/修改/删除实际回测结果均0。期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数、闭合笔数、胜率均N/A；本次新fit/cash/SQL=0/0/0，145前累计391fit/202cash不变。

开始与结束按本轮收益调参过拟合：否，尚无新实际收益且未改变科学设计。历史同史择题与最终归档假设风险：是。继续一次固定对照有价值：是，可有限证伪新信息包；扫符号/lag/窗口/风险救参无价值。TODO：root绑定完成147并精确授权一次四账户actual；149按新增材料做一次全面独审，禁止重播旧策略或以名义收益清除执行/PIT未知。


## 唯一 actual_run1 完成事实：149 独审在途，尚未独审接受

记录读回时间：2026-10-19 00:19 CST。root执行本次唯一现金运行，从2026-10-19 00:13:23至00:13:47 CST，耗时`23.882958583009895`秒；terminal `status=completed/exit_code=0/error=null/cash_accounts_started=4/new_cash_accounts=4`。本段只登记已保存产物，不重新计算策略、账户或置信区间。Stage149唯一新增资料全面独审已由root签发并在途，以下只是作者产物事实，**尚未独审接受**。

真实参数完全沿145/128/accepted131：本金100万元、0.25N初损、单family风险0.0025、总风险0.02、margin cap0.25、buffer1.1、原base/stress费用及滑点、u联合预算/D只减、固定1%毛容量和往返预留。没有修改/删除参数，没有根据本次收益追加符号、lag、窗口、模型或风控。四实际新增账户只属FX，旧B四本CONTROL_REUSED全部exact引用，`old_baseline_replays=old_control_cash_replays=0`；现金阶段新增fit/SQL/标签/下载/全库hash均0。147已完成6fit，本包累计变为**397fit/206cash**。

### 四本新 FX 完整金融摘要

| 窗口/成本 | 期末权益元 | 总收益% | 最大回撤% | Sharpe | 手续费元 | 总滑点归因元 | fills | 闭合笔数 | 闭合净胜率% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 2,943,480.4360 | 194.34804360 | -13.85474513 | 1.30484952 | 62,704.5640 | 155,396.7621 | 2629 | 1313 | 14.775324 |
| primary_2020/stress | 1,862,846.9545 | 86.28469545 | -10.89824454 | 1.08343718 | 65,398.0455 | 145,533.0239 | 1696 | 845 | 14.556213 |
| cold_2023/base | 1,866,630.4670 | 86.66304670 | -16.18100036 | 1.32972264 | 24,364.5330 | 59,068.9366 | 1124 | 561 | 14.973262 |
| cold_2023/stress | 1,502,805.4850 | 50.28054850 | -12.48770193 | 1.19819847 | 42,139.5150 | 89,014.1399 | 946 | 472 | 15.677966 |

收益和权益已按原账本扣费，滑点已在成交价中体现；表中“总滑点”只是归因金额，不再次扣除。交易次数同时披露fills与闭合笔数，胜率使用闭合episode净盈亏。

### 四本旧 CONTROL_REUSED 参考金融摘要（不重播）

| 窗口/成本 | 期末权益元 | 总收益% | 最大回撤% | Sharpe | 手续费元 | 总滑点归因元 | fills | 闭合笔数 | 闭合净胜率% |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 2,791,088.1945 | 179.10881945 | -15.05514962 | 1.24748385 | 59,041.8055 | 147,866.6573 | 2630 | 1314 | 14.079148 |
| primary_2020/stress | 1,569,355.1670 | 56.93551670 | -10.72842046 | 0.94913190 | 57,124.8330 | 127,727.1393 | 1547 | 772 | 13.989637 |
| cold_2023/base | 1,841,968.6025 | 84.19686025 | -16.65223808 | 1.29626523 | 23,651.3975 | 58,375.7036 | 1098 | 548 | 13.868613 |
| cold_2023/stress | 1,524,031.5110 | 52.40315110 | -11.83290777 | 1.21046910 | 41,628.4890 | 90,365.3500 | 922 | 460 | 14.782609 |

上述来源分别为原`NARROW_B_primary_2020_base/stress`、`NARROW_B_cold_2023_base/stress`的summary/daily和共同diagnostics；其逐项精确path/bytes/SHA保存在本次`baseline_references.json`及manifest `baseline_books`，不是新账户或新控制资格认证。

### 四组配对置信区间与冻结门

单位：收益差、DD差为百分点，DD差>0表示更浅；CI为每日log增长差，使用原070的252源日块/2000次indices，四组`status=valid`，未重生成seed、未做epsilon修复。

| 窗口/成本 | FX−CONTROL收益差pp | DD差pp | 每日log差均值 | 配对CI95下端 | 配对CI95上端 |
| --- | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 15.23922415 | 1.20040448 | 3.23561468619e-05 | -5.46231152377e-05 | 0.000108289441454 |
| primary_2020/stress | 29.34917875 | -0.16982408 | 0.000104346393721 | 1.27529487621e-05 | 0.00020678578372 |
| cold_2023/base | 2.46618645 | 0.47123773 | 1.45355451909e-05 | -4.22348971838e-05 | 8.09189389483e-05 |
| cold_2023/stress | -2.12260260 | -0.65479416 | -1.53283595577e-05 | -6.52182359732e-05 | 3.34913751742e-05 |

保存的gate为`status=unsupported/cash_nominal_pass=false/held_known_nominal_pass=false/nominal_pass=false`；FX四本自身收益为正、wealth正，但主2020stress回撤更深0.16982408pp，未达“严格更浅”；2023stress收益减少2.12260260pp、DD更深0.65479416pp，也未达其余三组不恶化门。因此即使主2020stress配对CI下端>0，也不能覆盖其他预声明失败条件。

两held完整前向family-u事实：holdout_0 known等u均值`0.00022177639638814095 R`、62434 family-u中62429 known、不同动作unknown=5、共同未解相同动作=38，保存status=unknown；holdout_1 known等u均值`-0.0010666206998949715 R`、93651/93651 known、不同动作unknown=0、共同未解相同动作=35，保存status=unsupported。held_1负增量直接未过门；held_0未知未填0。main全域选择FX4952、CONTROL4917，保留完整161014父行/arm；FX4952个source child均来自完整129动作域。

### 现金未知与暴露

四FX全部`execution_unknown=true/any_historical_stale=true`，下表按实际账本披露；容量fill/episode数字相同不表示真实成交已证明。terminal开放仓与历史stale分别记录，不因期末非stale便删除历史未知。

| FX窗口/成本 | 容量unknown fills/roots | entry unknown | 历史stale天 | 期末open/stale仓 | 期末open名义元 | max stale名义元 | min stale-zero权益元 | min all-open-zero权益元 | gap损失>1R次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| primary_2020/base | 48/48 | 4 | 1227 | 3/2 | 1,114,990.00 | 699,800.00 | 801,198.4030 | -186,857.6775 | 39 |
| primary_2020/stress | 24/24 | 1 | 1227 | 2/1 | 437,460.00 | 348,200.00 | 756,234.3385 | 449,356.1550 | 25 |
| cold_2023/base | 20/20 | 0 | 3 | 2/0 | 759,825.00 | 293,230.00 | 957,114.3880 | 50,689.4075 | 19 |
| cold_2023/stress | 10/10 | 0 | 2 | 2/0 | 250,740.00 | 251,340.00 | 966,056.0870 | 497,788.9890 | 14 |

旧控制同序四本容量unknown fills/roots为50/50、20/20、17/17、8/8；entry unknown为3、0、0、0；期末open/stale仓分别2/1、2/1、2/0、2/0，均仅引用旧保存数据。本次`financial_unknown=true/held_signal_unknown=true/execution_unknown=true`；零价权益只是预声明场景，不是普适损失界。尤其2020base全开放仓零价场景历史最小权益为负，不能把理想正收益称为已证明可生存的真实执行。

年度、95family含零、金融/商品、普通/F、最大盈亏及全部开放/未知审计分别保存在`annual_slices.csv.gz`、`family_year_including_zero.csv.gz`、`family_total_including_zero.csv.gz`、`sector_variant_attribution.csv.gz`、`largest_wins_losses.json`、`diagnostics.json`和每本九表；不删除极端盈亏或生成删赢家新曲线。ECB最终归档重建限制仍在，`strict_first_release_PIT_established=false/goal_complete=false/production_qualified=false/increased_betting_qualified=false`。

### 真实授权、来源与产物绑定

- 源码/tests仍为前述冻结SHA，manifest source_bundle保持14项；唯一现金manifest为`outputs/stage148_fx_cash/actual_run1/manifest.json`，63348字节，SHA `8a9f7836efeeb02331409a1a57134e67080a0b61926834ccfeae530693615258`。
- root auth为`outputs/stage145_fx_information_protocol/authorize148_cash.json`，7895字节，SHA `e5ef98ee8ce44506b12db115da442d558c6be1f80d2c9e2495c2634281618af5`。terminal SHA `202aea1b9cf7fdd1e3bf97d40742adcb75418a381655b52f66ce08e6a8f48eb7`。
- 147 choices_main源SHA `faeb022e5dc05856a507711af3b30aabef1b506a3b589ba4f629f87f0841b8ae`；held源SHA `e65572aa37238d951aa0a21fcf6eabe7831d5d460af3378d80b10a358f6499f5`。source_read_receipt记录精确复用132 cache JSON/NPZ、9520 native epochs/1552456天记录、399252 mothers、库stat前后一致，database_rehashed=false。

root真实CLI：

```sh
/Users/mac/Desktop/fian/.py311/bin/python /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/tools/stage148_fx_cash.py --protocol /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage145_fx_information_protocol/protocol.json --protocol-sha256 be0431bff87dc90d91a9f1b16940c9a6d8112a66d4309879abef46466ce4f270 --authorization /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage145_fx_information_protocol/authorize148_cash.json --authorization-sha256 e5ef98ee8ce44506b12db115da442d558c6be1f80d2c9e2495c2634281618af5 --output /Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage148_fx_cash/actual_run1
```

本次新增真实回测结果四本FX；修改/删除历史回测结果0。本记录读取现存输出，没有新增fit/cash/SQL/数据或分析曲线。开始与结束按本次收益救参过拟合：否；长期同史择题和最终归档限制风险：是。继续固定FX包做第二轮现金、改方向/窗口/风险救结果的价值：否；等待已授权Stage149一次独审核清新增资料、账本与实现仍有价值：是。当前作者产物的冻结门已不支持本包，最终“独审接受/拒绝”须待149终态，不能提前签署。
