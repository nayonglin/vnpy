# Stage215 SimNow CTP只读连通性复核

- line_id：futures_trend
- 当前模式：day
- 记录时间：2026-05-10 12:50
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：准实盘CTP通道连通性复核
- 是否重要突破：否，属于部署前通道门禁
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SimNow官网公告显示2025年后前置切换到 `182.254.243.31`：
    - 7x24：交易 `40001`，行情 `40011`
    - 第一套环境：`30001/30011`、`30002/30012`、`30003/30013`
  - vn.py CTP连接仍需要 `vnpy_ctp`、BrokerID、UserID、Password、交易/行情服务器、AppID、AuthCode。
- 我的判断：
  - 之前仓库Stage177/Stage179仍使用旧前置 `180.168.146.187` 和 `218.202.237.33`，这是本次无法直接连通的主要工程问题。
  - 当前网络和Mac原生 `vnpy_ctp` 路线已经可用，剩余问题是账号登录校验。

## 本次变更

- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh`：默认SimNow前置切换到官网新地址。
  - `examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`：网络探针前置切换到官网新地址。
  - `examples/portfolio_backtesting/ctp_simnow.example.env`：更新前置选择说明。
- 新增脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 运行结果

- 网络TCP探针：
  - 新7x24交易前置 `tcp://182.254.243.31:40001` 可达，耗时约 `52ms`。
  - 新7x24行情前置 `tcp://182.254.243.31:40011` 可达，耗时约 `40ms`。
  - 新第一套环境 `30001/30011`、`30002/30012`、`30003/30013` 在当前时间/网络下超时。
  - 旧前置 `180.168.146.187:*`、`218.202.237.33:*` 当前全部超时。
- `vnpy_ctp`：
  - 直接Python导入未设置 `DYLD_FRAMEWORK_PATH` 会失败。
  - 通过 `run_ctp_stage176_mac_readonly_probe.sh` wrapper 后，`CtpGateway` 导入成功。
- 本地凭证：
  - `ctp_simnow.local.env` 存在。
  - 必需字段均已配置。
  - 未输出密码或完整账号。
- 只读连接：
  - 交易服务器连接成功。
  - 行情服务器连接成功。
  - 行情服务器登录成功。
  - 交易服务器授权验证成功。
  - 交易服务器登录失败：`代码：3，信息：CTP:不合法的登录`。
  - 探针确认 `real_order_enabled=false`，`order_api_called=false`。

## 结论

- 当前不是网络不通，也不是Mac原生 `vnpy_ctp` 不可用。
- SimNow 7x24行情链路已经可以登录。
- 交易链路到授权验证都通过，但最终交易登录被CTP拒绝，错误为“不合法的登录”。
- 下一步应检查SimNow账号/密码/环境是否匹配，而不是修改策略或回测代码。

## 注意事项

- 运行输出出现多行 `_encode:25: command not found: -e`，但不影响CTP连接结果；更像本机shell启动脚本或环境函数噪声。
- 本阶段未发单，探针代码只监听账户、持仓、合约、委托、成交、日志事件。

## 输出文件

- 网络探针报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
- 网络探针CSV：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_fronts_stage179_simnow_network_probe_v1.csv`
- 只读探针summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- 只读探针logs：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_logs_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 过拟合反思

- 运行前判断：否。CTP连通性与策略参数无关。
- 运行后判断：否。本阶段只验证部署通道和只读连接。

## 继续价值反思

- 运行前判断：有价值。影子盘和准实盘必须先过CTP通道门禁。
- 运行后判断：有价值。网络、行情、授权链路已打通，剩余是账号登录问题。
- 下一步：
  - 确认SimNow账号是否属于新7x24环境。
  - 重新核对 `CTP_USERID/CTP_PASSWORD` 是否为SimNow投资者账号密码，而非网页登录或其他环境密码。
  - 若账号确认无误，再尝试第一套环境交易时段的 `30001/30011`。

## 合入建议

- 是否更新本线 `LINE.md`：等交易登录成功后再更新。
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
