# Stage087：OI 两臂独立现金账户实现与唯一 actual 结果，待独审

以下前半保留 17:49 的冻结实现记录；文末 17:57 节新增 root 精确授权后的唯一 actual 终态与结果。源码、测试和协议在运行时均未变。

- line_id：`futures_full_market_long_signal_ai`；时间：2026-10-18 17:49 CST。
- 重要突破：否。本阶段只完成实现与新合成边界验证，没有新金融成绩；累计仍为 333 fit / 70 cash，完整全市场高质量做多 AI 目标 active。
- 所有 Python 使用 `.py311/bin/python`。未修改 LINE、registry、根 memory/back_log、其他研究线、旧源、正式版、生产、CTP、邮件或定时任务。

## 开始判断与已有调研

开始新增按收益调参过拟合：**否**。本阶段执行收益前已冻结的 Stage084 与 implementation_clarifications，不选择新变量、阈值、stop、分配规则或模型；但已见历史研究与多轮择题风险仍存在，不能声称严格新 OOS。

开始继续价值：**有**。真正 CONTROL 与 OI 共享新 OI-missing 槽，旧 070 不能冒充本次同信息控制；必须让每臂各自形成持仓与权益，才能检查本次固定标量的信息增量是否转成净资金结果。

本阶段复用已读 Stage078 的一手资料/GitHub 调研，不新增泛搜、下载或数据工程。CME/CFTC 的定义支持 OI 是未平仓匹配风险存量，不能从增仓推出净多资金或上涨方向；TqSdk/RiceQuant 维护者代码支持收盘 OI 与真实合约身份/次日时钟的区分。SPO 论文只支持明确决策目标与约束的重要性，不赋予本次 OI 或复杂求解器收益资格。判断继续遵循 084：唯一原始数量标量值得一次低先验的可失败对照，旧 OI 确认/风险恢复与 080 预过滤均不复活。

## 冻结身份与本阶段代码

- 084 文档：8850B，SHA `0e59263ec479851454130648e3827e69a0a5e5aa47a79d0ba634715fdb03eb8f`。
- 084 protocol：6545B，SHA `82059f728efb70fedd54e2254f822898b6bbcf1b2ac3395cbd1c11470167cba5`。
- clarification：2167B，SHA `b72cfec8e934a9e347359f1a6f3bbb1384de2a6303c0b6b0bf5089bdab23b776`；显式校验其 parent protocol。
- 新实现：`tools/stage087_oi_cash.py`，25330B，SHA `162921962e5ef210a8a298f52494a1eb88102fdfcb6760a611f8e053e95713b8`。
- 新测试：`tools/test_stage087_oi_cash.py`，8808B，SHA `59393252b4f8710c21c824f17c38a31afb5fea5c01f837ccba63602b63697277`。
- 只 import 并 SHA 绑定 accepted070 原现金/分配、042 quote/ledger/source、054 纯诊断；没有 import 080，没有复制或 monkeypatch 原账户循环。完整 source_bundle 存于 `outputs/stage087_oi_cash/implementation_receipt.json`。

## 输入、独立账户与报告接线

086 已同步并核对当前源码的实际 schema：`stage086_oi_fit_v1`，需要 completed actual、12 attempted/12 completed fit、0 native、0 cash terminal。消费 `predictions_main.csv.gz`，只允许 `scope=main`、`policy=NARROW`、CONTROL/OI；每臂完整 161014 = 98 × 1643 行。全部 399252 母体留在信号适配中，原身份、sequence_index、cutoff、ready20、score>0/selected 均与 accepted070 对齐。OI 缺失指示在两臂逐 event 完全相同；缺失为 1 且原资格满足时仍可 potential=1。

严格为 CONTROL/OI × 2020 连续/2023 独立冷启 × base/stress = 8 个新内生账户。100 万、单 family 0.25%、总 2%、buffered margin 25%、buffer 1.10、初损 0.25N、Wilder20/20low、u 原 reserve/D 只减不回收、缺价延期和同日不重入均直接沿用 070 原核。held 模型只读诊断，永不拼入主账户；不加总事件 PnL。

