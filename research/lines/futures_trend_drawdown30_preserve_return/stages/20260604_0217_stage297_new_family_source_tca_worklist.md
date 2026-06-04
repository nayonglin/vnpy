# Stage297 新产品族 source/TCA 工作清单

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 02:17 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读归因与执行工作清单；不做收益回测，不修改策略，不生成交易白名单。
- 是否重要突破：否。它把扩池方向收敛成可执行补证清单，但不是正式候选。
- 是否触发A/B：否。当前 `promotion_allowed=false`、`paper_selector_allowed=false`、`trading_whitelist_allowed=false`。

## 外部调研与判断

- 参考资料：
  - Man Group `Trend Following: The Optimal Market Mix for a Trend Follower`
  - `Optimal Allocation of Trend Following Strategies`
  - `Trend-following trading strategies in commodity futures: A re-examination`
  - GitHub `Riskfolio-Lib`
  - GitHub `skfolio`
- 我的判断：
  - 外部研究支持趋势策略跨市场/跨风险驱动分散和风险预算，但也强调相关性、容量、执行成本和市场选择质量。
  - 本线不能把“增加品种数量”当作“降低风险”。正确单位应是有效独立风险槽；同族同向品种只能算同一风险槽或同族替补。
  - 当前最值得继续补证的是 `black_ferrous(j.DCE/i.DCE)`，不是因为收益足够，而是因为核心相关低、容量过线、basis/inventory 有源，能作为新产品族补证样本。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage597_new_family_source_tca_worklist.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TARGET_EFFECTIVE_RISK_SLOTS=7`
  - `TARGET_FAMILIES=6`
  - `TARGET_MAX_SLOT_RISK_PCT=15.0`
  - `MIN_FORWARD_DATES=20`
  - `MIN_FORWARD_RUNS=20`
  - `MIN_TCA_PER_NEW_PRODUCT=3`
  - `MIN_NEW_FAMILY_COUNT_PREFERRED=3`
  - `MIN_NEW_FAMILY_MATERIAL_PNL=50000`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage548/571/583/596 已冻结输出；本阶段不重放收益。
- 账户规模：N/A
- 成本口径：N/A
- 样本过滤：只读合成 `P0`、`P1_new_family_candidate`、`P1_same_family_depth_only`、高相关拒绝、容量/材料性拒绝产品。
- 策略/归因口径：有效风险槽、产品族、核心相关、source readiness、forward 样本深度、live TCA 缺口。

## 结果

- 期末权益：N/A
- 总收益：N/A
- 最大回撤：N/A
- Sharpe：N/A
- 总滑点：N/A
- 总交易次数：N/A
- 胜率：N/A
- 其他关键指标：
  - 决策：`new_family_worklist_black_ferrous_only_no_paper`
  - P0 有效产品族/风险槽：`4`
  - 当前 P1 新产品族数量：`1`
  - 加入当前 P1 后有效风险槽：`5`
  - 目标有效风险槽：`7`
  - 目标产品族：`6`
  - `black_ferrous` P1 产品：`2`，即 `j.DCE/i.DCE`
  - `black_ferrous` 正历史机会合计：`17000`
  - hard gates：`2/9`
  - `black_ferrous_low_core_corr`：通过，max abs core corr `0.0094`
  - `black_ferrous_materiality`：不通过，`17000 < 50000`
  - `black_ferrous_core_source_ready`：软通过，`2/2 basis+inventory+live_state ready`
  - `black_ferrous_member_warehouse_ready`：不通过，`0/2`
  - `new_family_live_tca_samples`：不通过，`0/6`
  - `source_alpha_allowed_now`：不通过，`0`
  - `forward_sample_depth`：不通过，`runs=2, dates=2`
  - `p0_live_tca_gap`：不通过，`0/9`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_report_stage597_new_family_source_tca_worklist_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_family_worklist_stage597_new_family_source_tca_worklist_v1.csv`
- product worklist：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_product_worklist_stage597_new_family_source_tca_worklist_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_gates_stage597_new_family_source_tca_worklist_v1.csv`
- next actions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_next_actions_stage597_new_family_source_tca_worklist_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_decision_stage597_new_family_source_tca_worklist_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage597_new_family_source_tca_worklist_chart_stage597_new_family_source_tca_worklist_v1.png`

## 结论

- 本阶段结论：
  - 用户提出的“减少单笔风险、扩大品种池、每年抓部分品种趋势收益，同时避免高相关风险”方向成立，但当前只能作为补证路线，不能作为收益回测或交易候选。
  - `j.DCE/i.DCE` 所在 `black_ferrous` 是当前唯一值得进入 P1 source/TCA 工作流的新产品族；它能把有效槽从 `4` 增到 `5`，但离目标 `7` 还差 `2` 个独立族。
  - `br.SHFE` 有收益但核心相关 `0.2783` 过高，不能当新增独立风险槽。
  - `soft_agri/precious_metals` 等部分产品族有数据源，但当前材料性不足，先不投入 TCA。
- 是否进入下一步：进入补证，不进入 paper、不进入 A/B、不进入白名单。
- 下一步：
  1. `black_ferrous(j/i)` 新建 P1 forward source 账本：basis/inventory/事件 route，每日只计一次 `received_at`，累计 `20` 日。
  2. `j/i` 每品种至少补 `3` 个真实或独立分钟证据 TCA 样本。
  3. P0 继续补 route/event/official endpoint/TCA；`y/c` 保持同族同向 top1-only。
  4. 达到样本深度后，只允许一次冻结的低风险 sleeve 评估，目标是改善 3/6 个月持有体验；未达标前禁止收益回测 selector。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有改交易规则、没有调参、没有用历史收益选择白名单、没有做收益回测；只是把已有冻结审计中的产品族、相关性、容量、source 和 TCA 证据合成工作清单。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但范围应收窄。
- 原因：Stage596 已证明有效风险槽不足是核心瓶颈；Stage597 进一步证明当前只有 `black_ferrous(j/i)` 值得补证。继续价值在于补 P1 新族 source/TCA 与 P0 执行闭环，而不是继续随机扩池或扫宽池收益。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新最新阶段和下一步。
- 是否更新 `research/registry.md`：是，更新本线最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破或跨线合并。
