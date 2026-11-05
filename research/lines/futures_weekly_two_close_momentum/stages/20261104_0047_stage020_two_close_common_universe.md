# Stage020 两周收盘规则的共同品种回测

- 研究线 `futures_weekly_two_close_momentum`，记录时间见文件名（上海时间）。固定样本内对照，无参数搜索。目标是取得可复核的经济结果，并单独保留燃油未完成路径。
- 对照 Q 使用三个周收盘价判断入场方向。候选 R 使用信号周与上一交易周两个周收盘价。两组均使用两根实体、MA5/10/20 斜率、固定一手、周线止损和同日先平后开。加仓及 MA40 关闭。
- 2015-01-05 至 2026-11-03，两组均从 30 万元独立起跑。事先从两组共同排除 `fu.SHFE`，其余 18 品种沿用 Stage019 的同一日历、实物日线、主力映射、合约规格、开盘成交代理、静态保证金、滑点及零手续费。燃油依据是 Stage019 在 `fu1604` 出现无法估算退出的到期中断。19 品种失败证据保留。
- 回测通过冻结策略的 `run` 接口执行。先调用原 `load_market` 完成哈希校验，然后仅将 `products` 列表过滤掉 `fu.SHFE`，保留余下加载结果。两组均传入 `week_body_filter=True, reverse_after_stop=True`，R 另外传入 `two_close_entry=True`。
- 参考 [LEAN 期货合约映射示例](https://github.com/QuantConnect/Documentation/blob/master/03%20Writing%20Algorithms/03%20Securities/99%20Asset%20Classes/06%20Futures/02%20Handling%20Data/99%20Examples.html) 的实物合约切换做法。换月成交需要旧腿成交依据，缺腿时不采用主力替代价。

冻结指纹

```text
589dc74b260a3ef6f16194caea3c27aa4c319156d5b8376e325d01f139323b08  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
5340f85e89948b61e64eaace99dc4ed98b9b802c18da7a715e7626c4a1ad7bb3  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
3bcaa09b0b5a1141b2a9dd856869d1048de233d6f7c550975a3a3a75b9d5cc8e  research/lines/futures_weekly_two_close_momentum/outputs/stage019_R_2015_20261103/inputs.json
653bab0f18f4da2211cfef428154abd5bad81452c6801e787759412684a97b94  research/lines/futures_weekly_two_close_momentum/outputs/stage019_R_2015_20261103/failure.txt
```
