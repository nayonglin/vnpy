# Stage001 Lag-1 Granger 动量溢出资格闭线

- line_id：`futures_trend_lag1_granger_spillover_qualification`
- 当前模式：`day`
- 记录时间：`2026-07-13 00:53 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：无收益网络资格审计、影响结论问题修复、研究线闭线
- 是否重要突破：否；这是结构性否证，不是策略收益突破
- 是否触发A/B：否；未形成信号或策略候选

## 外部调研与判断

- 参考资料：arXiv:2501.07135、arXiv:2308.11294、2026 commodity Granger-causality network 论文、statsmodels 0.14.6 官方文档与 GitHub 源码。
- 我的判断：跨商品 momentum spillover 具有外部研究先验，但论文完整 NMM 含 DTW/Levy、图优化和样本内净 Sharpe 网格，当前直接复制会引入过多自由度。本阶段只验证透明子假设：固定 lag1、132日、global BH 和半窗同号的 Granger incoming edge 是否广泛存在。
- GitHub 判断：未找到两篇 NMM 论文作者可直接复用的官方策略实现；复用 statsmodels 官方 Granger 与 multiple-testing API，不手写检验公式。

## 本次变更

- 新增脚本：`tools/stage001_lag1_granger_qualification.py`。
- 新增测试：`tests/test_stage001_lag1_granger_qualification.py`。
- 修改脚本：首轮独立 review 发现先过滤非法 close 再按 OI 选约，可能静默递补低 OI 合约；修复为先选 T-1 最高 OI、再校验 prior close，非法即失败。FDR 有效集补 `granger_status=ok`，decision/report 补有效 BH 数与 pmin/qmin。
- 删除脚本：无。
- 新增研究参数：`LOOKBACK=132`、`HALF_WINDOW=66`、`lag=1`、global `fdr_bh alpha=0.05`、最少完整 leader `29/56`、全体/2022资格率 `90%`、逐年最低 `80%`。
- 修改正式参数：无。
- 删除正式参数：无。

## 回测/归因参数

- 数据区间：Stage131 全部 `365` 个事件，`2018-01-15 -> 2026-04-30`；2022 全年 `48` 个事件只作完整性子集。
- 账户规模：不适用；未读取账户资金或权益。
- 成本口径：不适用；未运行交易回测。
- 样本过滤：full-market eligible 固定 `57` 产品；每事件 target 对其余 `56` leader，历史严格 `< entry_date`，最后132共同日；不足不补、不缩窗。
- 策略/归因口径：return date 合约由产品前一有效交易日 OI 最大选择，平局按合约代码升序；同一实际合约 close-to-close。检验 `target_t` 是否被 `leader_(t-1)` 在控制 `target_(t-1)` 后增量解释。

## 结果

- 期末权益：不适用；未回测。
- 总收益：不适用；未回测。
- 最大回撤：不适用；未回测。
- Sharpe：不适用；未回测。
- 总滑点：不适用；未回测。
- 总交易次数：`0`。
- 胜率：不适用；未回测。
- 源身份：Stage131 `365/365`、2022 `48`、eligible universe `57`；事件/宇宙 SHA 均匹配。
- T-1 selection ledger：`96,806` 行，ok returns `96,134`，return panel `2,750` 日；重复 contract/date、selection_date违规、跨合约直接收益、ok非有限收益均 `0`。
- review 修复后 `invalid_prior_close_rows=0`，说明原潜在递补 bug 未命中真实数据，结果数字不变。
- pair tests：`20,440=365×56`，完整132日 `14,747`；target历史完整 `358/365=98.0822%`，2022 `48/48=100%`。
- 未校正 `p<0.05` 共 `876`，`p<0.01` 共 `207`，`p<0.001` 共 `25`；global BH 有效样本 `14,747`，`pmin=1.3762259248285614e-05`，`qmin=0.066430622945741`，reject `0`。
- early/full/late 系数同号 `7,186` 行，但没有任何行同时通过 global BH，因此稳定 incoming edge `0`。
- 资格事件 `0/365`，2022 `0/48`，逐年均为0；2018/2019还存在可用 leader 少于冻结 `29/56` 的历史数据覆盖缺口，但2020以后多数事件覆盖通过，仍不能改变显著边为0。
- 数据库前后 SHA 均为 `59f0bd364253d7ec029cc183d48f161c15b9ee9af01075956924b4dad958f723`；网络、订单、账户、持仓、CTP、邮件和 live 调用均 `0/false`。
- 机械决策：`CLOSE_LINE_LAG1_GRANGER_NETWORK_INELIGIBLE`；`ready_for_stage002_signal_predecl=false`、`ready_for_strategy_ab=false`、`ready_for_live=false`。

## 独立 review

- 首轮：确认闭线置信度 `98%`；发现2个 P1。P1-1 是最高 OI 前错误过滤 close，已TDD修复并原口径全量重跑；P1-2 是365个高度重叠窗口使标准 BH 的形式独立/正依赖保证未被证明，不改变机械 `qmin>0.05` 结论。
- 首轮 P2：FDR 未显式要求 `granger_status=ok`、缺少非法 close 与真实 tie-break 测试、Git未跟踪；前两项已修复，Git状态保留且未擅自提交。
- 修复后终审：`P0=0/P1=0/P2=1/P3=0`，闭线置信度 `99%`；聚焦测试独立复跑 `8/8`。
- 唯一保留 P2：global BH 对重叠事件的形式 FDR 保证未证明。decision/report 已明确只将其作为事前冻结机械门，不对外表述为严格网络推断；本线已关闭，不要求再修或重跑。未来若另开网络线，必须事前使用 dependence-robust 方案或独立评估单元。

## 输出文件

- report：`outputs/stage001_lag1_granger_qualification/stage001_report.md`
- summary：`outputs/stage001_lag1_granger_qualification/stage001_decision.json`
- orders：不适用。
- daily：`stage001_t1_return_panel.csv.gz`
- quality：`stage001_gate_matrix.csv`、`stage001_product_data_audit.csv`、`stage001_t1_selection_ledger.csv.gz`、`stage001_event_leader_granger_ledger.csv.gz`、`stage001_event_network_qualification.csv`、`stage001_year_qualification.csv`、`stage001_manifest.csv`

## 结论

- 本阶段结论：透明 lag1 Granger spillover 在冻结的全事件/global BH/半窗同号合同下不具备资格，研究线关闭。
- 是否进入下一步：否；不得构造 network feature、策略回测、A/B 或 live。
- 下一步：不扫描 lag、窗口、FDR、alpha、leader数、产品或年份救参。若未来有独立理由研究复杂 network momentum，必须另开线，事前解决重叠依赖并提供可复验方法/代码；当前更高价值方向是获取授权 L2/L3 订单流历史或积累 forward OOS，而不是继续从同一日线制造规则。

## 过拟合反思

- 运行前判断：否；参数、数据全集和失败门均在看结果前冻结，Stage001 不读取 PnL。
- 运行后判断：否；失败后没有改成 event-level BH、挑年份/产品或扫描 lag/window，只修复更严格的数据语义与审计字段。
- 原因：闭线来自 `qmin=0.06643 > 0.05` 和稳定边0的机械结果；放宽多重检验才会构成明显结果后过拟合。

## 继续价值反思

- 运行前判断：有；这是尚未被仓库历史等价测试、且不依赖新增付费数据的结构性信息源。
- 运行后判断：本线无继续价值；总体降低回撤目标仍有价值。
- 原因：透明低自由度版本在资格层已失败，继续救参没有研究价值；复杂图模型自由度更高且缺官方代码，不应因当前失败而直接升级复杂度。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记闭线。
- 是否更新 `research/registry.md`：是，登记闭线和残余P2。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md` 重要闭线摘要；不追加 `memory.md`。
