# Stage171 前向连续行情补数

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 15:29 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：前向影子盘数据补齐，不是策略版本
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - PyPI `vnpy_tqsdk` 项目说明：https://pypi.org/project/vnpy-tqsdk/
  - vn.py GitHub 组织说明：https://github.com/vnpy
- 我的判断：`vnpy_tqsdk` 支持期货K线数据服务，且要求在 vn.py 全局配置中配置 `datafeed.name=tqsdk`、用户名和密码；本仓库已有 TqSdk 配置，所以可以先用它补前向行情。QMT 仍应作为后续只读账户/持仓/成交对账接口，不能把行情补齐等同于实盘接入完成。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage171_forward_market_data_update.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`--start`、`--end`、`--dry-run`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：`2026-04-22` 到 `2026-05-07`
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：`qmt_universe.PRODUCT_SPECS`
- 策略/归因口径：只补连续产品日线，不运行策略

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：18个产品，每个产品返回9根日线；失败0，空数据0，最大补齐日期`2026-05-07`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage171_forward_market_data_update_report_stage171_forward_market_data_update_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage171_forward_market_data_update_summary_stage171_forward_market_data_update_v1.json`
- orders：不适用
- daily：连续产品日线已写入 vn.py 数据库
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage171_forward_market_data_update_status_stage171_forward_market_data_update_v1.csv`

## 结论

- 本阶段结论：连续产品日线已经补到最新目标日，但 Stage78 回测实际依赖主力映射后的真实合约K线，所以这一步只解决了一半数据链。
- 是否进入下一步：是
- 下一步：补主力映射和真实主力合约日线，再重跑冻结Stage78前向日报。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段只补行情，不新增策略参数，不根据收益挑选规则。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：Stage170证明日报卡在前向数据缺口；补数是让影子盘追上真实日期的必要工程。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加
