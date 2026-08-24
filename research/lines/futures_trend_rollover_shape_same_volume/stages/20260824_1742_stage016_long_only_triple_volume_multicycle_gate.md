# Stage016 仅多头三倍量能多周期诊断冻结

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 冻结时间：2026-08-24 17:42 CST
- 工作区/分支：`.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：用户在 Stage015 全周期门失败后明确要求的诊断性多周期，不是晋级补救
- 是否重要突破：否
- 是否触发A/B：是，沿用 `skills/version-ab-experiment/SKILL.md`

## 外部调研与判断

- vn.py 官方回测引擎按实例设置开始、结束和资金并清空历史数据，支持每个窗口独立初始化：<https://github.com/vnpy/vnpy_ctastrategy/blob/main/vnpy_ctastrategy/backtesting.py>。
- scikit-learn 官方时间序列切分强调按时间顺序评估，避免用未来训练过去：<https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html>。
- 判断：1/2/3年、每年1月与6月独立起点能检验起点依赖，但不增加独立信息，不能覆盖 Stage015 已失败的 A/C 全周期成本门。

## 冻结实验合同

- A：正式 C9/15万；C：正式 + 换月延续；K：C + 仅多头30日同向且最近10日量严格大于前10日2倍时风险 `×1.5`；L：同样规则但阈值为严格3倍。
- K/L 其他多头 `×1.0`，全部空头在历史检查前旁路 `×1.0`；规则、参数、数据、成本与 Stage014/015 一致。
- 固定 `43` 个窗口：完整周期 + 1/2/3年；每个周期覆盖所有可用的1月和6月起点；临近完整终端窗口标 `*` 且只观察。
- A/C 精确复用 Stage013 同窗结果；K/L 各新跑43个真引擎独立窗口，共86次新回测、172个逻辑臂窗。
- 每窗必须新建资金、持仓与账户状态；只使用起点前可见历史热身，不跨窗续接权益。
- 固定五图：完整周期、1年、2年、3年、聚合热力图；输出原始 summary/comparison/aggregate/curve CSV。

## 预声明门槛

- 全周期：收益不低于左臂、回撤恶化不超过1pp、Sharpe不劣于0.01、滑点不超过105%、账户生存、broker100不恶化。
- 各周期 combined/1月/6月：收益胜率至少50%、收益差中位非负、DD非劣率至少80%、DD50失败数不增加、Sharpe非劣率至少80%、聚合滑点不超过105%、全部生存、broker100失败数不增加。
- L 必须同时通过 A_vs_L 与 C_vs_L 的完整周期和全部周期/起点门；任一失败即 `confirm_long_only_triple_volume_not_promotable_after_multicycle`。
- Stage015 已知 A_vs_L/C_vs_L 成本门失败为约束性事实；本次即使局部窗口通过，也不得晋级、不得发布正式物料、不得改 master 或生产。

## 回测参数与待填结果

- 数据区间：`2018-01-01 -> 2026-05-29`
- 初始资金：每个窗口独立 `150,000`
- 成本口径：沿用正式回测手续费、滑点、保证金和 broker10 审计
- 期末权益/总收益/最大回撤/Sharpe/总滑点/交易/胜率：运行后写入结果记录
- 新增参数：无；修改参数：无；删除参数：无

## 运行前反思

- 是否过拟合：是，高风险。L 是 K 失败后的后验阈值收紧，全周期仅17次增强；多起点不能把后验选择变成外生信号。
- 是否值得继续：是，但价值有限。只值得回答“收益改善是否依赖少数起点”，不值得据结果继续扫描阈值、倍率、方向、品种或年份。

## 安全边界与合入建议

- 只运行离线研究回测；订单/撤单 API 必须为 `0/0`，`ctp_connected=false`。
- 正式配置、正式物料、master、production、CTP 和实盘入口均不修改。
- 结果后更新本线 `LINE.md`；因路线仍关闭，不更新 `research/registry.md`；按诊断结论决定是否追加 `memory.md/back_log.md`。
