# Stage056 - full-market AI Top8 新开仓预算 cap 真引擎压力验证

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01T21:38:16 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结真实引擎候选 A/C 压力验证，不改官方实盘配置。
- 是否重要突破：`否`
- 是否触发A/B：`是`

## 外部调研与判断

- 参考资料：trend-following position sizing、Rob Carver risk budget、系统化趋势跟随综述、PySystemTrade/PyTrendFollow 等开源实现。
- 我的判断：有第一性价值的是“质量信号决定风险预算释放”，不是按最差品种/方向/月份做黑名单；因此本阶段只冻结 full-market AI Top8 一条规则。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage056_full_market_ai_budget_cap_engine.py`
- 新增测试：`tests/test_rebuilt_c9_stage056_full_market_ai_budget_cap.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：`MAX_NON_TOP8_VOLUME=1`、`selector=full_market_ai_top8`。
- 修改参数：无正式参数修改。
- 删除参数：无。

## 回测/归因参数

- A：`stage013_pressure_baseline`，Stage013。
- C：`stage056_full_market_ai_budget_cap`，Stage013 + 非 full-market AI Top8 新 flat_entry 最多 `1` 手。
- 样本：Stage054/055 去重左尾压力日级起点 `9` 个。
- 结束日期：`2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：沿用当前重建 C9/15w 与 Stage013 真实引擎口径。
- 样本过滤：不按品种/方向/日期/source 过滤。
- 策略/归因口径：真实引擎；不连接 CTP、不调用订单 API。

## 结果

- 期末权益：见 summary 输出。
- 总收益：Stage013 最小 `55.0954%`；Stage056 最小 `73.7259%`
- 最大回撤：Stage013 最差 `-37.7002%`；Stage056 最差 `-18.9994%`
- Sharpe：Stage013 中位 `0.7584`；Stage056 中位 `0.8065`
- 总滑点：见 summary 输出。
- 总交易次数：见 summary 输出。
- 胜率：见 summary 输出。
- 其他关键指标：Stage013 严格负窗口 `81351`，Stage056 严格负窗口 `183423`，80% 收益保留 `1/9`，cap 事件 `852`，减少手数 `5016`。

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage056_full_market_ai_budget_cap_engine/rebuilt_c9_stage056_full_market_ai_budget_cap_engine_report_stage056_full_market_ai_budget_cap_engine_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage056_full_market_ai_budget_cap_engine/rebuilt_c9_stage056_full_market_ai_budget_cap_engine_summary_stage056_full_market_ai_budget_cap_engine_v1.csv`
- daily：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage056_full_market_ai_budget_cap_engine/rebuilt_c9_stage056_full_market_ai_budget_cap_engine_curves_stage056_full_market_ai_budget_cap_engine_v1.csv`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage056_full_market_ai_budget_cap_engine/rebuilt_c9_stage056_full_market_ai_budget_cap_engine_budget_cap_events_stage056_full_market_ai_budget_cap_engine_v1.csv`
- goal_aggregate：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage056_full_market_ai_budget_cap_engine/rebuilt_c9_stage056_full_market_ai_budget_cap_engine_goal_aggregate_stage056_full_market_ai_budget_cap_engine_v1.csv`

## 结论

- 本阶段结论：`stage056_pressure_not_enough_stop_no_param_rescue`。
- 是否进入下一步：只有压力集相对 Stage013 改善且收益保留过关，才扩到更密日级/多周期；否则停止该形状，不扫 TopN 或手数。
- 下一步：停止扫 TopN/手数/品种；回到 Stage056 失败归因，寻找更稳定的预算信号。

## 过拟合反思

- 运行前判断：有风险但可控。规则来自最差窗口归因，必须小心；但它是固定横截面质量预算原则，不是品种/日期/方向补丁。
- 运行后判断：否。本阶段没有救参；如果继续调 Top8/Top6/2手就是过拟合。
- 原因：本阶段没有根据结果调整 TopN、手数或产品。

## 继续价值反思

- 运行前判断：有。Stage055 已显示 `selected_volume>1 且非 full-market AI top8` 与左尾亏损高度重合，值得做真实引擎验真。
- 运行后判断：有限。若压力集都不改善或右尾损失过大，该形状不应继续交易化。
- 原因：见核心指标和目标审计。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：只追加 `back_log.md`。
