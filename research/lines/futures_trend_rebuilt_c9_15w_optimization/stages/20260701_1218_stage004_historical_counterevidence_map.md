# Stage004 历史反证清单与下一阶段护栏

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:18 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：历史反证整理，不改策略逻辑，不跑真实组合引擎
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- Trend following / CTA 风险管理资料支持长期分散化趋势跟随，但也提示右尾复利容易被 drawdown control、止盈、提前降仓破坏。
- Deflated Sharpe / PBO / multiple testing 框架提示：历史上已经跑过大量候选后，继续围绕失败形状扫小参数会显著增加虚假发现概率。
- 本阶段采纳：把历史失败形状固化为约束。
- 本阶段否决：继续在 `topN/maxpos/R/分钟窗口/品种/方向/年份` 上救参。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage004_historical_counterevidence_map.py`
- 新增输出目录：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/`
- 修改策略脚本：无
- 删除脚本：无
- 新增参数：无策略参数；新增历史反证分类口径。
- 修改参数：无
- 删除参数：无

## 口径

- 资料来源：
  - 本线 Stage002/003。
  - 根目录 `memory.md` 中 Stage405/406/407/418 鸡蛋与 AI 池历史记录。
  - `futures_trend_c9_minrisk_highquality` Stage002/003/004/008/009/016/019/046/076/080/085-090/251。
  - `futures_trend_stage819_intraday_rules` Stage868-880、Stage882/883。
- 本阶段只做历史归纳，不新增策略候选，不把代理结论当正式回测。

## 禁止重复尝试清单

- 共整理 `15` 类禁试形状。
- 其中有明确收益保留数值且低于 `80%` 的形状 `9` 类。
- 关键禁试：
  - `full-market AI top9 + jd + maxpos5`：Stage405 收益保留仅 `4.5756%`，broker10 `108.0745%`。
  - `原正式 AI 池 + jd 参与 AI rerank top9`：Stage407 收益保留 `36.1730%`，jd 高频入选但挤掉核心右尾。
  - `50% scout + 0.5R restore`：Stage002 收益保留 `66.2493%`，broker10 从 `111.7365%` 恶化到 `116.8005%`。
  - `broker10 >95% 后 largest-margin 减到 80%`：Stage003 收益保留 `58.8738%`，最大回撤恶化到 `-54.1289%`。
  - `broker10 cap-only delayed restore`：Stage004 收益保留 `59.8070%`，最大回撤恶化 `7.6512pp`。
  - `no-follow 30m 降到 half 或 80%`：收益保留分别约 `77.6488%/78.8296%`，低于 `80%` 且 broker10/回撤不达标。
  - `opening range adverse exit`：收益保留 `40.2072%`，本质是砍右尾换平滑。
  - `entry-day confirmed breakeven`：收益保留 `77.7088%`，最大回撤恶化到 `-62.8055%`。
  - `DD>=30% -> 0.5x 主动降风险`：收益保留 `12.6009%`。
  - `+0.5R progress 同手数加仓`：收益大但 DD `-61.6881%`、broker10 `203.4450%`，不具备生存线。
- 高质量标签类不是完全否定：
  - `ai_rank_4_6 ∩ entry/first aligned` 有只读价值，但样本 `24` 笔、覆盖不足；禁止直接作为唯一交易开关。
  - `no-follow` 是有价值负标签，但存在右尾反例；禁止单独降仓或删除。

## 下一阶段允许原则

- 核心 C9 不挤占：新增品种、鸡蛋、外生信号或加风险，不得改变原核心右尾品种的主账户排队、连败状态和保证金路径。
- 鸡蛋先隔离后评价：`jd.DCE` 只能先走独立 sleeve / 独立风险槽 / forward watch；不能直接进共享 AI rerank。
- 高质量标签必须入场可见：允许 AI rank/score、entry/first aligned、no-follow、OI/价格一致、组合状态、保证金压力等入场时可见字段；禁止最终盈亏/MFE/MAE 反推。
- 加风险只允许独立小预算：不能主账户同手数 pyramiding；若要加风险，只能小额独立 sleeve，并有 broker10 生存硬闸和多周期 A/C 验证。
- 先代理、再真引擎、再多起点：代理通过后才能写真组合引擎；真引擎通过后再复跑 Stage167 口径、周期大于一年口径和 AI 审计。
- 收益保留不是可谈判项：默认必须保留 Stage167 中位总收益 `203.6425%` 的 `80%+`，即 `162.9140%+`。
- 完整点时化数据优先：外生数据必须完整覆盖、可审计 raw/hash/schema、entry_date 前可得、右尾缺口安全；否则只做数据工程。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/rebuilt_c9_stage004_report_stage004_historical_counterevidence_map_v1.md`
- prohibited：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/rebuilt_c9_stage004_prohibited_shapes_stage004_historical_counterevidence_map_v1.csv`
- allowed：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/rebuilt_c9_stage004_allowed_principles_stage004_historical_counterevidence_map_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/rebuilt_c9_stage004_rejected_return_retention_stage004_historical_counterevidence_map_v1.png`
- decision：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage004_historical_counterevidence_map/rebuilt_c9_stage004_decision_stage004_historical_counterevidence_map_v1.json`

## 结论

- 当前不能直接进入新策略参数扫描。
- 历史已经反复证明：共享 AI 池加鸡蛋、默认最小风险再恢复、no-follow 降仓、OR 退出、保本、DD 地板、同手数加仓都会在收益保留、右尾、broker10 或多起点稳定性上失败。
- 下一步 Stage005 只允许做一个冻结代理：C9 核心不挤占；`jd` 独立或非挤占；高质量标签必须入场时可见；加风险只能小额独立预算；通过后再写真引擎。

## 过拟合反思

- 运行前判断：否。本阶段是把历史失败经验固化成护栏，不产生新候选。
- 运行后判断：否。没有根据失败窗口调参数，也没有选择性只保留好结果。
- 风险提醒：如果下一步绕过这张清单继续扫 `topN/maxpos/R/窗口/品种/方向/年份`，就是明显过拟合。

## 继续价值反思

- 运行前判断：是。目标要求高，必须避免重复已反证路线。
- 运行后判断：是。Stage004 已把 Stage005 的可行形状收敛到非挤占鸡蛋和入场可见质量标签。
- 后续规划：Stage005 写冻结代理，不直接改正式策略；代理必须先验证是否跨年份、跨品种、跨起点保留右尾。

## 合入建议

- 是否更新本线 `LINE.md`：是，补 Stage004 当前状态。
- 是否更新 `research/registry.md`：是，把本线最新阶段从 Stage001 更新为 Stage004，便于后续继续。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段未产生正式候选或重要突破。
