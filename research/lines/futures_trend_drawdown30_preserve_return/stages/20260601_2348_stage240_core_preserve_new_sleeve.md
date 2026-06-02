# Stage240 核心不替换的新产品卫星仓审计

- line_id：`futures_trend_drawdown30_preserve_return`
- 当前模式：`day`
- 记录时间：2026-06-01 23:48 CST
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy`
- 阶段性质：A/C 部署结构审计；A 为 Stage526 控制组，B 为新增品种卫星仓 standalone，C 为 Stage526 核心完全保留 + 新品种卫星仓。
- 是否重要突破：否；方向被验证为结构上合理，但当前 new5 样本只产生微弱增益，不足以晋级。
- 是否触发A/B：是；涉及可能接入正式候选的产品池/资金 sleeve 结构，已按 `skills/version-ab-experiment/SKILL.md` 预声明 A/C 与晋级边界。

## 外部调研与判断

- 参考资料：
  - AQR《A Century of Evidence on Trend-Following Investing》：跨资产/跨市场趋势跟随的长期证据支持“广泛分散”。
  - AQR Time-Series Momentum 原始论文数据页：时间序列动量天然依赖多市场样本，单市场或少数市场会暴露路径集中风险。
  - SSRN《Trend Following with Managed Futures: The Search for Crisis Alpha》：管理期货趋势收益来自跨品种、跨宏观状态的分散趋势捕捉，但需要成本与相关性风险约束。
- 我的判断：
  - “降低单笔风险 + 扩大品种池”方向不是错的，但不能让新增品种和核心 `jm/OI/ru/lh` 等趋势腿竞争持仓槽位，否则会像 Stage539 一样错过主收益。
  - 低过拟合做法应该是：核心仓不动，新增品种只用独立低资金 sleeve 表达，并设置事前相关性/单品种 cap；如果 sleeve 自己赚不到足够的钱，就不能为了“分散”而加复杂度。
  - 本阶段不按历史赢家挑产品，不做产品黑名单，也不调 `risk=0.51/0.52` 这类小数。

## 本次变更

- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage540_core_preserve_new_sleeve.py`
- 修改脚本：同上，初跑后新增材料性晋级门槛，避免把 5000 元级别的微小硬通过误判成可晋级 alpha。
- 删除脚本：无
- 新增参数：
  - 新品种 sleeve 资金：`115000`
  - 新品种池：结构预筛产品剔除 Stage526 实际核心持仓产品后得到 `TA.CZCE/UR.CZCE/eb.DCE/pg.DCE/sn.SHFE`
  - A：`stage526_r080_pc25_maxpos4`
  - C1：`core_plus_new5_r030_pc15_maxpos2`
  - C2：`core_plus_new5_r050_pc15_maxpos2`
  - C3：`core_plus_new5_r050_pc10_maxpos3`
  - 同向相关性门控：`lookback=20/start=0.60/full=0.80/floor=0.50`
  - 晋级材料性门槛：卫星仓 PnL 至少 `1%` 账户资金或 `10%` sleeve 资金，且 63/126 日 p05 收益各改善不少于 `0.25pp`
- 修改参数：无交易 alpha 修改；只在审计脚本中补材料性门槛。
- 删除参数：无

## 回测/归因参数

- 数据区间：2020-01-02 至 2026-04-30，使用既有完整真实下一窗口成交口径。
- 账户规模：总账户 `615000`；Stage526 核心保持 `500000 C3 + xsmom true carry`；new5 sleeve 只用 `115000` 作为 sizing/base。
- 成本口径：正常滑点、2x、3x 成本压力。
- 样本过滤：new5 来自 Stage539 之前的结构预筛，不按本阶段收益再筛。
- 策略/归因口径：核心 Stage526 不替换、不重排、不被新增品种挤占；C 账户权益为 `615000 + cumsum(core_total_net_pnl + satellite_net_pnl)`，保证金为核心 exact margin + satellite exact margin。

## 结果

### A/C 账户结果

| 版本 | 期末权益 | 总收益 | 相对Stage526 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 2x DD | 3x DD | 卫星PnL | 滑点 | 交易次数 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 control | 23,369,505 | 3699.9195% | 100.0000% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | -39.0565% | -42.0555% | 0 | 1,342,190 | 905 |
| C1 r030 pc15 maxpos2 | 23,374,195 | 3700.6821% | 100.0206% | -36.1715% | 14.4398 | 1.6385 | 99.1929% | -38.9717% | -41.9832% | 4,690 | 1,344,100 | 1,014 |
| C2 r050 pc15 maxpos2 | 23,374,985 | 3700.8106% | 100.0241% | -36.1971% | 14.4421 | 1.6386 | 99.4192% | -38.9908% | -41.9958% | 5,480 | 1,343,810 | 966 |
| C3 r050 pc10 maxpos3 | 23,370,265 | 3700.0431% | 100.0033% | -36.2499% | 14.4708 | 1.6378 | 99.6536% | -39.0439% | -42.0486% | 760 | 1,343,040 | 946 |

### 3/6个月持有体验

