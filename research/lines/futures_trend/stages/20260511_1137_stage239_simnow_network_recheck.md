# Stage239 SimNow 网络与只读连通性复核

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-11 11:37 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：部署前通道门禁复核
- 是否重要突破：部分是；网络层恢复，但账户层未打通
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SimNow 新前置仍以 `182.254.243.31` 为核心：
    - `7x24`：`40001/40011`
    - 第一套环境：`30001/30011`、`30002/30012`、`30003/30013`
- 我的判断：
  - 当前问题已经不再是“整个 SimNow 网络都不通”。
  - 新状态更接近“交易时段前置 TCP 可达，但账户/登录回报仍未完成”。
  - 因此现在不能直接说“已经能接入 SimNow 模拟资金”，但可以说“网络门已经开了一半”。

## 本次尝试

- 运行网络探针：`examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
- 运行 dry-run：`bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh`
- 运行只读连接：
  - `SIMNOW_FRONT=trading bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 60`
  - `SIMNOW_FRONT=trading2 bash examples/portfolio_backtesting/run_ctp_stage177_simnow_readonly_probe.sh --connect --wait-seconds 60`

## 结果

- 网络TCP探针：
  - `7x24`：`40001/40011` 均 `Connection refused`
  - `trading`：`30001/30011` 可达
  - `trading2`：`30002/30012` 可达
  - `trading_mobile`：`30003/30013` 可达
- `vnpy_ctp`：
  - 导入正常
  - `CtpGateway` 导入正常
- 本地凭证：
  - 私有本机配置存在
  - 必需字段齐全
  - 本阶段未输出敏感信息
- 只读连接：
  - `trading` 与 `trading2` 都能进入 `连接登录 -> CTP`
  - 60 秒内未收到账户、持仓、合约、委托、成交或明确错误回报
  - 当前日志 CSV 仅有一条：`连接登录 -> CTP`

## 结论

- 当前不是“网络全断”。
- `trading / trading2 / trading_mobile` 三组交易时段前置已经恢复 TCP 可达。
- 但当前仍不能确认 SimNow 模拟资金已成功接入，因为还没有拿到账户回报或明确的登录成功/失败事件。
- 因此本阶段结论是：
  - **网络层：基本恢复**
  - **账户层：未打通**

## 注意事项

- 本次输出仍出现 `_encode:25: command not found: -e`，更像本机 shell 环境噪声，不像 CTP 登录失败根因。
- 本阶段未发单，`real_order_enabled=false`，`order_api_called=false`。

## 输出文件

- 网络探针 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_summary_stage179_simnow_network_probe_v1.json`
- 网络探针 report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
- 只读探针 summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_summary_stage174_ctp_vnpy_readonly_probe_v1.json`
- 只读探针 logs：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage174_ctp_vnpy_readonly_probe_logs_stage174_ctp_vnpy_readonly_probe_v1.csv`

## 过拟合反思

- 运行前判断：否。CTP/SimNow 连通性与策略参数无关。
- 运行后判断：否。本阶段只验证部署通道，不涉及策略调参。

## 继续价值反思

- 运行前判断：有价值。若能接入 SimNow 模拟资金，就能把部署日报从回放权益推进到账户实值。
- 运行后判断：仍有价值。当前已经确认可继续排查账户层，而不是继续怀疑网络层。

## 下一步建议

1. 在日盘连续交易时段和夜盘开盘后各重试一次 `trading` / `trading2`。
2. 增加更细的 CTP 事件抓取，确认登录失败是否未被当前 `EVENT_LOG` 捕获。
3. 若仍无回报，重点核对 SimNow 账号是否已激活、是否已改密、是否属于当前第一套环境。
