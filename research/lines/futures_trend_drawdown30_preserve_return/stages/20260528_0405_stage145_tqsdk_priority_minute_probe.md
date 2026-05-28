# Stage145 TqSdk高优先级分钟线采样探针

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：day
- 记录时间：2026-05-28 04:05 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：执行数据采样探针；不新增策略、不修改交易规则
- 是否重要突破：否；重要阻断识别
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：TqSdk 官方 `DataDownloader` 文档说明该工具可按 `dur_sec=60`、起止时间下载分钟K，但属于专业版历史下载功能。
- 我的判断：普通 TqSdk 行情连接可用，但 `DataDownloader` 历史下载权限不足；这不能解释为分钟线不存在，也不能作为策略失败证据。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage445_tqsdk_priority_minute_probe.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：`STAGE445_MAX_SYMBOLS=5`、`STAGE445_PER_SYMBOL_TIMEOUT_SECONDS=90`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：Stage144 高优先级目标窗口中的前5个合约范围
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：按 Stage144 高优先级排序取前5个合约，仅用于数据探针
- 策略/归因口径：用 TqSdk `DataDownloader(dur_sec=60)` 尝试下载高优先级分钟线

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：输入目标窗口 `60`
- 胜率：不适用
- 其他关键指标：
  - 决策标签：`tqsdk_history_download_permission_blocked`
  - 选中合约数：`5`
  - 成功下载合约数：`0`
  - 失败/超时合约数：`5`
  - TqSdk历史下载权限阻断合约数：`5`
  - 覆盖目标窗口：`0 / 60`
  - 覆盖率：`0.0000%`
  - 阻断原因：账户不支持 TqSdk 历史数据下载功能，需要专业版权限

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage445_tqsdk_priority_minute_probe_report_stage445_tqsdk_priority_minute_probe_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage445_tqsdk_priority_minute_probe_coverage_summary_stage445_tqsdk_priority_minute_probe_v1.csv`
- orders：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage445_tqsdk_priority_minute_probe_priority_window_coverage_stage445_tqsdk_priority_minute_probe_v1.csv`
- daily：不适用
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage445_tqsdk_priority_minute_probe_decision_stage445_tqsdk_priority_minute_probe_v1.json`

## 结论

- 本阶段结论：`DataDownloader` 路径被权限阻断，不能作为 Stage103 执行代理验证来源。
- 是否进入下一步：是。
- 下一步：改用 `TqBacktest + get_kline_serial(60)` 做历史分钟K回放抽取。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：只验证数据通路，不修改策略、不筛日期或品种。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：DataDownloader 被阻断但 TqSdk 仍有回测回放路径，值得继续验证。

## 合入建议

- 是否更新本线 `LINE.md`：是，与 Stage146/147 一并更新。
- 是否更新 `research/registry.md`：是，以 Stage147 最新结论为准。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`。