| 版本 | 63日p05 | 63日中位 | 126日p05 | 126日中位 | 判断 |
| --- | ---: | ---: | ---: | ---: | --- |
| Stage526 control | -18.2169% | 14.2303% | -10.9700% | 27.5593% | 基准 |
| C1 r030 pc15 maxpos2 | -18.1310% | 14.2175% | -11.0060% | 27.5232% | 63日左尾略好，126日左尾略差 |
| C2 r050 pc15 maxpos2 | -18.1735% | 14.2139% | -10.9437% | 27.5130% | 两个p05都略好，但改善仅 `0.0435pp/0.0263pp`，中位收益略降 |
| C3 r050 pc10 maxpos3 | -18.2063% | 14.2263% | -10.9636% | 27.5479% | 几乎无差异 |

### B卫星仓 standalone

| 版本 | sleeve期末 | sleeve收益 | sleeve最大回撤 | Sharpe | 交易 | 滑点 | 最大保证金 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| C1 r030 pc15 maxpos2 | 119,690 | 4.0783% | -13.8398% | 0.1257 | 109 | 1,910 | 31,182 |
| C2 r050 pc15 maxpos2 | 120,480 | 4.7652% | -14.6377% | 0.1425 | 61 | 1,620 | 29,337 |
| C3 r050 pc10 maxpos3 | 115,760 | 0.6609% | -6.3006% | 0.0472 | 41 | 850 | 17,986.5 |

### 年度归因

- C2 最佳卫星仓年度 PnL：2020 `-2,755`、2021 `+12,740`、2022 `0`、2023 `0`、2024 `0`、2025 `-4,505`、2026 `0`。
- C1 年度 PnL：2020 `-2,370`、2021 `+23,760`、2022 `-13,605`、2023 `0`、2024 `0`、2025 `-3,095`、2026 `0`。
- 这不符合“每年都能抓到部分新品种趋势收益”的要求：new5 主要只在 2021 年贡献，随后多年基本不交易或不赚钱。

## 图表视觉复盘

- 权益曲线：三条 C 账户线几乎与 Stage526 重合，肉眼无法看出独立收益层，说明新增 sleeve 不是主收益来源。
- 回撤曲线：C1/C2 回撤略浅，但差异非常细；没有改变 2021-2022 深水区的风险形状。
- 卫星累计 PnL：收益主要集中在 2021 年，2022 后大多横盘，2025 还有小亏；不是稳定年度收割。
- 3/6个月 p05：C2 两项都略好，但改善只有 `0.0435pp/0.0263pp`，远低于材料性门槛；中位收益反而略低。

## 输出文件

- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_report_stage540_core_preserve_new_sleeve_v1.md`
- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_summary_stage540_core_preserve_new_sleeve_v1.csv`
- daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_combined_daily_stage540_core_preserve_new_sleeve_v1.csv`
- satellite daily：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_satellite_daily_stage540_core_preserve_new_sleeve_v1.csv`
- satellite standalone：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_satellite_standalone_stage540_core_preserve_new_sleeve_v1.csv`
- satellite product：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_satellite_product_harvest_stage540_core_preserve_new_sleeve_v1.csv`
- rolling：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_rolling_holding_stage540_core_preserve_new_sleeve_v1.csv`
- cost：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_cost_stress_stage540_core_preserve_new_sleeve_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_decision_stage540_core_preserve_new_sleeve_v1.json`
- chart：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage540_core_preserve_new_sleeve_chart_stage540_core_preserve_new_sleeve_v1.png`

## 结论

- 本阶段结论：`core_preserve_new_sleeve_micro_pass_not_promotion`。
- 是否进入下一步：不作为晋级版本；不继续扫 new5 sleeve 的风险倍率、product cap 或 maxpos 小数。
- 下一步：
  - 保留“核心不替换、卫星不挤占、事前相关性预算”的结构原则。
  - 当前 new5 不能证明“扩大品种池后每年都有稳定趋势收益”；若继续品种选择，应转向更强的事前结构筛选或真实监控积累，而不是继续在同一 new5 上调参。
  - Stage526 仍是正常成本主候选；Stage540 只作为产品选择方向的反证/微弱正线索。

## 过拟合反思

- 运行前判断：否。原因是只验证结构假设，核心不替换，新增品种来自既有结构预筛，且只跑 3 个粗档。
- 运行后判断：不晋级是为了进一步避免过拟合。C2 虽然硬不劣化，但改善太小，且收益集中在 2021 年，若据此继续细调风险/cap/maxpos，很容易过拟合。
- 原因：真正可穿越周期的品种选择应带来可见、可复验、跨年度的新增趋势捕捉，而不是 5000 元级别的路径噪声。

## 继续价值反思

- 运行前判断：有价值。Stage539 已证明“核心被扩池挤掉”是主要失败机制，非挤占式 sleeve 是必要反证。
- 运行后判断：同一 new5 sleeve 继续调参价值低；但“选对品种是关键”的研究方向仍有价值。
- 原因：本阶段证明结构方式正确但品种集合不够强；后续若继续，应改变品种选择证据来源，例如更长 OOS、成交活跃度/趋势效率/产业基本面共振的事前打分，而不是在当前输出上扫参数。

## 合入建议

- 是否更新本线 `LINE.md`：是，追加 Stage240 结论。
- 是否更新 `research/registry.md`：是，当前研究线最新阶段更新为 Stage240。
- 是否追加根目录 `memory.md/back_log.md`：追加 `back_log.md` 重要摘要；`memory.md` 不追加，因为没有形成长期执行规则或正式候选替换。
