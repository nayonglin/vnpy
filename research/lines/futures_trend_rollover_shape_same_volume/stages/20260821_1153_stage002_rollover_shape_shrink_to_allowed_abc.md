# Stage002 主力换月按硬风控容量缩手 A/B/C

- line_id：`futures_trend_rollover_shape_same_volume`
- 当前模式：`day`
- 记录时间：`2026-08-21 11:53 CST`
- 基准提交：`c26ab93caab572df922f0abcc5ff7faabe934810`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy/.worktrees/rollover-shape-same-volume` / `codex/rollover-shape-same-volume`
- 阶段性质：用户确认后，将 Stage001 的 `exact-or-skip` 优化为“原手数优先、容量不足时缩至硬风控允许手数”的完整区间 A/B/C
- 是否重要突破：否；工程合同通过，但相对 Stage001 B 收益下降，且真实缩手样本只有 `1` 次
- 是否触发 A/B/C：是；A 为当前正式 C9/15万，B 为 Stage001 原手数或不开仓，C 为动态缩手

## 外部调研与判断

- CME position sizing 资料：`https://www.cmegroup.com/education/courses/trade-and-risk-management/proper-position-size`，支持仓位规模随交易风险和账户可承受风险调整。
- pysystemtrade instruments 资料：`https://github.com/pst-group/pysystemtrade/blob/develop/docs/instruments.md`，其生产体系同样将仓位限制和交易控制作为独立风险层。
- 我的判断：直接使用现有硬风控引擎已经给出的最大整数手数，不新增固定缩手比例、不按品种或年份调参，比“容量不足全部归零”更符合风险预算语义；但结构合理不等于历史表现一定更好。

## 本次版本变更

- 新增参数：`rollover_shape_volume_policy="shrink_to_allowed"`；候选功能开关仍默认关闭。
- 修改参数：B 显式使用 `exact_or_skip`，C 显式使用 `shrink_to_allowed`。
- 删除参数：无。
- 新增规则：C 最终手数为 `min(旧仓实际剩余手数, 当前全部硬风控允许手数)`；允许手数为 `0` 才不开仓。
- 修改规则：Stage001 B 的“必须完整覆盖旧仓，否则不开仓”保留为可复现策略，不再是当前研究分支启用候选后的默认手数规则。
- 删除规则：不再把“禁止任何缩手”作为 Stage002 C 合同。
- 诊断新增：`volume_policy`、`volume_outcome=full/reduced/skipped`、`was_reduced`；目标成交必须等于最终手数。
- 其余规则不变：新主力自身至少 `40` 根真实 K 线、MA5/10/20/40 同向排布、MACD 柱同向、旧仓风险只在本轮快照确实计入时释放、普通正式 AM41 开仓不变。
- 正式配置/CTP/下单：未修改正式配置，未连接 CTP，未调用真实订单或撤单 API。

## 回测参数

- 区间：`2018-01-01` 至 `2026-05-29`。
- 账户规模：`150,000`。
- A：`stage002_A_official_live_c9_15w`。
- B：`stage002_B_rollover_exact_or_skip`。
- C：`stage002_C_rollover_shrink_to_allowed`。
- 数据、成本和策略基底：三臂均使用正式 Stage901 C9 分钟 K 注入、正式 AI eligibility、broker10、0.5R stop/retry-once、相同 rates/slippage/size/pricetick。
- 唯一候选差异：B/C 的换月手数策略。
- 预声明门：逐行验证 B 的 `final=previous if selected>=previous else 0`，C 的 `final=min(previous, selected)`；同时验证 policy、targeted/skipped、full/reduced/skipped、was_reduced 和实际成交手数，候选诊断数必须等于换月平仓数。
- 身份校准：Stage002 A 与 Stage001 A、Stage002 B 与 Stage001 exact 候选均为 `2037` 个交易日；排除 profile/arm/variant/label 身份列后，全部共同曲线列逐行一致。
- 产物发布：全部 DataFrame 先在内存通过精确合同和身份校准，再写入同文件系统临时目录并以目录替换发布；校验或暂存写入失败均不覆盖上一版已验证产物。
- 产物读回：CSV 空成交状态统一规范化为空字符串；最终落盘 CSV 再用同一精确合同验证 B/C、成交、身份校准与临时目录残留。

## 回测结果

