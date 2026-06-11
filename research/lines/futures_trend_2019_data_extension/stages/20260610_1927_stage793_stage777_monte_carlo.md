# 2026-06-10 19:27 Stage793 / Stage777 官方候选 Monte Carlo 路径压力测试

## 版本改动

- 所属研究线：`futures_trend_2019_data_extension`
- 是否重要突破：是，完成 Stage792 官方候选的路径风险压力测试。
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage793_stage777_monte_carlo.py`
- 修改策略参数：无。
- 修改正式配置：无。
- 当前实盘默认：仍为 `official_live_stage372_20w_recovery_sleeve`，未切换 Stage777。
- 新增参数：
  - Monte Carlo `N_SIMS=10,000`
  - bootstrap 方法：`iid`、`block_20`、`block_60`、`block_120`
  - fan chart 抽样路径：`2,000`
  - 同期对照截止：`2026-04-30`
- 删除参数：无。
- 正式配置/CTP/下单：不连接 CTP、不调用下单、不切换 live default。

## 实验口径

本阶段不新增回测，只使用已有权益曲线做路径重采样和坏块压力测试。

- 候选：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`
  - 50万、`AM41`、基础风险 `0.40`、命中 `OI上升 + 价格沿方向` 恢复到 `0.80`、旧正式 AI 老师。
- 对照：当前官方 Stage372 20万逐月启动审计结果，即 `qmt_roll_stage744_official_monthly_start_audit`。
- 场景：
  - `candidate_2018_01_full`：Stage777 候选 2018-01 起点，至 `2026-05-29`。
  - `candidate_2020_01_common`：Stage777 候选 2020-01 起点，截到 `2026-04-30`，与 Stage372 同期。
  - `candidate_2022_01_common`：Stage777 候选 2022-01 起点，截到 `2026-04-30`。
  - `official_2020_01_common`：Stage372 2020-01 起点，至 `2026-04-30`。
  - `official_2022_01_common`：Stage372 2022-01 起点，至 `2026-04-30`。

## 新增结果

历史源路径：

| 场景 | 历史总收益 | 历史最大回撤 | 历史 Sharpe | 最差峰值日期 | 最差谷值日期 | 坏块天数 |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| `candidate_2018_01_full` | `3550.2530%` | `-49.4213%` | `1.3675` | `2022-03-09` | `2022-06-29` | `75` |
| `candidate_2020_01_common` | `2575.0800%` | `-49.1145%` | `1.5060` | `2022-03-09` | `2022-06-29` | `75` |
| `candidate_2022_01_common` | `132.9340%` | `-35.3554%` | `0.8089` | `2022-03-09` | `2022-06-29` | `75` |
| `official_2020_01_common` | `4264.1425%` | `-38.6713%` | `1.6284` | `2022-03-09` | `2022-12-07` | `184` |
| `official_2022_01_common` | `133.8550%` | `-28.0550%` | `0.8899` | `2022-01-04` | `2023-01-05` | `245` |

关键 Monte Carlo 结果，以下均为 `10,000` 条路径：

| 场景 | 方法 | p5收益 | p50收益 | p5最大回撤 | p50最大回撤 | 期末低于本金概率 | DD40概率 | DD50概率 | DD60概率 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `candidate_2018_01_full` | `block_60` | `436.6450%` | `3436.6525%` | `-63.4706%` | `-43.6202%` | `0.05%` | `64.67%` | `27.11%` | `7.95%` |
| `candidate_2018_01_full` | `block_120` | `399.9840%` | `3403.8259%` | `-61.2158%` | `-48.8269%` | `0.08%` | `68.82%` | `27.01%` | `5.95%` |
| `candidate_2020_01_common` | `block_60` | `340.4548%` | `2546.4093%` | `-62.8331%` | `-43.1775%` | `0.11%` | `63.32%` | `26.32%` | `7.34%` |
| `candidate_2020_01_common` | `block_120` | `376.0542%` | `2516.6436%` | `-59.2846%` | `-46.7506%` | `0.10%` | `63.58%` | `22.98%` | `4.45%` |
| `official_2020_01_common` | `block_60` | `583.4711%` | `4135.5293%` | `-53.3205%` | `-37.8753%` | `0.00%` | `39.74%` | `8.84%` | `1.20%` |
| `official_2020_01_common` | `block_120` | `610.2937%` | `4169.7554%` | `-49.6807%` | `-36.8440%` | `0.02%` | `32.12%` | `4.64%` | `0.29%` |

2022 起点压力：

- `candidate_2022_01_common`：
  - `block_60` p5 收益 `-21.3961%`，p50 收益 `128.1308%`，DD50 概率 `16.35%`，期末低于本金概率 `10.36%`。
  - `block_120` p5 收益 `-19.5958%`，p50 收益 `127.1477%`，DD50 概率 `15.22%`，期末低于本金概率 `9.47%`。
