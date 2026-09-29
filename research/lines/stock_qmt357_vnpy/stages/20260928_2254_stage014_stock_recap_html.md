# Stage014 股票冻结回测逐笔复盘 HTML

- line_id：`stock_qmt357_vnpy`。
- 记录时间：2026-09-28 22:54（Asia/Shanghai）；本阶段实现/验证约22:35—22:54。
- 模式：只展示已完成的 Stage012；非重要突破，不新增回测、不做A/B，不作为实盘候选。
- 工作区：`/Users/bytedance/Desktop/person/vnpy`，基准HEAD `abe45b3070e43206b40ad54cfbd053706894744a`。原有未提交工作全部保留，不提交/推送。

## 外部调研与判断

- 参考：[Plotly共享X轴](https://plotly.com/python/subplots/#subplots-with-shared-xaxes)、[官方GitHub](https://github.com/plotly/plotly.py)，以及仓库 `skills/futures-recap-html/SKILL.md` 与其完整显示合同。
- 判断：沿用 Stage038 的多周期聚合、MA、记录结构和HTML/Plotly绘制即可；不复制整份模板，不另建图表系统。
- 隔离优先：原Stage038模块顶层导入期货研究/运行入口。股票适配器只从SHA固定的源文件加载11个纯展示函数，不执行其import、全局路径配置、main或下载函数；不改变期货原文件。股票输出放本研究线，覆盖技能默认的期货输出目录，以满足用户明确的股票资源隔离要求。

## 变更

- 新增 `tools/stage014_stock_recap_html.py`：冻结源验证、股票买卖配对、同源未复权K线、股数/分红字段、缺口提示及独立输出；没有任何网络或交易引擎调用。
- 新增 `tests/test_stock_recap_html.py`：16项行为测试。
- 新增 `tools/stage014_verify_browser.js`：对已打开页面进行筛选、翻页、周期、真实鼠标拖拽缩放验收。
- 修改股票策略、期货脚本、配置、数据、冻结回测产物：均0。新增/修改/删除策略参数：均0。
- 渲染器SHA：`613672a4cc91493ba17dc055542e4b4172349de210ff932530caf04ce36bb93a`；生成前后未变。

## 冻结源与展示口径

- 源：`examples/stock_backtesting/qmt357_commit4ac255e/outputs/fixed_2020_20260928_commit4ac255e_repaired_v1/`，manifest COMPLETE。
- commit：`4ac255ece55671bb74962f23b5d7fae22fa377e7`；原策略文件为该commit的`震荡股高卖低买策略.py`，并非其未改动的357.py。
- 行情：该股票版本独立 `data/snapshots/history_201910_20260928_repaired_v1/panel.parquet`，SHA `e849804bc997e69a5d82321d03efc4717f5338913ec02aaca983c8059e3ecea3`。
- 2020-01-01—2026-09-28，30万初始本金；90%日预算、最多3只、单股32%、SL2%、TP45%及指定分级止损。只是展示已有结果，没有再执行策略。
- 452条买卖成交对应226笔闭合交易；37盈、189亏、0平；期末0仓，无遗漏成交。8筆含现金分红，共15,788.80元。
- 净损益取冻结 `round_trips.net_pnl`，并复核`卖出净所得+分红-买入含费成本`。滑点已在成交价内，不重复扣费。K线/成交点为未复权原价，原价涨跌和账户净收益分别标注；展示MA不是策略的复权信号。
- 默认30日K+日K；可选10日K、月K、周K。15分钟数据0条，不下载、不合成。MA5/10/20/40使用全部已有同源真实历史预热；缺失保持空值。
- 47笔前窗不足300个实有日线，2笔后窗不足50日；月窗缺口、每周期MA40空值数量逐笔可见。无其他股票代理，无未披露行情缺口。
- 已继承披露月度历史池、派生限价、固定费用、分红税/到账近似、剩余配股/重整及176个参考价小残差等局限。

## 冻结指标（非新回测结果）

| 指标 | Stage012原值 |
| --- | ---: |
| 期末权益 | 252,720.8403元 |
| 总收益 | -15.7597199% |
| 最大回撤 | -29.2172727% |
| Sharpe | -0.0875277 |
| 总滑点 | 26,550元 |
| 佣金含印花税 | 29,980.9597元 |
| 买卖成交 / 闭合交易 | 452 / 226 |
| 净胜率 | 16.3716814% |

所有冻结指标逐字段保留，未新增、修改或删除任何回测结果。

## 产物与复现

- 本线 `outputs/stage014_commit4ac255e_stock_recap_v1/`：`index.html`（18,144,958字节）、`summary.json`、`chart_manifest.csv`、`records.json`。
- summary记录所有输入与输出SHA、源身份、冻结指标、覆盖缺口、adapter/renderer SHA；输出目录必须是股票线outputs下的新目录，不允许覆盖。
- 页面自包含Plotly脚本和行情，可直接离线打开index.html；验收时仅使用127.0.0.1本地静态预览。
- 截图：`output/playwright/stock_recap_stage014_default.png`。

```bash
QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1 .py311/bin/python -I \
  research/lines/stock_qmt357_vnpy/tools/stage014_stock_recap_html.py \
  --output research/lines/stock_qmt357_vnpy/outputs/<新的股票复盘目录>

QMT_BACKTEST_DISABLE_STARTUP_CWD_GUARD=1 .py311/bin/python -I -m pytest \
  examples/stock_backtesting research/lines/stock_qmt357_vnpy/tests \
  --import-mode=importlib -q --tb=short
```

## 验证

- TDD：先出现16项预期失败（适配器尚未实现），实现后16 passed；最终完整股票回归 **309 passed in 43.66s**。未启动全仓期货/生产相关测试。
- 首次以默认pytest导入模式合并运行两个股票版本，`test_cli/test_data/test_engine/test_strategy`同名模块引起4项收集冲突；使用`--import-mode=importlib`后完整通过，未删除缓存或修改旧测试/业务代码。
- Node成功解析HTML全部2个内嵌script；源码及数据摘要再次核对无变化；`git diff --check`通过。
- 独立只读reviewer：Critical=0、Important=0；再次运行16测试；226笔成交价、股数、净损益、股息和价格涨跌映射错误0；74,649根页面日K OHLCV与panel逐值一致；所有源/产物/适配器SHA一致，`frozen_metrics`与源summary整个字典相等。保留的R=N/A仅模板展示，不虚构风险倍数。
- 浏览器Playwright：226全部/37盈利/189亏损/0持平；2026入场16笔，000001两笔；上一笔/下一笔0→1→0；无结果状态、缺分钟提示、五周期选择均通过。
- 实际鼠标拖拽：两个图X范围同时从`[0,547]`变为`[163.8169469598965,382.82923673997414]`；Reset axes后保留默认30日+日K。共享缩放验收通过，不仅检查静态matches字段。
- 已肉眼检查默认截图；没有JavaScript运行错误。临时HTTP服务器唯一console error是未配置`favicon.ico`的404，不影响离线页面与交互。
- 浏览器验证脚本初次CLI调用使用错误函数签名、随后文件末尾分号不符合该CLI表达式包装格式；均为验证工具调用问题，修正为`async page => {…}`后PASS，未修改产物掩盖问题。

## 反思与后续

- 运行前/后过拟合判断：否。只读展示固定全量样本，不挑赢家、不调参、不重跑回测，不形成新的alpha证据。
- 运行前/后继续价值：有。复盘页面方便定位亏损、费用和交易路径；原策略长期负收益的结论未改变，不据页面外观晋级实盘。
- 下一步：交付HTML，后续若研究亏损归因需单独定义问题，不在本阶段增加阈值寻优或分钟下载。
- 仅更新本线LINE；不更新registry、不追加根memory/back_log。无期货、生产、CTP或券商访问，无提交/推送。
