# Stage173 前向主力合约数据补齐

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 15:30 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：前向影子盘数据链修复，不是策略版本
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - PyPI `vnpy_tqsdk` 项目说明：https://pypi.org/project/vnpy-tqsdk/
  - vn.py GitHub 组织说明：https://github.com/vnpy
- 我的判断：本仓库 Stage78 的回测入口不是直接消费连续产品线，而是通过 `main_contract_mapping.py` 映射到真实主力合约后读取合约K线。因此只补连续线不够，必须同时补主力映射和真实主力合约日线。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage173_forward_main_contract_data_update.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--mapping-start`、`--bar-start`、`--end`、`--dry-run`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：主力映射`2026-05-01`到`2026-05-07`；合约K线`2026-04-22`到`2026-05-07`
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：官方 Stage78 宇宙，19个产品
- 策略/归因口径：只补主力映射和真实合约日线，不运行策略

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：新增/替换映射行38行；主力映射最大日期`2026-05-07`；涉及20个主力合约，成功20，失败0，空数据0，最大保存日期`2026-05-07`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_report_stage173_forward_main_contract_data_update_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_summary_stage173_forward_main_contract_data_update_v1.json`
- orders：不适用
- daily：真实主力合约日线已写入 vn.py 数据库
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage173_forward_main_contract_data_update_contract_bar_status_stage173_forward_main_contract_data_update_v1.csv`

## 结论

- 本阶段结论：Stage78 前向回测的数据链已经从“连续产品线”补齐到“主力映射 + 主力合约K线”。
- 是否进入下一步：是
- 下一步：重跑 Stage172，生成 `2026-05-07` 冻结Stage78前向影子盘日报。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：补数扩大可观测前向区间，不改变信号、参数、品种筛选或风控规则。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：Stage172 首次失败暴露真实断点在主力合约数据链；补齐后才能判断策略在最新交易日的理论状态。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加
