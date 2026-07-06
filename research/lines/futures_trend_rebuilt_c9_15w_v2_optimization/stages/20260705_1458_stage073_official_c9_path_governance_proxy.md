# Stage073 official C9 path governance proxy

- line_id：`futures_trend_rebuilt_c9_15w_v2_optimization`
- 当前模式：day
- 记录时间：2026-07-05T14:58:19
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：正式 C9 水下治理代理证伪；只读曲线级研究
- 是否重要突破：否，负结论
- 是否触发A/B：是；候选为可能影响正式资金治理的部署层代理，但本阶段只做最小证伪

## 外部调研与判断

- CPPI/TIPP、capital correction 和趋势跟随回撤资料均支持把资金治理作为独立层处理，但也提示降风险可能牺牲趋势右尾。
- 本次判断：先用不前视曲线级代理证伪，不通过则不进入真实引擎。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/tools/stage073_official_c9_path_governance_proxy.py`
- 修改脚本：无正式入口修改
- 删除脚本：无
- 新增参数：代理规则 `dd25_half_risk_proxy`，触发 `-25%`，解除 `-10%`，风险乘数 `0.5`；30w 闲置储备展示口径
- 修改参数：无正式交易参数
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage053 正式 C9 曲线，起点 `2018-01` 到 `2026-01` 逐半年，统一终点 `2026-06-30`；重点汇总 `2020-01` 以后。
- 账户规模：正式 `150,000`；展示口径 `300,000=150,000 交易袖 + 150,000 闲置储备`。
- 成本口径：沿用 Stage053 已有真实引擎曲线成本；代理不新增交易成本。
- 样本过滤：只读正式 C9，不读取或修改实盘日志。
- 策略/归因口径：曲线级代理，不是正式真实引擎回测。

## 结果

| sample           | version                       | variant_label         |   start_count |   positive_count |   min_return_pct |   median_return_pct |   max_return_pct |   worst_drawdown_pct |   median_drawdown_pct |   max_days_below_initial |   median_days_below_initial |   max_consecutive_below_initial_days |   median_proxy_active_days |
|:-----------------|:------------------------------|:----------------------|--------------:|-----------------:|-----------------:|--------------------:|-----------------:|---------------------:|----------------------:|-------------------------:|----------------------------:|-------------------------------------:|---------------------------:|
| starts_2020_2026 | official_c9_15w               | Official C9 15w       |            13 |               13 |         1.90107  |            126.199  |          3886.19 |             -55.3701 |              -24.469  |                      500 |                          20 |                                  387 |                          0 |
| starts_2020_2026 | account_30w_idle_reserve_view | 30w idle reserve view |            13 |               13 |         0.950533 |             63.0997 |          1943.09 |             -52.9113 |              -18.7861 |                      500 |                          20 |                                  387 |                          0 |
| starts_2020_2026 | dd25_half_risk_proxy          | DD25 half-risk proxy  |            13 |               13 |         1.90107  |            125.38   |          1515.04 |             -59.981  |              -24.469  |                      662 |                          19 |                                  439 |                          0 |

## 输出文件

- report：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage073_official_c9_path_governance_proxy/rebuilt_c9_v2_stage073_official_c9_path_governance_proxy_report_stage073_official_c9_path_governance_proxy_v1.md`
- summary：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage073_official_c9_path_governance_proxy/rebuilt_c9_v2_stage073_official_c9_path_governance_proxy_per_start_summary_stage073_official_c9_path_governance_proxy_v1.csv`
- curves：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage073_official_c9_path_governance_proxy/rebuilt_c9_v2_stage073_official_c9_path_governance_proxy_curves_stage073_official_c9_path_governance_proxy_v1.csv.gz`
- quality：`/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_rebuilt_c9_15w_v2_optimization/outputs/stage073_official_c9_path_governance_proxy/rebuilt_c9_v2_stage073_official_c9_path_governance_proxy_retention_vs_official_stage073_official_c9_path_governance_proxy_v1.csv`

## 结论

- 本阶段结论：`stage073_dd_brake_not_promoted_idle_reserve_accounting_only`。
- 是否进入下一步：不把 `dd25_half_risk_proxy` 进入真实引擎；30w 闲置储备只能作为账户展示/承受力口径，不能当策略升级。
- 下一步：若继续，应回到正式 C9 的真实成交/持仓层做 2022/2023 水下归因，寻找不以降风险砍恢复段为代价的结构信息；不要继续扫回撤阈值或风险乘数。

## 过拟合反思

- 运行前判断：否。只测试一个预声明、低自由度、账户层代理，并把右尾保留设为硬约束。
- 运行后判断：否。结果为负后直接停止，没有按 2022/2023 窗口继续调阈值或乘数。
- 原因：继续扫 `-20/-25/-30` 或 `0.3/0.5/0.7` 会变成历史窗口救参。

## 继续价值反思

- 运行前判断：有。正式 C9 右尾强但水下体验差，账户层治理值得先证伪。
- 运行后判断：有，但不是这条 brake 形状。价值在于收窄方向：亏损后降风险不是当前优先路线，应转向真实持仓/成交归因或新外生信息源。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等待下一阶段形成更明确路线。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段只是负结论代理，不是正式合入或重要突破。
