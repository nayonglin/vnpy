# Stage007 / Script750 A50正式版50万逐月启动 vs C50

## 版本改动

- 改动时间：`2026-06-09 11:25 CST`。
- 是否重要突破：否，属于重要负结论和资金口径澄清。
- 新增脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage750_official_500k_vs_c50_monthly_start.py`。
- 修改正式策略：无。
- 新增参数：`MODEL_TAG=stage750_official_500k_vs_c50_monthly_start_v1`、`A50_VARIANT=stage526_500k_force95_to80_recovery_sleeve_r080_pc25_maxpos4_stage750`、`MAX_WORKERS=4`。
- 修改参数：A50 只把当前正式 Stage372 逻辑的 `account_capital/c3_capital` 改为 `500,000`，保留 `risk_multiplier=0.80`、三连败 `1,1,1,0.1`、`recovery_sleeve`、AI池、`maxpos4`、broker10 `95%->80%` 强制减仓；C50 复用 Stage748，`account_capital/c3_capital=500,000`、`risk_multiplier=0.40`、关闭连败缩放与 recovery sleeve。
- 删除参数：无。
- 正式配置/CTP/下单：不改正式配置、不连接 CTP、不调用下单。

## 外部调研判断

- 多起点 / walk-forward 类验证用于处理单一起点美化和起点耦合；这次实验不优化参数，只把启动月份从 `2020-01` 滚动到 `2026-04` 做独立启动验证。
- 固定比例风险 sizing 在期货上会受到最小合约手数影响，20万和50万账户的可开仓颗粒度不同；因此必须做 A50 vs C50，不能只拿正式 A20 vs C50 下结论。
- GitHub 侧检索到的开源 walk-forward/backtest 项目也以多窗口、样本外和参数稳定性为核心验证框架，未看到能支持“单一资金曲线或少数启动月份更平滑即可替换主策略”的证据。
- 本阶段判断：不是过拟合式扫参，而是在拆除“正式版20万 vs C50 50万”的资金混杂项。参考资料：walk-forward/双样本验证思路 `https://arxiv.org/abs/2602.10785`；固定比例和期货合约手数口径 `https://nexusfi.com/a/risk-management/position-sizing`；GitHub walk-forward 主题和示例 `https://github.com/topics/walk-forward-analysis`。

## 回测参数

- 起点范围：`2020-01` 至 `2026-04`，共 `76` 个逐月独立启动。
- 统一终点：`2026-04-30`。
- A50：正式 Stage372 逻辑，50万资金口径。
- C50：Stage748 `0.40` 风险倍率、关闭连败缩放、关闭 recovery sleeve、50万资金口径。
- A20：Stage744 当前正式20万逐月启动结果，仅用于本金颗粒度对照。

## 新增结果

