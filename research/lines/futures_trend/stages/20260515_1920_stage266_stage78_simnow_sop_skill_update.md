# Stage266 Stage78 SimNow SOP Skill 更新

- line_id：`futures_trend`
- 当前模式：`day`
- 记录时间：2026-05-15 19:20 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：repo-local skill/SOP 更新
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：读取 `skills/futures-live-execution-sop/SKILL.md` 与系统 `skill-creator` 规范。
- 我的判断：本次不是新能力，属于现有 Stage78-1 SimNow SOP 的子流程固化；应更新现有 skill，而不是新建 skill。

## 本次变更

- 新增脚本：无
- 修改脚本：
  - `skills/futures-live-execution-sop/SKILL.md`
  - `skills/futures-live-execution-sop/agents/openai.yaml`
- 删除脚本：无
- 新增参数：无
- 修改参数：无
- 删除参数：无

## 变更内容

- 在 `futures-live-execution-sop` 中新增 `Daily 7x24 Dry-Run Gate` 小节。
- 固化顺序：
  1. Stage173 更新主力映射和日线。
  2. Stage188 跑 50万最新 AI 池影子盘。
  3. Stage177 用 `SIMNOW_FRONT=7x24` 刷新只读账户/持仓快照。
  4. Stage260 做每日执行闸门。
  5. 只有 `simnow_executable` 才能进入 Stage251 fresh pre-submit gate。
- 明确 `review` 禁止新开仓，`confirmed_flat + close signal` 必须跳过。
- 明确 `order_api_called_count` 必须保持 `0`。

## 结果

- 本阶段不跑回测。
- 本阶段不连接 SimNow。
- 本阶段不发单。
- skill 已包含 2026-05-15 Stage265 验证出的关键执行纪律：理论影子持仓不能覆盖 SimNow 真实账户状态。

## 输出文件

- skill：`skills/futures-live-execution-sop/SKILL.md`
- UI metadata：`skills/futures-live-execution-sop/agents/openai.yaml`

## 结论

- 本阶段结论：应更新现有 skill，不新建 skill；7x24 daily dry-run gate 已固化。
- 是否进入下一步：是。
- 下一步：后续用户要求“跑今日虚拟盘/今晚是否交易/SimNow闸门”时，直接按该小节执行。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：这是执行流程固化，不调整策略参数，不根据收益结果选择模型。

## 继续价值反思

- 运行前判断：有价值。
- 运行后判断：有价值。
- 原因：该 skill 更新能降低后续 agent 把理论平仓信号误发到 SimNow 空仓账户的风险。

## 合入建议

- 是否更新本线 `LINE.md`：是。
- 是否更新 `research/registry.md`：是。
- 是否追加根目录 `memory.md/back_log.md`：否。
