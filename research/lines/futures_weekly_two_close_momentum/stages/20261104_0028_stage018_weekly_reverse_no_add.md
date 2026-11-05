# Stage018 同日反手固定一手去掉加仓

- 研究线 `futures_weekly_two_close_momentum`，上海时间见文件名。P 为直接对照，Q 关闭最多一次断档加仓，F 为无加仓、无同日反手的补充对照。
- 取消 `--one-fixed-add` 与依赖它的 `--fresh-add-sequence`。保留固定一手底仓、两根周线实体和两周收盘同向、周 MA5/10/20 斜率、原周线止损、换月和同日反手。新反向头寸另起周期，旧仓平完后开一手。三版 MA40 均关闭。只改运行配置。
- 冻结 19 品种、初始 30 万元、2015-01-05 至 2026-11-03。沿用冻结行情和规格、日线开盘成交代理、静态保证金、既有滑点及零手续费。关闭加仓的旧入口仅输出收盘资金序列，开盘资金如需验证由独立复算给出。
- 参考 [TradingView pyramiding 及仓位反转说明](https://www.tradingview.com/pine-script-docs/concepts/strategies/#pyramiding)，同向加码与先平后开为两套动作。固定单因素比较，无参数扫描，有价值厘清加仓对资金、回撤和 PnL 的贡献。

冻结指纹

```text
ef4a26f96d65a4f7d9ee8043b8803408746ff23a82959b97eb125001ac249eb1  research/lines/futures_weekly_two_close_momentum/outputs/stage007_F_2015_20261103/SHA256SUMS
ddbc68ccf1b3a5500406f2d40e57162b511e938fe5b9b6b8fd1438260fb1b0d1  research/lines/futures_weekly_two_close_momentum/outputs/stage007_F_2015_20261103/inputs.json
aa5ee3868e07dfaf3533cd484535fc00ebf1f71c5429cde6c3b1302a680c0eb6  research/lines/futures_weekly_two_close_momentum/outputs/stage017_P_2015_20261103/SHA256SUMS
3dc615184564a164454646f379bd47d20a4c145a6932d50f299c412acea2f469  research/lines/futures_weekly_two_close_momentum/outputs/stage017_P_2015_20261103/inputs.json
4b9b2070be92d7b0ae5448c359a08d28c2234dc03fbcf3534e245b9c45935fb3  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
584f7835a13ef4af8f3681a25971ebad66cb6081fa8bbd3537d950606203cb28  research/lines/futures_weekly_two_close_momentum/tools/weekly_two_close_momentum.py
```

入口修复补充，2026-11-04 00:29 CST。原命令省略加仓参数时，argparse 先为共享参数写入 None 并触发校验错误。仅显式把命令行默认值设为零。实际回测策略逻辑不变。

```text
2de2027ec02c2da823b28328f62fba3f1d6b6ded0fc555a26d4f061692aae9eb  research/lines/futures_weekly_two_close_momentum/tools/run_weekly_portfolio.py
```
