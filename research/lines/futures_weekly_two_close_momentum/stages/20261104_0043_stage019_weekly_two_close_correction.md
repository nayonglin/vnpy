# Stage019 入场方向只比较两个周收盘价

- 研究线 `futures_weekly_two_close_momentum`，上海时间见文件名。Q 为冻结对照，R 新增 `--two-close-entry`。用户澄清的口径为信号周收盘与上一交易周收盘比较，严格大于做多，严格小于做空，相等跳过。
- 该比较用于普通开仓、同日反手和启用时的加仓候选。R 固定一手，无加仓，保留近两根实体同向、周 MA5/10/20 过滤、同日先平后开、原止损和换月。斜率计算沿用其历史窗口。MA40 关闭。
- 冻结 19 品种、期初 30 万元、2015-01-05 至 2026-11-03，沿用实物合约日线、日开盘成交代理、静态保证金、既有滑点和零手续费。
- 参考 [LEAN Momentum](https://github.com/QuantConnect/Lean/blob/master/Indicators/Momentum.cs) 的一期价格变化定义。此次按用户指定口径纠正规则，固定同样本对照，无参数扫描。以 OI301 的 2022-10-21 周 K 检验最早信号。

基准指纹

```text
8251d5906358471782477f6e5ccdcd5795b4fd548d13f7bb66135ea30656bdba  research/lines/futures_weekly_two_close_momentum/outputs/stage018_Q_2015_20261103/SHA256SUMS
8109f0e8bb692693dde560f13212a8638d7e194b4f6a99151878278f348e5a2e  research/lines/futures_weekly_two_close_momentum/outputs/stage018_Q_2015_20261103/inputs.json
2de2027ec02c2da823b28328f62fba3f1d6b6ded0fc555a26d4f061692aae9eb  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
```

候选源码指纹

```text
589dc74b260a3ef6f16194caea3c27aa4c319156d5b8376e325d01f139323b08  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
5340f85e89948b61e64eaace99dc4ed98b9b802c18da7a715e7626c4a1ad7bb3  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
6573c692efb7e6b35760af36362ee6c45326f917dd78359073511797e1865801  research/lines/futures_weekly_two_close_momentum/tools/test_weekly_portfolio_reversal.py
```
