# Stage149 预声明 replay 假设规格

- line_id：`futures_trend_c9_minrisk_highquality`
- 当前模式：`day`
- 记录时间：2026-06-20 23:23 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：预声明假设规格 / 证据门槛合同 / 只读上下文审计
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen《Time Series Momentum》：https://elmwealth.com/wp-content/uploads/2017/06/timeseriesmomentum.pdf
  - Hurst/Ooi/Pedersen《A Century of Evidence on Trend-Following Investing》：https://fairmodel.econ.yale.edu/ec439/hurst.pdf
  - Alpha Architect 对 time-series momentum 的历史证据摘要：https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/
  - PyTrendFollow：https://github.com/chrism2671/PyTrendFollow
  - MLM trend-following repository：https://github.com/amstrdm/mlm-trend-following
- 我的判断：趋势跟随的稳健性来自跨资产、跨周期、简单且预声明的趋势暴露，不来自从单段历史回撤、最终盈亏或分钟残差里挖补丁。开源 futures trend-following 主要是日线/组合层系统，不能解决本线“同源分钟 K 或盘口执行证据”缺口。Stage149 因此只应把下一条假设写成可反证的证据合同，而不是直接制造交易规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_c9_minrisk_highquality/tools/stage149_predeclared_replay_hypothesis_spec.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage045/Stage102/Stage148 固定 C9 minrisk 路径与账本；本阶段不新增策略回测。
- 账户规模：沿用本线 C9 minrisk 研究口径。
- 成本口径：沿用输入账本，`total_slippage=2,730,130`
- 样本过滤：不新增交易过滤；只读读取 Stage045 timestamp-ready replay ledger `219` 笔、Stage102 resolution rows `219` 笔、Stage148 目标缺口审计结果。
- 策略/归因口径：预声明 `H3_event_maturity_continuation_predeclared_spec`，明确 Stage045/102 event family 只能作为研究标签，不能作为开仓当时可见的交易条件；fallback/no-proxy 样本保持官方路径。

## 结果

- 期末权益：`39,176,437.60`
- 总收益：`26017.6251%`
- 最大回撤：`-45.0827%`
- Sharpe：`1.6331`
- 总滑点：`2,730,130`
- 总交易次数：`787`
- 胜率：`36.0902%`
- 其他关键指标：
  - decision：`stage149_predeclared_replay_hypothesis_spec_ready_no_rule`
  - next_best_action：`stage150_readonly_feasibility_or_wait_real_w0`
  - hypothesis_spec_ready：`1`
  - closed_route_collision_count：`0`
  - evidence_requirement_count：`11`
  - evidence_ready_count：`4`
  - evidence_missing_count：`7`
  - same_source_or_authorized_data_ready：`0`
  - stage045_replay_order_count：`219`
  - stage102_context_order_count：`219`
  - sample_context_row_count：`22`
  - preflight_rule_allowed：`0`
  - true_engine_allowed：`0`
  - strategy_feature_usable：`0`
  - current_package_promotion_allowed：`0`
  - side_effect_count：`0`
  - gate_status：`7/7` 通过，但通过含义是“规格已写、规则被拦、证据缺口仍在”，不是候选通过。

## 输出文件

- report：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_report_stage149_predeclared_replay_hypothesis_spec_v1.md`
- summary：`research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_summary_stage149_predeclared_replay_hypothesis_spec_v1.csv`
- orders：无
- daily：无新增 daily 账本
- quality：
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_hypothesis_spec_stage149_predeclared_replay_hypothesis_spec_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_closed_route_collision_stage149_predeclared_replay_hypothesis_spec_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_evidence_requirements_stage149_predeclared_replay_hypothesis_spec_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_sample_context_stage149_predeclared_replay_hypothesis_spec_v1.csv`
  - `research/lines/futures_trend_c9_minrisk_highquality/outputs/stage149_predeclared_replay_hypothesis_spec/qmt_roll_stage149_c9_minrisk_predeclared_replay_hypothesis_spec_gate_status_stage149_predeclared_replay_hypothesis_spec_v1.csv`
  - 5 张视觉图：official path spec status、closed route collision matrix、evidence requirement matrix、sample context matrix、gate status matrix。

## 结论

- 本阶段结论：Stage149 已把 Stage148 给出的“无新增数据时唯一允许动作”落实为一个冻结假设规格，而不是交易候选。该规格的核心是：未来任何分钟 overlay 只有在独立、点时化、可行动且不砍右尾的趋势成熟/延续证据出现时，才允许讨论风险减少或恢复；Stage045/102 的 event family 目前只能作为研究标签，不能直接进入规则。闭合路线碰撞为 `0`，说明没有重启 no-follow、opening-range、default minrisk restore、breakeven、absorption/reclaim、near-touch OHLC、far-from-touch、Tq transform、maxDD/final-PnL label 或账户层 overlay。但证据只 ready `4/11`，同源/授权分钟数据、提前量、右尾 atlas、LOYO、monthly-start、product-family 和 Stage145 真实包全部缺失，所以 `preflight_rule_allowed=0`。
- 是否进入下一步：是，但不能进入 true engine。
- 下一步：如果没有真实 W0/授权 orderflow，Stage150 只能做这个 H3 规格的只读可行性检查和视觉 atlas 需求清单，仍不产出交易规则；如果真实数据到货，则先跑 Stage125 -> Stage133 -> Stage112/113 验收。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有收益优化、阈值扫描、年份/品种切片、true engine 或交易规则；它反而把未来规则入口锁定在证据缺口上，防止从 Stage045/102 标签或已关闭路线里反推。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但价值主要是收束路线而非制造收益。
- 原因：当前线如果继续在旧路线周边救参，会逐步变成历史拟合。Stage149 把“下一步到底允许研究什么”固定成一个可拒绝、可验收的 H3 合同，并明确缺证据时不能进规则。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
