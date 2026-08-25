# Stage026 Q 正式策略运行时与物料闭包修复

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：正式生产故障修复与不可变物料治理
- 记录时间：2026-08-25 20:49 CST
- 工作区/分支：`.worktrees/fix-q-material-closure` / `codex/fix-q-material-closure`
- 阶段性质：恢复已晋升 Q 策略实现，修复正式物料依赖发现
- 是否重要突破：是；消除“配置声明 Q、实际策略忽略 Q”与核心策略未冻结的双重身份分裂
- 是否触发 A/B：否；本阶段不研究新 alpha，不调整 Q 参数

## 外部调研与判断

- 参考资料：Python 官方 `ast` 文档中的 `Import` / `ImportFrom` 节点语义。
- 我的判断：仓库现有 AST 依赖发现足够简单可靠，问题不在算法，而在正式发布器把入口显式设为空。修复应从真实生产 Python 入口递归闭包，同时保持 tests/Skills 只作为显式声明物料，避免测试动态导入污染生产闭包。

## 根因

1. 正式 config 已声明 Stage021-Q 的换月、成交量与 ATR 参数，但顶层 `qmt_roll_portfolio_strategy.py` 被回退为旧实现，具体 Stage847 类不消费 20 个 Q 参数；配置加载未报错，形成静默失效。
2. m0001 至 m0014 的 inventory 都没有 `examples/portfolio_backtesting/qmt_roll_portfolio_strategy.py`。
3. 发布器调用 `discover_materials(entrypoints=())`，关闭了已有的仓库内 Python import 闭包。因此资格测试与发布清单可以同时通过，却没有冻结实际策略引擎。

## 本次变更

- 恢复核心策略到已审核提交 `b907562db36d38ca5e07c9b1eba8e3e5dd9e88c5` 的精确字节；不重新发明策略逻辑。
- 新增完整正式配置合同：61 个 live override 键中，仅 `account_capital`、`c3_capital` 由外层执行 profile 消费，其余 59 个必须由具体 Stage847 策略类参数声明。
- 将核心策略显式加入 `DEFAULT_CRITICAL_FILES`。
- 正式发布器从 `examples/portfolio_backtesting` 下的生产 Python critical files 启动本地 import 闭包；tests/Skills 仍为 declared paths，不作为入口。
- 保留当前月度 AI 池绑定；任何 AI 池字节变化仍必须另建不可变 material version。

## 参数与回测

- 新增参数：无。
- 修改参数：无。
- 删除参数：无。
- 新增/修改/删除回测结果：无；本阶段为正式运行时恢复和发布治理修复，没有运行策略回测。
- 期末权益：不适用。
- 总收益：不适用。
- 最大回撤：不适用。
- Sharpe：不适用。
- 总滑点：不适用。
- 总交易次数：不适用。
- 胜率：不适用。

## 验证结果

- 核心策略与冻结 Q 提交字节一致。
- 完整 config/runtime 合同回归：10 项通过；独立审查两轮后 P0/P1/P2=`0/0/0`。
- 正式物料 discovery：80 个生产 Python 入口、237 个 inventory 路径、0 个 blocker，核心策略及本地 import 均在清单中。
- 发布、manifest、身份聚焦回归：72 个 pytest 用例与 39 个子测试通过。
- 物料闭包独立审查：P0/P1/P2=`0/0/0`。
- CTP/order/send/cancel API：`0/0/0/0`；本记录生成时尚未执行发布或生产安装。

## 结论与后续

- 本阶段代码结论：通过；原 `fu 1 -> 5` 的扩仓路径属于旧策略实现泄漏，恢复后的 `shrink_to_allowed` 使用 `min(previous_volume, allowed_volume)`，不得在换月时放大原持仓。
- 下一步：生成新的不可变正式物料，完成资格、激活、受控 `master` 晋升、fresh clone、Stage948 安装和 2026-08-25 Stage901 影子重算。最终身份以新 release manifest、`CURRENT.json`、资格证据与生产激活收据为准。

## 过拟合反思

- 运行前判断：否。
- 当前判断：否。
- 原因：只恢复已审核 Q 字节并修复发布依赖闭包，没有依据收益曲线选择参数或样本。

## 继续价值反思

- 运行前判断：是。
- 当前判断：是。
- 原因：故障会让正式配置与真实策略行为永久分裂，并使 clone 的正式物料无法复现实盘策略；修复直接恢复可验证性和换月风险边界。