实际入口只有一次共享 native load，随后八账本；原 084 绑定的 252 源日块/2000 次/seed20261018 两个 indices 只验证并读取，不重新生成、不复制旧数组。每账户写完整 fills、reservations、daily、positions、closed、open、rejections 与 summary；共写八摘要、四 OI−CONTROL 比较、配对 bootstrap 分布、年度、95 family 含零的年度/全期贡献、手续费/滑点、敞口/集中、未知与零价情景、同次 native arrays 生成的有限首例。首例按固定账户循环与原因选取，不能按收益挑选。

现金 nominal 条件直接复用 084：主 stress 收益差严格正、DD 不更深、CI 下端 >0；主 base 同方向且 DD 不更深；冷启两成本收益差非负且 DD 不更深。空 CONTROL 的 DD 为 NA/unidentified，不能机械填 0DD。明确 nominal 失败优先 unsupported；通过后仍保留真实 stale 缺价与 held 未决动作差异造成的资格限制。

主预测的 label-state 动作分歧单独输出 signal_identification，已知取消与未知分开。未成交的未知标签分歧不冒充财务敞口；正常期末 open 按原 close mark 估值并披露开放/零价情景，不新增“一切 open 都 financial unknown”的门。zero-price 仍是情景，不是普遍损失界。名义通过最多支持进一步研究，不晋级、不加注、不宣称达成原目标。

## 合成验证与实际预算

新文件缺失的 RED 已观察；另对取消误列未知和第 13 次 fit attempt 的精确失败观察后修正，未改金融参数。最终命令：

```text
.py311/bin/python -m unittest research/lines/futures_full_market_long_signal_ai/tools/test_stage087_oi_cash.py
Ran 10 tests ... OK
```

仅新测试，未跑旧 suite。覆盖：完整 main mother 与缺失不硬门、拒绝 held cash、共享 missing、一致配对索引宽度/整数范围、固定四比较门、空对照 DD、held 与 stale 未决、未成交 signal 未知不造财务门、取消与未知分开、拒绝未经授权时不创建输出、12 完成但第 13 次 attempt 仍拒绝。CLI `--help` exit0，import 的 native query 计数 0；fixture fit/cash 均 0。

actual 尚未授权/执行；本阶段新增 actual fit=0、cash=0、native SQL=0、labels=0、行情下载=0、整 DB/H5 hash=0、旧 baseline replay=0。参数新增/修改/删除均 0；期末权益、总收益、最大回撤、Sharpe、总滑点、总交易次数与胜率均 N/A。

## root 最小授权与后续

CLI 为 `--protocol --protocol-sha256 --authorization --output`；授权 schema 为 `stage084_exact_root_authorization_v1`，`authorized_by=root`、`stage=cash`、`exact_source_authorized=true`、固定 protocol SHA、精确 source_bundle、fresh output 与六个真实 input_bindings。

六角色只有 `market_protocol`、`narrow_labels`、`narrow_manifest`、`fit_manifest`、`predictions_main`、`held_diagnostic`。旧三项精确绑定来自 084；新三项由 root 待 086 completed actual manifest 后填真实 bytes/SHA，不猜旧 schema。候选绑定说明在 `outputs/stage087_oi_cash/proposed_input_bindings.json`，不是授权。拟 fresh 输出 `outputs/stage087_oi_cash/cash/` 当前不存在。失败保留，不自动修复重跑。

后续仅一次聚焦源码预审；root 按最终源码/manifest 签发后才允许 actual。actual 后按用户要求由独立 agent 全面核查结果、数据、逻辑、置信度与 bug；本阶段不把实现通过写成金融通过。

结束新增按成绩调参过拟合：**否**。没有新成绩、没有改协议科学参数；取消诊断修正来自既定状态语义，12 attempt 校验来自固定预算。结束继续价值：**有，限本次冻结 OI 对照的一次实际检验**；若固定收益/DD/CI/冷启或 held 门失败则停止这个包，不换窗口、方向、模型、品种、阈值、风险或止损救援。完整全市场高质量 long AI 目标仍未完成。

