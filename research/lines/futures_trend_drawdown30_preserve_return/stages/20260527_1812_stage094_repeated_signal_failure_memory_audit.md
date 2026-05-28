# Stage094 同品种信号失败记忆特征只读审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：`2026-05-27 18:12 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：只读特征归因；验证“同品种多次信号失败后，下一次信号是否更容易成功”。
- 是否重要突破：否，重要边界确认。胜率假设部分成立，但收益期望不成立。
- 是否触发A/B：否。本阶段只做特征审计，不产生可晋级策略版本；若下一步做真实引擎冷却规则，将触发 A/B。

## 外部调研与判断

- 参考资料：
  - Hurst, Ooi, Pedersen, *A Century of Evidence on Trend-Following Investing*：https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026
  - Moskowitz, Ooi, Pedersen, *Time Series Momentum*：https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
  - Kim, Tse, Wald, *Time series momentum and volatility scaling*：https://www.sciencedirect.com/science/article/pii/S1386418116301379
- 我的判断：
  - 趋势跟随长期有效的核心不是高胜率，而是少数大趋势尾部覆盖大量小亏。
  - 连续失败有两个相反解释：一是趋势突破前的反复试探，二是震荡/假突破状态持续。不能直接相信“不会一直震荡”，必须同时检验胜率、平均收益、大赢家捕获和年份稳定性。
  - 因此本阶段把用户想法定义为只使用入场前已完成交易结果的点时化特征，先验证，不直接写成加仓规则。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage394_repeated_signal_failure_memory_audit.py`
- 修改脚本：无正式策略默认修改。
- 删除脚本：无。
- 新增参数：
  - 记忆范围：`同品种+同方向`、`同品种+同信号形态`。
  - 计数特征：历史已完成信号次数、252日内历史信号次数、252日内失败次数、历史连续失败次数、252日内连续失败次数、失败后第几次尝试。
  - 分桶：`0/1/2/3+`，尝试次数为 `1/2/3/4+`。
  - bootstrap：`5000` 次，比较目标桶单笔均值是否优于补集。
  - 大赢家口径：盈利交易 PnL 的 75% 分位；尾部赢家口径：全部交易 PnL 的 90% 分位。
- 修改参数：无。
- 删除参数：无。

## 回测/归因参数

- 数据区间：沿用 Stage328 C3 round-trip 样本，`2020-01-02` 至 `2026-04-30`。
- 账户规模：沿用 C3 `50万` 下单路径；Stage079 继承同一 C3 下单路径，因此先在 C3 交易层验证。
- 成本口径：本阶段使用 Stage328 round-trip `gross_pnl` 做交易层归因；没有重构日权益和成本压力。
- 样本过滤：`379` 个 C3 round-trip leg。
- 策略/归因口径：只使用入场前已经完成且已知盈亏的同品种/同方向或同品种/同信号历史交易，避免偷看当前交易结果。

## 结果

- 期末权益：本阶段未重跑权益；沿用 Stage083 C3 `30,925,650`。
- 总收益：本阶段未重跑权益；沿用 Stage083 C3 `6085.1300%`。
- 最大回撤：本阶段未重跑权益；沿用 Stage083 C3 `-31.0767%`。
- Sharpe：本阶段未重跑权益；沿用 Stage083 C3 `1.3143`。
- 总滑点：本阶段未重跑权益；沿用 C3 `1,556,750`。
- 总交易次数：沿用 C3 成交笔数 `757`；本阶段 round-trip 样本 `379`。
- 胜率：C3 round-trip gross 胜率 `45.3826%`。
- 其他关键指标：
  - 全体 round-trip：总 gross PnL `30,728,550`，单笔均值 `81,077.97`，单笔中位数 `-1,800`。
  - `同品种+同方向` 历史连续失败 `>=2`：样本 `81`，胜率 `49.3827%`，比补集高 `5.0874pp`；但单笔均值 `43,795.62`，低于补集 `91,211.76`，差 `-47,416.14`；bootstrap 均值优于补集概率 `16.60%`。
  - `同品种+同方向` 252日内连续失败 `>=2`：样本 `61`，胜率 `50.8197%`，比补集高 `6.4800pp`；单笔均值 `38,211.23`，低于补集 `89,300.83`，差 `-51,089.60`；bootstrap 均值优于补集概率 `19.14%`。
  - `同品种+同方向` 252日失败次数 `>=2`：样本 `122`，胜率 `52.4590%`，比补集高 `10.4357pp`；单笔均值 `31,727.21`，低于补集 `104,505.18`，差 `-72,777.96`；bootstrap 均值优于补集概率 `4.38%`。
  - `同品种+同信号` 252日失败次数 `>=2`：样本 `37`，胜率 `62.1622%`，比补集高 `18.5949pp`；单笔均值 `11,229.73`，低于补集 `88,634.65`，差 `-77,404.92`；bootstrap 均值优于补集概率 `0.12%`。
  - `同品种+同方向` 252日内连续失败 `3+`：样本仅 `17`，总 gross PnL `-1,324,790`，单笔均值 `-77,928.82`，5%分位 `-502,304`，但样本太小，只能作为下一轮固定冷却候选，不能作为规则结论。
  - 核心模式：失败次数越多，胜率更容易提高，但大赢家捕获率下降，平均收益下降；这不适合趋势策略直接加仓。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_report_stage394_repeated_signal_failure_memory_audit_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_feature_summary_stage394_repeated_signal_failure_memory_audit_v1.csv`
- hypothesis：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_hypothesis_tests_stage394_repeated_signal_failure_memory_audit_v1.csv`
- featured round trips：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_featured_round_trips_stage394_repeated_signal_failure_memory_audit_v1.csv`
- year bucket：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_year_bucket_stage394_repeated_signal_failure_memory_audit_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_decision_stage394_repeated_signal_failure_memory_audit_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage394_repeated_signal_failure_memory_audit_feature_charts_stage394_repeated_signal_failure_memory_audit_v1.png`

## 结论

- 本阶段结论：用户假设在“胜率”层面部分成立，但在“收益期望/趋势尾部捕获”层面不成立。不能做成“连续失败后加仓”。
- 是否进入下一步：可以进入一个极窄的下一步，但不是加仓，而是验证固定冷却规则。
- 下一步：若继续，只测试一个低自由度真实引擎版本：`同品种+同方向` 在 `252日` 内出现 `3次连续已执行亏损` 后，冷却 `90日` 或直到时间衰减；不扫 `2/3/4次`，不扫冷却天数小数。该规则的目标是减少 3个月/6个月坏体验，而不是提高长期收益。

## 过拟合反思

- 运行前判断：不是过拟合。先定义点时化特征、再统一跑所有样本，不按单个年份或品种定规则。
- 运行后判断：当前审计不是过拟合，但若直接围绕 `3+` 小样本负桶调阈值或冷却天数，会过拟合。
- 原因：`3+` 近期连续失败只有 `17` 笔，且 2026 贡献了最大负值；必须用固定粗规则真引擎验证，不能继续微调。

## 继续价值反思

- 运行前判断：有价值。该特征来自策略结构本身，且可以解释短持有体验中反复假突破的痛感。
- 运行后判断：继续有价值，但方向收窄。连续失败后加仓没有价值；只剩“3+近期连续失败后的固定冷却”值得一次真实引擎反证。
- 原因：胜率改善但均值下降，说明它更像过滤/冷却候选，而不是 alpha 加强候选。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage094 边界。
- 是否更新 `research/registry.md`：否，未形成正式候选。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 摘要；`memory.md` 暂不更新，除非后续真实引擎验证改变研究政策。
