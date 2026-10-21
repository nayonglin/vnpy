# Stage206：CURVE53 固定 K 四本独立现金执行记录

- line_id：`futures_full_market_long_signal_ai`。
- 当前模式：独立 long-only 研究；本文件记录 root 唯一一次实际现金运行，不构成正式 C9、生产或加注资格。
- 记录时间：`2026-10-19 19:23 CST`。实际开始 `19:21:28.505741`、完成 `19:21:56.368602`；用时 `27.86271749995649` 秒，root session `47842`，exit `0`。
- 工作区/分支：`/Users/mac/Desktop/fian`，`codex/ai-training-data-expansion`。
- 阶段性质：冻结 Stage204 后的四本候选现金证伪；旧 Stage157 自身四本只读复用。
- 是否重要突破：**否**。四本候选收益全部低于旧控制，四个日级增量 CI 均跨零，预设门不通过。
- 是否触发正式 A/B：否。沿用 Stage204 对独立研究线的边界，不替换正式版本或旧控制。
- 复审状态：**Stage207 对这次 actual 四本的最终现金独立审查仍 pending**。源码预审和程序 exit `0` 均不能代替实际资金、费用、持仓与统计复审；本文件不宣布审查完成。最终路线决策留给 root Stage208。

## 外部调研与判断

- 本阶段沿用 Stage204 冻结的资料判断和可证伪假说，没有新增资料下载、行情、源码投影、benchmark 或旧控制重审。研究依据见 [Stage204 协议](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage204_local_curve_information_protocol/protocol.json) 及 [Stage204 阶段记录](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/stages/20261019_1904_stage204_local_curve_information_protocol.md)。
- 判断：局部相邻名义月份的相对便宜关系提供了不同于原 COMMON52 的有限信息，但文献中的曲率 spread 收益不能直接作为本包 long-only、正分数选择、固定 K 现金收益的依据。Stage205 六个 q 系数均负，只支持事前方向的一致性；是否有经济增量必须由自身递归资金、手数、费用、容量与固定控制比较回答。

## 本次变更与参数

- 新增脚本：`tools/stage206_local_curve_information_cash.py` 和定向 fixture `tools/test_stage206_local_curve_information_cash.py`；实际运行前已冻结，运行后没有修改其绑定源码或 fixture。
- 源码绑定：`33,678` 字节，SHA256 `295009d493bf0b0e6032936793b3a70f5f807ba3dadfc2ed4e83fe3ac55e3549`。
- fixture 绑定：`9,025` 字节，SHA256 `89d26c11786a9a7af9a7448500f8909ce076e76b46df058db2b95f4880ed5539`。四个定向 fixture 已通过，含合成四本 raw/checkpoint 后的完整 metadata 闭环；没有复跑旧 suite。
- 修改脚本：无。删除脚本：无。
- 新增参数：**Stage206 没有新增可调现金参数**。候选继承 Stage205 的 `COMMON52 + q = 53` 维设计，其中 q 为局部 log-price chord 相对价格，沿用 train-only 有限 q 均值/尺度和缺失时设计值 `0`；没有新增缺失指示模型。
- 继承模型：Stage205 六个固定 Ridge，`alpha=1.0`、`fit_intercept=True`、`solver=cholesky`，scope 为 main/holdout_0/holdout_1，cutoff 为 `2020-01-01/2023-01-01`。原训练 target、成熟样本、权重与 COMMON scaler 不变。本阶段模型拟合 `0`。
- 修改参数：无。删除参数：无。没有改 q 符号、模型、窗口、产品过滤、分数阈值、K、止损、风险或参与率。
- 新增回测结果：四本 `CURVE53` 自身资金账本。修改/删除既有回测结果：均无；`VOLUNTARY_RESELECT` 原四本按 source-only 绑定读取，`replayed=False`。

## 固定执行与预算