| 指标 | A 正式基线 | B exact-or-skip | C shrink-to-allowed |
| --- | ---: | ---: | ---: |
| 期末权益 | `13,071,214.10` | `13,518,540.80` | `13,492,951.90` |
| 总收益 | `8614.1427%` | `8912.3605%` | `8895.3013%` |
| 最大回撤 | `-56.2069%` | `-57.2674%` | `-57.2674%` |
| Sharpe | `1.3622` | `1.3625` | `1.3631` |
| 总滑点 | `1,525,590` | `1,576,750` | `1,573,350` |
| 总交易次数 | `808` | `809` | `811` |
| 非零日胜率 | `52.5841%` | `52.7170%` | `52.8745%` |

### C 相对 B

- 期末权益：`-25,588.90`。
- 总收益：`-17.0593pp`。
- 最大回撤：`0.0000pp`，完全相同。
- Sharpe：`+0.0006`，近似持平。
- 总滑点：`-3,400`。
- 总交易次数：`+2`。
- 非零日胜率：`+0.1575pp`。

### C 相对 A

- 期末权益：`+421,737.80`。
- 总收益：`+281.1585pp`。
- 最大回撤：恶化 `-1.0604pp`。
- Sharpe：`+0.0009`，近似持平。
- 总滑点：`+47,760`。
- 总交易次数：`+3`。
- 非零日胜率：`+0.2904pp`。

### 换月事件合同

- A：换月平仓 `23` 次，无候选诊断。
- B：候选诊断 `23` 次，原手数目标并成交 `13`，缩手 `0`，不开仓 `10`，未成交 `0`，exact contract 通过。
- C：候选诊断 `23` 次，目标并成交 `14`；其中原手数 `13`、缩手 `1`、不开仓 `9`、未成交 `0`，volume contract 通过。
- 唯一缩手事件：`2023-07-19` `SM.CZCE` 多头，`SM309 -> SM310`，旧仓 `299` 手，硬风控允许 `180` 手，最终目标/次日实际成交均为 `180` 手。
- 未初始化目标合约仍有 `5` 次，但都只有 `1` 根真实 K 线，因此没有“40 根但未完整初始化”的真实成功样本。
- 新增回测结果：Stage002 三臂 summary/comparison/curve、成交、事件和换月诊断。
- 修改回测结果：Stage001 不删除、不覆盖；Stage002 在同一代码版本重跑 A/B/C。
- 删除回测结果：无。

## 输出文件

- summary：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_abc_summary.csv`
- comparison：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_abc_comparison.csv`
- daily：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_abc_curve.csv`
- trades：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_trades.csv`
- trade events：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_trade_events.csv`
- quality：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_rollover_shape_diagnostics.csv`
- decision：`research/lines/futures_trend_rollover_shape_same_volume/artifacts/stage002/stage002_decision.json`
- 最终生成时间：`2026-08-21T11:53:21+08:00`；`stage001_curve_identity_pass=1`。

## 结论

- 决策：`stage002_shrink_to_allowed_implemented_research_only_not_promoted`。
- 工程判断：通过。C 确实只在存在正容量时缩手，目标和实际成交手数一致，没有超过旧仓、没有静默变为零手、没有绕过硬风控。
- 性能判断：不通过晋级。C 相对 B 少赚 `25,588.90`，最大回撤没有改善，Sharpe 差异近似噪声。
- 是否进入下一步：保留用户要求的动态缩手实现和可复现 B/C 策略；不合入正式配置、不激活实盘、不据唯一 SM 样本调整缩手比例。
- TODO：只做固定规则 forward shadow，等待更多真实容量不足换月事件；不做多起点或参数扫描，因为最小有效实验已经没有显示 C 优于 B。
- 独立复审修复：contract pass 已从宽松的 `0<final<=previous` 收紧为逐行精确 policy 公式与诊断/成交语义；产物改为校验后原子目录发布。
- 最终回归：`71 passed, 41 subtests passed`；落盘 B/C strict contract、`299 -> 180` 成交、Stage001 曲线身份和 atomic residue 均通过。

## 过拟合反思

- 运行前：否。最终手数完全由既有硬风控容量机械决定，没有新小数阈值、品种或窗口补丁。
- 运行后：低到中等。规则本身低自由度，但真实缩手事件只有 `1` 次，不能从该事件推导稳定收益或风险改善。
- 禁止事项：不得围绕 `SM.CZCE`、`299 -> 180`、日期、方向或历史盈亏设置专属比例。

## 继续价值反思

- 运行前：有。正容量被 exact gate 直接归零存在执行语义损失。
- 运行后：工程和 forward shadow 仍有价值；主动回测优化价值低。C 完成了用户指定语义，但历史上没有优于 B。
