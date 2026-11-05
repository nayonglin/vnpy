# Stage021 Q 与 R 的独立起跑多周期对照

- 研究线 `futures_weekly_two_close_momentum`，上海时间见文件名。范围沿用 Stage020 两组共同的 18 个品种，排除燃油。数据冻结到 2026-11-03。
- 全周期先复跑并逐文件校验 Stage020 输出。独立窗口以 2015 年起每个 1 月 1 日、6 月 1 日为起点，执行 1、2、3 个完整日历年。窗口左闭右开，以周年前最后一个实际交易日结束。预期 22、20、18 个成对窗口。每窗每版以 300,000 元、空仓、无待成交订单开始。窗前历史仅用于周线和均线计算。末日按权益盯市，后续订单不执行。
- Q 入场方向比较三个周收盘价，R 比较相邻两个。两版共用两根实体、周 MA5/10/20 斜率、固定一手、周线止损、同日先平后开。成本采用相同冻结滑点、日开盘成交代理及零手续费。
- 收益、最大回撤、Sharpe 逐窗比较。严格优胜分别计票，数值差小于等于 1e-9 为平。按 1/2/3 年各分全体、1 月和 6 月。事前定义稳定优势为 Q 在每个周期的 1 月和 6 月子组，三个指标分别严格赢超过半数。另列三项同窗全胜和反例。窗口重叠，票数用于描述起点敏感性。
- 参考 [Hyndman 的滚动起点验证](https://otext.robjhyndman.com/hyndsight/tscv/)，使用实际独立复跑，避免把全周期权益切片当作冷启动表现。规则与窗口在结果前固定，未做择参。有价值检验 Stage020 全样本优势能否跨起点。

冻结指纹

```text
589dc74b260a3ef6f16194caea3c27aa4c319156d5b8376e325d01f139323b08  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
5340f85e89948b61e64eaace99dc4ed98b9b802c18da7a715e7626c4a1ad7bb3  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
d1c342b33e826e10a29d3bf78070cbc379d9b46fb49ea98f997d2677c2032e01  research/lines/futures_weekly_two_close_momentum/outputs/stage020_Q_18_2015_20261103/SHA256SUMS
8d44b259de363c8a47637259df85b2677acaede8991e2aa6ae40600b44ef45b6  research/lines/futures_weekly_two_close_momentum/outputs/stage020_Q_18_2015_20261103/inputs.json
65515c13329668ad4cb8a1779446f53c3c1138f281dd9a3c0fdc84c72f7f2a1c  research/lines/futures_weekly_two_close_momentum/outputs/stage020_R_18_2015_20261103/SHA256SUMS
2391f2d678e140c362e13bfbecbcc294dc4899c139cf781715bdc11f4ba76ddb  research/lines/futures_weekly_two_close_momentum/outputs/stage020_R_18_2015_20261103/inputs.json
```

执行器指纹与首次校验修正

```text
92f01ccd9963d779950285f00de9dbc463560b3a0d953a51fd9197e94cd4de40  research/lines/futures_weekly_two_close_momentum/tools/run_stage021_multicycle.py
```

首次全周期 Q 的 CSV 现金列序列化为 300000.0。复核器现按 Decimal 校验其等于 300000，并按照 Stage020 的 CSV、JSON 文件顺序生成校验清单。首次产物保留。
