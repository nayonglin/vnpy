# Stage252 SimNow 前置与账号环境审计

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：`2026-05-12 16:42`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：SimNow 登录失败后的无下单、无密码暴露环境审计
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：
  - SimNow 官方产品页：`https://www.simnow.com.cn/product.action`
  - vn.py/VeighNa 社区关于 SimNow `CTP:不合法的登录` 的讨论
  - 本地 Stage179/251 输出
- 我的判断：
  - SimNow 官方说明里，7x24/第二套环境与第一套交易环境存在服务时间和生效节奏差异；新注册或改密后的账号不一定立即在第二套/7x24环境可用。
  - `CTP:不合法的登录` 更像账号、密码、前置环境、生效状态不匹配，而不是策略代码问题。
  - 当前不应继续反复尝试登录，避免触发连续登录失败限制。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `examples/portfolio_backtesting/run_ctp_stage179_simnow_network_probe.py`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无
- 代码修正：
  - Stage179 网络探针补充 `180.168.146.187:10130/10131`、`10201/10211`、`10202/10212` 等历史/官方文档前置。
  - 本阶段未打印任何密码、AuthCode 明文。

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
  - 本地 `ctp_simnow.local.env` 已配置：
    - `CTP_USERID`：已配置，长度 6，未泄露明文
    - `CTP_PASSWORD`：已配置，长度 12，未泄露明文
    - `CTP_BROKERID`：已配置，长度 4
    - `CTP_APPID`：已配置，长度 18
    - `CTP_AUTH_CODE`：已配置，长度 16
    - `SIMNOW_FRONT=7x24`
    - `CTP_TD_ADDRESS/CTP_MD_ADDRESS` 留空，由脚本 profile 决定
  - 扩展网络探针：
    - `7x24_182`：`40001/40011` 可达
    - `trading/trading2/trading_mobile`：`30001/30011/30002/30012/30003/30013` 均 `Connection refused`
    - `7x24_180`：`10130/10131` 超时
    - `first_180_group1/group2`：`10201/10211/10202/10212` 超时
  - 最新 Stage251 仍为：`fresh_pre_submit_gate_blocked`
  - 真实 submit/send_order 调用次数：`0`

## 输出文件

- report：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_report_stage179_simnow_network_probe_v1.md`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_report_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.md`
- summary：
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage179_simnow_network_probe_summary_stage179_simnow_network_probe_v1.json`
  - `examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage251_phaseb_fresh_pre_submit_gate_summary_20260430_stage251_phaseb_fresh_pre_submit_gate_v1.json`
- orders：不适用
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：当前 Mac 到 SimNow 只有 `7x24_182` 网络可达；但该环境返回 `CTP:不合法的登录`，更像账号/密码/7x24生效状态问题。第一套交易前置当前网络不可用。
- 是否进入下一步：是，但需要用户侧配合确认 SimNow 账号环境。
- 下一步：
  1. 用户登录 SimNow 官网确认资金账号是否就是 `CTP_USERID` 使用的纯数字账号。
  2. 确认 7x24/第二套环境是否已开通并生效；如果刚改密，等待到下一个或第三个交易日再试。
  3. 避免连续多次错误登录；等确认后再重跑 Stage251。

## 过拟合反思

- 运行前判断：否。SimNow 前置审计不改策略、参数或回测结果。
- 运行后判断：否。本阶段只定位连接/账号环境问题。
- 原因：这是实盘执行环境验证，不会优化历史收益。

## 继续价值反思

- 运行前判断：是。没有稳定可登录的 SimNow 前置，真实 submit adapter 没有测试对象。
- 运行后判断：是，但下一步需要用户确认账户环境，不能靠代码猜密码或账号生效状态。
- 原因：当前阻塞已经从工程代码收敛到 SimNow 账户/前置匹配。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否，等 SimNow Stage251 通过后再写重要合入摘要
