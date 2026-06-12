# Stage818 Stage813 20w vs 50w 资金曲线对比图

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-12 13:38 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：只读可视化
- 是否重要突破：否
- 是否触发A/B：否，本阶段不新增回测，只画 Stage813 50w 与 Stage817 20w 已落盘曲线

## 外部调研与判断

- 参考资料：本阶段不新增外部策略调研；沿用 Stage817 对 VeighNa/vn.py 组合回测模块的资料判断。
- 我的判断：图形只是帮助比较 20w 与 50w 的资金路径，不能作为新增策略证据；归一化图比绝对权益图更适合看资本效率和路径形状。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage818_stage813_20w_50w_equity_curves.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG=stage818_stage813_20w_50w_equity_curves_v1`
  - 输入 20w curves：`qmt_roll_stage817_stage813_20w_yearly_curves_stage817_stage813_20w_yearly_v1.csv`
  - 输入 50w curves：`qmt_roll_stage813_stage804_rsi_partial_exit_ablation_yearly_on_curves_stage813_stage804_rsi_partial_exit_ablation_yearly_v1.csv`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用 Stage813/Stage817 年度起点曲线，`2018-01` 至 `2026-01`，统一终点 `2026-05-29`
- 账户规模：20w 与 50w
- 成本口径：沿用已落盘 curves
- 样本过滤：年度起点 9 个
- 策略/归因口径：只读绘图，不重跑策略

## 结果

- 绝对值资金曲线图：蓝线 `Stage813 50w`，红线 `Stage813 20w`，纵轴为权益万元。
- 归一化资金曲线图：蓝线 `Stage813 50w`，红线 `Stage813 20w`，纵轴为初始权益归一化 NAV。
- 可视化判断：
  - 绝对值图直观看到 50w 绝对权益规模始终明显更高。
  - 归一化图显示 2018-2020 起点 20w 资本效率明显弱于 50w；2021-2024 起点 20w 局部阶段反而更强，和 Stage817 聚合结果一致。
  - 2025/2026 短样本两者形态接近，不足以证明 20w 更优。

## 输出文件

- absolute：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage818_stage813_20w_50w_equity_curves_absolute_stage818_stage813_20w_50w_equity_curves_v1.png`
- normalized：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage818_stage813_20w_50w_equity_curves_normalized_stage818_stage813_20w_50w_equity_curves_v1.png`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage818_stage813_20w_50w_equity_curves_report_stage818_stage813_20w_50w_equity_curves_v1.md`
- summary：无新增
- orders：无
- daily：无新增，读取 Stage813/Stage817 curves
- quality：无

## 结论

- 本阶段结论：Stage818 图谱已生成，可用于观察 20w/50w 路径差异。
- 是否进入下一步：否，单独画图不改变 Stage817 结论。
- 下一步：若继续，应做 Stage813 20w vs 当前 Stage372 20w 的同起点归一化曲线和回撤曲线，而不是继续只比较 Stage813 自身的本金版本。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段只读既有曲线，不改策略、不筛样本、不用图形反推规则。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值但边界有限。
- 原因：图能帮助直观看路径差异，但不能替代成本压力和同口径基准对照。

## 合入建议

- 是否更新本线 `LINE.md`：否。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否。
