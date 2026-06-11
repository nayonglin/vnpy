# Stage798：Stage777 官方候选亏损比例 Top20 K线扩展复盘

- 记录时间：2026-06-11 01:42 CST
- 研究线：`futures_trend_2019_data_extension`
- 当前工作模式：day
- 是否重要突破版本：否
- 版本性质：只读法证/图形复盘，不修改策略、不修改回测参数、不作为正式候选变更

## 本次调研和判断结论

本次没有做新的外部策略调研，因为任务是对刚才同一候选版本的历史亏损交易继续画图复盘，核心信息来自本仓库已有成交明细和本地K线数据。判断结论：这类工作属于“观察坏交易形态”的法证工作，过拟合风险低；但如果后续直接根据这 20 笔反推阈值，则会立刻变成高过拟合风险，必须再做年度/逐月启动验证。

## 版本口径

- 源版本：`official_candidate_stage777_50w_am41_oi08_old_ai_v1`
- 统计区间：2020-01-01 到 2026-05-29
- 排序指标：`theory_loss_pct = -directional(entry->exit return pct)`
- 画图范围：开仓前 50 根、平仓后 50 根
- 均线：MA5、MA10、MA20、MA40
- 下方面板：成交量柱 + OI 线
- 分页：20 笔交易，每页 4 笔，共 5 张图

## 数据修正说明

- 复用 Stage797 的 closed lots 缓存，不重跑策略回测。
- 原单合约日线目录 `tqsdk_daily_2010_2026_04` 缺少 4 笔交易对应的画图K线：
  - `SH607.CZCE`
  - `SH605.CZCE`
  - `hc2005.SHFE`
  - `MA605.CZCE`
- 已在 Stage798 脚本内增加画图专用 fallback：当单合约日线缺失时，从本地分钟补数文件聚合成日线再画图。
- 该 fallback 只影响可视化，不影响成交明细、盈亏排序和任何回测结果。

## 新增/修改/删除参数

- 新增参数：
  - `TOP_N = 20`
  - `PER_PAGE = 4`
  - 分钟线聚合日线 fallback，仅用于画图
- 修改参数：
  - 无策略参数修改
  - 无回测参数修改
- 删除参数：
  - 无

## 新增回测/复盘结果

- closed lots：261 笔
- 亏损 lots：131 笔
- Top20 最差理论亏损比例：9.219512%
- Top20 第20名理论亏损比例：3.100602%
- Top20 中命中 OI 放大规则的交易数：8 笔
- Top20 缺失K线交易数：0 笔
- 其中用分钟线聚合日线补画：4 笔

## Top20交易列表

