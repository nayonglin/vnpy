# Stage283 41407 AppType 确认为直连投资者

- line_id：`futures_trend`
- 当前模式：day
- 记录时间：2026-05-20 16:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：CTP/SimNow Mac CP SDK 看穿式终端上报模式确认
- 是否重要突破：是
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：用户从券商侧确认 `client_hermanna_1.0` 的 AppType 为“直连投资者”；结合 Stage282 已核对的本地 CP SDK 头文件和 CTP 文档。
- 我的判断：既然 AppType 是直连投资者，正式 414xx/CP 路线不应主动调用 `RegisterUserSystemInfo` 或 `SubmitUserSystemInfo`。这两者是中继模式接口；Stage282 中二者返回 `ret=-6` 与该结论一致。后续应只聚焦扩展版 `ReqUserLogin(..., length, systemInfo)` 的 `systemInfo` 数据格式是否符合券商后台采集要求。

## 本次变更

- 新增脚本：无
- 修改脚本：无
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 回测/归因参数

- 数据区间：不涉及行情回测
- 账户规模：Stage78-1 正式执行口径仍为 `500000`；本阶段只确认 CTP AppType
- 成本口径：不涉及
- 样本过滤：`414xx/CP` 券商测试路线
- 策略/归因口径：不报单、不回测，只确认终端上报接口选择

## 结果

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用
- 其他关键指标：
  - AppType：直连投资者
  - 正式路径：`ReqUserLogin(req, request_id, systemInfoLen, systemInfo)`
  - 不应作为正式路径调用：`RegisterUserSystemInfo`、`SubmitUserSystemInfo`
  - 未闭环事项：`DataCollectforMacOS` 打印出的 `CollectData` 是否可原样作为 `systemInfo`，还是必须使用链接库/头文件获取原始采集字节

## 输出文件

- report：本 stage 文件
- summary：无新增运行输出
- orders：无
- daily：不适用
- quality：不适用

## 结论

- 本阶段结论：`414xx/CP` 的看穿式上报模式已经从“三选一”收敛为“直连投资者登录扩展参数”。后续不再把 `RegisterUserSystemInfo` / `SubmitUserSystemInfo` 作为正常路径；只保留为历史诊断证据。剩余关键问题是 `systemInfo` 的来源和字节格式。
- 是否进入下一步：是
- 下一步：
  1. 向券商确认 `DataCollectforMacOS` 输出的 `CollectData` 是否可原样传入扩展版 `ReqUserLogin`。
  2. 若不可原样传入，请券商提供 Mac 版 `DataCollect.h`/动态库或 C++ demo，使用官方 `CTP_GetSystemInfo` 原始字节接入。
  3. 在终端采集上报被券商后台确认前，`414xx/CP` 不作为正式自动执行 adapter。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是 CTP 接入模式确认，不涉及策略收益、参数、品种池或回测窗口选择。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：AppType 确认后，排除了中继上报路径，后续沟通可以聚焦在直连登录扩展参数和采集数据格式上，减少无效试错。

## 合入建议

- 是否更新本线 `LINE.md`：是
- 是否更新 `research/registry.md`：是
- 是否追加根目录 `memory.md/back_log.md`：暂不追加；这是执行链路线内阶段记录。