- 数据区间：`2020-01-01` 至 `2026-10-16` continuous；`2023-01-01` 至 `2026-10-16` 独立 cold start，分别 base/stress。窗口共享历史，不是独立盲样本。
- 初始资金 `1,000,000` 元；初始止损 `0.25N`；单 family 风险 `0.0025`、总计划风险 `0.02`、buffered margin cap `0.25`、margin buffer `1.1`；参与率 `1%`。原手续费、tick 滑点、anchor、预算整数化和执行顺序不变。
- K：沿用 Stage155 的提前一个名义月份 voluntary session 边界，`D<K` 后才进行 parent 内排序，实际 lifecycle 为源到期与 K 的较早值；不是已认证的账户交割期限。ordinary/F family 优先级及原 forced exit 不变。
- 信号：只对 CURVE53 choices 的局部副本使用既有 `B` schema 别名，调用已接受 Stage131 原现金算术；没有改全局旧臂、引擎或观察器。anchor 仍来自完整原 mothers，不借旧选择池作为 admission gate。
- 市场：直接读取 Stage132 原生 NPZ cache，`1,552,456` native contract-days、`9,520` epochs；无新价格、SQL、标签、projection、下载或分钟数据。
- 现金预算实耗：started/completed/raw checkpoint 均为 `4/4/4`；新现金 `4`、旧控制重放 `0`、新 fit `0`、SQL `0`、新 labels `0`、downloads `0`、全库 hash `0`。累计 fit `427`、cash `230`。
- 失败纪律：四本 raw ledgers、各自 checkpoint 和 `financial_terminal.json` 均先于报告/metadata；无自动重试或完成账本重放。financial terminal 的 `metadata_pending=true` 是金融阶段写入时的快照；后续 actual terminal 与最终 manifest 已成功完成 metadata，不是第五本现金或重新执行。

## 完整新四本与旧复用四本摘要

金额单位为元；胜率是已关闭 episode 按净 PnL 的胜率。滑点已经体现在成交价和现金 PnL 内，表中是滑点归因，**不得再次扣除**。closed trades 与 BUY/SELL fills 是不同计数。

| 账本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 手续费 | 滑点归因 | closed trades | 净胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 新 CURVE53 · 2020 base | 2,178,251.36 | 117.825136% | -13.546843% | 0.912910 | 61,238.64 | 165,029.50 | 1,377 | 12.926652% |
| 新 CURVE53 · 2020 stress | 1,423,082.18 | 42.308218% | -12.654460% | 0.607323 | 74,287.82 | 183,062.84 | 982 | 12.729124% |
| 新 CURVE53 · 2023 cold base | 1,713,541.09 | 71.354109% | -12.519651% | 1.135724 | 23,433.91 | 61,173.95 | 535 | 13.644860% |
| 新 CURVE53 · 2023 cold stress | 1,407,591.34 | 40.759134% | -12.709684% | 0.943136 | 40,093.66 | 92,258.73 | 445 | 13.258427% |
| 旧157只读 · 2020 base | 2,229,270.22 | 122.927022% | -15.627420% | 0.978453 | 52,034.78 | 140,259.04 | 1,295 | 12.200772% |
| 旧157只读 · 2020 stress | 1,528,419.71 | 52.841971% | -11.359301% | 0.787447 | 68,710.29 | 167,960.05 | 952 | 12.079832% |
| 旧157只读 · 2023 cold base | 1,825,436.55 | 82.543655% | -9.902149% | 1.320956 | 20,778.45 | 53,623.57 | 494 | 12.955466% |
| 旧157只读 · 2023 cold stress | 1,526,645.82 | 52.664582% | -6.422761% | 1.223020 | 36,269.18 | 83,952.08 | 422 | 13.033175% |

