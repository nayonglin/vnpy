# Stage077 Stage075组合层forward paper监控入口

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-27 02:09 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：组合层候选 monitor-only；不修改78-1、C3、股票账户参数或组合权重
- 是否重要突破：否。本阶段把 Stage075/076 候选接入日常验证，不产生新策略版本。
- 是否触发A/B：否。按 `version-ab-experiment`，监控、dashboard、post-mortem 不运行 A/B/C。

## 外部调研与判断

- 参考资料：
  - QuantStats 组合绩效报告包含回撤、滚动统计和 Ulcer Index 等组合监控指标。
  - PortfoliosLab / pfolio 对 Ulcer Index 的说明强调该指标同时衡量回撤深度和持续时间，适合识别“长期水下/持有压力”。
  - forward testing / paper trading 的通用原则是实时记录信号、成交、PnL、回撤和风险状态，而不是继续优化历史参数。
- 我的判断：
  - Stage075/076 已经显示 `50万C3 + 30万独立股票账户` 相对78-1明显平滑，但不能直接晋级正式策略。
  - 低过拟合推进方式是把它固定为组合层 paper 监控对象，设置绿/黄/红闸门，后续只根据真实复跑状态决定是否继续，而不是根据历史弱窗口调股票权重或参数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage377_stage075_combo_forward_paper_monitor.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：只新增监控阈值，不新增交易参数。
  - 最大回撤硬闸门：`-30.00%`
  - 现金对照收益优势：`20.00pp`
  - 现金对照回撤容忍：`-0.75pp`
  - 两年停滞闸门：504日滚动收益必须 `> 0.00%`
  - 252日相对现金收益黄灯：`-5.00pp`
  - 252日相对现金收益红灯：`-10.00pp`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04-27`
- 账户规模：
  - 期货腿：50万
  - 股票腿：30万
  - 组合/现金对照：80万
- 成本口径：沿用 Stage075 期货C3曲线与股票整手账户 min-fee paper 曲线；本阶段不新增成交成本假设。
- 样本过滤：只使用 Stage075/076 既有曲线；不新增品种、不重排窗口。
- 策略/归因口径：
  - `official78_50w`
  - `A_c3_50w`
  - `B_stock_30w`
  - `cash_50w_c3_plus_30w_cash`
  - `C_50w_c3_plus_30w_stock`

## 结果

- 期末权益：`30,193,682.12`（80万组合口径）
- 总收益：`3674.2103%`
- 最大回撤：`-28.0463%`
- Sharpe：`1.3187`
- 总滑点：无新增统计；沿用底层既有曲线
- 总交易次数：无新增统计；本阶段 monitor-only
- 胜率：无新增统计；本阶段 monitor-only
- 其他关键指标：
  - 当前监控状态：`yellow`
  - 红灯原因：无
  - 黄灯原因：历史252日相对现金收益曾偏弱
  - 相对78-1最大回撤改善：`12.1196pp`
  - 相对78-1 Ulcer改善：`34.94%`
  - 相对现金收益优势：`25.2353pp`
  - 相对现金最大回撤差：`0.5755pp`
  - 最新252日相对现金收益：`-0.0375pp`
  - 历史最差252日相对现金收益：`-7.6039pp`
  - 504日最差滚动收益：`28.5960%`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_report_stage377_stage075_combo_forward_paper_monitor_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_summary_stage377_stage075_combo_forward_paper_monitor_v1.csv`
- orders：无
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_daily_monitor_stage377_stage075_combo_forward_paper_monitor_v1.csv`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_thresholds_stage377_stage075_combo_forward_paper_monitor_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_decision_stage377_stage075_combo_forward_paper_monitor_v1.json`
- html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage377_stage075_combo_forward_paper_monitor_dashboard_stage377_stage075_combo_forward_paper_monitor_v1.html`

## 结论

- 本阶段结论：Stage075/076 组合层候选历史上仍满足最大回撤30以内、显著优于78-1平滑度，并略优于30万现金对照；但因历史252日相对现金收益曾弱到 `-7.6039pp`，监控状态为黄灯，不能声明目标已完成或候选可直接实盘。
- 是否进入下一步：是，进入组合层 forward paper。
- 下一步：
  - 每个新交易日更新期货和股票 paper 数据后复跑本脚本。
  - 若连续 paper 仍为绿灯，再接真实双账户持仓/成交对账。
  - 若黄灯，先做只读归因，不调整股票权重或参数救窗口。
  - 若红灯，候选降级，继续寻找真正独立收益源或费用敏感度更低的承载工具。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只把已有候选变成复跑监控，不调策略阈值、股票权重、品种池或历史窗口。若后续黄灯/红灯后调权重救结果，才会转为过拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：该候选已经满足历史回撤和平滑度目标的一部分，forward paper 是验证能否进入真实部署评估的必要步骤；但黄灯说明仍需要观察，而不是直接晋级。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage077 paper 监控入口与黄灯状态。
- 是否更新 `research/registry.md`：是，最新阶段更新为 Stage077。
- 是否追加根目录 `memory.md/back_log.md`：否。本阶段是监控入口，不是重要突破、路线废弃或正式候选晋级。
