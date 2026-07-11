# Stage008 权威权益 Stage013 单位滑点压力

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 回测完成时间：`2026-07-10 23:12 CST`
- 独立审查完成时间：`2026-07-11 00:43 CST`
- 工作区：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：冻结 A/C 的真实引擎单位滑点敏感性，不是完整执行仿真
- 是否重要突破：否；本阶段失败关闭，但发现后续必须修正的窗口回撤统计口径
- 是否触发 A/B：是；A=当前 AI C9，C=A+Stage006 权威权益 Stage013

## 外部调研与判断

- 参考资料：QuantConnect 官方 slippage reality model 文档与 key concepts；vn.py 官方 GitHub 源码及本地 `vnpy_portfoliostrategy.backtesting` 实际扣费公式。
- 我的判断：滑点必须在引擎成交层进入逐笔净损益并反馈后续权益和整数手数；静态期后扣费不能替代。本阶段只验证单位滑点单调扰动，不把它表述为盘口冲击、成交概率或延迟仿真。

## 本次变更

- 新增脚本：`tools/stage008_reconciled_equity_slippage_stress.py`
- 新增测试：`tools/test_stage008_reconciled_equity_slippage_stress.py`
- 修改脚本：无正式策略、实盘配置、CTP、邮件或 launchd 变更
- 删除脚本：无
- 新增参数：仅研究元数据 `slippage_multiplier=1/2/3`
- 修改参数：无；Stage013 继续冻结 `drawdown=30%/active<=1/pilot=1手`
- 删除参数：无

## 回测参数

- 数据区间：`2020-01-02 -> 2026-06-30`，`1,571` 个交易日
- 账户规模：`150,000`
- AI：当前 official eligibility，A/C 均 `504` 行、`55` 个 eval_date
- 成本口径：引擎初始化前逐合约把 metadata 单位滑点缩放为 `1x/2x/3x`；佣金和其他逻辑不变
- A/C 配对：每档成本都独立重跑 A 与 C，同档比较，不用 1x A 与高成本 C 混比
- 2022 局部窗口：原报告以 `2021-12-31` 权益为种子并在窗口内重置高水位；独立审查证明该指标只能作局部归因，不能再作为“账户真实 2022 水下幅度”硬门

## 结果

| 滑点 | A期末权益/收益 | C期末权益/收益 | 收益保留 | A/C最大回撤 | 全周期改善 | 原局部2022改善 | 压力窗改善 | Broker10 A/C | 结果 |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | --- | --- |
| 1x | `5,996,631 / 3897.7540%` | `4,826,685.8 / 3117.7905%` | `79.9894%` | `-55.3701%/-40.0046%` | `15.3655pp` | `12.0107pp` | `22.8197pp` | `88.3398%/88.3322%` | 通过单档门 |
| 2x | `3,870,901.5 / 2480.6010%` | `2,168,334.3 / 1345.5562%` | `54.2432%` | `-57.0944%/-42.2385%` | `14.8559pp` | `6.7299pp` | `22.8120pp` | `86.7582%/91.4648%` | 失败 |
| 3x | `2,871,417.6 / 1814.2784%` | `1,944,757 / 1196.5047%` | `65.9493%` | `-59.2247%/-44.3503%` | `14.8743pp` | `6.3501pp` | `25.7098pp` | `90.7077%/93.3607%` | 失败 |

- Sharpe A/C：1x `1.3967/1.4057`；2x `1.2730/1.1257`；3x `1.1634/1.0764`。
- 总滑点 A/C：1x `759,970/537,010`；2x `1,039,900/538,880`；3x `1,319,430/765,630`。
- 总交易次数 A/C：1x `641/641`；2x `634/630`；3x `630/627`。
- 非零交易日胜率 A/C：1x `52.8302%/52.5763%`；2x `52.2682%/51.6284%`；3x `51.8593%/51.1472%`。
- 逐笔闭仓胜率 A/C：1x `45.8716%/44.9541%`；2x `45.9627%/45.1411%`；3x `46.5625%/45.9120%`。

## 机械审计

