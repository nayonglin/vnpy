# Stage003 Stage182 提前生效反事实 A/C

- line_id：`futures_trend_stage013_current_ai_revalidation`
- 当前模式：`day`
- 记录时间：`2026-07-10 20:08:53 CST`
- 是否重要突破：否；early-activation 反事实路线关闭
- 新增参数：无策略参数；反事实输入把后来 Stage182 live inference 提前到 `2021-04 -> 2021-12`
- 修改参数：A/C AI 文件从当前 504 行扩为 hybrid 585 行，现有 504 行完全保留
- 删除参数：无

## 调研与判断

- scikit-learn TimeSeriesSplit 明确时间序列训练必须在过去、测试在未来；QuantConnect walk-forward 文档要求滚动训练和 warm-up。
- 原冻结 walk-forward 使用 720 天训练窗，首个 OOS 预测为 2022-01-28；本阶段追加九个月只代表后来 Stage182 规则可以追溯计算，不代表原历史政策缺失。

## 回测口径

- 区间：`2020-01-01 -> 2026-06-30`；账户 `150,000`。
- A：append-only hybrid AI + 当前 C9；C：A + 冻结 Stage013 `30%/1/1`。
- 成本、保证金、相关门、forced-margin、0.5R 开仓日止损重试和退出均不改。

## 结果

- A：期末权益 `4,201,665.50`，总收益 `2701.1103%`，最大回撤 `-52.7853%`，Sharpe `1.3993`，总滑点 `498,000.00`，交易次数 `586`，非零日胜率 `52.3077%`，逐笔胜率 `46.4883%`。
- C：期末权益 `3,582,335.90`，总收益 `2288.2239%`，最大回撤 `-31.3413%`，Sharpe `1.5216`，总滑点 `223,840.00`，交易次数 `586`，非零日胜率 `52.4225%`，逐笔胜率 `45.3020%`。
- C 相对 hybrid A / 当前 official A 收益保留：`0.8471` / `0.5871`。
- 全周期/2022/固定压力窗回撤改善：`21.4439` / `7.8771` / `30.5078` pp。
- broker10 变化：`0.0000` pp。
- 输入机械口径：当前 `504/55`，反事实追加 `81/9`，hybrid `585/64`；这不是原冻结政策的缺失修复。

## 最终结论

- 决策：`stage003_close_counterfactual_early_activation_no_parameter_rescue`；独立 review `P0=0/P1=2/P2=3`、数值正确性置信度 `99%`，`promotion_ready=false`。
- 数值作为反事实实验可信，但历史政策语义不成立；追加 81 行中 37 行在 eval date 前没有非零策略状态，不能作为严格 PIT 原政策重建。
- 候选级 AI 明细已保存到 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage003_append_only_ai_gap_fill_engine/stage013_current_ai_stage003_append_only_ai_gap_fill_engine_ai_candidate_detail_stage003_append_only_ai_gap_fill_engine_v1.csv.gz`。
- 新增回测结果见 `/Users/bytedance/Desktop/person/vnpy/research/lines/futures_trend_stage013_current_ai_revalidation/outputs/stage003_append_only_ai_gap_fill_engine/stage013_current_ai_stage003_append_only_ai_gap_fill_engine_summary_stage003_append_only_ai_gap_fill_engine_v1.csv`；未修改或删除历史结果。

## 过拟合反思

- 运行前：低。只修复确定的数据缺口，参数与门槛预声明，不按结果调月池或 Stage013。
- 运行后：存在政策回填偏差。没有参数扫描，但把后来 12 月训练门槛事后提前到原 720 天 warm-up 期，不可用于晋级。

## 继续价值反思

- 运行前：有。它直接检验 Stage002 改善是否依赖长期 bootstrap 池。
- 运行后：本路线无继续价值，不扩逐半年、不调 `30%/1/1`；Stage002 当前原政策路线仍有价值。