## 17:57 追加：唯一 actual 已完成，尚待独立全审

root 已核对 088 聚焦 preflight Critical/Important=0/0，并签发精确授权：`outputs/stage084_oi_information_protocol/cash_root_authorization.json`，4401B，SHA `e76ff6de7427ae9a0a2be15d581beaef3168dbf7da24106c180bac645b517031`。启动前 fresh 核对两新源文件、该授权、086 actual manifest/terminal 的 bytes/SHA，输出 `outputs/stage087_oi_cash/cash/` 原不存在。未改冻结源码、测试或科学参数，未因 held 两组名义增量已负而选择性省略已冻结的现金账户。

实际命令仅启动一次，session `25625`，exit0；started `2026-10-18 17:56:54.836 CST`，finished `17:57:13.415 CST`，终态统计耗时 `18.578501709` 秒。8 started / 8 completed cash、恰 1 次共享 native SQL；0 fit、0 新标签、0 旧 baseline replay、0 下载、0 整 DB/H5 hash。源 receipt 为 1552456 合约日/9520 epoch，DB stat 前后完全相同，仅继承 accepted266 SHA，无重新 hash。本阶段实际预算完整用尽，不重跑。

作为输入的 086 actual manifest 为 30975B/SHA `6b7f4e45b39663bcf9c356132d45bd4abc7d143b9f6846f58908ade56a27374c`，terminal 317B/SHA `5a5d1993a7e8a63d9a81c96802183a3ed9a51879724d2175ac8b0de10c604a96`，12 attempted/12 completed fit、0 SQL/cash。原累计 333 fit/70 cash 加 086/087 后为 **345 fit/78 cash**；并非本阶段另做 12 fit。

### 八个资金账户结果

全部初始资金 1000000，同一冻结 NARROW 原执行与独立内生资金。胜率为已闭合净 PnL>0 的比例，不是信号准确率。

| arm | 窗口 | 成本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 闭合笔数 | 闭合净胜率 | 手续费 | 滑点归因 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| CONTROL | 2020 连续 | base | 1125252.8245 | 12.52528245% | -11.74815156% | 0.29728845 | 280 | 12.5000% | 8992.1755 | 21510.590545 |
| CONTROL | 2020 连续 | stress | 1183779.6610 | 18.37796610% | -7.99315230% | 0.48779409 | 264 | 12.1212% | 20550.3390 | 42087.083717 |
| CONTROL | 2023 冷启 | base | 1253214.6225 | 25.32146225% | -5.05956738% | 1.08109225 | 108 | 12.9630% | 3330.3775 | 6514.136377 |
| CONTROL | 2023 冷启 | stress | 1138445.0910 | 13.84450910% | -5.44406329% | 0.77972635 | 98 | 12.2449% | 8184.9090 | 13996.929549 |
| OI | 2020 连续 | base | 1124652.4730 | 12.46524730% | -11.74815156% | 0.29499993 | 280 | 12.5000% | 9017.5270 | 21520.492292 |
| OI | 2020 连续 | stress | 1184637.2760 | 18.46372760% | -7.99315230% | 0.48968834 | 263 | 12.1673% | 20552.7240 | 41943.822884 |
| OI | 2023 冷启 | base | 1252230.7545 | 25.22307545% | -5.35009154% | 1.06469182 | 108 | 12.9630% | 3364.2455 | 6535.038124 |
| OI | 2023 冷启 | stress | 1138254.0050 | 13.82540050% | -5.46162684% | 0.77754469 | 98 | 12.2449% | 8245.9950 | 13980.299023 |

成本改变交易路径与整数风险分配，不能把不同成本账户的收益排序解释为增加成本必然提高收益。未为该排序回放、改成本或改账户。

### 四个配对比较与冻结结论

差值均为 OI−CONTROL；DD 差负代表更深。CI 单位是平均每日 log 增长差，沿 084 绑定的同日历 252 源日块/2000次/seed20261018 indices，四项均跨 0。窗口和成本不是独立复制。