| 账本 | fills | 累计成交手数 | 最高 buffered margin | 最高 frozen initial risk | 容量未知 roots/fills | 入场执行未知 | stale days |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 新 CURVE53 · 2020 base | 2,755 | 9,830 | 431,706.00 | 19,099.98 | 38/38 | 4 | 9 |
| 新 CURVE53 · 2020 stress | 1,968 | 4,464 | 333,038.20 | 8,354.01 | 18/18 | 2 | 6 |
| 新 CURVE53 · 2023 cold base | 1,071 | 3,967 | 345,830.43 | 14,011.40 | 6/6 | 0 | 0 |
| 新 CURVE53 · 2023 cold stress | 896 | 2,370 | 337,508.60 | 8,354.01 | 1/1 | 0 | 0 |
| 旧157只读 · 2020 base | 2,592 | 8,385 | 435,693.50 | 18,229.08 | 40/40 | 2 | 9 |
| 旧157只读 · 2020 stress | 1,912 | 4,047 | 318,089.20 | 7,453.61 | 18/18 | 2 | 5 |
| 旧157只读 · 2023 cold base | 990 | 3,472 | 361,550.20 | 14,125.25 | 9/9 | 0 | 0 |
| 旧157只读 · 2023 cold stress | 849 | 2,071 | 318,089.20 | 7,453.61 | 4/4 | 0 | 0 |

所有八个比较路径均标识 `execution_unknown=true`；continuous 新旧均有历史 stale。容量审计保留理想原量退出及未知状态，不把缺失执行证据置零，也不证明订单簿可成交。所有日级 wealth log 都为 valid；`actual_wealth_positive=true` 不等于极端场景有普适损失下界。新 CURVE53 base 的 all-open-long-zero 场景最低权益分别为 `-173,084.14`（2020）和 `-111,795.51`（2023 cold）；该场景不能解释成已发生破产或已验证 universal bound。

## 四个固定 paired 日级 CI

沿用 Stage070 原始 source-calendar 索引：`2,000` 次、block length `252`；逐日对齐的 log growth 为 CURVE53 减旧157，不重建索引、不加入 epsilon、不把破产 log 置零。CI 单位为**每日 log-growth 差**，不是收益百分点；这只是给定历史与模型包的条件区间。

| 窗口/成本 | 收益差 pp | DD 差 pp（正为变浅） | 平均每日 log 差 | 95% CI 下界 | 95% CI 上界 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2020 base | -5.101886 | +2.080577 | -0.00001409120543 | -0.00017272396110 | +0.00016823827051 |
| 2020 stress（primary） | -10.533753 | -1.295159 | -0.00004346272938 | -0.00017372230429 | +0.00009614156186 |
| 2023 cold base | -11.189546 | -2.617502 | -0.00006913346745 | -0.00028532408623 | +0.00015211078682 |
| 2023 cold stress | -11.905448 | -6.286922 | -0.00008873560735 | -0.00024656350541 | +0.00008087969229 |

四本自身收益均正，但四个收益增量全部为负；primary stress 的回撤也更深。仅2020 base 的 DD 改善 `2.080577pp`，不能覆盖其他三本回撤和全部收益的退化。四个 CI 下界均负且跨零，因此原四 CI 下界全部严格正的条件失败；不能因为区间跨零就宣称负增量已获显著性证明，也不能宣称存在稳定正增量。

新四本的已关闭净胜率均略高，但收益均更低、手续费及滑点归因均更高，且 `3/4` 本 DD 更深。这些是自身递归现金与选择路径共同出现的结果，不能仅凭配对账本把收益差全部因果归于更多成本；没有在本阶段做反事实成本分解，也没有把已进入 fill price 的滑点再次扣除。

## 原 target held 门与最终程序门

held 使用 Stage205 已冻结的原 Stage129 首次退出 `net_R_stress`，不是 K 截断 target，也不是 funded cash；本阶段只读取其 binding，没有重算 labels、held 模型或选择。

| held 组 | 已知 equal-u 平均增量 R | distinct differential unknown | 同动作 unresolved（增量0并披露） | 原 nominal_pass |
| --- | ---: | ---: | ---: | --- |
| holdout_0 | +0.002263041394377146 | 7 | 23 | false |
| holdout_1 | -0.0008020094736690167 | 7 | 31 | false |

Stage204 要求两组已知增量均严格正、distinct unknown 均为0。本次 holdout_1 的已知增量为负，两组各7个 distinct unknown 均不能当作0；held 门独立失败。现金结果即便改善，也不能覆写此门；本次现金与held恰好均不支持。

