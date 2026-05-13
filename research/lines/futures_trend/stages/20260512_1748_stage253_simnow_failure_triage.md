# Stage253 SimNow 登录失败根因细分定位

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 17:48`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：SimNow 前置/账号/代码链路根因细分
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SimNow 官方产品页：`https://www.simnow.com.cn/product.action`
  - vn.py 官方仓库：`https://github.com/vnpy/vnpy`
  - vnpy_ctp 官方仓库：`https://github.com/vnpy/vnpy_ctp`
  - 本地 Stage215/247/248/251/252 记录与输出
- 我的判断：
  - 本地 Mac + vn.py + vnpy_ctp wrapper 不是主因，因为历史同一链路已经成功拿到账户、合约和持仓确认。
  - AppID/AuthCode 大概率不是主因，因为最新 7x24 探针已到 `交易服务器授权验证成功`，失败发生在交易登录阶段。
  - 当前第一嫌疑是 `7x24` 账号/密码/环境生效状态不匹配；第一套交易环境账号历史曾成功，但当前网络前置不可达，无法复验。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage253_simnow_failure_triage.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不适用
- 账户规模：不适用
- 成本口径：不适用
- 样本过滤：不适用
- 策略/归因口径：不适用

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - 根因判断：`7x24账号/密码/环境生效状态不匹配；第一套交易前置当前网络不可用，无法作为替代验证`
  - 本地 `vnpy_ctp` 导入链路：基本排除
  - 网络可达性：部分阻塞，仅 `7x24_182` 可达
  - AppID/AuthCode/认证链路：大概率不是主因，因 `td_auth_success=True`
  - 7x24交易账号/密码/环境匹配：当前第一嫌疑
  - 第一套交易环境账号：历史曾成功，当前不可复验
  - 真实 submit/send_order 调用次数：`0`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage253_simnow_failure_triage_report_stage253_simnow_failure_triage_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage253_simnow_failure_triage_summary_stage253_simnow_failure_triage_v1.json`
- orders：不适用
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：当前不应继续盲目重试 7x24 登录，也不应继续写真实 submit。最小下一步是等待第一套交易前置恢复可达后重跑 `SIMNOW_FRONT=trading`，或由用户确认 7x24/第二套环境账号已生效并匹配当前密码。
- 是否进入下一步：是，但需要用户侧确认或等待前置可达。
- 下一步：不泄露密码的前提下，用户去 SimNow 官网确认 `CTP_USERID` 对应资金账号是否已开通 7x24/第二套环境；确认后再重跑 Stage251。

## 过拟合反思

- 运行前判断：否。故障定位只分析执行环境，不改策略。
- 运行后判断：否。本阶段只生成诊断报告，不影响任何回测结果。
- 原因：连接/账号环境和策略参数无关。

## 继续价值反思

- 运行前判断：是。必须定位登录失败，才能安全讨论 SimNow 跑单。
- 运行后判断：是，但下一步不是代码可单独解决，需要账号环境确认。
- 原因：可疑面已经从代码/网络/AppID 收敛到 7x24 账号环境匹配。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，等 Stage251 通过后再写重要合入摘要
