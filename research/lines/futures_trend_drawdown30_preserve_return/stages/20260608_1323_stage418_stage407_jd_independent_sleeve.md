# Stage418 Stage407 鸡蛋独立风险槽验证

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-08 13:23 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/B/C 风险结构验证；正式核心不变 + 新品种独立 sleeve。
- 是否重要突破：否，机制有正向证据，但收益材料性不足。
- 是否触发A/B：是，读取并遵循 `skills/version-ab-experiment/SKILL.md`，因为候选可能成为正式扩池/风控结构。

## 外部调研与判断

- 参考资料：
  - AQR `Trend Following`：趋势跟踪长期价值来自多市场、多方向、分散右尾，不等于用最近几笔输赢决定所有市场是否开仓。
  - Man Group `Trend Following: the Optimal Market Mix`：市场组合和分散度会显著影响趋势跟踪表现，新增市场应看组合路径和相关性。
  - Hurst/Ooi/Pedersen `A Century of Evidence on Trend-Following Investing`：趋势跟踪的核心是跨市场分散捕捉趋势。
  - Concretum `Position Sizing in Trend-Following`：仓位管理会深刻改变权益曲线、回撤和风险调整收益，风险预算比入场小修补更关键。
- 我的判断：主账户连败 `0.1` 不适合继续用小数/本地化补丁救；更低过拟合的机制是核心账户保持原有防守，新品种用独立风险槽承担自己的小风险，避免挤占核心 AI 池和污染核心连败状态。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage705_stage407_jd_independent_sleeve.py`
- 修改脚本：无正式策略脚本修改；仅新增研究 wrapper。
- 删除脚本：无。
- 新增参数：
  - `SLEEVE20_VARIANT=stage526_200k_core_unchanged_plus_jd_independent_sleeve20k`
  - `SLEEVE50_VARIANT=stage526_200k_core_unchanged_plus_jd_independent_sleeve50k`
  - `JD_PRODUCT=jd.DCE`
  - `sleeve_capital=20,000/50,000`
  - `max_concurrent_positions=1`，只允许 JD 独立风险槽开仓。
- 修改参数：无正式参数修改；A 和核心路径保持 `official_live_stage372_20w_recovery_sleeve`。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-02` 至 `2026-04` 既有 Stage372 全周期窗口。
- 账户规模：合并账户仍按 `200,000`；JD sleeve 仅作为独立 sizing/risk state，不额外抬高账户初始资金。
- 成本口径：正常成本、`2x`、`3x` 成本压力。
- 样本过滤：A 当前正式 AI 池；B Stage407 原池 + `jd.DCE` 参与 AI rerank top9；C1/C2 正式核心完全保留，JD 单产品独立运行。
- 策略/归因口径：
  - A：当前正式 `stage526_200k_force95_to80_recovery_sleeve_r080_pc25_maxpos4`。
  - B：`stage526_200k_force95_to80_recovery_sleeve_r080_pc25_original_ai_plus_jd_ai_rerank_top9_maxpos5`。
  - C1：A 核心 + JD 独立 `20k` 风险槽。
  - C2：A 核心 + JD 独立 `50k` 风险槽。

## 结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 | 胜率 | broker10峰值 | JD sleeve PnL |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| A 正式核心 | `8,728,285` | `4264.1425%` | `-38.6713%` | `1.6279` | `506,220` | `633` | `52.2586%` | `79.6015%` | `0` |
| B Stage407 共享rerank | `3,284,935` | `1542.4675%` | `-33.2821%` | `1.3858` | `298,030` | `688` | `51.7181%` | `82.6211%` | `0` |
| C1 核心+JD sleeve20k | `8,728,425` | `4264.2125%` | `-38.6713%` | `1.6279` | `506,280` | `639` | `52.3009%` | `79.6015%` | `+140` |
| C2 核心+JD sleeve50k | `8,727,995` | `4263.9975%` | `-38.7106%` | `1.6262` | `506,560` | `657` | `52.4518%` | `79.7409%` | `-290` |

- 2x 成本最大回撤：A `-40.6555%`；B `-35.1162%`；C1 `-40.6555%`；C2 `-40.7000%`。
- 红框窗口 `2025-04-16` 至 `2025-07-25`：
  - A `+5,605,230`
  - B `+90,830`
  - C1 `+5,605,230`
  - C2 `+5,605,230`
- JD sleeve 年度贡献：
  - C1：2025 `+490`，2026 `-350`，全周期 `+140`，开仓 `3` 次。
  - C2：2020 `-1,780`，2024 `-1,460`，2025 `+3,650`，2026 `-700`，全周期 `-290`，开仓约 `12` 次。
- 入场诊断：
  - C1 候选 `61` 行、打开 `3` 行、零手 `55` 行、选中手数合计 `6`。
  - C2 候选 `60` 行、打开 `11` 行、零手 `44` 行、选中手数合计 `23`。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_report_stage705_stage407_jd_independent_sleeve_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_summary_stage705_stage407_jd_independent_sleeve_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_daily_stage705_stage407_jd_independent_sleeve_v1.csv`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_equity_only_stage705_stage407_jd_independent_sleeve_v1.png`
- quality：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage705_stage407_jd_independent_sleeve_decision_stage705_stage407_jd_independent_sleeve_v1.json`

## 结论

- 本阶段结论：`jd_independent_sleeve_watch_not_promoted`。
- 机制结论：独立风险槽是正确方向。它完全保留了正式版红框 `+5,605,230` 的右尾，没有重演 Stage407 的 `+90,830` 断崖；说明新增品种不能进入共享 AI rerank/topN/全局连败主池。
- 候选结论：JD 本身暂不具备材料性。20k sleeve 只贡献 `+140`，50k sleeve 反而 `-290`；这不是可接正式的收益源。
- 是否进入下一步：不继续在 JD 上扫 sleeve 大小、月份、方向、AI rank 或 topN；保留“独立风险槽”作为后续新增品种/新品类的结构原则。
- 下一步：如果继续风控机制目标，应转向更通用的独立风险槽准入规则，例如先用固定 forward/paper 监控证明某品种或品类有材料性，再进入小 sleeve；不要继续改主账户 `0.1` 连败机制。

## 过拟合反思

- 运行前判断：否。候选是预声明的资金/风险隔离结构，不是针对红框日期、JD rank、月份或产品盈亏的补丁。
- 运行后判断：继续救 JD 会过拟合；保留隔离结构不算过拟合。
- 原因：C1/C2 能解释 Stage407 断崖来自“共享主池挤占”，但 JD 自身贡献太小。如果为了让 JD 赚钱再调 `20k/50k`、只放 2025、过滤方向或改 rank，就是明显用历史噪声造规则。

## 继续价值反思

- 运行前判断：有价值。前面多次证明主账户连败机制不能靠小数、本地化或补1手修复，必须验证结构性隔离。
- 运行后判断：目标仍有价值，但 JD sleeve 本身不值得继续救。
- 原因：独立风险槽解决了核心右尾被挤掉的问题，这是风控结构上的有效经验；但一个新增品种只有 `+140/-290` 的全周期贡献，无法支撑正式接入。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录独立风险槽机制验证和 JD 不晋级。
- 是否更新 `research/registry.md`：否，本线仍为原研究线。
- 是否追加根目录 `memory.md/back_log.md`：是，作为重要路线结论和后续策略约束。