- 决策：`official_500k_vs_c50_monthly_start_c50_not_promoted`。
- 硬失败项：`mature252_c50_return_wins_lt45pct`、`mature252_median_return_delta_negative`。
- 观察失败项：`mature252_c50_dd40_fail_more_than_a50`、`all_c50_both_wins_not_more_than_a50_both_wins`。
- `2020-01` 起点 A50：期末权益 `21,371,670`，总收益 `4174.3340%`，最大回撤 `-39.7236%`，Sharpe `1.6218`，总滑点 `1,161,790`，总交易次数 `677`，胜率 `52.8954%`，broker10 峰值 `80.7186%`，强制减仓 `7` 次 / `795` 手。
- `2020-01` 起点 C50：期末权益 `5,565,350`，总收益 `1013.0700%`，最大回撤 `-39.7082%`，Sharpe `1.3285`，总滑点 `470,250`，总交易次数 `686`，胜率 `52.7165%`，broker10 峰值 `74.8301%`，强制减仓 `3` 次 / `229` 手。
- 全体 `76` 个起点：C50 收益胜出 `6/76`，回撤胜出 `48/76`，收益和回撤同时胜出 `5/76`；A50 收益和回撤同时胜出 `27/76`。C50 正收益 `67/76`，A50 正收益 `72/76`；C50 DD30 失败 `27/76`，A50 DD30 失败 `27/76`；C50 DD40 失败 `5/76`，A50 DD40 失败 `2/76`。C50-A50 收益差中位数 `-143.2740pp`，收益保留中位数 `50.6167%`，回撤改善中位数仅 `+0.5285pp`。
- 成熟 `>=252` 交易日样本 `64` 个：C50 收益胜出 `3/64`，回撤胜出 `42/64`，收益和回撤同时胜出 `3/64`；A50 收益和回撤同时胜出 `22/64`。C50 与 A50 均 `64/64` 正收益；C50 DD40 失败 `5/64`，A50 DD40 失败 `2/64`；C50-A50 收益差中位数 `-190.8690pp`，收益保留中位数 `50.6167%`，回撤改善中位数 `+0.5285pp`。
- 年份结构：`2020` 起点 C50 收益胜出 `0/12`、收益差中位数 `-3069.3200pp`；`2021` 为 `0/12`、`-669.7420pp`；`2022` 为 `1/12`、`-200.3180pp`；`2023` 为 `0/12`、`-102.6065pp`；`2024` 为 `2/12`、`-12.1475pp`；`2025` 为 `1/12`、`-12.2450pp`；`2026` 短样本为 `2/4`、`-0.3610pp`。
- A50 vs A20 资金颗粒度对照：A50 收益胜出 `57/76`，收益差中位数 `+62.9365pp`，交易数中位数多 `42`；成熟 `>=252` 样本 A50 收益胜出 `51/64`，收益差中位数 `+109.5108pp`，交易数中位数多 `45`。说明 50万本金改善的不只是 C，正式逻辑同样受益。

## 输出文件

- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_summary_stage750_official_500k_vs_c50_monthly_start_v1.csv`
- 检查项：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_checks_stage750_official_500k_vs_c50_monthly_start_v1.csv`
- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_report_stage750_official_500k_vs_c50_monthly_start_v1.md`
- 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_chart_stage750_official_500k_vs_c50_monthly_start_v1.png`
- 热力图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_heatmap_stage750_official_500k_vs_c50_monthly_start_v1.png`
- A50 vs A20 图：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage750_official_500k_vs_c50_monthly_start_a20_chart_stage750_official_500k_vs_c50_monthly_start_v1.png`

## 结论与后续

- C50 不是“更合理的正式替代”。同样 50万资金口径下，它的收益胜率从上一轮相对 A20 的 `23/76` 降到相对 A50 的 `6/76`，成熟样本仅 `3/64`；这说明上一轮 C50 看起来更平滑，核心不是它更会选机会，而是它有资金颗粒度优势且风险更低。
- A50 说明正式版自身也受 20万整数手颗粒度影响；资金放到 50万后，正式逻辑的收益胜率相对 A20 为 `57/76`，成熟样本 `51/64`。因此“C50 更合理”被公平对照反证，真正更强的是正式逻辑在更大账户下能保留右尾复利。
- C50 的价值仅限低弹性参考或独立保守 sleeve，不应替换主策略；固定低风险 + 关闭连败机制路线应停止继续扫风险倍率、本金或年份补丁。
- 后续如果继续追求低回撤体验，应转向账户层资金分层、出金/锁盈、生存线、独立 sleeve 或外生 selector，而不是改主策略连败/风险倍率。

## 反思

- 过拟合反思：运行前不是过拟合，因为只做资金口径公平拆分和逐月启动验证，没有新增交易规则或按结果调参；运行后也不把 `2024/2026` 少数绿格拿来救 C50，否则会变成年份窗口拟合。
- 继续价值反思：本阶段有价值，已经拆清“20万资金颗粒度”和“关闭连败低风险壳”的混杂；但本研究路线继续救 C50 已无价值，应该停止。
