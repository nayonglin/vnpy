# Stage176 Mac原生CTP路线验证

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-08 16:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：Mac原生CTP执行环境验证，不是策略版本
- 是否重要突破：是，修正Stage175“Mac不作为CTP连接机”的初步判断
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - vn.py CTP接口文档：CTP支持期货/期货期权，连接字段包括用户名、密码、经纪商代码、交易服务器、行情服务器、产品名称、授权编码：https://www.vnpy.com/docs/cn/community/info/gateway.html
  - SimNow产品与服务：BrokerID统一`9999`，默认AppID为`simnow_client_test`，认证码为16个`0`，提供多组CTP前置：https://www.simnow.com.cn/product.action
- 我的判断：用户明确希望最终在Mac上跑实盘后，应优先打通Mac原生路线。最新版`vnpy_ctp==6.7.11.4`在当前Mac arm64编译失败，但旧版`6.7.2.1`可以编译安装；通过补齐framework二进制和ad-hoc签名后，`CtpGateway`可导入。因此Mac路线继续推进。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/build_qmt_roll_stage176_ctp_mac_native_route_pack.py`
  - `examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh`
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage174_readonly_probe.py`：增加`CtpGateway`深度导入诊断。
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：影子边界`300,000`，本阶段不连接账户
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：只验证Mac CTP运行环境，不改Stage78

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - `vnpy_ctp==6.7.2.1`在当前`macOS arm64 + Python 3.11`成功编译安装。
  - 包内`libthostmduserapi_se.a`和`libthosttraderapi_se.a`实际为Mach-O universal动态库。
  - 已复制到framework期望位置并执行`codesign --force --sign -`。
  - 通过`DYLD_FRAMEWORK_PATH` wrapper启动后，`CtpGateway`导入成功，`default_name=CTP`。
  - Stage174只读探针dry-run输出：`vnpy_ctp_import_available=true`、`ctp_gateway_import_available=true`、`real_order_enabled=false`、`order_api_called=false`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage176_ctp_mac_native_route_report_stage176_ctp_mac_native_route_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage176_ctp_mac_native_route_summary_stage176_ctp_mac_native_route_v1.json`
- orders：不适用
- daily：不适用
- quality：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage176_ctp_mac_native_route_runbook_stage176_ctp_mac_native_route_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage176_ctp_mac_native_route_checklist_stage176_ctp_mac_native_route_v1.csv`

## 结论

- 本阶段结论：Mac原生CTP路线继续推进，当前已过安装/导入关；下一关是配置SimNow或期货公司CTP环境变量并运行只读连接探针。
- 是否进入下一步：是
- 下一步：用户准备CTP仿真或实盘只读凭证；使用`bash examples/portfolio_backtesting/run_ctp_stage176_mac_readonly_probe.sh --connect --wait-seconds 30`连接，只监听账户、持仓、合约、委托、成交事件。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：依赖版本和动态库加载修复不改变策略参数、不影响回测收益。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：用户目标是Mac实盘；当前已从“安装失败”推进到“可导入、待连接”，继续价值明确。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新，等CTP只读连接成功后再更新
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：建议后续CTP只读连接成功后再追加