- `official_2022_01_common`：
  - `block_60` p5 收益 `-15.6082%`，p50 收益 `124.3048%`，DD50 概率 `3.96%`，期末低于本金概率 `8.88%`。
  - `block_120` p5 收益 `-26.1295%`，p50 收益 `121.6343%`，DD50 概率 `8.16%`，期末低于本金概率 `12.55%`。

坏块前置压力测试：

| 场景 | 压力方式 | 总收益 | 最大回撤 | 最低净值 | 水下天数 |
| --- | --- | ---: | ---: | ---: | ---: |
| `candidate_2018_01_full` | 坏块前置一次 | `1841.0501%` | `-57.4836%` | `0.3961` | `750` |
| `candidate_2018_01_full` | 坏块前置两次 | `792.9059%` | `-78.4958%` | `0.2003` | `931` |
| `candidate_2018_01_full` | 坏块放大1.5倍前置 | `1239.5291%` | `-69.5313%` | `0.2733` | `809` |
| `candidate_2020_01_common` | 坏块前置一次 | `1254.7361%` | `-49.2864%` | `0.4722` | `296` |
| `candidate_2020_01_common` | 坏块前置两次 | `531.3482%` | `-74.1941%` | `0.2403` | `468` |
| `candidate_2020_01_common` | 坏块放大1.5倍前置 | `838.5834%` | `-63.5051%` | `0.3272` | `369` |
| `official_2020_01_common` | 坏块前置一次 | `2272.5843%` | `-43.7867%` | `0.5054` | `400` |
| `official_2020_01_common` | 坏块前置两次 | `517.9005%` | `-65.5251%` | `0.3100` | `681` |
| `official_2020_01_common` | 坏块放大1.5倍前置 | `1728.4773%` | `-54.0267%` | `0.3895` | `455` |

输出：

- Monte Carlo 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage793_stage777_monte_carlo_summary_stage793_stage777_monte_carlo_v1.csv`
- 坏块压力：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage793_stage777_monte_carlo_bad_block_stress_stage793_stage777_monte_carlo_v1.csv`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage793_stage777_monte_carlo_report_stage793_stage777_monte_carlo_v1.md`
- 图：
  - `qmt_roll_stage793_stage777_monte_carlo_dd_probability_stage793_stage777_monte_carlo_v1.png`
  - `qmt_roll_stage793_stage777_monte_carlo_fan_chart_stage793_stage777_monte_carlo_v1.png`
  - `qmt_roll_stage793_stage777_monte_carlo_bad_block_stress_stage793_stage777_monte_carlo_v1.png`

## 外部调研与判断

- 公开交易系统 Monte Carlo 资料普遍把 trade/return reshuffle 用于估计回撤、亏损簇和资金需求；但趋势策略有自相关和状态依赖，单日 iid 重排会低估路径风险。
- 因此本阶段主判断使用 `block_60/block_120`，保留连续趋势/反转窗口；`iid` 只作为下限参考。
- Bailey/Lopez de Prado 的 backtest overfitting/Deflated Sharpe 框架提醒，多版本研究后挑出的候选需要承认选择偏差。本阶段没有把 MC 结果当作 alpha 证明，只把它作为候选生存性否证。

参考：

- scikit-learn TimeSeriesSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Bailey/Lopez de Prado DSR: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551
- Man Group 趋势回撤讨论: https://www.man.com/insights/is-this-time-different

## 决策

- Stage777 + 旧老师仍保留为官方候选，因为收益右尾和 p5 收益仍强，Monte Carlo 下期末低于本金概率很低。
- 但它不是低回撤部署口径：
  - 候选 `2020` 同期 `block_60/block_120` 的 DD50 概率约 `26.32%/22.98%`；
  - 当前 Stage372 `2020` 同期约 `8.84%/4.64%`。
- 不支持直接切换 live default。
- 若要推进，只能在“高风险候选”框架下推进，例如独立资金 sleeve、显式回撤容忍度、外层风险预算或 forward shadow；不能把它包装成 Stage372 的防守替代。

## 反思

- 开始前过拟合反思：否，本阶段是路径重采样和压力测试，不调策略参数。
- 结束后过拟合反思：否，实验没有用结果反向改规则；但如果接下来为了降低 `DD50` 概率去扫 OI 倍率、AM 根数或 topN，就是过拟合。
- 开始前继续价值反思：有价值，因为候选刚升官方候选，必须验证路径生存性。
- 结束后继续价值反思：有价值继续做候选治理，但价值方向不是优化参数，而是风险分层、shadow、独立 sleeve 和执行可行性。