`continuation_gate.json`：`status=unsupported`，`cash_nominal_pass=false`、`return_gate=false`、`drawdown_gate=false`、`all_four_daily_log_CI_lower_positive=false`、`held_known_strictly_positive_all_two=false`、`held_known_nominal_pass=false`、`held_signal_unknown=true`、`financial_unknown=true`、`execution_unknown=true`、`any_historical_stale=true`、`nominal_pass=false`。`goal_complete/production_qualified/increased_betting_qualified` 均为 `false`。

## 输出与可复验身份

- [实际 manifest](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/manifest.json)：`80,845` 字节，SHA256 `2e8cba428b04426a74fbd771298b88c71ccc37a8acf3a041980d76804873e9ad`。
- [actual terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/actual_terminal.json)；[financial terminal](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/financial_terminal.json)。
- [八行账户摘要](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/account_summaries.csv.gz)；[四 paired 比较](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/comparisons.csv.gz)；[程序 continuation gate](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/continuation_gate.json)。
- [候选 diagnostics](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/diagnostics.json)；[旧157只读引用](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/baseline_references.json)；[费用/预算/tick披露](/Users/mac/Desktop/fian/research/lines/futures_full_market_long_signal_ai/outputs/stage206_local_curve_information_cash/actual_run1/budget_and_tick_disclosure.json)。
- 同一 manifest 已绑定四本各自 fills/reservations/daily/positions/closed/open/capacity/entry-unknown/rejections、raw checkpoint，以及 annual、family-year/total 含零、sector/variant 总体与年度含零、尾部和bootstrap distributions。本次记录只读取小摘要/比较/diagnostic，没有读取大账本或重新执行。
- 协议 SHA256：`b3a950dfb96333457f6a78f89796e07827a5758d0006eb43f71fad3cffd276ca`；root cash authorization SHA256：`e959df7eed89602bb8cd18839f70323a0eb67277aab15b09ffa7b99381cdece6`。
- 承接 Stage205 manifest SHA256：`a373ba2e5d8e8835131f0752b3c2b4f6fc73af71a84b3c484d9f158c013ef13f`；held diagnostic SHA256：`be4e1c45adff96507654d7a59acbf4184d970ecd5494b218639a425c7ac58d5f`。

## 反思、结论与待办

- 运行前是否有过拟合风险：**是**。同一历史上已有多轮择题，新增 q 的研究本身带选择偏差；因此方向、53维表示、模型、窗口、K、风险和4cash预算必须先冻结。未承诺新盲 OOS。
- 运行后是否仍有过拟合风险：**是**。方向六负不是跨周期经济资格；若根据本次四本表现回头筛年份、品种、q 可用性、tenor距离、符号或风险倍率，会把失败结果转成事后调参。本阶段没有这样做，也没有隔离 q 数值与固定均值填补的隐式可用性交互的因果价值。
- 运行前是否值得继续这次四本：**是**。原 target held 与实际资金 target 不同，方向门已通过后，完整固定四本能有限成本地回答经济增量，不能以held失败提前跳过。
- 运行后是否值得继续优化当前 q/53/Ridge/K 包：**否**。新四本相对旧四本收益均降、primary stress DD 更深、四CI均不满足正下界，且held已知/未知门失败；没有允许继续救 q、符号、模型、窗口、产品、阈值、止损或风险的证据。
- 本阶段结论：程序完整执行、证据已固化；按冻结门初步经济判断为 unsupported。保留旧控制及全部负结果，不晋级、不加注、不替换既有策略。
- TODO：仅等待 Stage207 对这次实际四本的现金独立复审并记录具体bug/置信边界；由 root Stage208 结合实际复审给最终路线决策。审查完成前不宣称本阶段actual账本已独立验收，也不重跑完成账本。
- 合入建议：本 agent 仅新增本唯一 stage。`LINE.md`、`research/registry.md` 及根 `memory.md/back_log.md` 均未修改，统一由root合入者处理。
