# Stage168：共同 K 的双臂现金实现与 actual 事实，独审待定

以下是 02:26 实现时记录；02:32 唯一 actual 补记见文末。

- 时间：2026-10-19 02:26 CST。研究线：`futures_full_market_long_signal_ai`。非重要突破；只实现 166 已冻结的经济合同，未产生新金融成绩。没有改 LINE、registry、旧源码或正式物料。
- 已读 registry、本线 LINE、166 小协议及 131/148/157 必要接口。166 SHA：`ebd24d42728e9309d390e4b31ff692ed5e0b723b4721744bcdd0ea063a9c014a`。本次不重复联网；沿 160 已完成的官方/维护者来源判断与 164 事前设计。署名席位分布不是全市场净多，q 的事前增量仍待证伪；主源不证明 alpha。采用 TDD 与完成前验证；正式版本 A/B skill 的正式身份/发布工作不在本独立研究授权内。

实现仅新增 `tools/stage168_member_concentration_cash.py` 与对应测试。CONTROL54、CONCENTRATION54 各自完整 main 选择，局部适配 131 的 B 字段后恢复真实臂名，不改全局 ARMS；用完整原 mothers 建 canonical。共 2 臂×2 起点×2 成本=8 本独立递推，保存原/source、K、effective 边界，D<K、不合成退出成交，原更早生命周期保留。普通/F、商品/金融及所有 98 目录仍保留；不按 q 可得性硬删。0.25N、无 PT、预算/保证金/容量/费滑/原132cache 与070索引不变，slippage 已含成交价，不二次扣除。

每本先保存 fills、reservations（预算）、daily、positions、closed/open、capacity/entry unknown、rejections、kernel summary 和 checkpoint；每次启动/完成另有独立计数收据。8 本全部 checkpoint 后先写 `financial_terminal.json`，然后才计算报表、四配对 CI、held 门和 manifest。metadata 失败保留启动/完成/落盘数，已启动目录禁止重放。修正 157 旧字段路径：`anchor_and_execution` 位于 128 顶层。不会读取 155 的旧 cash control 路径，也不读取 131/159 现金成绩。

统计固定为 CONCENTRATION54−CONTROL54。主2020 stress 收益/回撤均严格改善且配对 CI 下界>0，另3组 R/DD 不差；候选四组 own R>0，八本 wealth positive；CONTROL DD 为 null/空参考时 unknown，不替换0。held 直接消费167原 first-exit target 诊断，两 scope 已知等u增量须>=0，差异 unknown 阻止泛化资格；它不是 K 现金 target。即使算术门全过，仍不签 strict PIT、历史法定清零、真实执行、加注或正式资格。

验证只跑新增测试：

```text
.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage168_member_concentration_cash.py
Ran 8 tests in 0.394s — OK
```

先观察缺实现 RED；随后合成 fixture 纠正了路径笔误、摘要缺字段和单母行导致的合法 observation exit。最终覆盖独立 child/immutable anchor、完整 canonical、K 缺价延期、空臂、八本先 checkpoint、第二本失败保留2 started/1 completed/1 checkpoint、未知 DD、差异 held unknown、正负配对方向及零 family-year。未跑旧 suite，未用真实数组或成绩作 fixture，未 fit、真实 cash、SQL、新标签、下载或回放旧基线。累计金融数仍397 fit/210 cash；合成账本不计入 actual。

API：CLI 参数 `--protocol --protocol-sha256 --authorization --authorization-sha256 --output`。root 单独签 `stage166_exact_root_authorization_v1`，`stage=cash`、`authorized_by=root`、`exact_source_authorized=true`；绑定 `source_bundle()`，全部166 `source_bindings` 原样，加167 `fit_manifest/choices_main/boundaries/held_diagnostic`；输出为全新 `outputs/stage168_member_concentration_cash/<run>`。167 schema/status/12fit/terminal/protocol 与全部 fit 输入链校验后才能开始。169 已收到静读接口，不 import168 重算审计。

源码收据：cash 27499 bytes / SHA `1a1bbfbca7a4b67de45f3dacf50e2d100905942648e42c4f741be40d5af50076`；test 11681 bytes / SHA `8d6fc1d9912abb3a827a4865ed6ebd2fa2128dac9ab746c7aad28e9dcb703e2a`。后续如修实现，root 必须重新生成精确 source authorization，不沿用此 hash。

开始及结束反思：本轮新增收益后调参 **否**，因为只落实固定166、无新金融；同史多轮择题及归档修订风险 **是**。继续完成这一项新增信息对照 **有价值**，因为同训练身份/共享 missing/共同执行可识别固定算法的条件增量；继续 K 日期/模型/stop/risk 救参 **无价值且禁止**。下一步由 root 在167完成和精确 source auth 后另行启动一次8账并做169独审；本 agent 不 actual，完整高质量long目标尚未达成。

