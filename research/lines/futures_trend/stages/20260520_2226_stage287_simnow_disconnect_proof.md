# Stage287 普通 SimNow 程序化断网回调证明

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 22:26 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：SimNow 执行链路异常场景证据
- 是否重要突破：否，属于券商验收材料补充
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段遵循 Stage78-1 SimNow SOP；断网场景采用本机 TCP 代理切断连接，不关闭整台 Mac 网络。
- 我的判断：直接拔网线会影响用户机器和当前会话，且不可复现；本机代理在 CTP API 与 SimNow 前置之间转发连接，登录成功后关闭代理 socket，更适合稳定复现“运行中网络断开”的 CTP 回调。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/run_ctp_stage287_simnow_disconnect_proof.py`
  - `examples/portfolio_backtesting/run_ctp_stage287_simnow_disconnect_proof.sh`
  - `examples/portfolio_backtesting/build_ctp_stage287_disconnect_evidence_png.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：
  - `--pre-disconnect-wait-seconds`
  - `--stable-after-login-seconds`
  - `--post-disconnect-wait-seconds`
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及回测
- 账户规模：不涉及策略资金口径；执行环境为普通 SimNow `9999/trading`
- 成本口径：不涉及
- 样本过滤：只读登录与断开回调，不发单
- 策略/归因口径：Stage78-1 执行异常场景 proof，不改变策略逻辑

## 结果

- 期末权益：不涉及
- 总收益：不涉及
- 最大回撤：不涉及
- Sharpe：不涉及
- 总滑点：不涉及
- 总交易次数：不涉及策略交易统计
- 胜率：不涉及
- 其他关键指标：
  - 状态：`disconnect_observed`
  - 远端交易前置：`tcp://182.254.243.31:30001`
  - 远端行情前置：`tcp://182.254.243.31:30011`
  - 本机交易代理：`tcp://127.0.0.1:53350`
  - 本机行情代理：`tcp://127.0.0.1:53351`
  - 行情登录成功：`True`
  - 交易授权成功：`True`
  - 交易登录成功：`True`
  - 结算确认成功：`True`
  - 交易断开回报：`交易服务器连接断开，原因4097`
  - 行情断开回报：`行情服务器连接断开，原因4097`
  - `send_order_api_called_count=0`
  - `cancel_order_api_called_count=0`
  - 委托行数：`0`
  - 成交行数：`0`

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_summary_20260520_221731_stage287_simnow_disconnect_proof_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_report_20260520_221731_stage287_simnow_disconnect_proof_v1.md`
- evidence_html：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_evidence_20260520_221731_stage287_simnow_disconnect_proof_v1.html`
- evidence_png：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_evidence_20260520_221731_stage287_simnow_disconnect_proof_v1.png`
- logs：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_logs_20260520_221731_stage287_simnow_disconnect_proof_v1.csv`
- proxy_events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage287_simnow_disconnect_proof_proxy_events_20260520_221731_stage287_simnow_disconnect_proof_v1.csv`

## 结论

- 本阶段结论：普通 SimNow `9999/trading` 下，程序先完成行情/交易登录、交易授权、结算确认，然后在本机代理断开后收到交易与行情两条断开回调；断网异常场景已形成可截图证据。
- 是否进入下一步：是
- 下一步：可把 Stage285/286/287 三张证据合并发给券商：开仓、平仓、撤单、断网回调。若券商要求必须在 `1010/41407/41415` 评测前置复刻，则等该路线的系统信息上报与报单拒绝原因闭环后再做同类 proof。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：本阶段不是策略收益实验，没有调参数、没有选择收益窗口，只验证执行通路异常回调。

## 继续价值反思

- 运行前判断：有价值
- 运行后判断：有价值
- 原因：实盘系统必须能识别断线并 fail-closed；该证据能说明 CTP/vn.py 层能捕获断开事件，后续 supervisor 才能据此暂停发单、触发告警和重连。

## 合入建议

- 是否更新本线 `LINE.md`：是，补充 Stage287 证据摘要
- 是否更新 `research/registry.md`：是，将最新关键阶段更新到 Stage287
- 是否追加根目录 `memory.md/back_log.md`：否，本阶段是执行异常证据补充，不改变策略正式基准和研究结论
