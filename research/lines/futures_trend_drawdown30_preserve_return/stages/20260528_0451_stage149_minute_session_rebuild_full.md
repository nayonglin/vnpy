# Stage149 全量分钟会话执行账本重建

- 研究线：`futures_trend_drawdown30_preserve_return`
- 时间：2026-05-28 04:51 CST
- 工作模式：`day`
- 是否重要突破：是。Stage148 的高优先级样本错位被扩展到全量 Stage443 订单宇宙，确认这是系统性执行口径问题。
- 是否触发 A/B：否。本阶段不新增候选策略、不修改 Stage079/C3/Stage103 规则，只重建执行代理数据。
- 决策标签：`session_proxy_mismatch_confirmed_extend_full_rebuild`

## 外部调研与判断

- TqSdk 官方文档支持通过 `TqBacktest + get_kline_serial(..., duration_seconds=60)` 回放历史1分钟K，本阶段采用该路径作为可执行数据通路。
- TqSdk `DataDownloader(dur_sec=60)` 在 Stage145 已被账户专业版权限阻断；这不是分钟线不可得，而是下载接口权限问题。
- xtquant 官方 native API 依赖 MiniQMT/本地行情环境，前序本地 `xtdata` 导入失败，因此本阶段不依赖 QMT 分钟数据。
- 判断：当前最值得晋级的不是新 alpha 候选，而是“分钟会话执行 ledger 重建”这条工程/研究前置。没有这个账本，3个月/6个月持有体验优化会建立在错误成交价格上。

参考：

- TqSdk 文档：<https://tqsdk-python.readthedocs.io/>
- TqSdk 回测免责声明：<https://www.shinnytech.com/blog/disclaimer/>
- xtquant native API：<https://dict.thinktrader.net/nativeApi/start_now.html>

## 本阶段改动

- 修改脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage448_minute_session_rebuild_batch.py`
- 新增环境变量覆盖：
  - `STAGE448_MODEL_TAG`
  - `STAGE448_OUTPUT_PREFIX`
  - `STAGE448_RAW_SUBDIR`
- 新增报告字段：
  - `preferred_real_open_cash_delta_vs_same_close_valid_same_close`
  - `same_last5_cash_delta_vs_same_close_valid_same_close`
- 新增/修改参数：仅执行审计参数，非策略参数。
  - `STAGE448_TARGET_SCOPE=all`
  - `STAGE448_MAX_SYMBOLS=0`
  - `STAGE448_MAX_SECONDS_PER_SYMBOL=150`
  - 分片批次：`0-60`、`61-120`、`121-180`、`181-228`
- 删除参数：无。
- 策略变更：无。未修改 Stage079/C3/Stage103 的入场、出场、品种池、AI池、仓位或资金规则。

## 运行方式

先用四个互不重叠的 rank 分片写入 raw cache，再用全量配置只读缓存做统一聚合：

```bash
STAGE448_MODEL_TAG=stage449_minute_session_rebuild_full_v1 \
STAGE448_OUTPUT_PREFIX=qmt_roll_stage449_minute_session_rebuild_full \
STAGE448_TARGET_SCOPE=all \
STAGE448_MAX_SYMBOLS=0 \
STAGE448_MAX_SECONDS_PER_SYMBOL=150 \
.py311/bin/python examples/portfolio_backtesting/analyze_qmt_roll_stage448_minute_session_rebuild_batch.py
```

raw cache 目录沿用：

`examples/portfolio_backtesting/downloaded_futures/tqsdk_stage448_minute_session_rebuild_batch/`

## 全量结果

| 指标 | 数值 |
| --- | ---: |
| 选中合约数 | 228 |
| 成功/缓存合约数 | 228 |
| 失败/超时/空合约数 | 0 |
| 1分钟K数量 | 1,453,601 |
| 目标窗口数 | 3,561 |
| 覆盖窗口数 | 1,624 |
| 覆盖率 | 45.6052% |
| 接回账本交易数 | 692 |
| 有效 same close 交易数 | 547 |
| 有效 next open 交易数 | 624 |
| 无效 same close 数量 | 145 |
| 无效 next open 数量 | 0 |
| 14:55 vs same close 大错位 | 345 / 547 = 63.0713% |
| 真实开盘 vs daily next open 大错位 | 321 / 624 = 51.4423% |
| 剔除无效价后 14:55 vs same close 最大价差 | 4,008 |
| 剔除无效价后 real open vs next open 最大价差 | 6,000 |
| 真实开盘相对同日收盘现金差估计，含无效 same close | -1,736,968,162.06 |
| 真实开盘相对同日收盘现金差估计，剔除无效 same close | 120,068,722.90 |
| 14:55 VWAP 相对同日收盘现金差估计，剔除无效 same close | 109,785,288.59 |

注意：含无效 same close 的现金差汇总不能用于交易判断，因 `145` 笔账本 same close 为 `0` 或无效；本阶段正式解释以“剔除无效 same close”口径为准。

## 回测指标字段

本阶段是执行口径审计，不是策略回测；以下字段不适用：

- 期末权益：不适用
- 总收益：不适用
- 最大回撤：不适用
- Sharpe：不适用
- 总滑点：不适用
- 总交易次数：不适用
- 胜率：不适用

## 输出文件

- 报告：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_report_stage449_minute_session_rebuild_full_v1.md`
- 决策 JSON：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_decision_stage449_minute_session_rebuild_full_v1.json`
- 账本明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_ledger_proxy_detail_stage449_minute_session_rebuild_full_v1.csv`
- 窗口覆盖：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_window_coverage_stage449_minute_session_rebuild_full_v1.csv`
- 分钟K：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage449_minute_session_rebuild_full_minute_bars_stage449_minute_session_rebuild_full_v1.csv`

## 结论

- Stage079 仍是当前正常成本账户 baseline。
- Stage103 仍保留为同日收盘口径研究主候选，但不能直接进入真实 paper/影子盘。
- 全量结果显示，日线 same close 与日线 next open 均不能直接视作真实会话可执行价格：有效样本中 14:55 代理价大错位率 `63.0713%`，真实开盘代理价相对 daily next open 大错位率 `51.4423%`。
- 当前最值得晋级的是执行模型：先用分钟会话代理价重建 Stage079/Stage103 的可部署权益曲线，再重新比较 3个月/6个月持有体验。继续在同日收盘口径上做 alpha 小修价值低。

## 后续规划和 TODO

1. 用 Stage149 的 `ledger_proxy_detail` 重构 Stage079 和 Stage103 的分钟会话代理执行权益。
2. 分别评估 `14:55最后5分钟VWAP`、`21:00/09:00开盘5分钟first open`、以及缺失窗口的保守处理。
3. 重跑 Stage079/Stage103 的全周期、多起点、rolling 90/180/252/504、成本压力和保证金审计。
4. 只有在分钟执行口径仍通过后，才允许讨论 Stage103 或新候选是否进入 paper/影子盘。

## 过拟合与继续价值反思

- 运行前过拟合反思：否。只校准执行价格，不改变交易信号、不筛日期、不筛品种、不使用未来收益。
- 运行后过拟合反思：否。错位只用于否定错误成交口径，不作为过滤条件或调参依据。
- 运行前继续价值反思：是。Stage147/148 已显示执行价格错位，必须扩展到全量才能判断是否系统性。
- 运行后继续价值反思：是，但方向应从“救同日收盘曲线”转为“分钟会话执行曲线重建”。若分钟口径下 Stage103 优势消失，应主动降级，而不是继续救参数。
