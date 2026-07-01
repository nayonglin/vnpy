# Stage008 高质量标签小额非挤占加风险代理

- line_id：`futures_trend_rebuilt_c9_15w_optimization`
- 当前模式：`day`
- 记录时间：`2026-07-01 12:48 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：lot-level 只读上界代理；读取 Stage007 quality features 和 Stage006 curves，不是真实组合引擎，不改 C9，不连接 CTP，不调用下单。
- 是否重要突破：否，但代理结果支持进入真实引擎验证。
- 是否触发A/B：否。代理不是候选实盘版本。

## 外部调研与判断

- 参考资料：
  - Probability of Backtest Overfitting：`https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253`
  - Deflated Sharpe Ratio：`https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf`
  - Meta-labeling/triple-barrier：`https://hudsonthames.org/does-meta-labeling-add-to-signal-efficacy-triple-barrier-method/`
  - A Century of Evidence on Trend-Following Investing：`https://fairmodel.econ.yale.edu/ec439/hurst.pdf`
- 我的判断：
  - PBO/DSR 约束下，本阶段只能测一个预声明标签和一个固定小额比例，不能扫标签组合、倍率、年份、品种或方向。
  - meta-labeling 思路可用于“主 C9 信号不变，二级质量标签释放额外风险预算”，但必须通过真实成交/保证金路径验证。
  - 趋势跟随右尾约束要求加风险不能挤占原 C9 头寸，避免牺牲复利底座。

## 本次变更

- 新增脚本：`research/lines/futures_trend_rebuilt_c9_15w_optimization/tools/stage008_high_quality_add_risk_proxy.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `TAG_COLUMN=tag_ai4_6_entry_or_first_aligned`
  - `ADD_RISK_FRACTION=0.25`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据底座：
  - Stage006 curves：`18,495` 行
  - Stage007 quality features：`3,401` closed lots
- 代理规则：
  - 对 `tag_ai4_6_entry_or_first_aligned=True` 的 lot 增加 `25%` 非挤占风险。
  - 增量 PnL = `realized_pnl * 0.25`，在该 lot 平仓日计入曲线。
  - 不模拟真实成交、保证金占用、滑点增量、资金复用和日内路径，所以只能视作上界代理。
- 策略/实盘安全：
  - `strategy_changed=false`
  - `true_engine=false`
  - `order_api_called=false`
  - `ctp_connected=false`

## 结果

- 标签样本：
  - selected lots：`306`
  - selected realized PnL：`22,617,180.00`
  - proxy delta PnL：`5,654,295.00`
  - unmatched delta dates：`0`
- 多起点代理：
  - 样本起点：`17`
  - `>=252` 交易日成熟起点：`15`
  - 收益改善/不变/变差：`16 / 1 / 0`
  - 最大回撤改善/不变/变差：`15 / 2 / 0`
  - 基准最低收益：`1.9011%`
  - 代理最低收益：`1.9011%`
  - 基准中位收益：`203.6425%`
  - 代理中位收益：`227.6866%`
  - 基准最差最大回撤：`-56.2069%`
  - 代理最差最大回撤：`-55.2574%`
  - 基准中位最大回撤：`-47.2779%`
  - 代理中位最大回撤：`-46.4309%`
- 未解决项：
  - `annual_negative_rows=29`，没有改善年度负收益行问题。
  - 代理没有 broker10/保证金/真实成交约束，不能证明“任意大于一年起点正收益”。

## 输出文件

- report：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_report_stage008_high_quality_add_risk_proxy_v1.md`
- lot_deltas：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_lot_deltas_stage008_high_quality_add_risk_proxy_v1.csv`
- curves：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_curves_stage008_high_quality_add_risk_proxy_v1.csv`
- summary：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_summary_stage008_high_quality_add_risk_proxy_v1.csv`
- annual_returns：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_annual_returns_stage008_high_quality_add_risk_proxy_v1.csv`
- chart：`research/lines/futures_trend_rebuilt_c9_15w_optimization/outputs/stage008_high_quality_add_risk_proxy/rebuilt_c9_stage008_high_quality_add_risk_proxy_proxy_chart_stage008_high_quality_add_risk_proxy_v1.png`

## 结论

- 本阶段结论：固定 `ai4_6_entry_or_first_aligned` + `25%` 非挤占加风险代理是正向的：所有起点收益不变或改善，最大回撤不变或改善，中位收益从 `203.6425%` 到 `227.6866%`。这说明高质量标签有继续写真实组合引擎的价值。
- 是否进入下一步：进入。
- 下一步：Stage009 写真实组合引擎，至少要处理成交时点、增量滑点/手续费、保证金/broker10、资金复用、C9 原头寸不被挤占、多起点和 AI 审计；并复查 `annual_negative_rows=29` 是否仍未改善。

## 过拟合反思

- 运行前判断：否。只测一个预声明标签 `ai4_6_entry_or_first_aligned` 和一个保守 `25%` 非挤占比例，不扫参。
- 运行后判断：否。代理没有切换标签、年份、品种、方向或风险倍率；结果好坏都不反向修改规则。
- 原因：本阶段是是否值得写真引擎的上界代理，不是最终候选。

## 继续价值反思

- 运行前判断：是。Stage007 已给出高覆盖高质量标签，必须先用代理检验是否值得写真引擎。
- 运行后判断：有。代理所有起点收益不差且回撤多数改善，但它不是成交/保证金级真实引擎，下一步要写真引擎验证。
- 原因：该方向开始贴近用户目标里的“AI 选品优化、高质量信号、加大风险投入”，但还没满足“任意大于一年周期正收益”和真实交易约束。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段仍是只读代理，不是正式候选或重要合入。
