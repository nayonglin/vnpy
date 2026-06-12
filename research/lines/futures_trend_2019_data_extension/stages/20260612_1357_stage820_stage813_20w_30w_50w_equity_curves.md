# Stage820 Stage813 20w/30w/50w年度多起点资金曲线对比

- line_id：`futures_trend_2019_data_extension`
- 当前模式：`day`
- 记录时间：2026-06-12 13:57
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：可视化对比
- 是否重要突破：否
- 是否触发A/B：否；沿用既有 Stage813 50w、Stage819 30w、Stage817 20w 曲线，不新增策略版本

## 外部调研与判断

- 参考资料：
  - vn.py 官方 GitHub README：`https://github.com/vnpy/vnpy/blob/master/README_ENG.md`，组合策略模块支持多合约策略历史回测和自动交易。
  - `vnpy_portfoliostrategy` PyPI：`https://pypi.org/project/vnpy_portfoliostrategy/`，组合策略模块支持多合约组合回测、参数优化和实盘。
- 我的判断：
  - 多起点曲线对比的价值在于观察路径一致性、回撤段和资金口径差异，不应用来反推新阈值。
  - 归一化图比绝对权益图更适合比较资金效率；绝对权益图更适合观察不同本金口径下的最终账户体量。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage820_stage813_20w_30w_50w_equity_curves.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `MODEL_TAG = stage820_stage813_20w_30w_50w_equity_curves_v1`
  - `SERIES = Stage813 50w / Stage819 30w / Stage817 20w`
- 修改参数：无
- 删除参数：无
- 回测逻辑：无新增回测；只读取既有曲线 CSV 绘图。

## 回测/归因参数

- 数据区间：共享年度起点 `2018-01` 至 `2026-01`，统一使用既有回测曲线数据。
- 账户规模：20w、30w、50w。
- 成本口径：沿用各自既有 Stage813/817/819 回测输出。
- 样本过滤：三份曲线共有的 `start_month` 交集，共 `9` 个年度起点。
- 策略/归因口径：Stage813 逻辑的不同资金口径曲线对比，不改变策略参数。

## 结果

- 新增绝对权益图：蓝色 `Stage813 50w`，绿色 `Stage819 30w`，红色 `Stage817 20w`。
- 新增归一化净值图：三条曲线均以各自起点净值 `1.0` 开始，用于比较资金效率。
- 观察结论：
  - 2018-01 起点中，30w 归一化净值明显高于 50w 和 20w，但绝对/归一化图都能看到中途高波动与深回撤。
  - 2019-01、2020-01 起点中，30w 归一化表现整体强于 50w/20w；50w 绝对权益更大但归一化不总是最优。
  - 2022-01、2023-01 起点中，30w 归一化优势更清晰，说明 20w 的整数手颗粒度确实压制进攻效率。
  - 2024-01、2025-01 起点中，20w 归一化并不弱，说明资金变大不是单调改善；不同年份受可交易手数、保证金和品种路径共同影响。
  - 2026-01 起点仍是短样本亏损段，不能据此做策略调整。

## 输出文件

- absolute：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage820_stage813_20w_30w_50w_equity_curves_absolute_stage820_stage813_20w_30w_50w_equity_curves_v1.png`
- normalized：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage820_stage813_20w_30w_50w_equity_curves_normalized_stage820_stage813_20w_30w_50w_equity_curves_v1.png`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage820_stage813_20w_30w_50w_equity_curves_report_stage820_stage813_20w_30w_50w_equity_curves_v1.md`

## 结论

- 本阶段结论：Stage820 完成三资金口径年度多起点曲线对比。
- 是否进入下一步：可进入风险归因，但不应继续扫本金。
- 下一步：
  - 若继续，优先比较 Stage819 30w 与 Stage372 20w 的同起点风险段，而不是继续画更多本金口径。
  - 对 2018-2020 的权益低谷做品种集中度、保证金峰值和最大亏损交易簇归因。

## 过拟合反思

- 运行前判断：不是过拟合；这只是既有回测曲线的可视化。
- 运行后判断：仍不是过拟合；没有据图修改任何规则。
- 原因：图只能帮助识别路径风险，不能作为新增参数的证据。

## 继续价值反思

- 运行前判断：有价值；三资金口径放在同一张图里可以直接观察 20w、30w、50w 的路径差异。
- 运行后判断：有价值但有限；图已经说明 30w 的进攻效率强，但深回撤仍存在。
- 原因：继续价值应转向风险归因和当前实盘默认 Stage372 的公平对照，而不是继续做资本曲线排列组合。

## 合入建议

- 是否更新本线 `LINE.md`：否。
- 是否更新 `research/registry.md`：否。
- 是否追加根目录 `memory.md/back_log.md`：否；本阶段是可视化，不是重要候选变更。
