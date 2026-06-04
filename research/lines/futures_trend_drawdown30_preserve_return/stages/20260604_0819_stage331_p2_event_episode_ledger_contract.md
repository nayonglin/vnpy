# Stage331 P2 Event Episode Ledger Contract 审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 08:19 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：P2 公开源事件 seed 与 episode ledger 合同审计；不重放策略、不改交易规则、不生成 selector/paper/交易白名单、不连接 CTP。
- 是否重要突破：否。它把基本面/舆情公开源从 source evidence 推进到 event seed/episode 合同，但没有产生 alpha 结论。
- 是否触发A/B：否。没有策略候选、没有 paper selector、没有交易白名单。

## 外部调研与判断

- 参考资料：
  - Event window methodology：`https://eventstudy.de/docs/window-selection`
  - Event data preparation：`https://eventstudy.de/docs/data-preparation`
  - Overlapping event window correlation：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3167271`
  - Purged cross-validation：`https://en.wikipedia.org/wiki/Purged_cross-validation`
  - USDA WASDE release process：`https://www.usda.gov/about-usda/general-information/staff-offices/office-chief-economist/world-agricultural-outlook-board/wasde-report`
- 我的判断：
  - 事件研究必须严格区分 `event seed` 与 `verified episode`。前者只说明某个事件源在某个时间点可得；后者必须经过后续价格窗口、非重叠、purged walk-forward、左尾和 TCA 验证。
  - USDA WASDE 是月度、定时发布的供应需求事件源；Crop Progress 是季节性周度事件源。它们适合做 forward monitor，但不能用历史回填直接生成 selector。
  - 同一产品同一 PIT 日期出现多个事件 seed 时，后续窗口会重叠，不能简单计为多个独立 episode。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage631_p2_event_episode_ledger_contract.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：
  - `REQUIRED_PIT_DATES = 20`
  - `REQUIRED_PIT_MONTHS = 12`
  - `REQUIRED_INDEPENDENT_EPISODES_PER_FAMILY = 3`
  - `REQUIRED_WALK_FORWARD_SPLITS = 3`
  - `REQUIRED_LIVE_TCA_PER_PRODUCT = 3`
  - `REQUIRED_LEFT_TAIL_WINDOWS = 2`
- 修改参数：无交易参数修改。
- 删除参数：无。

## 回测/归因参数

- 新增收益回测：无。
- 输入数据：Stage330 master PIT ledger `6` 行。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：
  - event seed 仅允许 `public_html_event_release_page` 且 event type 属于 `crop_progress_release_page`、`cotton_wool_outlook_release_page`、`wasde_esmis_release_page`。
  - `crop_progress_methodology_page`、`esmis_api_documentation` 只作为 methodology/source support，不作为事件 seed。
  - 必须保持 `selector_allowed=0`、`paper_or_whitelist_allowed=0`、`verified_independent_episode=0`。
- episode 合同：
  - 入场时钟：`next_tradable_session_after_received_at_utc`
  - 事件窗口：后续 `20/63/126` 交易日窗口，样本足够后再评估。
  - 估计窗口：事件前 `120-250` 交易日，且截至事件前 `10-30` 交易日。
  - 非重叠：同产品同 PIT 日期多事件、同产品同 event family 重叠窗口必须 purge 或人工去重。

## 结果

- 期末权益：不适用，本阶段不重算收益。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`p2_event_episode_seed_contract_ready_selector_locked`
  - event seed rows：`3`
  - event products covered：`2`
  - verified independent episodes：`0`
  - required independent episodes per family：`3`
  - selector rows：`0`
  - paper/whitelist rows：`0`
  - hard gates：`9/9`
  - `ag.SHFE`：PIT dates `1`，event seed rows `0`，verified episodes `0`，progress `2.5%`，状态 `event_seed_missing_selector_locked`。
  - `CY.CZCE`：PIT dates `1`，event seed rows `2`，event families `2`，methodology support rows `2`，same-day overlap groups `1`，verified episodes `0`，progress `37.5%`。
  - `SR.CZCE`：PIT dates `1`，event seed rows `1`，event families `1`，methodology support rows `1`，verified episodes `0`，progress `37.5%`。

## 输出文件

- script：`examples/portfolio_backtesting/analyze_qmt_roll_stage631_p2_event_episode_ledger_contract.py`
- event seed ledger：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_event_seed_ledger_stage631_p2_event_episode_ledger_contract_v1.csv`
- episode contract：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_episode_contract_stage631_p2_event_episode_ledger_contract_v1.csv`
- product progress：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_product_episode_progress_stage631_p2_event_episode_ledger_contract_v1.csv`
- gates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_gates_stage631_p2_event_episode_ledger_contract_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_decision_stage631_p2_event_episode_ledger_contract_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_report_stage631_p2_event_episode_ledger_contract_v1.md`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage631_p2_event_episode_ledger_contract_chart_stage631_p2_event_episode_ledger_contract_v1.png`

## 图表视觉复盘

- 左上图显示：`CY` 有 `2` 条 event seed、`SR` 有 `1` 条、`ag` 为 `0`；但 verified episodes 三者均为 `0`，且距离 `3` episode 红线很远。
- 右上 heatmap 显示：`CY` 覆盖 `crop_progress_release_page` 和 `cotton_wool_outlook_release_page`，`SR` 覆盖 `wasde_esmis_release_page`；`ag` 全空，不能进入事件 selector。
- 左下合同状态显示：当前真正满足的是 `event_seed` 和 `selector_lock`，`pit_depth/event_window/estimation_window/overlap_purge/independent_episode/walk_forward/left_tail/live_tca` 都只是合同定义，尚未满足。
- 右下 gate 图显示：绿色包含 fail-closed lock。`overlap_groups_not_independent=1` 很关键，说明 CY 同日双事件不能被算成两个独立 episode。

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage631_p2_event_episode_ledger_contract.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage631_p2_event_episode_ledger_contract.py`：通过。
- `python -m json.tool ...decision_stage631_p2_event_episode_ledger_contract_v1.json`：通过。
- 图表视觉检查：通过；修正了同日多事件 overlap 统计后，图表和表格结论一致。

## 结论

- 本阶段结论：`CY/SR` 的公开源已经可以进入 event seed ledger 合同，但不能进入 selector、paper、A/B 或交易白名单。
- 是否进入下一步：进入，但下一步仍是证据累计和合同化，不是交易。
- 下一步：
  1. 继续按交易日追加 Stage629/630，至少累计 `20` 个 PIT 日期和 `12` 个月跨度。
  2. 对 `CY/SR` 的事件 seed 追加 post-event 20/63/126 交易日 outcome ledger，但仅作为后验标签，不允许当日回填。
  3. 对同产品同日多事件做 purge/人工去重，避免重复算独立 episode。
  4. 为 `ag` 寻找事件型公开源或授权源；否则它只能保留为 source monitor，不进入 event route。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有使用事件后收益、没有筛选赢家事件、没有调参，只把事件 seed、episode 合同和 fail-closed 锁定写清楚。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：低单笔风险扩池要靠“选对独立风险槽”，而事件 seed/episode ledger 是将基本面/舆情数据转成可实盘、可审计 selector 的必要前置层。当前仍远未晋级，但方向有效。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage331 摘要。
- 是否更新 `research/registry.md`：是，最新阶段推进到 Stage331。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
