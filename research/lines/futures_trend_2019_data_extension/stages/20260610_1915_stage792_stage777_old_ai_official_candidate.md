# 2026-06-10 19:15 Stage792 / Stage777 + 旧正式 AI 老师升级为官方候选

## 版本改动

- 所属研究线：`futures_trend_2019_data_extension`
- 是否重要突破：是，正式升级为官方候选版本；但不是实盘默认版本。
- 新增候选版本：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`
- 新增配置：`examples/portfolio_backtesting/qmt_roll_official_candidate_stage777_config.py`
- 修改配置：`examples/portfolio_backtesting/qmt_roll_official_live_config.py` 仅新增 `official_candidates` 登记，不修改 `OFFICIAL_LIVE_VERSION`。
- 当前实盘默认：仍为 `official_live_stage372_20w_recovery_sleeve`，即 Stage372 20万 recovery sleeve 口径。
- 正式配置/CTP/下单：不连接 CTP、不调用下单、不切换实盘默认 signal source。

## 候选口径

- 资金：`500,000`
- 策略基底：Stage777，即 Stage775/Stage757 分支上的 `AM41 + OI0.8`
- AI 老师：旧正式 AI 老师池，`ai_top8_plus_fu_satellite_post_signal_entry_filter`
- AI eligibility：`qmt_roll_selection_long015_volref30_corr_fu_candidate_robustness_ai_top8_plus_fu_satellite_post_signal_eligibility.csv`
- 品种池：`static18_plus_fu_universe`
- 基础等效风险：`0.40`
- OI 命中等效风险：命中 `OI上升 + 价格沿交易方向` 后由 `0.40` 恢复到 `0.80`
- 最大持仓：`4`
- 连败缩放：关闭，`streak_risk_multipliers=1.0,1.0,1.0,1.0`
- recovery sleeve：关闭
- AM：研究口径 `research_exact_array_manager_size=41`，`array_manager_size_floor=40`

## 新增结果

本阶段没有新增回测，只做候选固化和官方候选登记；依据来自 Stage777 逐月启动和 Stage791 年度起点抽取。

- Stage777 逐月启动 `2018-01 -> 2026-05`，共 `101` 个起点：
  - 正收益 `96/101`
  - 收益中位数 `170.7890%`
  - p10 收益 `56.2340%`
  - 最小收益 `-7.6440%`
  - 中位最大回撤 `-35.3554%`
  - 最差最大回撤 `-50.1325%`
  - DD40 失败 `47/101`
  - DD50 失败 `1/101`
  - Sharpe 中位数 `1.3341`
  - 总交易次数 `29,862`
- Stage777 成熟逐月启动 `>=252` 交易日，共 `89` 个起点：
  - 正收益 `89/89`
  - 收益中位数 `272.3490%`
  - p10 收益 `83.7680%`
  - 最小收益 `56.2340%`
  - 中位最大回撤 `-43.5538%`
  - 最差最大回撤 `-50.1325%`
  - DD40 失败 `47/89`
  - DD50 失败 `1/89`
- Stage791 年度起点 `2018-01 -> 2026-01`，共 `9` 个起点：
  - 正收益 `8/9`
  - 收益中位数 `179.5130%`
  - 最小收益 `-4.9740%`
  - 最差最大回撤 `-49.4213%`
  - DD40 失败 `4/9`
  - DD50 失败 `0/9`
- Stage791 成熟年度起点 `2018-01 -> 2025-01`，共 `8` 个起点：
  - 正收益 `8/8`
  - 收益中位数 `653.1200%`
  - p10 收益 `83.3988%`
  - 最小收益 `82.3880%`
  - 最大回撤中位数 `-42.0124%`
  - 最差最大回撤 `-49.4213%`

代表年度起点：

| 起点 | 期末权益 | 总收益 | 最大回撤 | Sharpe | 总滑点 | 总交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2018-01` | `18,251,265` | `3550.2530%` | `-49.4213%` | `1.3671` | `1,145,460` | `648` |
| `2019-01` | `21,189,950` | `4137.9900%` | `-49.3661%` | `1.5261` | `1,295,330` | `602` |
| `2022-01` | `1,106,350` | `121.2700%` | `-35.3554%` | `0.7607` | 未新增抽取 | `262` |
| `2026-01` | `475,130` | `-4.9740%` | `-15.5310%` | `-0.1741` | 未新增抽取 | `22` |

胜率说明：本阶段不新增逐笔重跑；Stage791 已保存年度曲线抽取指标，部分年度行含非零日胜率，候选清单暂不把它包装成逐笔胜率。

## 外部调研与判断

- scikit-learn `TimeSeriesSplit` 官方文档强调时间序列验证必须保持时间顺序，支持我们继续把 AI 老师看作 point-in-time/walk-forward selector，而不是把未来 AI 池倒灌回历史。
- 公开 trend-following 研究和 Man Group 对趋势策略历史回撤的讨论都说明，趋势策略的长期右尾通常伴随长回撤和路径依赖；因此 Stage777 的高收益不应被误读成低风险正式替代。
- 我的判断：升级为官方候选是合理的，因为旧老师在 Stage777 target 上明显保留右尾，且 AI-off 被 Stage784 反证；但不能直接升级为实盘默认，因为早期起点最大回撤接近 `-49%`，且 AM41 仍依赖研究 wrapper。

参考：

- scikit-learn TimeSeriesSplit: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Man Group trend-following drawdown discussion: https://www.man.com/insights/is-this-time-different
- Hurst/Ooi/Pedersen trend-following paper: https://fairmodel.econ.yale.edu/ec439/hurst.pdf

## 决策

- 决策：`Stage777 + 旧正式 AI 老师` 升级为官方候选版本。
- 不切换：当前官方实盘默认仍为 Stage372 20万 `official_live_stage372_20w_recovery_sleeve`。
- 不继续扫参：不因本次升级继续扫 `OI 0.7/0.8/0.9/1.0`、`AM 40/41/80/120`、AI topN、训练窗、horizon 或连败阈值。

## 后续规划和 TODO

- 为候选版本补一条独立 shadow/dry-run 入口，明确与 Stage372 live shadow 隔离。
- 若要进一步向实盘推进，必须先做最新日线 fresh shadow、执行 dry-run、下单映射和对账检查。
- 对 `AM41` 做工程化整理：如果候选要进入实盘，不应长期依赖研究脚本里的 `QmtRollPortfolioStrategyExactAm` wrapper。
- 做风险委员会口径说明：这是高收益高回撤候选，回撤容忍度不能用 Stage372 20万防守口径混同。

## 反思

- 开始前过拟合反思：不是直接过拟合，因为本次不调参数，只把已验证口径固化为候选；但候选自身仍有中等偏高过拟合/路径依赖风险，主要来自 `AM41 + OI0.8` 在 2022 回撤和早期起点 DD40 高失败率。
- 结束后过拟合反思：没有新增参数搜索，过拟合风险没有被放大；但如果下一步继续围绕这条线扫 OI 倍率、AM 根数或 AI topN，就是过拟合。
- 开始前继续价值反思：有价值，因为旧老师明显强于新老师和 AI-off，是目前 Stage777 系列最有候选价值的固定口径。
- 结束后继续价值反思：有价值继续做工程候选治理和 shadow，但不建议继续做小参数优化；下一步应验证“能否可执行、能否承受回撤”，不是继续找更好看的历史曲线。
