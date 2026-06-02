# Stage251 年度延续选品卫星仓真实回放审计

- 时间：2026-06-02 02:05 CST
- 研究线：`futures_trend_drawdown30_preserve_return`
- 阶段性质：A/C 部署结构审计；A=`stage526_r080_pc25_maxpos4`，B=年度选品卫星仓 standalone，C=Stage526 核心完全保留 + 年度选品卫星仓。
- 是否重要突破：阶段性是。年度 `prev_year_top6 + risk0.50` 在年度空仓重启语义下机械通过硬不劣化与材料性门槛，但不能直接晋级正式候选，因为该语义没有连续跨年持仓。
- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage551_annual_persistence_sleeve_replay.py`
- 图表：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage551_annual_persistence_sleeve_replay_chart_stage551_annual_persistence_sleeve_replay_v1.png`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage551_annual_persistence_sleeve_replay_report_stage551_annual_persistence_sleeve_replay_v1.md`
- 决策：`annual_persistence_sleeve_promotion_candidate_found`，但仅作为 Stage252 连续动态语义验证的输入。

## 调研判断

- 外部调研参考 AQR 的趋势跟踪长期证据与 Rob Carver `pysystemtrade` 的期货组合工程经验：趋势策略长期依赖跨市场广度、风险预算和相关性治理，而不是单一品种预测。
- GitHub/资料判断：`pysystemtrade` 这类实现强调 instrument diversification multiplier 与相关性/风险预算；本阶段因此不直接放大单品种，而采用 `product_cap15 + maxpos3 + same_direction_corr_gate`。
- 我的判断：用户提出的“减少单笔风险、扩大品种池、每年抓到部分品种趋势”方向有第一性原理基础，但“选对品种”必须按点时已知信息验证，不能用 Oracle6 或全样本赢家。
- 参考：AQR Trend Following 研究页 `https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing`；Rob Carver `pysystemtrade` `https://github.com/robcarver17/pysystemtrade`。

## 版本变更

- 新增脚本：`analyze_qmt_roll_stage551_annual_persistence_sleeve_replay.py`。
- 新增参数：
  - `SLEEVE_CAPITAL=115000`
  - 年度选择模式：`prev_year_positive`、`prev_year_top6`
  - 风险粗档：`risk_multiplier=0.30/0.50`
  - `product_cap_ratio=0.15`
  - `max_concurrent_positions=3`
  - `max_single_trade_capital_usage_ratio=0.30/0.35`
  - 同向相关性门控：`lookback20/start0.60/full0.80/floor0.50`
  - 成本压力：`1x/2x/3x`
- 修改参数：无正式策略参数修改；Stage526 核心不替换。
- 删除参数：无。
- 执行语义：每年用上一年已知的单品种真实账本选品；每年年初卫星仓从空仓启动；核心 Stage526 不动。这是可执行近似，但尚未验证跨年持仓连续动态宇宙。

## 关键结果

| 版本 | 期末权益 | 总收益 | 最大回撤 | Ulcer | Sharpe | broker10最大 | 2x回撤 | 3x回撤 | 卫星PnL | 63日p05改善 | 126日p05改善 | 总滑点 | 总交易次数 | 非零日胜率 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Stage526 | 23,369,505 | 3699.9195% | -36.2670% | 14.4691 | 1.6385 | 99.7299% | -39.0565% | -42.0555% | 0 | 0.0000pp | 0.0000pp | 1,342,190 | 905 | 53.6330% |
| prevpos r030 | 23,355,055 | 3697.5699% | -36.4871% | 14.5084 | 1.6369 | 99.5748% | -39.3026% | -42.3301% | -14,450 | -0.0951pp | -0.1041pp | 1,344,950 | 1,051 | 53.6996% |
| prevpos r050 | 23,413,165 | 3707.0187% | -36.0667% | 14.3738 | 1.6418 | 99.2131% | -38.8688% | -41.8816% | 43,660 | 0.2152pp | 0.1636pp | 1,346,600 | 1,103 | 53.2947% |
| top6 r030 | 23,374,175 | 3700.6789% | -36.2691% | 14.4532 | 1.6388 | 99.4533% | -39.0640% | -42.0687% | 4,670 | 0.0831pp | 0.0186pp | 1,344,580 | 1,041 | 53.9143% |
| top6 r050 | 23,486,940 | 3719.0146% | -36.1021% | 14.3864 | 1.6440 | 99.3864% | -38.8803% | -41.8667% | 117,435 | 0.2555pp | 0.2523pp | 1,346,875 | 1,127 | 53.7077% |

## 图表目检

- 权益曲线：所有 C 曲线与 Stage526 高度贴合，说明卫星仓影响是边际抬升，不是重构主曲线。
- 回撤图：top6 r050 在 2021-2022 水下段略浅，但视觉上只是很小改善。
- 卫星累计PnL：top6 r050 在 2022、2024、2026 拉开；prevpos r030 长期在 0 下方，直接淘汰。
- 年度贡献：top6 r050 的年度选择提示 2021/2022/2024/2025/2026 为正，2023 为负。
- 脆弱点：top6 r050 的单产品最大贡献为 2026 `lu.INE +55,020`，占卫星PnL约 `46.85%`；不过剔除 2026 后卫星PnL仍约 `64,905`，不完全单年驱动。

## 结论

- Stage251 证明：`prev_year_top6 + risk0.50 + pc15 + maxpos3` 不是纯噪音，年度延续选品确实能在低风险卫星仓里补一点收益和左尾体验。
- 但 Stage251 不能直接晋级：年度空仓重启会制造跨年持仓语义偏差，且 3/6个月 p05 改善只有 `0.25pp` 附近，刚压线。
- 后续规划：必须做 Stage252 连续动态宇宙验证；如果连续语义失败，Stage251 降为经验；如果连续语义仍通过，再做 2026/lu 剔除、成本压力和部署材料性复核。

## 反思

- 过拟合反思：本阶段运行前不是过拟合，因为只用上一年已知账本、固定 top6/positive 与粗风险档；运行后若继续围绕 `topN=5/7`、`risk0.45/0.55` 或品种剔除救结果，就会过拟合。
- 继续价值反思：有价值。它首次把“扩池 + 低单笔风险 + 年度选品”落到真实下一窗口引擎并出现正边际，但必须马上用更真实的连续动态语义复核。
