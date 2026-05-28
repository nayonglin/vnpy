# Stage293 官方采集库 41407 只读登录成功

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-28 11:21 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：CTP/券商测试通路只读验证
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：券商提供的 `sfit_tst_1.0_20250325_7643_MacOS` 官方测试版采集库、本仓库 Stage78-1 CTP/SimNow SOP、Stage292 未连通记录。
- 我的判断：开盘时段券商前置恢复可达；官方 `MacDataCollect.framework` 生成的 `CTP_GetSystemInfoUnAesEncode` 结果可被 41407 扩展登录链路接受。本阶段只证明只读登录/账户/持仓查询链路可用，不等于可以直接上正常策略手数。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：不适用。
- 账户规模：不适用；本阶段未运行策略、未下单。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：Stage78-1 执行通路只读验证；不涉及 alpha。

## 结果

- 端口探测：
  - `182.140.218.46:41407` 连接成功。
  - `182.140.218.46:41415` 连接成功。
  - `182.140.218.46:41207` 连接成功。
  - `182.140.218.46:41215` 连接成功。
- 原生 C++ 41407 TD-only 只读验证：
  - API 版本：`v6.7.7_MacOS_CP_20240716 15:00:00`。
  - `CTP_SYSTEM_INFO_SOURCE=collector_api:_Z28CTP_GetSystemInfoUnAesEncodePcRi`。
  - `CTP_CLIENT_SYSTEM_INFO=set(len=264)`。
  - `CTP_NATIVE_REGISTER_USER_SYSTEM_INFO=0`，`CTP_NATIVE_SUBMIT_USER_SYSTEM_INFO=0`，符合直连投资者路径。
  - `OnFrontConnected` 成功。
  - `ReqAuthenticate ret=0`，`OnRspAuthenticate ErrorID=0`。
  - `ReqUserLogin system_info_len=264 ret=0`，`OnRspUserLogin ErrorID=0`。
  - session 字段：`FrontID=15`，`SessionID=-1264121675`，`TradingDay=20260528`，`LoginTime=11:21:12`。
  - `ReqSettlementInfoConfirm ret=0`，`OnRspSettlementInfoConfirm ErrorID=0`。
  - 账户快照：`account_count=1`。
  - 持仓快照：`position_count=2`。
  - summary：`front_connected=true auth_ok=true login_ok=true settlement_ok=true account_count=1 position_count=2`。
- 委托 API：未调用。
- 撤单 API：未调用。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：`0`
- 胜率：不适用。

## 输出文件

- report：无独立文件，控制台只读输出已在本阶段记录中摘要。
- summary：无独立文件。
- orders：无，未下单。
- daily：无。
- quality：无。

## 结论

- 本阶段结论：官方 Mac 采集库 + CP Mac SDK + 41407 原生 C++ TD-only 只读链路已打通，且使用的是官方采集函数输出的 `264` 字节 systemInfo。
- 是否进入下一步：是，但继续 fail-closed。
- 下一步：
  1. 将 `FrontID=15 / SessionID=-1264121675 / TradingDay=20260528 / LoginTime=11:21:12` 发给券商，让其后台确认穿透监管采集上报是否生效。
  2. 等券商确认上报有效后，再讨论 1 手 smoke order；未确认前不恢复报单测试。
  3. 若后续要接策略执行，仍需按 Stage78-1 SOP 走 fresh snapshot、dry-run、1 手、显式确认、对账闭环。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本阶段验证的是官方采集库、CTP 前置连通性和只读登录链路，不涉及策略参数或历史样本拟合。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：本阶段把 Stage292 的端口不可达阻塞推进到 41407 只读登录成功，是实盘前执行链路的必要前置证据。

## 合入建议

- 是否更新本线 `LINE.md`：建议后续合入时更新 41407 状态为“官方采集库只读登录成功，待券商后台确认穿透上报”。
- 是否更新 `research/registry.md`：暂不更新，避免并行研究线冲突。
- 是否追加根目录 `memory.md/back_log.md`：建议合入者追加摘要；本阶段先保留线内记录。
