# Stage301 risk-slot source-first rescreen

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-04 03:10 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读合成 Stage574/571/597/600 证据，重新审计 DCE 阻塞后的扩池风险槽；不做收益回放、不改策略、不生成交易白名单。
- 是否重要突破：否，但它把“扩池”从 `j/i` 单点补证重新拉回 source-first 的全族风险槽判断。
- 是否触发A/B：否。`promotion_allowed=false`、`paper_selector_allowed=false`、`trading_whitelist_allowed=false`。

## 外部调研与判断

- 参考资料：
  - Man Group `Trend Following: The Optimal Market Mix for a Trend Follower`
  - `Optimal Allocation of Trend Following Strategies`
  - `Diversifying Trends / CoTrend`
  - `skfolio` / `PyPortfolioOpt` 的 HRP、聚类和风险预算实现
- 我的判断：
  - 趋势策略的稳定性确实依赖多市场、多风险驱动和低相关暴露，但“相关性”不能只按品种数量理解，必须按风险槽/产品族理解。
  - Stage299/300 证明 DCE 官方源被 `HTTP 412/400` 阻塞后，继续围绕 `j/i` 做普通 browser-cookie 修复价值下降；下一步要么找可授权 DCE 通道，要么优先找非 DCE 且 source 稳定的新产品族。
  - 这不是收益择优回测，而是 source、相关性、容量、TCA 的可执行性分层；因此不会把后验收益直接升级成实盘规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage601_risk_slot_source_first_rescreen.py`
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：
  - `P0_EFFECTIVE_SLOTS_AFTER_YC_TOP1=4`
  - `TARGET_EFFECTIVE_SLOTS=7`
  - `TARGET_MAX_SLOT_RISK_PCT=15.0`
  - `MAX_CORE_CORR_WATCH=0.10`
  - `SOURCE_RICH_COMPONENT_PCT=80.0`
  - `MATERIAL_FAMILY_PNL=50000.0`
- 修改参数：无策略参数修改。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不做新回测；读取 Stage574 单品种机会/容量、Stage597 产品工作清单、Stage571 source priority、Stage600 DCE browser/session 取证。
- 账户规模：不适用。
- 成本口径：不适用。
- 策略/归因口径：source-first 风险槽复筛，不生成 TopN、risk、family cap、相关阈值扫描。

## 结果

- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。
- 其他关键指标：
  - 决策：`source_first_rescreen_no_new_tradeable_slot`
  - products rescreened：`38`
  - families rescreened：`11`
  - deployable new family slots now：`0`
  - effective slots now：`4`
  - effective slots if black_ferrous source resolved：`5`
  - target effective slots：`7`
  - hard gates：`5/7`
  - promotion allowed：`false`
  - paper selector allowed：`false`
  - trading whitelist allowed：`false`

## 风险槽复筛结论

- 当前 P0 仍只有 `4` 个有效独立槽；`y/c` 同族同向必须 top1-only。
- `al.SHFE/bu.SHFE/TA.CZCE/pg.DCE` 的 source 或收益有亮点，但都属于已有 `base_metals/energy_oil/petrochem` 家族，只能做同族 tie-break 或替补，不能降低独立单槽风险。
- `black_ferrous(j.DCE/i.DCE)` 仍是唯一低相关新族候选，但 Stage600 已证明普通 browser-cookie 不能修复 DCE 官方源；未找到可授权/稳定替代源前，它不能计入当前可交易风险槽。
- `soft_agri/precious_metals` 具备相对完整 source 且核心相关低，但历史机会为负或不足；当前只允许低频 forward monitor，不投入 TCA、不进入 paper。
- `rubber(br.SHFE)` 有正收益代表，但核心相关 `0.2783` 明显越过 `0.10` 观察线，不能作为分散槽。

## 图表视觉复盘

- 左上散点图显示：`br.SHFE` 位于 `0.10` 相关阈值右侧且距离很远，确认“有收益但不分散”；`j/i` 靠近低相关区域但被标记为 DCE source blocker；`al.SHFE` 收益高且 source score 高，但颜色显示为同族深度，不是新增槽。
- 右上 family score 显示：source-first 排名靠前的仍是 P0 既有族，`black_ferrous` 排名可接受但状态是 DCE blocked；`precious_metals/soft_agri` 是 source/no edge。
- 左下风险槽图显示：P0 当前、加入同族深度、计入 DCE 当前阻塞后三者都停在 `4` 槽、单槽 `25%`；即使未来解决 `j/i` 数据源也只是 `5` 槽、`20%`，仍不达 `7` 槽/`14.3%` 目标。
- 右下闸门显示：`deployable_new_family_slots_now` 和 `effective_slots_after_dce_blocker` 两个核心门未过；所以本阶段不允许 paper/白名单。

## 输出文件

- product rescreen：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_product_rescreen_stage601_risk_slot_source_first_rescreen_v1.csv`
- family rescreen：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_family_rescreen_stage601_risk_slot_source_first_rescreen_v1.csv`
- slot scenarios：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_slot_scenarios_stage601_risk_slot_source_first_rescreen_v1.csv`
- gates：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_gates_stage601_risk_slot_source_first_rescreen_v1.csv`
- next actions：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_next_actions_stage601_risk_slot_source_first_rescreen_v1.csv`
- decision：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_decision_stage601_risk_slot_source_first_rescreen_v1.json`
- report：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_report_stage601_risk_slot_source_first_rescreen_v1.md`
- chart：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage601_risk_slot_source_first_rescreen_chart_stage601_risk_slot_source_first_rescreen_v1.png`

## 验证

- `.py311/bin/python -m py_compile examples/portfolio_backtesting/analyze_qmt_roll_stage601_risk_slot_source_first_rescreen.py`：通过。
- `.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage601_risk_slot_source_first_rescreen.py`：通过。
- `.py311/bin/python -m json.tool ...decision_stage601_risk_slot_source_first_rescreen_v1.json`：通过。
- 输出文件存在：通过。
- 图表视觉检查：通过；已修正右上状态标签和左下场景标签过长问题。

## 结论

- 本阶段结论：扩池方向仍成立，但当前不能晋级为 paper、A/B 或交易白名单；DCE 阻塞后没有新的可交易独立风险槽。
- 是否进入下一步：是，但下一步不应继续扫宽池收益。
- 下一步：
  1. P0 继续补 `v/ao/lu` route/event/official endpoint/TCA，`y/c` 保持同族同向 top1-only。
  2. `black_ferrous(j/i)` 停止普通 browser-cookie 修复路线，只找可授权 DCE 源、交易所可下载替代源或稳定准官方源。
  3. `al/bu/TA/pg` 只做同族 tie-break/替补，不计入新增风险槽。
  4. `soft_agri/precious_metals` 只做低频 forward monitor；20日后若有固定事前 selector edge，再决定是否补 TCA。
  5. 下一轮优先找非 DCE、source 稳定、低相关的新独立产品族；如果仍找不到两个新族，应把扩池目标转向外部承载工具或跨策略组合。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段没有做新收益回放、没有扫 TopN/risk/corr/family cap、没有根据历史收益生成白名单，只合成已有冻结证据并显式扣除了 DCE source blocker。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值，但路线需要转向 source-stable 新族或授权数据。
- 原因：本阶段证明“加同族深度”不能降低单槽风险，DCE 未解决时 `j/i` 也不能帮当前实盘；下一步只有找到至少两个新独立族，才可能把单槽风险压到 `15%` 附近。

## 合入建议

- 是否更新本线 `LINE.md`：是，更新当前状态与下一步。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段不是正式候选、重要突破、路线废弃或跨线合并。
