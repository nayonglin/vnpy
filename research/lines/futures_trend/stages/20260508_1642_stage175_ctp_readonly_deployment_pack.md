# Stage175 CTP实盘只读环境部署包

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 16:42 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：CTP只读环境部署包，不是策略版本
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py CTP接口文档：CTP支持Windows、Ubuntu，支持期货/期货期权，只支持双向持仓，不提供历史数据；连接字段包括用户名、密码、经纪商代码、交易服务器、行情服务器、产品名称、授权编码：https://www.vnpy.com/docs/cn/community/info/gateway.html
  - SimNow产品与服务：BrokerID统一`9999`，默认AppID为`simnow_client_test`，认证码为16个`0`，提供多组交易/行情前置：https://www.simnow.com.cn/product.action
  - `vnpy_ctp` PyPI版本索引：当前最新`6.7.11.4`，历史版本从`6.5.1.0`到`6.7.11.4`。
- 我的判断：第78国内期货执行应继续优先CTP/vn.py，但当前Mac arm64不适合做CTP连接机；应准备Windows或Ubuntu环境，先跑SimNow或期货公司仿真。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/build_qmt_roll_stage175_ctp_readonly_deployment_pack.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：影子边界`300,000`，本阶段不连接真实账户
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：只做CTP部署环境和凭证清单，不改Stage78

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 当前Mac环境：`vnpy=True`、`vnpy_ctp=False`
  - 安装尝试：`.py311/bin/python -m pip install vnpy_ctp`
  - 尝试版本：`6.7.11.4`
  - 结果：`failed_on_macos_arm64_source_build`
  - 主要原因：源码编译中出现 `CThostFtdcInvestorInfoCommRecField`、`CThostFtdcCombLegField`、`CThostFtdcInputOffsetSettingField` 等类型未定义。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_report_stage175_ctp_readonly_deployment_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_summary_stage175_ctp_readonly_deployment_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_checklist_stage175_ctp_readonly_deployment_v1.csv`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_env_examples_stage175_ctp_readonly_deployment_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_broker_request_template_stage175_ctp_readonly_deployment_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage175_ctp_readonly_deployment_bootstrap_commands_stage175_ctp_readonly_deployment_v1.md`

## 结论

- 本阶段结论：当前Mac不继续作为CTP实盘/仿真连接机；准备Windows或Ubuntu环境，优先SimNow或期货公司仿真，再跑Stage174只读探针。
- 是否进入下一步：是
- 下一步：用户准备CTP仿真/实盘只读所需信息和Windows/Ubuntu机器；我在该环境运行安装、环境变量检查和只读探针。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：部署环境验证不改变策略参数，不根据收益结果做选择。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：Stage78要进入真实影子盘，必须先解决CTP账户/持仓/成交只读对账环境。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等CTP只读探针在Windows/Ubuntu真实连通后再更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：暂不追加
