# Stage000 L1 Top-of-Book 外部假设与边界审计

- line_id：`futures_trend_l1_topbook_entry_quality`
- 当前模式：`day`
- 记录时间：`2026-07-13 01:02 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：外部/GitHub调研、既有数据合同去重、新线注册
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：Stoikov micro-price、Cont/Kukanov/Stoikov OFI、queue imbalance、hftbacktest、TqSdk官方tick API。
- 我的判断：L1 bid/ask price+size 可以作为短时入场 adverse-selection 信息，但不能重建 queue/cancel 或深度滑点。Stage044 拒绝的是用 bars/research artifacts 假装 MBP10/MBO；本线另行验证真实 vendor futures tick 的 level1，不绕过 MBP10 合同，也不声称替代它。
- GitHub判断：`sstoikov/microprice` 与 `nkaz001/hftbacktest` 可参考字段计算和审计边界；不直接复制做策略。先验证本地凭据、历史端点、真实合约和事件窗口覆盖。

## 本次变更

- 新增脚本：无。
- 修改脚本：无。
- 删除脚本：无。
- 新增参数：无正式参数，只冻结 canary 与数据门。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：计划覆盖机械12事件的6分钟开盘窗口。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：按交易所×夜盘分层的最早/最晚事件，不读取结果。
- 策略/归因口径：只做L1数据可读性，不计算markout或策略PnL。

## 结果

- 期末权益/收益/回撤/Sharpe/滑点/胜率：均不适用。
- 总交易次数：`0`。
- 本地证据：Stage133 raw option tick 已观察到 level1-5 原始列；本地 `tqsdk=3.9.4` 且 `get_tick_data_series` 存在。

## 结论

- 本阶段结论：注册独立L1路线，只允许12条数据canary。
- 是否进入下一步：是，进入Stage001预声明与实现。
- 下一步：12/12硬门，不救参。

## 过拟合反思

- 运行前判断：否；只验证数据可读性，分层与窗口事前固定。
- 运行后判断：尚未请求数据或读取收益，不构成结果后过拟合。
- 原因：不按2022亏损、方向或产品选事件。

## 继续价值反思

- 运行前判断：有但有限；只有数据全覆盖才值得继续。
- 运行后判断：值得一次固定canary，不代表值得回测。
- 原因：信息源结构新，但作用尺度与组合回撤目标存在距离。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否；尚无结果。
