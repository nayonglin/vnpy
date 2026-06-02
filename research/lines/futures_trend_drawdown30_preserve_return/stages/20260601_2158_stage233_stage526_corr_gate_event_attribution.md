# Stage233 Stage526同向相关性门控逐笔/路径归因

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-06-01 21:58 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：固定 Stage232 control/C1 的逐笔归因；不新增策略规则，不扫参数。
- 是否重要突破：否，未形成替代候选；但确认 floor0.50 的优势主要是路径依赖，不是直接门控事件收益。
- 是否触发A/B：否。本阶段是 Stage232 A/C 的复盘归因，不新增可接入版本。

## 外部调研与判断

- 参考资料：
  - Moskowitz/Ooi/Pedersen time-series momentum：趋势跟随依赖多市场分散和持续趋势，但组合层风险预算会改变收益路径：https://research.cbs.dk/en/publications/time-series-momentum
  - ScienceDirect `Time series momentum and volatility scaling`：趋势组合表现会受波动/风险缩放显著影响：https://www.sciencedirect.com/science/article/pii/S1386418116301379
  - ScienceDirect `Optimal allocation of trend following strategies`：资产间相关性既可能帮助识别趋势，也可能带来组合风险，不能简单视为只该压制的变量：https://www.sciencedirect.com/science/article/pii/S0378437115003404
  - PyTrendFollow / mlm-trend-following 等开源实现强调连续合约、前月执行、风险过滤和组合工程，说明机制要保持可解释、可执行：https://github.com/chrism2671/PyTrendFollow
- 我的判断：
  - Stage232 的 floor0.50 不能只看总收益更好；必须确认新增手数本身是否有正 edge。
  - 如果正收益来自后续权益路径放大，而直接门控事件本身为负，则不能把它当成“相关性门控应该放宽”的强证据。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage533_stage526_corr_gate_event_attribution.py`
- 修改脚本：无正式策略脚本修改。
- 删除脚本：无。
- 新增参数：无交易参数；新增归因层：
  - `direct_corr_scaled_delta`：Stage232 中直接被相关性门控缩放、floor0.50 实际多开的手数。
  - `downstream_equity_sizing_delta`：floor0.50 早期路径改变权益后，后续普通开仓 sizing 产生的手数差异。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：`2020-01-01` 至 `2026-04-30`
- 账户规模：沿用 Stage526/Stage232 的 50万 C3 下单口径与组合账户口径。
- 成本口径：正常成本；本阶段只解释 control 与 C1 的实际路径差。
- 样本过滤：
  - control：`r080_pc25_maxpos4_control`，同向相关性门控 `lookback=20/start=0.60/full=0.80/floor=0.35`
  - C1：`r080_pc25_maxpos4_corr20_f50`，只把 floor 放宽到 `0.50`
- 策略/归因口径：
  - 重跑两个真实引擎路径，保存合约级逐日持仓与 PnL。
  - 对每个 control/C1 都实际开仓且手数不同的事件，追踪对应合约 `C1-control` 持仓差从出现到归零的净 PnL edge。

## 结果

### 总览

| 指标 | 数值 |
| --- | ---: |
| 决策标签 | `corr_floor50_gain_is_path_dependent_not_direct_gate_edge` |
| 有手数差异事件 | 165 |
| 直接相关性缩放手数差异事件 | 24 |
| 后续权益路径 sizing 差异事件 | 141 |
| 合计手数差异 | 937 |
| 正 edge 事件 | 73 |
| 负 edge 事件 | 92 |
| 事件归因 edge | 600,485 |
| 总合约持仓 edge | 606,875 |
| 事件解释率 | 98.9471% |

### 分层结论

| 层级 | 事件数 | 手数差异 | edge |
| --- | ---: | ---: | ---: |
| direct_corr_scaled_delta | 24 | 316 | -26,805 |
| downstream_equity_sizing_delta | 143 | 618 | 627,290 |
| direct_corr_integer_no_delta | 4 | 0 | 0 |

解释：

- 直接放宽相关性门控产生的多开手数，合计反而亏 `-26,805`。
- floor0.50 的总优势主要来自后续权益路径更高后，普通开仓 sizing 增大产生的 `+627,290`。
- 因此，Stage232 的 C1 不是“相关性门控直接识别错了很多好信号”，而是“少量路径差改变后，后续复利和 sizing 给了正贡献”。

### 时段归因

| 时段 | 事件数 | 手数差异 | edge |
| --- | ---: | ---: | ---: |
| bad_2022_main | 22 | 82 | 42,970 |
| pre_bad_window | 50 | 91 | 67,910 |
| post_bad_window | 99 | 761 | 489,605 |

解释：

- 2022 主坏窗口没有被 floor0.50 明显伤害，反而是小幅正 edge。
- 主要正贡献来自 2023 之后的路径扩张，尤其 2025 年。
- 这也是不能直接晋级的原因：它更像路径复利收益，不是稳定可解释的门控事件 alpha。

### 产品归因

主要正贡献：

- `jm.DCE +272,520`
- `OI.CZCE +152,510`
- `hc.SHFE +78,110`
- `ru.SHFE +78,050`
- `lh.DCE +70,320`

主要负贡献：

- `MA.CZCE -108,770`
- `AP.CZCE -38,390`
- `SA.CZCE -17,700`
- `fu.SHFE -10,700`
- `sp.SHFE -8,760`

### 年度归因

- `2025 +300,275`
- `2023 +124,965`
- `2022 +108,750`
- `2024 +65,420`
- `2026 -43,405`

## 图表视觉复盘

- 图表：`/Users/bytedance/Desktop/person/vnpy/examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_chart_stage533_stage526_corr_gate_event_attribution_v1.png`
- 视觉判断：
  - 左上散点中红点代表直接相关性门控事件，明显正负混杂，且几个大负点都来自红点；这不支持直接放宽门控。
  - 蓝点代表后续 sizing 路径事件，低相关区 `corr<=0.65` 分布密集，并贡献主要正 edge，说明 floor0.50 的收益是路径复利/仓位尺寸变化，不是相关性阈值本身的稳定信号。
  - 右上累计曲线在 2022 主坏窗口小幅上行，2023-2026 才拉开；2026 回撤一段说明该路径收益仍会吐回。
  - 左下产品贡献显示 `jm/OI/hc/ru/lh` 是正贡献核心，`MA/AP/SA` 是反向拖累；若后续做机制优化，不能做产品黑名单，只能看触发状态。
  - 右下时段柱状图显示 post_bad_window 占绝大多数正贡献，说明这一版的优势不够像坏窗口专用保护，更像复利路径扰动。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_report_stage533_stage526_corr_gate_event_attribution_v1.md`