## 02:32 actual 补记：固定 q 包 unsupported，等待169独审

root 单独授权并启动唯一 actual session80989，2026-10-19 02:31:14—02:31:48 CST，exit0、33.720210875秒。小型 `actual_terminal.json` 与 `financial_terminal.json` 均为 completed，8 started / 8 completed / 8 raw ledgers checkpointed；本次新 fit、SQL、下载、标签、旧基线重放均0。12个新增 fit 属167，合并累计409 fit/218 cash。没有新增、修改或删除金融参数，没有修改旧金融结果；仅增加下表新8本结果。169 尚待独审，不能写 accepted。

| 臂 | 起点/成本 | 期末权益 | 收益% | 最大回撤% | Sharpe | 滑点金额 | fills/闭合交易 | 闭合净胜率% |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CONTROL54 | 2020/base | 2,160,944.0880 | 116.094409 | -15.597626 | 0.931026 | 156,624.7589 | 2872/1435 | 12.682927 |
| CONCENTRATION54 | 2020/base | 2,177,670.8535 | 117.767085 | -15.591458 | 0.936874 | 157,339.9229 | 2876/1437 | 12.665275 |
| CONTROL54 | 2020/stress | 1,469,984.9830 | 46.998498 | -10.824285 | 0.718663 | 178,903.7486 | 2064/1029 | 11.661808 |
| CONCENTRATION54 | 2020/stress | 1,470,182.8610 | 47.018286 | -10.810388 | 0.719026 | 178,834.4400 | 2062/1028 | 11.673152 |
| CONTROL54 | 2023/base | 1,545,749.6345 | 54.574963 | -8.678663 | 1.014974 | 50,983.4537 | 1051/524 | 11.832061 |
| CONCENTRATION54 | 2023/base | 1,545,749.6345 | 54.574963 | -8.678663 | 1.014974 | 50,983.4537 | 1051/524 | 11.832061 |
| CONTROL54 | 2023/stress | 1,447,487.7705 | 44.748777 | -7.954556 | 1.074857 | 82,377.4373 | 873/434 | 12.672811 |
| CONCENTRATION54 | 2023/stress | 1,447,539.6455 | 44.753965 | -7.954556 | 1.074971 | 82,375.9863 | 873/434 | 12.672811 |

配对仍为 CONCENTRATION54−CONTROL54；DD正差表示更浅。2020 base收益差+1.67267655pp/DD差+0.00616799pp，日log均值CI95 [−1.89022377e−5,+3.23261548e−5]；主2020 stress收益差+0.0197878pp/DD差+0.01389695pp，CI [−2.54660594e−6,+2.78979431e−6]。2023 base两点差与CI均0；2023 stress收益差+0.0051875pp/DD差0，CI [−2.68073561e−9,+1.18182711e−7]。主CI下界不大于0，未满足事前严格门；不把微小正点估计写成稳定优势。

`continuation_gate.json` 为 unsupported：cash_nominal_pass=false、held_known_nominal_pass=false、nominal_pass=false；收益门、DD门、候选四组正收益和八本正财富虽为true，主CI失败且root所读167 held1已知增量为负。held仍是原 first-exit 诊断，非K现金target。全部8本 execution_unknown=true；两臂2020 base/stress历史 stale 分别8/5日，2023均0；期末各本 stale_positions=0，但两臂2020 base各2个开放仓，其余各3个。缺价/容量/入场未知完整保留，不等于真实可兑现结果。

本次只读取小终态、gate、8行 account_summaries、4行 comparisons、diagnostics 必要摘要，并核小 manifest 字节，不重读大CSV或回放资金。原始证据目录：`outputs/stage168_member_concentration_cash/actual_run1/`；manifest 125057 bytes / SHA `c3d82f0bf1101e3b63a4bbfab9793a9e40b2b4aa6770c07bb9e230f179c0499f`。源/测锁定hash不变。financial_terminal 中 metadata_pending=true 是先于汇总保存的原始时序事实，最终 actual_terminal completed/exit0 表明该次后续汇总完成，未覆盖旧checkpoint。

结束反思：新增收益后救参过拟合 **否**，因为只登记唯一冻结运行，未改 q、日期、模型、stop 或风险；同史多轮择题风险仍 **是**。该次最小证伪价值已实现，继续此 q/Ridge/K 包救参 **无价值且禁止**；继续169一次独审及完整六所long目标 **有价值**。未建立严格PIT、历史账户清零、真实执行、稳定新增AI优势、加注或正式资格；goal仍未达成。