| 排名 | lot_id | 合约 | 方向 | 开仓日 | 平仓日 | 理论亏损% | 实际PnL | R倍数 | risk_multiplier | OI命中 | 信号 | 退出 |
| --- | ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| 1 | 163 | jm2301.DCE | long | 2022-08-29 | 2022-08-31 | 9.219512 | -306180 | -1.741935 | 2.0 | 1 | long_case1a | long_prev2day_stop |
| 2 | 176 | fu2305.SHFE | long | 2023-01-31 | 2023-02-03 | 6.356085 | -77440 | -3.193033 | 1.0 | 0 | long_case2 | long_prev2day_stop |
| 3 | 115 | lh2201.DCE | long | 2021-11-01 | 2021-11-02 | 5.924171 | -192000 | -2.993116 | 1.0 | 0 | long_case2 | long_base_stop |
| 4 | 191 | fu2310.SHFE | long | 2023-08-22 | 2023-08-25 | 5.652290 | -141370 | -1.172222 | 1.0 | 0 | long_case3 | long_prev2day_stop |
| 5 | 58 | ru2105.SHFE | long | 2020-12-03 | 2020-12-07 | 5.414013 | -42500 | -1.734694 | 2.0 | 1 | rollover_reopen | long_prev2day_stop |
| 6 | 261 | SH607.CZCE | short | 2026-04-30 | 2026-05-07 | 4.776119 | -901440 | -2.369200 | 2.0 | 1 | short_case1a | short_prev2day_stop |
| 7 | 154 | fu2209.SHFE | long | 2022-05-27 | 2022-05-31 | 4.759683 | -91800 | -2.379841 | 1.0 | 0 | long_case1a | long_prev2day_stop |
| 8 | 129 | SM205.CZCE | long | 2022-01-12 | 2022-01-18 | 4.000941 | -134300 | -2.015651 | 1.0 | 0 | long_case1a | long_prev2day_stop |
| 9 | 50 | MA101.CZCE | long | 2020-10-23 | 2020-10-27 | 3.936630 | -19680 | -1.963602 | 1.0 | 0 | long_case2 | long_prev2day_stop |
| 10 | 121 | sp2201.SHFE | long | 2021-12-06 | 2021-12-13 | 3.887399 | -113680 | -1.414634 | 1.0 | 0 | long_case2 | long_prev2day_stop |
| 11 | 120 | ru2205.SHFE | long | 2021-11-25 | 2021-11-29 | 3.800703 | -291550 | -1.830769 | 2.0 | 1 | rollover_reopen | long_prev2day_stop |
| 12 | 79 | SA105.CZCE | long | 2021-03-18 | 2021-03-23 | 3.800000 | -18240 | -0.826087 | 1.0 | 0 | long_case3 | long_prev2day_stop |
| 13 | 229 | AP505.CZCE | long | 2025-02-24 | 2025-02-26 | 3.783784 | -439600 | -1.891892 | 2.0 | 1 | long_case2 | long_prev2day_stop |
| 14 | 143 | fu2205.SHFE | long | 2022-03-25 | 2022-03-29 | 3.701101 | -331800 | -1.874259 | 2.0 | 1 | long_case3 | long_prev2day_stop |
| 15 | 45 | CF101.CZCE | short | 2020-09-29 | 2020-10-12 | 3.582555 | -55200 | -30.666667 | 1.0 | 0 | short_case1a | short_prev2day_stop |
| 16 | 256 | SH605.CZCE | short | 2026-03-03 | 2026-03-04 | 3.463203 | -1080000 | -1.729107 | 2.0 | 1 | short_case1a | short_base_stop |
| 17 | 10 | hc2005.SHFE | long | 2020-03-16 | 2020-03-19 | 3.325817 | -8260 | -1.421687 | 1.0 | 0 | long_case2 | long_prev2day_stop |
| 18 | 128 | jm2205.DCE | long | 2022-01-06 | 2022-01-10 | 3.307888 | -177840 | -1.642105 | 2.0 | 1 | long_case1a | long_prev2day_stop |
| 19 | 253 | MA605.CZCE | long | 2026-01-27 | 2026-02-03 | 3.135739 | -308060 | -1.553191 | 1.0 | 0 | long_case1a | long_prev2day_stop |
| 20 | 167 | jm2301.DCE | long | 2022-11-30 | 2022-12-02 | 3.100602 | -125100 | -1.311321 | 1.0 | 0 | long_case1a | long_prev2day_stop |

## 输出文件

- 脚本：`examples/portfolio_backtesting/analyze_qmt_roll_stage798_stage777_top20_loss_kline_atlas.py`
- 明细：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_top_losses_stage798_stage777_top20_loss_kline_atlas_v1.csv`
- 汇总：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_summary_stage798_stage777_top20_loss_kline_atlas_v1.csv`
- 图1：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_page01_stage798_stage777_top20_loss_kline_atlas_v1.png`
- 图2：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_page02_stage798_stage777_top20_loss_kline_atlas_v1.png`
- 图3：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_page03_stage798_stage777_top20_loss_kline_atlas_v1.png`
- 图4：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_page04_stage798_stage777_top20_loss_kline_atlas_v1.png`
- 图5：`examples/portfolio_backtesting/backtest_outputs/qmt_roll_stage798_stage777_top20_loss_kline_atlas_page05_stage798_stage777_top20_loss_kline_atlas_v1.png`

## 反思

- 是否过拟合：否。原因是本阶段没有新增交易规则、没有挑参数，只是把已发生的亏损交易按事前开平仓路径画出来。
- 过拟合风险点：如果后续看图后直接提出“某个形态必然过滤”的规则，并只在这 20 笔上验证，就是过拟合。
- 是否还有价值继续做：有。Top20 已经比 Top5 更能看出坏交易是否有共性，下一步可以做“先观察、后预声明规则、再多起点验证”的闭环。

## 后续规划和 TODO

1. 先肉眼复盘 Top20，重点看是否存在共性：高位反向突破、趋势末端加速、OI 放大但价格反转、均线粘合后假突破、短期极端振幅。
2. 如提出新过滤特征，必须先写明不看未来的定义，再跑年度/逐月启动验证。
3. 不扫小阈值，不用单笔大亏反推专门补丁。