| 窗口/成本 | 收益差（百分点） | DD 差（百分点） | 平均每日 log 差 95%CI |
| --- | ---: | ---: | --- |
| 2020 base | -0.06003515 | 0 | [-1.651315139e-6, 1.029946636e-6] |
| 2020 stress | +0.08576150 | 0 | [-2.814428564e-6, 3.965079090e-6] |
| 2023 base | -0.09838680 | -0.290524159 | [-3.437719343e-6, 1.720955980e-6] |
| 2023 stress | -0.01910860 | -0.017563550 | [-7.776342844e-6, 5.481139371e-6] |

`continuation_gate.json` 为 `unsupported`，`cash_nominal_pass=false`、`held_known_nominal_pass=false`、`nominal_pass=false`。主 stress CI 下端未大于 0；主 base 反方向；冷启两成本收益与 DD 均未满足原门。086 两 held 组按 u 等权已知增量均负，其中一组另有未决动作差异。失败有明确名义证据，不只是因为 unknown，也不能用主 stress 的微小点差掩盖共同失败。

按 084 停止这一个**日级真实 epoch OI 净变化/成交量标量、54 槽 Ridge、NARROW 原执行**包，不换变换、窗口、符号、模型、年份、产品、阈值、stop 或风险救参。未晋级、未加注、未宣布完成原目标；独立全审后由 root 统一结案。

### 完整账本、未知与复现交接

实际共输出 3008 fill 行、10232 账户日、4386 持仓日、1499 closed、8 open、5434 reservation、3921 rejection；95 family 含零的年度 4180 行、全期 760 行；同次已加载 native arrays 固定首因 14 例。逐笔/逐日与 finite 原价证据全部保留。年度为连续账户切片，2026 为部分年，不能当独立冷启。

两个主 base 各 2 个历史 stale 日、主 stress 各 1 日；两个冷启两成本均 0 stale。八账户期末各 1 正常 open、0 stale；正常开放按原 close mark 估值并披露 zero-price 情景，不因一般未来风险自动改成 financial unknown。`financial_unknown=true` 来自真实历史 stale 记录；`signal_unknown_main=false`，没有把未成交 signal 标签分歧制造为资金风险。仍不声称日线 barrier/close mark 是真实 broker 成交或普遍损失界。

关键交接：

- cash manifest：32503B，SHA `4bd03bbf9862c021bb2de967f1d06a9ead6373f25f973dd64deca58312215784`。
- actual terminal：518B，SHA `aba6c8375970353340d23a2a4e984195661bbbca5b86d3a2cb16992cfbfad952`。
- account_summaries：2184B，SHA `a0634feb6b17994aa20f183ef897dea6c93621865377a1904b80133115e44563`。
- comparisons：519B，SHA `cc092a6af75772e512d1cffa7ee0904db3833de8e46079698f8c932f4cab53a9`。
- continuation gate：481B，SHA `4bddd308467c52a8854d4edb3e927e6fe484b0558142c3b1dd1c629da868d766`。
- finite native cases：40930B，SHA `57373c4e67b44a10291ed7c18dcd9eab63a8f4f9b0b63c054a4b9c80df782b6a`，raw OHLC 有限核验材料，不作常规可复现资产大量复制。

已通知 root 与 088 终态和 manifest 身份；最终 actual 全面独审仍待 root 对 085/086/087 三 manifest 的精确授权，不自行扩大重放/SQL。新增回测结果为上述八账户，修改/删除旧回测结果 0；模型、交易参数新增/修改/删除均 0。

实际开始反思：**没有新增按结果调参**，已见 held 负结果仍按冻结预算完成整个实验以避免选择性报告；继续实际一次的价值是补齐资金证据，而非维持乐观解释。实际结束反思：**没有新增过拟合救参**；继续这一个失败 OI 包的价值为**否**，继续用户的全市场全品种高质量 long AI 完整目标为**是**。下一步由 root 先完成一次独立全审，之后沿新的实质信息或机制问题推进，保留本包停止结论。
