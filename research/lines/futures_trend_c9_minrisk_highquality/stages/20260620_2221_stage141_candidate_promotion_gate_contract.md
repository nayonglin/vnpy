# Stage141 候选晋级硬闸门合同

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：`2026-06-20 22:21 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：候选晋级合同 / 抗过拟合硬闸门 / 不进入策略研究
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Bailey、Borwein、Lopez de Prado、Zhu 的 Backtest Overfitting/PBO 论文：强调投资回测中的 winner-picking 风险，普通 hold-out 在投资回测语境下可能不可靠。
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253
  - Bailey、Lopez de Prado 的 Deflated Sharpe Ratio：DSR 用于校正多重检验选择偏差和非正态收益带来的 Sharpe 膨胀。
    https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
  - Journal of Computational Finance 的 PBO 页面：PBO 用于评估策略选择过程导致的回测过拟合概率。
    https://www.risk.net/journal-of-computational-finance/2471206/the-probability-of-backtest-overfitting
- 我的判断：
  - 未来如果拿到真实分钟/盘口数据，不能靠“某个版本收益和回撤看起来好”就进入候选；必须先固定一个不可谈判的 promotion contract。
  - 用户目标要求降低回撤、收益保留 80% 以上、无过拟合、普世可穿越周期、视觉分析。因此 Stage141 把这些要求转为硬 gate：收益、回撤、保证金压力、预声明、点时化授权数据、true engine、样本外、跨年、跨品种、月度起点、右尾保护、bottom-loss 改善、视觉图和 PBO/DSR。
  - 这一步不是新 alpha，但能防止后续拿到数据后用参数扫描、年份/品种补丁、synthetic fixture 或单张指标表误推进。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage141_candidate_promotion_gate_contract.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `min_return_retention_ratio=0.80`
  - `min_drawdown_abs_reduction_pp=5.0`
  - `max_pbo_allowed=0.10`
  - `min_dsr_required=0.00`
  - `min_visual_artifact_count=5`
  - `min_oos_gate_count=4`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage134 的官方路径曲线；本阶段未新增回测。
- 账户规模：沿用当前研究线 C9/minrisk 口径。
- 成本口径：沿用 Stage134 汇总口径，总滑点 `2,730,130`。
- 样本过滤：无新增样本过滤。
- 策略/归因口径：只生成未来候选晋级合同和 selftest；不运行 true engine，不进入 A/B，不连接 CTP，不调用 order API，不改变 official config。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - `decision=stage141_candidate_promotion_contract_ready_no_candidate_no_strategy`
  - `contract_ready=1`
  - `hard_gate_count=15`
  - `contract_selftest_case_count=6`
  - `contract_selftest_pass_count=6/6`
  - `current_candidate_promotion_allowed=0`
  - `synthetic_promotion_allowed=0`
  - `min_candidate_total_return_pct=20814.1001%`
  - `max_candidate_drawdown_abs_pct=40.0827%`
  - `min_drawdown_abs_reduction_pp=5.0`
  - `max_candidate_broker10_pct=111.7365%`
  - `real_w0_data_delivered=0`
  - `stage133_release_allowed_now=0`
  - `real_stage112_intake_allowed_now=0`
  - `true_engine_allowed=0`
  - `strategy_feature_usable=0`
  - `official_config_changed=0`

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage141_candidate_promotion_gate_contract/qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_report_stage141_candidate_promotion_gate_contract_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage141_candidate_promotion_gate_contract/qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_summary_stage141_candidate_promotion_gate_contract_v1.csv`
- orders：无
- daily：无新增 daily 回测输出
- quality：
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_promotion_contract_stage141_candidate_promotion_gate_contract_v1.csv`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_contract_selftest_cases_stage141_candidate_promotion_gate_contract_v1.csv`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_gate_status_stage141_candidate_promotion_gate_contract_v1.csv`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_future_candidate_input_schema_stage141_candidate_promotion_gate_contract_v1.md`
- 视觉图：
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_official_path_thresholds_stage141_candidate_promotion_gate_contract_v1.png`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_promotion_contract_matrix_stage141_candidate_promotion_gate_contract_v1.png`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_contract_selftest_matrix_stage141_candidate_promotion_gate_contract_v1.png`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_anti_overfit_layers_stage141_candidate_promotion_gate_contract_v1.png`
  - `qmt_roll_stage141_c9_minrisk_candidate_promotion_gate_contract_gate_status_matrix_stage141_candidate_promotion_gate_contract_v1.png`

## 结论

- 本阶段结论：
  - Stage141 晋级合同已固定，任何未来分钟/盘口候选必须同时满足 15 个 hard gate；单靠收益、单靠回撤、单靠局部样本或缺少 OOS/视觉证据均不得晋级。
  - 自测证明：官方基线本身因回撤未改善被拦；收益高但回撤只改善 1pp 被拦；回撤改善但收益保留不足被拦；指标好但缺 OOS 证据被拦；synthetic positive 只验证合同逻辑，不允许 promotion。
  - 当前无真实 W0 数据、无 Stage112/113 放行、无真实候选，因此 `current_candidate_promotion_allowed=0`。
- 是否进入下一步：是，但下一步必须围绕真实数据到货和候选输入 schema，不得绕开 Stage112/113 和 Stage141 合同。
- 下一步：
  - 若真实 W0 到货，先 Stage125 -> Stage133 -> Stage112/113；通过后候选必须按 Stage141 schema 提供指标、OOS、视觉和抗过拟合证据。
  - 若没有真实数据，下一步最多做“候选结果读取器/validator”的接口，不得构造伪候选或从历史闭合盈亏反推规则。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：
  - 本阶段没有新增交易规则、参数阈值搜索、品种/年份筛选或收益优化；相反，是把未来候选必须满足的反过拟合约束写成硬闸门。
  - synthetic case 只用于测试合同逻辑，且明确 `promotion_allowed_now=0`，不会污染策略证据。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：
  - 这一步把用户目标的抽象要求转为可执行合同，能防止未来真实数据到位后因为短期结果诱人而降低标准。
  - 边界是它本身不产生 alpha；真正候选仍必须等授权点时化数据、true engine 和视觉/OOS 证据。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage141 一条状态摘要。
- 是否更新 `research/registry.md`：否，本阶段不是突破、废弃、正式候选或跨线合并。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是当前线日常研究约束。
