# Stage001 候选边际风险贡献四锚点 1x canary 失败并关闭路线

- line_id：`futures_trend_candidate_marginal_risk_contribution`
- 当前模式：研究候选 / 四锚点 1x 真引擎 canary
- 记录时间：`2026-07-12 20:53 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `codex/stage130-option-probe`
- 阶段性质：冻结 A/C 真引擎验证、独立结果复核、失败即停
- 是否重要突破：否；重要路线关闭结论
- 是否触发A/B：是；仅 A/C canary，未进入 full

## 外部调研与判断

- 参考资料：Alexander/Fabozzi 风险贡献分解、Roncalli 风险预算、Ledoit/Wolf 收缩协方差、scikit-learn `LedoitWolf`、`pysystemtrade`。
- 我的判断：标准 component RC 与 Ledoit-Wolf 数学成立，但“把相关风险映射为候选缩手”在当前 C9 路径上破坏趋势复利和后续机会序列；失败来自真实路径，不是公式或统计实现错误。

## 本次版本

- A：`current_official_ai_c9_control`，当前 C9/15w Stage847 正式逻辑。
- C：`current_official_ai_c9_candidate_mrc`，A + 最终 planner 后的同日候选 component-risk 缩手。
- 新增参数：严格 T-1 actual-contract 共同 `63` 日、LedoitWolf、`scale=min(1, IC/RC)`、`max(1, floor(before*scale))`。
- 修改参数：无。
- 删除参数：无。
- manifest：`caff0cdbbd07d35e437f0a351725eb6253c03a90418839f49bf283fd84e0cfe1`，独立审查签认后运行。
- 回测命令环境：`PYTHONHASHSEED=0`、`OMP/OPENBLAS/MKL/NUMEXPR=1`、`TZ=Asia/Shanghai`。

## 回测参数

- 起点：`2020-01`、`2022-01`、`2022-07`、`2026-01`。
- 终点：`2026-06-30`。
- 账户规模：`150,000`。
- 成本口径：1x；metadata 手续费为0，滑点按正式 metadata，因此收益是非负手续费下的上界。
- AI：A/C eligibility 核心字段 `504/504` 完全一致，等于 current official AI SHA `fc50e035...271fc`；`55` 个 eval date、`19` 个产品。
- 候选风险输入：当日实际持仓合约和实际计划合约各自 T-1 日收益，不拼历史主力、不跨合约计算收益。

## 回测结果

| 起点 | 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总手续费 | 交易次数 | 非零日胜率 | 逐笔胜率 | 最长水下日 | broker10峰值 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020-01 | A | 5,996,631.0 | 3,897.7540% | -55.3701% | 1.3963 | 759,970 | 0 | 641 | 52.8302% | 45.8716% | 662 | 88.3398% |
| 2020-01 | C | 3,709,746.9 | 2,373.1646% | -57.2294% | 1.3307 | 488,950 | 0 | 641 | 53.4567% | 44.6154% | 792 | 87.7801% |
| 2022-01 | A | 319,909.0 | 113.2727% | -39.9820% | 0.6682 | 27,950 | 0 | 326 | 49.4327% | 41.4634% | 651 | 64.5100% |
| 2022-01 | C | 298,978.6 | 99.3191% | -40.6473% | 0.6639 | 24,650 | 0 | 325 | 50.3195% | 41.1043% | 652 | 56.4563% |
| 2022-07 | A | 462,813.7 | 208.5425% | -55.1835% | 0.9400 | 41,090 | 0 | 292 | 50.0000% | 41.4966% | 665 | 72.7529% |
| 2022-07 | C | 341,492.1 | 127.6614% | -53.4343% | 0.8082 | 28,120 | 0 | 281 | 51.8382% | 39.7163% | 780 | 68.8837% |
| 2026-01 | A | 154,651.6 | 3.1011% | -14.2479% | 0.3718 | 3,080 | 0 | 38 | 53.4247% | 44.4444% | 98 | 51.5137% |
| 2026-01 | C | 146,101.6 | -2.5989% | -16.3055% | -0.0642 | 2,790 | 0 | 40 | 53.4247% | 42.1053% | 112 | 54.8258% |

## 冻结门槛

- 收益保留：`60.8854% / 87.6814% / 61.2160% / -83.8077%`；2020、2022-07、2026 三个锚点失败。
- 历史回撤：2020 恶化 `1.8593pp`；2022-01 恶化 `0.6652pp`；2022-07 改善 `1.7492pp`。
- 2022 水下：2022-01 `651 -> 652`，2022-07 `665 -> 780`，均失败。
- 最新路径：2026 回撤恶化 `2.0575pp`，broker10 恶化 `3.3121pp`，失败。
- decision：共9项失败，`canary_pass=false`、`full_allowed=false`、`cost_stress_allowed=false`、`promotion_allowed=false`。

## MRC 运行证据

| 起点 | opened/batch | available/unavailable | 缩手候选 | 减少手数 |
| --- | ---: | ---: | ---: | ---: |
| 2020-01 | 289/264 | 263/1 | 126 | 1,301 |
| 2022-01 | 152/140 | 140/0 | 55 | 99 |
| 2022-07 | 132/124 | 124/0 | 43 | 88 |
| 2026-01 | 19/17 | 17/0 | 9 | 17 |

- available batch 全部精确63共同日且严格 T-1；无放大、无清零、final volume 全匹配。
- 唯一 unavailable：`2021-04-09|lh2109.DCE`，真实历史58日，`1 -> 1`、reduced=0、reason=`insufficient_common_history`。

## 独立结果审查

- 审查员：独立 agent `Meitner`。
- 结论：`P0=0 / P1=0 / P2=2`，可信度 `99%`；候选确定失败，禁止 full/2x/3x/救参。
- 复算与 summary 最大绩效差 `5.68e-14`；账户权益恒等式最大误差 `4.66e-10`。
- review manifest `23/23`、Stage137 `394/394`、canary source并集 `415/415` 均匹配。
- 40份核心gzip可读；`2,267,438` 条 positions 的逐行 identity、continuity、每日成交变化和 terminal reconciliation 全为0。
- 独立 metadata 重算 c3 margin 最大误差 `2.33e-10`；32项 A golden 全过。
- 三张 PNG 可解码且视觉正常。

## 不影响本次结果的 P2 日志

1. 输出目录残留旧 `...actual_contract_returns...csv.gz`：`988,754` 行、止于 `2026-04-21`。本次引擎、snapshot 和 manifest 全部绑定明文 `.csv` 的 `116,445` 行与 SHA `f730...da9`，旧 gzip 未被读取，不影响结果；暂不删除，后续任何复用必须显式忽略或隔离。
2. `evaluate_canary` 尚未把 `reduced_candidate_count/reduced_volume > 0` 设为显式 gate。本次四锚点真实缩手分别为 `126/55/43/9` 行、减少 `1301/99/88/17` 手，证据非空，因此不影响本次失败结论；若未来复用代码，必须先补硬门。

## 输出文件

- report：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_report_stage001_candidate_marginal_risk_contribution_engine_v1.md`
- summary：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_ac_summary_stage001_candidate_marginal_risk_contribution_engine_v1.csv`
- decision：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_decision_stage001_candidate_marginal_risk_contribution_engine_v1.json`
- runtime：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_runtime_audit_stage001_candidate_marginal_risk_contribution_engine_v1.csv`
- normalized chart：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_normalized_equity_drawdown_stage001_candidate_marginal_risk_contribution_engine_v1.png`
- absolute chart：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_absolute_equity_stage001_candidate_marginal_risk_contribution_engine_v1.png`
- 2022 chart：`outputs/stage001_candidate_marginal_risk_contribution_engine/candidate_mrc_stage001_candidate_marginal_risk_contribution_engine_focus_2022_stage001_candidate_marginal_risk_contribution_engine_v1.png`

## 结论

- 本阶段结论：候选失败且证据可信；它虽然降低部分滑点和2022-07回撤，但显著破坏收益、复利顺序和水下时间。
- 是否进入下一步：否；本路线立即关闭。
- 下一步：不修改63日、LedoitWolf、RC公式、scale、floor、minimum lot、品种或锚点救参；新实验必须另开结构不同的研究线并重新预声明。

## 过拟合反思

- 运行前判断：否；设计、数据、四锚点和门槛均在收益可见前冻结。
- 运行后判断：本次结果本身否；但继续调本候选明确会过拟合。
- 原因：失败跨2020、2022与2026，不是单一月份噪声；针对失败结果改参数只会追逐样本路径。

## 继续价值反思

- 运行前判断：有；独立签认后值得做一次最小 canary。
- 运行后判断：本候选没有继续价值；总体目标仍有价值。
- 原因：最小 canary 已充分否定该机制，不需要 full；下一步应换结构，不在同一公式上救参。

## 合入建议

- 是否更新本线 `LINE.md`：是，标记 Stage001 失败并关闭。
- 是否更新 `research/registry.md`：是，更新路线状态与决策。
- 是否追加根目录 `memory.md/back_log.md`：仅追加 `back_log.md` 路线关闭摘要，不改 `memory.md`。