- events：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_events_stage533_stage526_corr_gate_event_attribution_v1.csv`
- aggregate：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_aggregate_stage533_stage526_corr_gate_event_attribution_v1.csv`
- positions：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_positions_stage533_stage526_corr_gate_event_attribution_v1.csv`
- candidates：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_candidate_pairs_stage533_stage526_corr_gate_event_attribution_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_decision_stage533_stage526_corr_gate_event_attribution_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage533_stage526_corr_gate_event_attribution_chart_stage533_stage526_corr_gate_event_attribution_v1.png`

## 结论

- 本阶段结论：不晋级 `floor0.50`，Stage526 control 继续保留为主研究候选。
- 是否进入下一步：是，但不是沿相关性 floor 调参。
- 下一步：
  - 停止 `floor=0.45/0.55/0.60` 小数扫描。
  - 若继续研究相关性门控，只能转为“直接事件为负时如何避免放宽”的状态解释，例如把放宽限制在更明确的趋势扩散/低相关后续 sizing 状态，而不是通用 floor 放宽。
  - 更优先的下一步是做 `MA/AP/SA` 负贡献事件的共同状态复盘，判断是否存在统一的低自由度“假突破/弱趋势扩散”特征；不得做产品黑名单。

## 过拟合反思

- 运行前判断：否。只解释 Stage232 固定 A/C 差异，不新增交易规则。
- 运行后判断：否，并且结论主动收紧。
- 原因：直接门控事件为负，说明不能因为总净值好就把 floor0.50 合入；这一步避免了把路径复利误当成 alpha。

## 继续价值反思

- 运行前判断：是。Stage232 需要逐笔归因，否则容易误判。
- 运行后判断：是，但研究方向改变。
- 原因：已证明 floor0.50 的优势是路径依赖；继续研究相关性 floor 本身价值下降，继续研究“哪些状态下多开手数亏损”更有价值。

## 合入建议

- 是否更新本线 `LINE.md`：是，记录 Stage233 结论。
- 是否更新 `research/registry.md`：是，更新最新关键阶段。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md`；不追加 `memory.md`，因为没有形成默认策略政策变更。
