# Stage044：原生风险预算冻结产物与规范复盘验收器

- 时间：2026-10-19 18:28 CST；研究线 `futures_trend_full_market_noai_one_lot`。
- 新增 `tools/stage044_validate_budget_artifacts.py` 与对应测试；未修改已冻结 Stage022 或其他旧模块、官方代码、LINE、金融 runner 或旧输出。
- 本阶段不是重要突破；新增金融回放、行情下载、生产访问均为 0。没有以测试 fixture 产生或代替金融绩效证据，也没有对正在运行的新金融源执行验收。

## 入口

```bash
/Users/mac/Desktop/fian/.py311/bin/python \
  research/lines/futures_trend_full_market_noai_one_lot/tools/stage044_validate_budget_artifacts.py \
  --source <完整冻结的新run绝对目录> \
  --recap <canonical与Stage020终稿绝对目录> \
  --output <新的validation.json绝对路径>
```

`--output` 可省略以打印 JSON；已存在输出禁止覆盖。`--node` 可显式指定语法检查运行时；默认优先 PATH，否则使用已发现的 bundled Node `/Users/mac/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node`，没有安装或下载任何工具。

## 验收合同

1. 明确指定 source 与 recap；检查源 manifest 全部哈希成员、recap 全部 artifact 哈希、源目录/manifest 绑定、回测 metrics 原样保留、records.json 哈希与 HTML 内嵌 records 完全一致。
2. 确认四项源/summary flags：恢复 native 风险预算、一手是上限而非固定数量、真实开盘风险复核、取消品种数上限。必须是 `fixed_size=0/min=1/max=1/max_concurrent_positions=93`，并与本次输入93品种一致。**没有“实际持仓数必须大于4”的断言**；fixture 实际最多1品种也能通过。
3. 从真实成交顺序独立重建持仓，每产品 gross 手数不超过1，不接受无仓平仓/同合约加仓；核对最终残仓与源 residual、复盘 residual；保留生命周期截止日开仓/平仓和期末残仓期限检查。
4. 所有实际 open 必须逐笔对应 filled audit，冻结 signal snapshot 身份唯一且合约/产品/方向/case/原信号时间一致；核对真实成交价格、乘数、tick、冻结止损和审计字段。
5. 独立重算原信号货币预算与实际 open 可用资源预算，保留原 min/max 风险、risk_ratio、原连败/overheat/30日倍率和资本使用率；检查 actual risk 为 `max(abs(fill-stop)*size,tick*size,1)`，且实际风险不超过开盘预算、开盘预算不超过原信号授权。0、非有限、反向止损或超额均拒绝，不凭 summary 自报0违规放行。
6. 所有 completed episodes 同时对应源 closed_episodes、原 open/close trades、all_trade_episodes、chart_manifest 与 records：身份、日期、价格、方向、case、毛盈亏、净盈亏/费用与标的价格涨跌逐值对齐。gross profit/loss/flat 与 net win-rate 的口径分开。
7. 六周期 payload 和逐笔 manifest bar数逐项对齐；对可独立验证的 MA5/10/20/40 点重算比较，拒绝可验证窗口中的空值或数值错误；分钟可用性按实际数据判断。
8. 对全部 HTML 内嵌脚本使用 Node `--check`，只做语法解析，不执行脚本或网络请求。浏览器默认周期、交互、联动缩放与视觉验收仍由根任务执行，语法成功不能替代浏览器验收。

## TDD 与冻结测试

- 初始5项测试 RED（入口缺失）；实现后 GREEN。另加同产品两手、hash闭合但错误 MA、manifest仅身份相同但价格错误的用例；对应缺失保护先观察失败再实现。
- 专项 **8/8通过**：正确 fixture（实际1品种而非强制>4）、实际 open 风险超额、audit snapshot 错绑、容量回4、双手叠加、MA篡改、manifest价格篡改、hash闭合但 JavaScript 语法错误。
- 冻结后全线命令：`MPLCONFIGDIR=/private/tmp/fian-stage039-mpl /Users/mac/Desktop/fian/.py311/bin/python -m unittest discover -s research/lines/futures_trend_full_market_noai_one_lot/tools -p 'test_*.py'`。
- 结果：**129 tests，18.028秒，全部通过**；`git diff --check` 通过。只读 fixture 验收未创建金融策略引擎回放。
- 验收器 SHA256：`73e459b42ed155137f02126c157dd2fb1f1a3e00ea9ccb84de70d86dd38e8db9`。
- 测试 SHA256：`6bac9a62be533162f19980f6b8c471f7c22cc47ad8e7dd9695dc0f5a9511f4e4`。

## 结果与反思

- 新增/修改/删除策略参数与金融结果均无；没有新的权益、收益、回撤、Sharpe、滑点、成交或胜率。源实际冻结后由根任务运行本验收器，并另由独立 agent 审查金融数据和结论。
- 开始/结束过拟合判断：**否**。本阶段检查预先授权的一手预算与展示不变量，没有扫阈值或用收益挑样本。
- 开始/结束继续价值判断：**是**。hash闭合不自动保证内容一致；必须同时核对原成交、预算审计、闭合交易与复盘记录，才能避免把不一致或超额委托包装成正确图表。验收通过仅证明该研究产物的相应一致性，不构成正式晋升或实盘认证。
