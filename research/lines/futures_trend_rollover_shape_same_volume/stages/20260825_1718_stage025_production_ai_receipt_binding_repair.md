# Stage025 正式 AI 池回执路径绑定修复

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：正式生产故障修复与发布治理加固
- 记录时间：2026-08-25 17:18 CST
- 工作区/分支：`.worktrees/fix-production-ai-receipt-binding` / `codex/fix-production-ai-receipt-binding`
- 阶段性质：正式执行安全修复，不改变 alpha
- 是否重要突破：是；修复会阻断日回执的正式路径身份漂移，并补齐月度 AI 池不可变发布边界
- 是否触发A/B：否；没有策略规则、参数或交易逻辑变化

## 外部调研与判断

- 参考资料：GitHub Artifact Attestations 文档；Python `pathlib.Path.resolve(strict=True)` 文档。
- 我的判断：正式资产必须同时绑定内容哈希和可验证来源身份。只比较相同 SHA256、却允许正式回执引用可变 `backtest_outputs` 路径，会丢失不可变物料 provenance；生产各入口应统一解析 `CURRENT.json` 指向的 payload。

## 本次变更

- 新增脚本：无。
- 修改脚本：Stage945 正式 AI 路径改为活动物料解析结果；Stage947 阻断尚未发布为不可变物料的月更候选；日后处理该精确路径绑定失败时允许同发布身份下单次安全重试；失败邮件保留 `production_signal_*` 精确 blocker。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- Skill：补充 AI 池变化必须新建 material version、资格、晋升、Stage948 安装后才能刷新影子与签回执；补充无订单 `postclose-precompute` 的受控恢复条件。

## 回测/归因参数

- 数据区间：不适用；仅使用 2026-08-25 正式只读影子输入验证回执签发。
- 账户规模：正式 C9/15w，未连接 CTP。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：正式 Q `stage021_q_rollover_volume_atr_v1`，策略字节与参数不变。

## 结果

- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：不适用，未回测。
- 胜率：不适用，未回测。
- 其他关键指标：相关测试 `144 passed, 53 subtests passed`；三个 Skill 均通过 `quick_validate.py`；使用 2026-08-25 正式只读影子绑定的不可变 AI 路径在临时目录成功生成回执，未覆盖生产回执；order/send/cancel API `0/0/0`。

## 输出文件

- report：本 stage 文件。
- summary：测试输出与临时回执验证结果，不保存临时回执实体。
- orders：无，订单 API `0`。
- daily：未生成回测资金曲线。
- quality：路径身份、失败归因、单次重试、月更候选阻断和 Skill 结构校验均通过。

## 结论

- 本阶段结论：16:35 失败根因已在代码与流程层修复；任何后续 AI 池字节变化必须先成为新的不可变正式 release，不能用可变候选直接签生产回执。
- 是否进入下一步：是；完成独立复核和正式物料晋升、远端 master 推送、Stage948 安装，再用受控无订单 postclose 支持任务重建当天回执。
- 下一步：验证远端/生产六身份、7/7 launchd、回执 target 与 AI payload 身份一致，继续保持交易会话 fail-closed 直到回执有效。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：本次只修资产路径、发布状态机和错误可观测性，没有依据历史收益选择规则或参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：故障会让正式日回执持续失败；月更流程若不修会把未激活候选误报为实盘已更新，均是直接生产风险。

## 合入建议

- 是否更新本线 `LINE.md`：是，正式安装完成后更新当前生产身份与 Stage025 结果。
- 是否更新 `research/registry.md`：是，正式安装完成后统一更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：是；生产安全修复和正式物料晋升属于重要合入摘要，待最终闭环后追加。
