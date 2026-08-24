# Stage022 Q正式晋升与生产激活

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`late_night`
- 记录时间：2026-08-25 01:15（Asia/Shanghai）
- 工作区/分支：`vnpy-q-promotion.i6m1vu` / `codex/promote-q-official-20260824`
- 阶段性质：用户明确 operator override 下的正式物料发布、资格证明与生产激活
- 是否重要突破：是，Q 已成为当前正式生产版本
- 是否触发A/B：否，本阶段不生成新回测，只晋升已冻结 Q

## 外部调研与判断

- 参考资料：本阶段不新增策略研究；按仓库 `futures-live-execution-sop`、正式物料冻结合同和 Stage948 生产安装门执行。
- 我的判断：用户明确授权可以决定采用 Q，但不能替代代码、物料、只读账户、独立评审和订单零调用证据；因此保留历史门失败事实，并以 fail-closed 方式安装。

## 本次变更

- 新增脚本：无。
- 修改脚本：正式配置固定 Q；资格构建器补齐 active material critical-files 绑定。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：正式 ruleset 切换为 `stage021_q_rollover_volume_atr_v1`，精确复用 Q 20 项参数。
- 删除参数：无；明确未带入 R 的低量 `0.8` 或 S 的高量 `2.0`。

## 回测/归因参数

- 数据区间：沿用 Stage021 冻结结果 `2018-01-01 -> 2026-05-29`。
- 账户规模：C9/15万。
- 成本口径：沿用 Stage021。
- 样本过滤：本阶段无新回测。
- 策略/归因口径：Q = N 的多空量能风险缩放 + 多空对称 1×前置 ATR5 逆向冲击禁开 + 正式换月续开。

## 结果

- 期末权益：`15,135,800.10`（沿用冻结 Q，无新增回测）
- 总收益：`9990.5334%`
- 最大回撤：`-44.9033%`
- Sharpe：`1.495411`
- 总滑点：`1,571,580`
- 总交易次数：`821`
- 胜率：`52.8467%`
- 其他关键指标：broker10 峰值 `99.6724%`；正式物料 148 文件；生产资格 296 关键文件、35 套/880 测试、2 次只读 CTP；独立评审 `0/0/0`；全部订单 API `0`。

## 输出文件

- report：私有 `production-live/qualification-bundle/qualification.json`
- summary：私有 `production-live/activation/latest.json`
- orders：无新增订单，API `send/cancel/order=0/0/0`
- daily：当前 `production_daily_data_receipt_invalid`，保持 fail closed
- quality：evidence `87ec367f5fee427eaf333c07fa15caf946003a4eaa4e202e3b333a5594da9ebe`

## 结论

- 本阶段结论：Q 已保存为 m0009 正式物料并快进发布到远端 master，生产稳定目录已安装并激活 7/7 launchd。
- 是否进入下一步：进入自然 forward 实盘观察，不再历史扫参。
- 下一步：由既有日更数据回执和时段闸在正常调度中恢复可交易状态；禁止人工伪造回执或绕过授权门。

## 过拟合反思

- 运行前判断：是，Q 的历史选择风险较高。
- 运行后判断：晋升动作本身否；策略选择风险仍是。
- 原因：本阶段不调参、不回测，但 Q 来自连续后验迭代，且原 A 侧 broker 门失败；只能用未来真实样本检验穿越性。

## 继续价值反思

- 运行前判断：是，正式保存与可恢复生产安装有直接价值。
- 运行后判断：是，forward 观察有价值；继续历史阈值优化无价值。
- 原因：发布链已逐文件绑定代码与物料，剩余信息只能来自新增自然事件。

## 合入建议

- 是否更新本线 `LINE.md`：是，已更新。
- 是否更新 `research/registry.md`：否，line_id 未变化。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md`，不改 `memory.md`。
