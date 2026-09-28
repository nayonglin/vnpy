# Stage006 最终实现评审 BLOCK 修复

- line_id：`futures_trend_xgboost_pit_curve_account_labels`
- 当前模式：冻结 development OOS 训练前实现修复
- 记录时间：2026-09-03 02:12（Asia/Shanghai）
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：独立评审阻断修复、纯合成验证、只读元数据预检
- 是否重要突破：否
- 是否触发A/B：是；继续遵守 Stage006 已冻结 A/B/C 合同，但本阶段未运行 A/B

## 外部调研与判断

- 参考资料：XGBoost Learning to Rank 官方文档；Python `os.link`、`os.rename` 原子文件操作语义。
- 我的判断：reviewer 提出的两个 P1 和一个 P2 均成立。固定单路径上的授权消费原语虽然原子，但生产入口允许替换路径会破坏“一份授权一次运行”；允许替换 Ranker 工厂会破坏冻结模型身份；只核验 seal 字段形状不足以证明开标签前的实际 payload 已被封存。

## 本次变更

- 新增脚本：无。
- 修改脚本：`tools/stage006_dual_ranker_development_oos.py`、`tests/test_stage006_dual_ranker_development_oos.py`。
- 删除脚本：无。
- 新增参数：无。
- 修改参数：无；XGBoost 参数、PIT 月份、特征、selector 和效果门均保持冻结。
- 删除参数：生产入口移除 `authorization_path`、`consumption_path`、`result_dir`、`ranker_factory` 覆盖，只保留授权 SHA256。
- 实现修复：生产路径由 runner 位置唯一导出；实际 estimator 必须精确为冻结 `XGBRanker` 且参数等于冻结合同；标签开放前重新计算并比较主模型、重复模型、ordered predictions、selection 的全部 SHA256。
- 回归补充：同一消费路径 16 路并发只能一个成功；FakeRanker 必须被技术门拒绝；四类 pre-effect payload 与模型摘要任一篡改均拒绝开标签。

## 回测/归因参数

- 数据区间：未运行回测；仅只读核验 development 2022-01-28 至 2024-11-29 的元数据边界。
- 账户规模：冻结合同 `150,000`，本阶段未用于回测。
- 成本口径：未运行回测。
- 样本过滤：只读确认 266 行、35 个月、17 个 OOS 折、初始成熟 115 行。
- 策略/归因口径：未读取 per-job `label.json`，未训练模型，未评价效果。

## 结果

- 期末权益：不适用，未回测。
- 总收益：不适用，未回测。
- 最大回撤：不适用，未回测。
- Sharpe：不适用，未回测。
- 总滑点：不适用，未回测。
- 总交易次数：不适用，未回测。
- 胜率：不适用，未回测。
- 其他关键指标：Stage006 专项 `30 passed`；本研究线 `87 passed`；`py_compile` 通过；聚合 development label 与 reconciliation 数据行解析计数均为 `0`。

## 输出文件

- report：`reviews/20260903_stage006_final_implementation_review.md`，首轮结论 `BLOCK_STAGE006_DEVELOPMENT_RUN`，严重度 `0/2/1/0`。
- summary：本阶段记录。
- orders：无。
- daily：无。
- quality：等待同一独立 reviewer 对修复后 runner/tests 做最终复审。

## 结论

- 本阶段结论：三个阻断缺口已按反例测试修复，本地验证通过；这不是运行授权，也不是收益提升证据。
- 是否进入下一步：是，但只进入独立复审。
- 下一步：只有复审 `P0/P1/P2=0` 且授权精确绑定修复后 runner/tests 和复审文件，才允许一次冻结 development run。

## 过拟合反思

- 运行前判断：否。
- 运行后判断：否。
- 原因：未读取真实标签、未训练、未比较收益或回撤、未修改模型参数和效果阈值；本阶段只收紧执行和盲态边界。

## 继续价值反思

- 运行前判断：是。
- 运行后判断：是。
- 原因：三个问题直接决定一次性授权、冻结模型和 pre-effect seal 是否可信；修复后才能让首次真实训练结果具备可审计意义。

## 合入建议

- 是否更新本线 `LINE.md`：复审结论后统一更新。
- 是否更新 `research/registry.md`：复审结论后统一更新。
- 是否追加根目录 `memory.md/back_log.md`：当前不追加；无回测结果、无重要突破、无正式候选。
