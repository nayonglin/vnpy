# Stage042：风险预算最多1手版本的参数化账户概览工具

- 时间：2026-10-19 18:23 CST。
- line_id：`futures_trend_full_market_noai_one_lot`。
- 本阶段仅展示适配与合成fixture核验，不是重要策略突破，不运行金融回测，不改变策略、源输入、旧输出或LINE。
- 当前真实新回测仍由根任务运行；本阶段没有生成、读取或认领其绩效。

## 调研、判断与实施

已阅读本线LINE、registry及`skills/futures-recap-html/SKILL.md`与`references/recap-contract.md`。判断：现有Stage032账户资金曲线UI已明确，复用其Plotly绘图即可；新的风险预算语义须由冻结源和parent摘要共同核验，不能替换旧页面文字后继续认领旧固定1手业绩。本工具仅账户概览，不替代Stage038逐笔K线规范复盘。此前已查阅官方Plotly与vn.py资料，本次没有新增网络行情或依赖下载。

新增：

- `tools/stage042_account_overview.py`，纯展示模块，无策略/引擎import。
- `tools/test_stage042_account_overview.py`，8项非金融来源合同测试。
- 命令参数：`--source`、`--parent`、`--output`，均接受绝对目录；拒绝输出覆盖/包含来源目录及覆盖已有输出。
- 原Stage032冻结绘图块经AST定位复用，不运行其旧main、旧来源读写或硬编码文案。共享日期轴、原Plotly原生缩放与复位能力保留。
- 修复初始本金高于回撤前全部日末权益时的展示索引问题：最大回撤高点标记为`initial_capital`，不伪称某个日末点已达本金。

## 来源核验与动态披露

1. parent摘要的`source_manifest_sha256`必须等于source manifest实际SHA256，且`backtest_metrics`与source summary完整相等。
2. `run_id`必须等于source目录名；逐项校验manifest全部`hashes`及`code_snapshot_hashes`，拒绝绝对路径、越界路径和缺文件。
3. daily、summary、trades、closed_episodes、residual_open_positions均须存在明确hash绑定；真实成交、完整episode、残仓计数复核。
4. manifest与summary均须明确三项预算恢复标志：`native_risk_budget_restored`、`one_lot_is_maximum_not_fixed`、`next_open_risk_recheck`；并要求`fixed_size=0`、`max_position_size=1`、取消4品种上限标志及daily-proxy模式一致。
5. 每日权益与初始本金加累计net_pnl、balance、highlevel、drawdown、ddpercent一致，期末权益/收益/最大回撤与源summary一致；校验日期排序、唯一、点数与截止日期。
6. 日期区间、起始资金、日点数、episode数、残仓数/开仓日期/完整残仓清单均动态展示；风险预算恢复/真实开盘复核/跳空非保证止损上限和完整source boundaries显著披露。
7. 输出summary记录全部源文件hash、source/parent/generator/Stage032绘图源hash、输出各artifact hash与字节数；写输出后再次核验source与parent没有变化。

## 输出合同

新独立目录内生成：自包含`index.html`、`equity_drawdown.png`、`figure.json`、`equity_drawdown.csv`、`summary.json`。Plotly JSON可供根任务原生Plotly展示。HTML使用原嵌入式Plotly依赖，预计约5MB，实际大小取决于每日点数。

根任务已指定、但本阶段尚未执行的真实运行命令：

```bash
/Users/mac/Desktop/fian/.py311/bin/python research/lines/futures_trend_full_market_noai_one_lot/tools/stage042_account_overview.py \
  --source /Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/run_20261019_native_budget_one_lot_v1 \
  --parent /Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/recap_20261019_native_budget_one_lot_v1_reviewed \
  --output /Users/mac/.codex/worktrees/full-market-noai-one-lot/fian/research/lines/futures_trend_full_market_noai_one_lot/outputs/overview_20261019_native_budget_one_lot_v1
```

## 验证证据

- RED：测试先写，新模块不存在，FileNotFoundError。
- GREEN：8项测试全部通过：动态事实/初始本金峰值、任意被绑定证据篡改、跨来源parent、预算恢复标志、残仓计数、episode计数、输出隔离、hash越界路径。
- 合成2日展示fixture端到端生成通过（临时目录已删除，不是金融运行）：HTML 4,828,778字节；PNG 148,187字节；figure.json 9,023字节；CSV 137字节；全部输出hash重新一致。临时matplotlib字体缓存自动使用系统临时目录，未安装依赖。
- `git diff --check`针对两个新增工具通过。浏览器交互尚未针对新真实源验收，不沿用旧验收结论冒充本次已验收。
- Stage032未改，SHA256 `b66996d564b9879ed84bc46d5eaee69912fc4b31711c6af0658ca9ab4e88ec7c`。
- Stage042 SHA256 `09829162d51d0d9a60497da23a2e2424c70d53bc56fd48c801f2d7316ebd75f9`。
- 测试 SHA256 `9fb852adc4e9d2c00c448561051da92f4be29775c898a5dc02f50589ef689fef`。

## 回测记录与后续

本阶段没有新增/修改/删除任何金融回测结果；不填写假期末权益、收益、回撤、Sharpe、滑点、交易次数或胜率。没有strategy rerun、market download、production access。

过拟合判断：否，仅来源核验与展示适配，没有按收益选择参数、品种、日期或交易。继续价值：是，避免旧固定1手与新风险预算cap1身份混淆。TODO：根任务完成金融运行及独立审查后，使用唯一冻结新source+对应parent运行本工具，再独立核验数字、JavaScript、浏览器双图联动与原生Plotly展示。
