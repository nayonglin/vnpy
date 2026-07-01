# Stage153 当前重建版逐年起点多周期回测到今天

- line_id：`futures_trend_stage819_intraday_rules`
- 当前模式：`day`
- 记录时间：`2026-06-30 23:32 CST`
- 工作区/分支：`/Users/bytedance/Desktop/person/vnpy` / `master`
- 阶段性质：按用户要求，对当前重建版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once` 做从 2018 年开始、起点间隔 1 年、统一终点为今天的多周期回测与曲线绘制
- 是否重要突破：否
- 是否触发A/B：否

## 外部调研与判断

- 参考资料：本轮按用户此前“不要搜索”的约束不做外网/GitHub搜索；使用本仓现有 official live wrapper、Stage901 C9 live runner、Stage153 新增年度起点脚本。
- 我的判断：这次回测能作为“当前重建版”的路径风险基准，但不能证明其等同于删除前旧正式版；旧版 1:1 仍需 Stage53/Stage67/Stage149 输入链恢复。

## 本次变更

- 新增脚本：
  - `examples/portfolio_backtesting/analyze_qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630.py`
  - `examples/portfolio_backtesting/visualize_qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630.py`
- 修改脚本：无
- 删除脚本：无
- 新增参数：年度起点 `Jan 1 every year`，请求终点 `2026-06-30`
- 修改参数：无策略参数修改；复用当前 official live override
- 删除参数：无

## 回测/归因参数

- 数据区间：请求起点 `2018-01-01` 起，每年 `1月1日` 一个独立冷启动起点；请求结束日统一 `2026-06-30`
- 实际结束日：全部样本实际结束日均为 `2026-06-30`
- 账户规模：`150,000`
- 成本口径：沿当前 Stage847/C9 live wrapper 原始配置，不改滑点
- 样本过滤：年度起点 `9` 个，`2018-01` 至 `2026-01`
- 策略/归因口径：当前重建版 `official_live_stage847_c9_15w_stage819_05r_stop_retry_once`，Stage182 当前月度 AI 池，C9 entry-day `0.5R` stop/retry-once；不连接 CTP，不读取账户，不调用订单 API

## 结果

- 样本数：`9`
- 正收益：`9/9`
- 期末权益最低/中位/最高：`152,851.60 / 339,299.00 / 13,776,968.70`
- 总收益最低/中位/最高：`1.9011% / 126.1993% / 9084.6458%`
- 收益最差起点：`2026-01`
- 收益最好起点：`2019-01`
- 最大回撤最差：`-56.2069%`，来自 `2018-01`
- 最大回撤中位：`-39.9820%`
- Sharpe 最低/中位/最高：`0.2860 / 1.2246 / 1.4786`
- peak broker10 margin/equity：`96.6295%`
- broker100 失败：`0`
- 总滑点合计：`4,281,170`
- 总交易次数合计：`3,531`
- 日非零收益胜率中位：`52.6749%`
- DD30/DD40/DD50 失败数：`5 / 4 / 4`

### 起点明细

| 起点 | 实际起点 | 实际终点 | 交易日 | 期末权益 | 总收益 | 最大回撤 | Sharpe | broker10峰值 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `2018-01` | `2018-01-02` | `2026-06-30` | `2058` | `12,857,154.10` | `8471.4361%` | `-56.2069%` | `1.3510` | `91.4950%` |
| `2019-01` | `2019-01-02` | `2026-06-30` | `1815` | `13,776,968.70` | `9084.6458%` | `-55.7845%` | `1.4786` | `96.6295%` |
| `2020-01` | `2020-01-02` | `2026-06-30` | `1571` | `5,979,281.00` | `3886.1873%` | `-55.3701%` | `1.3959` | `88.3398%` |
| `2021-01` | `2021-01-04` | `2026-06-30` | `1328` | `2,395,239.80` | `1496.8265%` | `-54.3180%` | `1.2859` | `80.7461%` |
| `2022-01` | `2022-01-04` | `2026-06-30` | `1085` | `323,799.00` | `115.8660%` | `-39.9820%` | `0.6772` | `64.5100%` |
| `2023-01` | `2023-01-03` | `2026-06-30` | `843` | `338,069.40` | `125.3796%` | `-24.4690%` | `0.9137` | `59.9696%` |
| `2024-01` | `2024-01-02` | `2026-06-30` | `601` | `339,299.00` | `126.1993%` | `-22.5622%` | `1.2246` | `55.8731%` |
| `2025-01` | `2025-01-02` | `2026-06-30` | `359` | `198,567.40` | `32.3783%` | `-22.6508%` | `0.7362` | `56.9317%` |
| `2026-01` | `2026-01-05` | `2026-06-30` | `116` | `152,851.60` | `1.9011%` | `-14.7303%` | `0.2860` | `51.5137%` |

## 输出文件

- summary：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_summary_stage153_c9_live_15w_annual_starts_to_20260630_v1.csv`
- stats：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_stats_stage153_c9_live_15w_annual_starts_to_20260630_v1.csv`
- curves：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_curves_stage153_c9_live_15w_annual_starts_to_20260630_v1.csv`
- decision：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_decision_stage153_c9_live_15w_annual_starts_to_20260630_v1.json`
- report：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_report_stage153_c9_live_15w_annual_starts_to_20260630_v1.md`
- dashboard：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage153_c9_live_15w_annual_starts_to_20260630_dashboard_stage153_c9_live_15w_annual_starts_to_20260630_v1.png`

## 结论

- 本阶段结论：当前重建版逐年起点到 `2026-06-30` 全部正收益，但左尾回撤仍重；早期起点 `2018-2021` 最大回撤均超过 `-54%`，更像高进攻、高波动版本，而不是低回撤实盘舒适版本。
- 是否进入下一步：是
- 下一步：把本结果作为当前重建版路径风险基准；继续优先恢复/锁定 Stage53/Stage67/Stage149 输入链和关键产物 hash。不要因为本次 9/9 正收益去扫 AI 池、R 倍数、重试次数或年份窗口。

## 过拟合反思

- 运行前判断：否
- 运行后判断：否
- 原因：起点间隔、结束日、资金和 live profile 均由用户请求和当前官方配置固定；本次只是多起点冷启动回测，不调策略参数、不按结果筛窗口。

## 继续价值反思

- 运行前判断：是
- 运行后判断：是
- 原因：结果能给当前重建版一个行为风险基准，尤其确认全部实际终点到 `2026-06-30` 且 broker100 未破；但它不能替代旧正式版 1:1 复原验证。

## 合入建议

- 是否更新本线 `LINE.md`：暂不更新；等待当前重建版回测、AI池复原、Stage149恢复结论统一整理
- 是否更新 `research/registry.md`：否
- 是否追加根目录 `memory.md/back_log.md`：否