- 本地独立复算六臂收益、回撤、窗口回撤、保留率和 broker10 与汇总最大误差 `<1.6e-14`。
- 六臂均满足 `account_equity = 150,000 + cumulative(net_pnl)`，最大绝对误差 `<5e-10`；日期重复 `0`。
- 1x A/C 与 Stage006 的核心逐日列 `1,571/1,571` 完全一致，最大差 `0`。
- 三档权威权益 reconciliation 均通过：缺失/重复/in-range extra/post-end/future trade 全为 `0`，权益最大误差 `<3e-9`；合法 pre-start warm-up 均为 `145` 日。
- Gate 事件 `58/66/68`，回撤低于 30%、未应用、非 1 手、活跃持仓超限、未打开等违规均为 `0`。
- `783` 个合约单位滑点逐项精确缩放；原 metadata 前后 SHA256 均为 `6add2e...d2311c`，未被污染。
- Manifest `62/62` 文件大小与 SHA256 全部通过，无未列出的额外文件。
- 测试：从工具目录运行 Stage006/007/008 共 `12/12` 通过；从仓库根目录以包路径运行会因测试文件未注入 tools 目录而模块找不到，这是测试入口可移植性 P2，不是策略断言失败。独立 agent 对关联 Stage005-008 运行 `15/15` 通过。

## 独立 agent 审查

- 结论：`P0=0/P1=1/P2=3`；数字置信度 `99.5%`，语义置信度 `90%`。
- P1：原 `year_2022` 指标在窗口开头重置高水位。若用全账户历史高水位计算 2022 期间的真实水下幅度，1x/2x/3x 的 A/C 改善仅为 `3.5171/1.1658/0.8601pp`，不是报告局部口径的 `12.0107/6.7299/6.3501pp`。
- P2：lineage 未冻结完整历史数据库和传递依赖，不能保证未来字节级重跑；Stage008 自身仅 2 个聚合单测；三档图使用独立 Y 轴且未注明局部高水位口径。
- 该 P1 不会造成误晋级，因为 Stage008 已因 2x/3x 收益保留和 broker10 明确失败；但后续所有晋级门必须把全账户历史高水位作为主口径，局部重置口径只作归因辅助。

## 输出文件

- report：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_report_stage008_reconciled_equity_slippage_stress_v1.md`
- summary：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_summary_stage008_reconciled_equity_slippage_stress_v1.csv`
- paired gate：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_paired_gates_stage008_reconciled_equity_slippage_stress_v1.csv`
- reconciliation：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_reconciliation_stage008_reconciled_equity_slippage_stress_v1.csv`
- manifest：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_manifest_stage008_reconciled_equity_slippage_stress_v1.csv`
- chart：`outputs/stage008_reconciled_equity_slippage_stress/stage013_current_ai_stage008_reconciled_equity_slippage_stress_equity_drawdown_by_slippage_stage008_reconciled_equity_slippage_stress_v1.png`

## 结论

- 本阶段结论：`stage008_fail_close_no_parameter_rescue`。2x/3x 收益保留只有 `54.24%/65.95%` 且 broker10 恶化，不满足部署前成本稳健性。
- 最终目标：未完成。Stage007 `2022-01` 独立启动收益保留仍为 `57.7149%`，Stage008 没有改变结构，不可能修复该缺口。
- 是否进入下一步：Stage008 本身不救参；继续做跨起点机会成本归因和低自由度结构研究。

## 过拟合反思

- 运行前判断：否；成本倍率和所有门在运行前冻结。
- 运行后判断：否；没有根据结果调整倍率或 Stage013 参数，失败如实关闭。
- 风险边界：若围绕 2x/3x 再扫滑点、门槛、月份、品种、方向或 pilot 手数，就是过拟合。

## 继续价值反思

- Stage008 救参：无价值；压力门已明确失败。
- 总目标研究：仍有价值；1x 全周期仍保留 `79.99%` 且回撤明显改善，问题集中在成本敏感和 `2022-01` 冷启动恢复，值得先做统一归因再决定一个结构版本。

## 合入建议

- 更新本线 `LINE.md`：是。
- 更新 `research/registry.md`：待结构候选结论后统一更新。
- 追加根目录 `memory.md/back_log.md`：Stage005 P0、Stage006 修复、Stage007 半年和 Stage008 失败属于重要里程碑，待本轮结构归因完成后统一追加。
