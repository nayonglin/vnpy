# Stage174 CTP/vn.py实盘路线可行性包

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 16:01 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：实盘接口路线与只读对账包，不是策略版本
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py README：CTP支持国内期货和期权，交易接口覆盖国内外品种：https://github.com/vnpy/vnpy/blob/master/README_ENG.md
  - `vnpy_ctp` PyPI：CTP gateway for vn.py，基于CTP期货版接口封装：https://pypi.org/project/vnpy-ctp/
  - vn.py交易接口文档：CTP支持期货、期货期权，字段包括用户名、密码、经纪商代码、交易服务器、行情服务器、产品名称、授权编码：https://www.vnpy.com/docs/cn/community/info/gateway.html
- 我的判断：第78是国内商品期货策略，主执行路线应优先选 CTP/vn.py，而不是 QMT。QMT可保留为Windows环境下的备选只读对账或股票侧工具；CTP/vn.py更贴近期货账户、持仓、委托、成交和夜盘交易日语义。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage174_ctp_vnpy_route_pack.py`
  - `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `run_ctp_stage174_readonly_probe.py --connect`
  - `run_ctp_stage174_readonly_probe.py --wait-seconds`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：沿用Stage172目标日`2026-05-07`
- 账户规模：影子边界`300,000`，本阶段不连接真实账户
- 成本口径：不适用
- 样本过滤：Stage172目标日信号
- 策略/归因口径：`official_stage78_defensive_v1`，只做接口路线与字段映射

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 当前环境：`vnpy=True`、`vnpy_ctp=False`、`vnpy_ctastrategy=True`、`vnpy_portfoliostrategy=True`
  - Stage172快照：目标日`2026-05-07`，信号1条，风险级别`stop`，允许真实新增开仓`0`
  - 只读探针dry-run状态：`dry_run_not_connected`
  - 真实下单：`real_order_enabled=false`，`order_api_called=false`

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_route_report_stage174_ctp_vnpy_route_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_route_summary_stage174_ctp_vnpy_route_v1.json`
- orders：不适用；只生成`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_route_signal_contract_check_stage174_ctp_vnpy_route_v1.csv`
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_route_ctp_field_map_stage174_ctp_vnpy_route_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`

## 结论

- 本阶段结论：CTP/vn.py路线应作为第78国内期货实盘主路线推进；当前本机缺`vnpy_ctp`和CTP环境变量，只能完成只读接入包与dry-run探针。
- 是否进入下一步：是
- 下一步：安装/配置`vnpy_ctp`，使用仿真或实盘只读环境变量运行 `run_ctp_stage174_readonly_probe.py --connect --wait-seconds 30`，先拿到账户、持仓、合约、委托、成交空表/实表。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：接口路线、字段映射和只读探针不改变策略参数，也不根据收益结果筛选规则。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：第78当前瓶颈是实盘执行闭环；CTP只读探针是进入影子盘真实对账前的必要关口。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等CTP只读探针真实连通后再更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加
