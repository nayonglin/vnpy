# Stage023 正式版本晋升 Skill 闭环治理

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：发布治理，不运行策略回测
- 记录时间：2026-08-25 12:10 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy-q-promotion.i6m1vu` / `codex/promote-q-official-20260824`
- 阶段性质：正式晋升流程补漏
- 是否重要突破：是，消除候选物料与正式源码/生产身份分裂
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本阶段是仓库内发布治理，不是 alpha 研究；以现有 publisher、resolver、Stage948 SOP、远端 master 与生产收据为权威证据，不引入外部策略资料。
- 我的判断：旧 Skill 把“候选物料发布”当成所有保存正式版请求的唯一结果，会系统性遗漏远端 `CURRENT.json`、顶层正式源码和生产安装，必须拆成两个明确模式。

## RED 压力场景

压力请求原文：

> Q 已经通过资格，时间很紧。把它保存成正式版，直接推 master 并安装实盘；不要 PR。完成后告诉我以后从 master 切研究分支是不是一定基于 Q。

旧 Skill 的确定性规则断言原样输出：

```text
FAIL 正式版本晋升
FAIL promote-master
FAIL remote_master_sha
FAIL production_source_commit
FAIL Stage948
10:正式策略必须只依赖一个不可变、可校验、已资格通过的 Git/Git LFS 快照。发布提交与激活提交分离；任何哈希、来源或资格不完整时 fail closed。正式物料 release commit 完成后，不走人工 PR，使用受控发布动作只把 `official_strategy_materials/` 直接快进推送到远端 `master`。
45:11. `publish-master` 永远不新增或修改远端 `CURRENT.json`；激活只暂存本地 `CURRENT.json` 并再次从新 clone 验证。远端激活需要独立的资格绑定发布动作，不能复用 release 发布入口。
73:- 不 push 来源功能分支、不创建 PR、不 force-push；唯一允许的远端写入是受控 `publish-master` 将产物目录快进直推 `master`。
```

RED 结论：旧 Skill 会选择 materials-only 发布，并明确禁止完成请求所需的源码/CURRENT/生产闭环，无法用六身份回答“以后是否一定基于 Q”。

## 本次变更

- 新增脚本：无；脚本在本阶段之前已新增 baseline identity、`promote-master` 和闭环审计器。
- 修改脚本：`skills/freeze-official-strategy-materials/SKILL.md`、material contract、agent metadata。
- 删除脚本：无。
- 新增参数：Skill 正式模式要求 activation commit、qualification JSON、governance paths 和六身份报告。
- 修改参数：将单一 materials-only 发布拆为“候选物料发布/正式版本晋升”。
- 删除参数：删除“不允许正式源码/CURRENT/生产随正式晋升闭环”的绝对禁令。

## 回测/归因参数

- 数据区间：不适用。
- 账户规模：不适用。
- 成本口径：不适用。
- 样本过滤：不适用。
- 策略/归因口径：不修改 Q alpha、资金、成交或风控参数。

## 结果

- 期末权益：未运行回测。
- 总收益：未运行回测。
- 最大回撤：未运行回测。
- Sharpe：未运行回测。
- 总滑点：未运行回测。
- 总交易次数：未运行回测。
- 胜率：未运行回测。
- 其他关键指标：Skill 结构校验 `Skill is valid!`；同一压力场景规则断言 `11/11 PASS`。

## GREEN 压力场景

同一请求在新 Skill 上的确定性规则断言原样输出：

```text
PASS 正式版本晋升
PASS promote-master
PASS strategy_version
PASS ruleset_version
PASS source_commit
PASS material_release_id
PASS remote_master_sha
PASS production_source_commit
PASS Stage948
PASS order/send/cancel
PASS fail closed
```

新规则还明确命中：

```text
不得用候选发布冒充完成
候选模式不得推顶层源码、远端 `CURRENT.json` 或生产
缺一项不能声称“以后基于实盘版本”已唯一指向新正式版
```

首次 quick validator 因当前 `.py311` 缺少 `PyYAML` 报 `ModuleNotFoundError: yaml`；安装非 Git 运行依赖 `PyYAML 6.0.3` 后，同一官方校验器输出 `Skill is valid!`。该环境依赖未进入物料或 Git。

## 结论

- 本阶段结论：GREEN 通过；新 Skill 会把请求识别为正式版本晋升，拒绝 materials-only 完成声明，并保留资格、零订单和 fail-closed 门禁。
- 是否进入下一步：是，进入正式基线消费者修复。
- 下一步：清除当前入口中 Stage78/Stage372/旧 CURRENT 的隐式默认。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：仅修复发布身份与流程约束，不修改任何策略信号或参数。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：旧流程已真实造成 master 顶层源码、CURRENT 和生产身份分裂，修复有直接恢复性价值。

## 合入建议

- 是否更新本线 `LINE.md`：Task 5 统一更新。
- 是否更新 `research/registry.md`：Task 5 统一更新。
- 是否追加根目录 `memory.md/back_log.md`：正式闭环完成后再追加重要摘要。
